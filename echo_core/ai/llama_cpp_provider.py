from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import socket
import time
from typing import Any, Callable, Iterator, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from echo_core.ai.base import (
    AIProviderConnectionError,
    AIProviderContextLimitError,
    AIProviderError,
    AIProviderHTTPError,
    AIProviderResponseError,
    AIProviderStreamError,
    AIProviderTimeoutError,
    ChatMessage,
)


DEFAULT_LLAMACPP_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LlamaCppProvider:
    """OpenAI-compatible chat provider for a local llama.cpp server."""

    endpoint: str = DEFAULT_LLAMACPP_ENDPOINT
    timeout_seconds: float = 30.0
    max_tokens: int = 256
    system_prompt: str = ""
    model_name: str = "local"
    opener: Callable[..., Any] = urlopen

    def generate_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        return "".join(
            self.stream_response(user_message, conversation_history, system_prompt)
        ).strip()

    def stream_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        messages = self._build_messages(user_message, conversation_history, system_prompt)
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        started_at = time.monotonic()
        chunk_count = 0
        LOGGER.debug(
            "llama.cpp request started: endpoint=%s prompt_chars=%s history_messages=%s stream=true",
            self.endpoint,
            len(user_message),
            len(conversation_history or []),
        )

        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                for raw_line in self._iterate_sse_lines(response):
                    chunk = self._parse_stream_line(raw_line)
                    if chunk is None:
                        continue
                    chunk_count += 1
                    yield chunk
        except HTTPError as exc:
            elapsed = time.monotonic() - started_at
            body_text = self._read_http_error_body(exc)
            LOGGER.warning(
                "llama.cpp request HTTP failure after %.2fs: status=%s body=%s",
                elapsed,
                exc.code,
                body_text[:200],
            )
            if exc.code == 503:
                raise AIProviderHTTPError(
                    f"Local llama.cpp server is still loading. {body_text}".strip(),
                    status_code=exc.code,
                ) from exc
            if exc.code == 400 and self._is_context_limit_error(body_text):
                raise AIProviderContextLimitError(
                    f"Conversation context is full. {body_text}".strip(),
                    status_code=exc.code,
                ) from exc
            raise AIProviderHTTPError(
                f"Local llama.cpp request failed with HTTP {exc.code}. {body_text}".strip(),
                status_code=exc.code,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            elapsed = time.monotonic() - started_at
            LOGGER.warning("llama.cpp request timed out after %.2fs", elapsed)
            raise AIProviderTimeoutError("Local llama.cpp request timed out.") from exc
        except URLError as exc:
            elapsed = time.monotonic() - started_at
            LOGGER.warning("llama.cpp connection failure after %.2fs: %s", elapsed, exc)
            raise AIProviderConnectionError("Local llama.cpp server is unavailable.") from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            elapsed = time.monotonic() - started_at
            LOGGER.warning("llama.cpp malformed response after %.2fs: %s", elapsed, exc)
            raise AIProviderResponseError("Local llama.cpp response was not valid.") from exc
        except AIProviderError:
            raise
        finally:
            elapsed = time.monotonic() - started_at
            LOGGER.debug(
                "llama.cpp request finished in %.2fs with %s streamed chunks",
                elapsed,
                chunk_count,
            )

    def _build_messages(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None,
        system_prompt: str | None,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        prompt = (system_prompt or self.system_prompt or "").strip()
        if prompt:
            messages.append(ChatMessage(role="system", content=prompt))

        if conversation_history:
            messages.extend(conversation_history)

        normalized_user_message = user_message.strip()
        if not messages or messages[-1].role != "user" or messages[-1].content != normalized_user_message:
            messages.append(ChatMessage(role="user", content=normalized_user_message))
        return messages

    @staticmethod
    def _iterate_sse_lines(response: object) -> Iterator[str]:
        readline = getattr(response, "readline", None)
        if readline is None:
            raise AIProviderResponseError("Local llama.cpp response did not support streaming.")

        while True:
            raw_line = readline()
            if raw_line in {b"", ""}:
                break
            if isinstance(raw_line, bytes):
                yield raw_line.decode("utf-8", errors="replace").strip()
            else:
                yield str(raw_line).strip()

    @staticmethod
    def _parse_stream_line(raw_line: str) -> str | None:
        if not raw_line:
            return None
        if not raw_line.startswith("data:"):
            return None

        payload_text = raw_line[5:].strip()
        if not payload_text:
            return None
        if payload_text == "[DONE]":
            return None

        try:
            payload_data = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise AIProviderStreamError("Local llama.cpp stream emitted malformed JSON.") from exc

        return LlamaCppProvider._extract_stream_content(payload_data)

    @staticmethod
    def _extract_content(payload_data: Any) -> str:
        if not isinstance(payload_data, dict):
            raise AIProviderResponseError("Local llama.cpp response structure was unexpected.")

        choices = payload_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIProviderResponseError("Local llama.cpp response had no choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIProviderResponseError("Local llama.cpp response choice was invalid.")

        message = first_choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content

        text = first_choice.get("text")
        if isinstance(text, str):
            return text

        raise AIProviderResponseError("Local llama.cpp response did not include assistant text.")

    @staticmethod
    def _extract_stream_content(payload_data: Any) -> str | None:
        if not isinstance(payload_data, dict):
            raise AIProviderStreamError("Local llama.cpp stream structure was unexpected.")

        choices = payload_data.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIProviderStreamError("Local llama.cpp stream choice was invalid.")

        delta = first_choice.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str) and content:
                return content

        text = first_choice.get("text")
        if isinstance(text, str) and text:
            return text

        message = first_choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content:
                return content

        return None

    @staticmethod
    def _read_http_error_body(exc: HTTPError) -> str:
        try:
            body = exc.read()
        except OSError:
            return ""
        return body.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _is_context_limit_error(body_text: str) -> bool:
        lowered = body_text.lower()
        return (
            "exceeds the available context size" in lowered
            or "n_prompt_tokens" in lowered
            or "n_ctx" in lowered
            or "context size" in lowered
        )


LlamaCppAIProvider = LlamaCppProvider
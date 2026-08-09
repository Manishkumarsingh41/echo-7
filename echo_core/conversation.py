from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable

from echo_core.ai.base import (
    AIProvider,
    AIProviderConnectionError,
    AIProviderError,
    AIProviderContextLimitError,
    AIProviderHTTPError,
    AIProviderResponseError,
    AIProviderStreamError,
    AIProviderTimeoutError,
    ChatMessage,
)
from echo_core.config import (
    DEFAULT_LLAMACPP_CONTEXT_RETRY_SAFETY_TOKENS,
    DEFAULT_LLAMACPP_CONTEXT_SIZE,
    DEFAULT_LLAMACPP_MAX_OUTPUT_TOKENS,
)


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """Represents the result of processing a single user input."""

    reply: str
    should_exit: bool = False
    succeeded: bool = True
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ContextWindowSettings:
    """Token-budget settings for rolling llama.cpp context selection."""

    context_window_tokens: int = DEFAULT_LLAMACPP_CONTEXT_SIZE
    output_token_reserve: int = DEFAULT_LLAMACPP_MAX_OUTPUT_TOKENS
    retry_safety_tokens: int = DEFAULT_LLAMACPP_CONTEXT_RETRY_SAFETY_TOKENS
    estimated_chars_per_token: int = 4
    message_overhead_tokens: int = 4


class ConversationEngine:
    """Coordinates conversation flow and exit handling."""

    _exit_commands = {"exit", "quit", "bye"}

    def __init__(
        self,
        provider: AIProvider,
        system_prompt: str | None = None,
        context_settings: ContextWindowSettings | None = None,
    ) -> None:
        self._provider = provider
        self._system_prompt = system_prompt
        self._context_settings = context_settings or ContextWindowSettings()
        self._history: list[ChatMessage] = []

    @property
    def history(self) -> tuple[ChatMessage, ...]:
        """Return the current runtime conversation history."""

        return tuple(self._history)

    def clear_history(self) -> None:
        """Clear the current runtime conversation history."""

        self._history.clear()

    def load_history(
        self,
        messages: list[ChatMessage] | tuple[ChatMessage, ...],
    ) -> None:
        """Replace runtime history with messages from a saved chat."""

        valid_messages: list[ChatMessage] = []

        for message in messages:
            if message.role not in {"user", "assistant"}:
                continue

            content = message.content.strip()

            if not content:
                continue

            valid_messages.append(
                ChatMessage(
                    role=message.role,
                    content=content,
                )
            )

        self._history = valid_messages

    @classmethod
    def is_exit_command(cls, message: str) -> bool:
        return message.strip().lower() in cls._exit_commands

    def handle_message(self, message: str) -> ConversationTurn:
        normalized_message = message.strip()

        if not normalized_message:
            return ConversationTurn(
                reply="Please type a message or 'exit' to quit."
            )

        if self.is_exit_command(normalized_message):
            return ConversationTurn(
                reply="Shutting down. Goodbye.",
                should_exit=True,
            )

        history_snapshot = tuple(self._history)

        try:
            reply = self._generate_response_with_retry(
                normalized_message,
                history_snapshot,
            )

        except AIProviderError as exc:
            return ConversationTurn(
                reply=self._error_reply(exc),
                succeeded=False,
                error_message=str(exc),
            )

        self._commit_turn(
            normalized_message,
            reply,
        )

        return ConversationTurn(
            reply=reply,
        )

    def stream_message(
        self,
        message: str,
        emit_chunk: Callable[[str], None],
        cancel_event: Event | None = None,
    ) -> ConversationTurn:
        normalized_message = message.strip()

        if not normalized_message:
            return ConversationTurn(
                reply="Please type a message or 'exit' to quit."
            )

        if self.is_exit_command(normalized_message):
            return ConversationTurn(
                reply="Shutting down. Goodbye.",
                should_exit=True,
            )

        history_snapshot = tuple(self._history)

        try:
            reply, cancelled = self._stream_response_with_retry(
                normalized_message,
                history_snapshot,
                emit_chunk,
                cancel_event=cancel_event,
            )

        except AIProviderError as exc:
            return ConversationTurn(
                reply=self._error_reply(exc),
                succeeded=False,
                error_message=str(exc),
            )

        if cancelled:
            return ConversationTurn(
                reply=reply,
                succeeded=False,
                error_message="generation cancelled",
            )

        self._commit_turn(
            normalized_message,
            reply,
        )

        return ConversationTurn(
            reply=reply,
        )

    def build_model_history(
        self,
        user_message: str,
        *,
        retry: bool = False,
    ) -> tuple[ChatMessage, ...]:
        """Build history trimmed to fit the active context window."""

        return tuple(
            self._trim_history_for_budget(
                tuple(self._history),
                user_message,
                retry=retry,
            )
        )

    def _generate_response_with_retry(
        self,
        user_message: str,
        history_snapshot: tuple[ChatMessage, ...],
    ) -> str:
        for retry in (False, True):
            model_history = self._trim_history_for_budget(
                history_snapshot,
                user_message,
                retry=retry,
            )

            try:
                return self._provider.generate_response(
                    user_message,
                    model_history,
                    self._system_prompt,
                )

            except AIProviderContextLimitError as exc:
                if retry:
                    raise exc

        raise AIProviderResponseError(
            "Local llama.cpp request could not be prepared."
        )

    def _stream_response_with_retry(
        self,
        user_message: str,
        history_snapshot: tuple[ChatMessage, ...],
        emit_chunk: Callable[[str], None],
        cancel_event: Event | None = None,
    ) -> tuple[str, bool]:
        last_error: AIProviderContextLimitError | None = None

        for retry in (False, True):
            model_history = self._trim_history_for_budget(
                history_snapshot,
                user_message,
                retry=retry,
            )

            chunks: list[str] = []

            stream = self._provider.stream_response(
                user_message,
                model_history,
                self._system_prompt,
            )

            try:
                for chunk in stream:
                    if (
                        cancel_event is not None
                        and cancel_event.is_set()
                    ):
                        return "".join(chunks).strip(), True

                    if not chunk:
                        continue

                    chunks.append(chunk)
                    emit_chunk(chunk)

                    if (
                        cancel_event is not None
                        and cancel_event.is_set()
                    ):
                        return "".join(chunks).strip(), True

                if (
                    cancel_event is not None
                    and cancel_event.is_set()
                ):
                    return "".join(chunks).strip(), True

                return "".join(chunks).strip(), False

            except AIProviderContextLimitError as exc:
                last_error = exc

                if chunks:
                    raise exc

                if not retry:
                    continue

                raise exc

            finally:
                close_stream = getattr(
                    stream,
                    "close",
                    None,
                )

                if callable(close_stream):
                    close_stream()

        if last_error is not None:
            raise last_error

        raise AIProviderResponseError(
            "Local llama.cpp stream could not be prepared."
        )

    def _commit_turn(
        self,
        user_message: str,
        assistant_reply: str,
    ) -> None:
        self._history.append(
            ChatMessage(
                role="user",
                content=user_message,
            )
        )

        self._history.append(
            ChatMessage(
                role="assistant",
                content=assistant_reply,
            )
        )

    def _trim_history_for_budget(
        self,
        history_snapshot: tuple[ChatMessage, ...],
        user_message: str,
        *,
        retry: bool,
    ) -> list[ChatMessage]:
        available_tokens = self._context_budget_tokens(
            retry=retry
        )

        model_history = list(
            history_snapshot
        )

        while (
            model_history
            and self._estimate_prompt_tokens(
                model_history,
                user_message,
            )
            > available_tokens
        ):
            if (
                len(model_history) >= 2
                and model_history[0].role == "user"
                and model_history[1].role == "assistant"
            ):
                del model_history[:2]
                continue

            del model_history[0]

        return model_history

    def _context_budget_tokens(
        self,
        *,
        retry: bool,
    ) -> int:
        reserve = (
            self._context_settings.output_token_reserve
        )

        if retry:
            reserve += (
                self._context_settings.retry_safety_tokens
            )

        return max(
            0,
            self._context_settings.context_window_tokens
            - reserve,
        )

    def _estimate_prompt_tokens(
        self,
        model_history: list[ChatMessage],
        user_message: str,
    ) -> int:
        tokens = 0

        if (
            self._system_prompt
            and self._system_prompt.strip()
        ):
            tokens += self._estimate_message_tokens(
                self._system_prompt
            )

        for message in model_history:
            tokens += self._estimate_message_tokens(
                message.content
            )

        tokens += self._estimate_message_tokens(
            user_message
        )

        return tokens

    def _estimate_message_tokens(
        self,
        content: str,
    ) -> int:
        per_token = max(
            1,
            self._context_settings.estimated_chars_per_token,
        )

        content_tokens = (
            len(content)
            + per_token
            - 1
        ) // per_token

        return (
            content_tokens
            + self._context_settings.message_overhead_tokens
        )

    @staticmethod
    def _error_reply(
        exc: AIProviderError,
    ) -> str:
        if isinstance(
            exc,
            AIProviderContextLimitError,
        ):
            return (
                "Conversation context is full. "
                "Please start a new topic or shorten the prompt."
            )

        if isinstance(
            exc,
            AIProviderTimeoutError,
        ):
            return (
                "Local brain request timed out. "
                "Please try again."
            )

        if isinstance(
            exc,
            AIProviderConnectionError,
        ):
            return (
                "Local brain is temporarily unavailable."
            )

        if isinstance(
            exc,
            AIProviderHTTPError,
        ):
            if exc.status_code == 503:
                return (
                    "Local brain is still loading. "
                    "Please try again shortly."
                )

            return (
                "Local brain returned an HTTP error."
            )

        if isinstance(
            exc,
            AIProviderStreamError,
        ):
            return (
                "Local brain stream failed. "
                "Please try again."
            )

        if isinstance(
            exc,
            AIProviderResponseError,
        ):
            return (
                "Local brain returned an unexpected response."
            )

        return (
            "Local brain is temporarily unavailable."
        )


def run_text_chat(
    engine: ConversationEngine,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    """Run the interactive text conversation loop."""

    while True:
        try:
            user_message = input_func(
                "You: "
            )

        except EOFError:
            output_func(
                "ECHO: Shutting down. Goodbye."
            )
            return

        turn = engine.handle_message(
            user_message
        )

        output_func(
            f"ECHO: {turn.reply}"
        )

        if turn.should_exit:
            return


def run_streaming_text_chat(
    engine: ConversationEngine,
    input_func: Callable[[str], str],
    write_func: Callable[[str], None],
) -> None:
    """Run the interactive text conversation loop with progressive output."""

    while True:
        try:
            user_message = input_func(
                "You: "
            )

        except EOFError:
            write_func(
                "ECHO: Shutting down. Goodbye.\n"
            )
            return

        write_func(
            "ECHO: "
        )

        emitted_any_chunk = False

        def emit_chunk(
            chunk: str,
        ) -> None:
            nonlocal emitted_any_chunk

            emitted_any_chunk = True

            write_func(
                chunk
            )

        turn = engine.stream_message(
            user_message,
            emit_chunk=emit_chunk,
        )

        write_func(
            "\n"
        )

        if (
            not emitted_any_chunk
            or not turn.succeeded
            or turn.should_exit
        ):
            write_func(
                f"ECHO: {turn.reply}\n"
            )

        if turn.should_exit:
            return
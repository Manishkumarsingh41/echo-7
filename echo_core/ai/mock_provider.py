from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

from echo_core.ai.base import ChatMessage


@dataclass(frozen=True, slots=True)
class MockAIProvider:
    """Deterministic response provider for Phase 1."""

    echo_name: str = "ECHO-7"

    def generate_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        normalized = user_message.strip().lower()
        if normalized in {"hello", "hi", "hey", "hello echo", "hi echo", "hey echo"}:
            return f"Hello. I'm {self.echo_name}."
        if normalized in {"who are you", "who are you?", "what are you", "what are you?"}:
            return f"I'm {self.echo_name}, your local personal AI companion."
        return f"I heard you say: {user_message.strip()}"

    def stream_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        yield self.generate_response(user_message, conversation_history, system_prompt)


MockProvider = MockAIProvider

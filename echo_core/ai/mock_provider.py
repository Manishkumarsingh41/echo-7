from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MockAIProvider:
    """Deterministic response provider for Phase 1."""

    echo_name: str = "ECHO-7"

    def generate_response(self, user_message: str) -> str:
        normalized = user_message.strip().lower()
        if normalized in {"hello", "hi", "hey", "hello echo", "hi echo", "hey echo"}:
            return f"Hello. I'm {self.echo_name}."
        if normalized in {"who are you", "who are you?", "what are you", "what are you?"}:
            return f"I'm {self.echo_name}, your local personal AI companion."
        return f"I heard you say: {user_message.strip()}"

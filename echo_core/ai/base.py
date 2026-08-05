from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    """Contract for any future ECHO response provider."""

    def generate_response(self, user_message: str) -> str:
        """Generate a single response for the given user message."""

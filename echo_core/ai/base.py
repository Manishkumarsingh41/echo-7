from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, Sequence


MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single conversation message."""

    role: MessageRole
    content: str


class AIProviderError(RuntimeError):
    """Base exception for recoverable AI provider failures."""


class AIProviderTimeoutError(AIProviderError):
    """Raised when a provider times out waiting for a response."""


class AIProviderConnectionError(AIProviderError):
    """Raised when a provider cannot connect to its backend."""


class AIProviderHTTPError(AIProviderError):
    """Raised when a provider receives an HTTP error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AIProviderResponseError(AIProviderError):
    """Raised when a provider receives malformed or unexpected data."""


class AIProviderContextLimitError(AIProviderHTTPError):
    """Raised when the request exceeds the model's available context window."""


class AIProviderStreamError(AIProviderError):
    """Raised when a streaming response fails after it has started."""


class AIProvider(Protocol):
    """Contract for any future ECHO response provider."""

    def generate_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a single response for the given user message."""

    def stream_response(
        self,
        user_message: str,
        conversation_history: Sequence[ChatMessage] | None = None,
        system_prompt: str | None = None,
    ) -> Iterator[str]:
        """Stream response chunks for the given user message."""

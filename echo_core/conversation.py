from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from echo_core.ai.base import AIProvider


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """Represents the result of processing a single user input."""

    reply: str
    should_exit: bool = False


class ConversationEngine:
    """Coordinates conversation flow and exit handling."""

    _exit_commands = {"exit", "quit", "bye"}

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    @classmethod
    def is_exit_command(cls, message: str) -> bool:
        return message.strip().lower() in cls._exit_commands

    def handle_message(self, message: str) -> ConversationTurn:
        normalized_message = message.strip()
        if not normalized_message:
            return ConversationTurn(reply="Please type a message or 'exit' to quit.")
        if self.is_exit_command(normalized_message):
            return ConversationTurn(reply="Shutting down. Goodbye.", should_exit=True)
        return ConversationTurn(reply=self._provider.generate_response(normalized_message))


def run_text_chat(
    engine: ConversationEngine,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    """Run the interactive text conversation loop."""
    while True:
        try:
            user_message = input_func("You: ")
        except EOFError:
            output_func("ECHO: Shutting down. Goodbye.")
            return

        turn = engine.handle_message(user_message)
        output_func(f"ECHO: {turn.reply}")
        if turn.should_exit:
            return

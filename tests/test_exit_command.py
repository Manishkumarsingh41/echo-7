from echo_core.conversation import ConversationEngine
from echo_core.ai.mock_provider import MockAIProvider


def test_exit_command_is_recognized():
    engine = ConversationEngine(provider=MockAIProvider())

    assert engine.is_exit_command("exit") is True
    assert engine.is_exit_command(" quit ") is True
    assert engine.is_exit_command("hello") is False

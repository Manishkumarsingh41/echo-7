from echo_core.conversation import ConversationEngine, run_text_chat
from echo_core.ai.mock_provider import MockAIProvider


def test_conversation_engine_uses_provider_for_normal_messages():
    engine = ConversationEngine(provider=MockAIProvider())

    turn = engine.handle_message("Hello Echo")

    assert turn.reply == "Hello. I'm ECHO-7."
    assert turn.should_exit is False


def test_run_text_chat_handles_exit_command():
    engine = ConversationEngine(provider=MockAIProvider())
    prompts: list[str] = []
    outputs: list[str] = []

    messages = iter(["Hello Echo", "exit"])

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(messages)

    def fake_output(message: str) -> None:
        outputs.append(message)

    run_text_chat(engine=engine, input_func=fake_input, output_func=fake_output)

    assert prompts == ["You: ", "You: "]
    assert outputs == [
        "ECHO: Hello. I'm ECHO-7.",
        "ECHO: Shutting down. Goodbye.",
    ]

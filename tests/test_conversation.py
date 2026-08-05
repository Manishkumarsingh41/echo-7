from echo_core.ai.base import AIProviderContextLimitError, AIProviderTimeoutError, ChatMessage
from echo_core.ai.mock_provider import MockAIProvider
from echo_core.conversation import ContextWindowSettings, ConversationEngine, run_streaming_text_chat, run_text_chat


class HistoryAwareProvider:
    def generate_response(self, user_message, conversation_history=None, system_prompt=None):
        if "what name" in user_message.lower():
            user_messages = [message.content for message in conversation_history or [] if message.role == "user"]
            if user_messages:
                return user_messages[0].removeprefix("My name is ").rstrip(".")
        return "Okay."


class TimeoutProvider:
    def generate_response(self, user_message, conversation_history=None, system_prompt=None):
        raise AIProviderTimeoutError("request timed out")

    def stream_response(self, user_message, conversation_history=None, system_prompt=None):
        raise AIProviderTimeoutError("request timed out")


class StreamingProvider:
    def generate_response(self, user_message, conversation_history=None, system_prompt=None):
        return "Hello world"

    def stream_response(self, user_message, conversation_history=None, system_prompt=None):
        yield "Hello"
        yield " world"


class RecordingProvider:
    def __init__(self) -> None:
        self.generate_calls: list[tuple[str, tuple[ChatMessage, ...], str | None]] = []
        self.stream_calls: list[tuple[str, tuple[ChatMessage, ...], str | None]] = []

    def generate_response(self, user_message, conversation_history=None, system_prompt=None):
        self.generate_calls.append((user_message, tuple(conversation_history or ()), system_prompt))
        return "Assistant reply with enough words to keep the context busy."

    def stream_response(self, user_message, conversation_history=None, system_prompt=None):
        self.stream_calls.append((user_message, tuple(conversation_history or ()), system_prompt))
        yield "OK"


class RetryThenSuccessProvider:
    def __init__(self) -> None:
        self.generate_calls: list[tuple[str, tuple[ChatMessage, ...], str | None]] = []
        self._retry_triggered = False

    def generate_response(self, user_message, conversation_history=None, system_prompt=None):
        history = tuple(conversation_history or ())
        self.generate_calls.append((user_message, history, system_prompt))
        if user_message == "Newest prompt should retry once" and not self._retry_triggered:
            self._retry_triggered = True
            raise AIProviderContextLimitError("request exceeds available context size", status_code=400)
        return "Recovered answer"

    def stream_response(self, user_message, conversation_history=None, system_prompt=None):
        history = tuple(conversation_history or ())
        self.generate_calls.append((user_message, history, system_prompt))
        if user_message == "Newest prompt should retry once" and not self._retry_triggered:
            self._retry_triggered = True
            raise AIProviderContextLimitError("request exceeds available context size", status_code=400)
        yield "Recovered answer"


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


def test_conversation_engine_uses_session_history():
    engine = ConversationEngine(provider=HistoryAwareProvider())

    first_turn = engine.handle_message("My name is Alex.")
    second_turn = engine.handle_message("What name did I tell you?")

    assert first_turn.reply == "Okay."
    assert second_turn.reply == "Alex"
    assert [message.role for message in engine.history] == ["user", "assistant", "user", "assistant"]


def test_conversation_engine_surfaces_timeout_without_mock_fallback():
    engine = ConversationEngine(provider=TimeoutProvider())

    turn = engine.handle_message("Explain RAG")

    assert turn.succeeded is False
    assert turn.reply == "Local brain request timed out. Please try again."
    assert turn.error_message == "request timed out"
    assert engine.history == ()


def test_run_streaming_text_chat_outputs_progressively():
    engine = ConversationEngine(provider=StreamingProvider())
    messages = iter(["Hello", "exit"])
    outputs: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(messages)

    def fake_write(text: str) -> None:
        outputs.append(text)

    run_streaming_text_chat(engine=engine, input_func=fake_input, write_func=fake_write)

    assert outputs[:4] == ["ECHO: ", "Hello", " world", "\n"]
    assert "ECHO: Shutting down. Goodbye.\n" in outputs


def test_context_trimming_preserves_recent_complete_turns_and_system_prompt():
    provider = RecordingProvider()
    engine = ConversationEngine(
        provider=provider,
        system_prompt="You are ECHO-7.",
        context_settings=ContextWindowSettings(
            context_window_tokens=170,
            output_token_reserve=20,
            retry_safety_tokens=5,
            estimated_chars_per_token=1,
            message_overhead_tokens=0,
        ),
    )

    engine.handle_message("User turn 1 with a lot of words")
    engine.handle_message("Assistant turn 2 should still matter")
    engine.handle_message("User turn 3 with even more words")
    turn = engine.handle_message("Newest user message must remain")

    assert turn.reply == "Assistant reply with enough words to keep the context busy."
    assert len(provider.generate_calls) == 4

    latest_user_message, latest_history, latest_system_prompt = provider.generate_calls[-1]
    assert latest_user_message == "Newest user message must remain"
    assert latest_system_prompt == "You are ECHO-7."
    assert latest_history[0].content != "User turn 1 with a lot of words"
    assert any(message.content == "User turn 3 with even more words" for message in latest_history)
    assert len(latest_history) < len(engine.history)
    assert len(engine.history) == 8


def test_context_limit_error_retries_once_without_mock_fallback():
    provider = RetryThenSuccessProvider()
    engine = ConversationEngine(
        provider=provider,
        system_prompt="You are ECHO-7.",
        context_settings=ContextWindowSettings(
            context_window_tokens=170,
            output_token_reserve=20,
            retry_safety_tokens=40,
            estimated_chars_per_token=1,
            message_overhead_tokens=0,
        ),
    )

    engine.handle_message("Alpha words for the first turn")
    engine.handle_message("Beta words for the second turn")

    turn = engine.handle_message("Newest prompt should retry once")

    assert turn.succeeded is True
    assert turn.reply == "Recovered answer"
    assert len(provider.generate_calls) == 4
    first_retry_history = provider.generate_calls[-2][1]
    second_retry_history = provider.generate_calls[-1][1]
    assert len(second_retry_history) < len(first_retry_history)
    assert len(engine.history) == 6


def test_streaming_history_is_committed_only_after_success():
    provider = RecordingProvider()
    engine = ConversationEngine(provider=provider)
    outputs: list[str] = []

    turn = engine.stream_message("Hello stream", emit_chunk=outputs.append)

    assert turn.succeeded is True
    assert outputs == ["OK"]
    assert len(engine.history) == 2

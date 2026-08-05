from echo_core.ai.mock_provider import MockAIProvider


def test_mock_provider_greeting_response():
    provider = MockAIProvider()

    assert provider.generate_response("Hello Echo") == "Hello. I'm ECHO-7."


def test_mock_provider_identity_response():
    provider = MockAIProvider()

    assert provider.generate_response("who are you?") == "I'm ECHO-7, your local personal AI companion."

from __future__ import annotations

from types import SimpleNamespace

from apps.desktop import main as desktop_main
from echo_core.ai.mock_provider import MockAIProvider
from echo_core.ai.llama_cpp_server import LlamaHealthState
from echo_core.config import AppConfig


def test_startup_failure_uses_mock_provider(monkeypatch):
    captured = {}

    class FakeManager:
        def __init__(self, config):
            self.config = config

        def bootstrap(self):
            return SimpleNamespace(
                ready=False,
                installation=None,
                health=SimpleNamespace(state=LlamaHealthState.UNAVAILABLE, body="startup failed"),
                session=None,
                endpoint="http://127.0.0.1:8080/v1/chat/completions",
                status_lines=("Local ECHO brain unavailable.",),
                diagnostic="startup failed",
            )

    def fake_load_config():
        return AppConfig(ai_provider="auto")

    def fake_run_text_chat(engine, input_func, output_func):
        captured["provider_type"] = type(engine._provider)
        captured["provider_is_mock"] = isinstance(engine._provider, MockAIProvider)

    monkeypatch.setattr(desktop_main, "LlamaCppServerManager", FakeManager)
    monkeypatch.setattr(desktop_main, "load_config", fake_load_config)
    monkeypatch.setattr(desktop_main, "configure_logging", lambda level: None)
    monkeypatch.setattr(desktop_main, "run_text_chat", fake_run_text_chat)
    monkeypatch.setattr(desktop_main, "run_streaming_text_chat", lambda *args, **kwargs: None)

    assert desktop_main.main() == 0
    assert captured["provider_type"] is MockAIProvider
    assert captured["provider_is_mock"] is True

from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from echo_core.ai.base import (
    AIProviderConnectionError,
    AIProviderContextLimitError,
    AIProviderHTTPError,
    AIProviderResponseError,
    AIProviderStreamError,
    AIProviderTimeoutError,
    ChatMessage,
)
from echo_core.ai.llama_cpp_provider import LlamaCppProvider
from echo_core.ai.llama_cpp_server import (
    LlamaHealthState,
    LlamaCppHealthCheck,
    LlamaCppInstallation,
    LlamaCppServerManager,
    LlamaCppServerSession,
)
from echo_core.ai.mock_provider import MockAIProvider
from echo_core.config import AppConfig
from echo_core.conversation import ConversationEngine


class FakeSseResponse:
    def __init__(self, lines: list[bytes], status: int = 200) -> None:
        self._lines = lines
        self._index = 0
        self.status = status

    def __enter__(self) -> "FakeSseResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def readline(self) -> bytes:
        if self._index >= len(self._lines):
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line

    def read(self) -> bytes:
        return b"".join(self._lines)


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.waited = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None):
        self.waited = True
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def _build_installation(root: Path) -> LlamaCppInstallation:
    runtime_path = root / "USB-Uncensored-LLM" / "Shared" / "bin" / "llama-server.exe"
    model_path = root / "USB-Uncensored-LLM" / "Shared" / "models" / "Phi-3.5-mini-instruct-Q4_K_M.gguf"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("runtime")
    model_path.write_text("model")
    return LlamaCppInstallation(
        runtime_path=runtime_path,
        model_path=model_path,
        drive_root=root,
        model_label="Phi-3.5 Mini Instruct Q4",
    )


def _sse_line(content: str) -> bytes:
    return f"data: {content}\n".encode("utf-8")


def test_discovery_finds_runtime_and_model_on_removable_drive(tmp_path):
    installation = _build_installation(tmp_path)
    manager = LlamaCppServerManager(AppConfig(), drive_roots=lambda: [tmp_path])

    discovered = manager.discover_installation()

    assert discovered is not None
    assert discovered.runtime_path == installation.runtime_path
    assert discovered.model_path == installation.model_path
    assert discovered.model_label == "Phi-3.5 Mini Instruct Q4"


def test_llama_cpp_provider_streams_chunks_in_order():
    captured_payload: dict[str, object] = {}

    def opener(request, timeout):
        captured_payload["request"] = json.loads(request.data.decode("utf-8"))
        return FakeSseResponse(
            [
                _sse_line(json.dumps({"choices": [{"delta": {"content": "Retrieval"}}]})),
                _sse_line(json.dumps({"choices": [{"delta": {"content": "-Augmented"}}]})),
                _sse_line(json.dumps({"choices": [{"delta": {"content": " Generation"}}]})),
                _sse_line(json.dumps({"choices": [{"delta": {"content": " is..."}}]})),
                b"data: [DONE]\n",
            ]
        )

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        timeout_seconds=5.0,
        max_tokens=64,
        system_prompt="Be concise.",
        opener=opener,
    )

    chunks = list(provider.stream_response("Explain RAG"))

    assert chunks == ["Retrieval", "-Augmented", " Generation", " is..."]
    assert captured_payload["request"]["stream"] is True
    assert captured_payload["request"]["max_tokens"] == 64
    assert captured_payload["request"]["messages"][0] == {"role": "system", "content": "Be concise."}
    assert captured_payload["request"]["messages"][-1] == {"role": "user", "content": "Explain RAG"}


def test_llama_cpp_provider_generate_response_joins_streamed_chunks():
    def opener(request, timeout):
        return FakeSseResponse(
            [
                _sse_line(json.dumps({"choices": [{"delta": {"content": "Hello"}}]})),
                _sse_line(json.dumps({"choices": [{"delta": {"content": " world"}}]})),
                b"data: [DONE]\n",
            ]
        )

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    assert provider.generate_response("Hello Echo") == "Hello world"


def test_llama_cpp_provider_reports_connection_failure():
    def opener(request, timeout):
        raise URLError("connection refused")

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    with pytest.raises(AIProviderConnectionError):
        list(provider.stream_response("Hello Echo"))


def test_llama_cpp_provider_reports_timeout_failure():
    def opener(request, timeout):
        raise TimeoutError("request timed out")

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    with pytest.raises(AIProviderTimeoutError):
        list(provider.stream_response("Hello Echo"))


def test_llama_cpp_provider_reports_http_failure():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            500,
            "Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b"boom"),
        )

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    with pytest.raises(AIProviderHTTPError):
        list(provider.stream_response("Hello Echo"))


def test_llama_cpp_provider_reports_context_limit_failure_distinctly():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"request (1043 tokens) exceeds the available context size (1024 tokens)"),
        )

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    with pytest.raises(AIProviderContextLimitError):
        list(provider.stream_response("Hello Echo"))


def test_llama_cpp_provider_rejects_malformed_stream_chunks():
    def opener(request, timeout):
        return FakeSseResponse([b"data: {not-json}\n"])

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    with pytest.raises(AIProviderStreamError):
        list(provider.stream_response("Hello Echo"))


def test_llama_cpp_provider_ignores_empty_and_done_chunks():
    def opener(request, timeout):
        return FakeSseResponse(
            [
                b"\n",
                _sse_line(json.dumps({"choices": [{"delta": {"content": "Alpha"}}]})),
                _sse_line(json.dumps({"choices": [{"delta": {}}]})),
                b"data: [DONE]\n",
            ]
        )

    provider = LlamaCppProvider(
        endpoint="http://example.test/v1/chat/completions",
        opener=opener,
    )

    assert list(provider.stream_response("Hello Echo")) == ["Alpha"]


def test_health_check_reports_loading_state():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b"Loading model"),
        )

    manager = LlamaCppServerManager(AppConfig(), opener=opener)

    health = manager.check_health()

    assert health.state is LlamaHealthState.LOADING
    assert health.status_code == 503
    assert "Loading model" in health.body


def test_health_check_reports_ready_state():
    def opener(request, timeout):
        return FakeSseResponse([b"ok\n"], status=200)

    manager = LlamaCppServerManager(AppConfig(), opener=opener)

    health = manager.check_health()

    assert health.state is LlamaHealthState.READY
    assert health.status_code == 200


def test_wait_for_ready_times_out():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b"Loading model"),
        )

    state = {"value": 0.0}

    def clock() -> float:
        return state["value"]

    def sleep(seconds: float) -> None:
        state["value"] += seconds

    config = replace(AppConfig(), llama_startup_timeout_seconds=2.0, llama_poll_interval_seconds=1.0)
    manager = LlamaCppServerManager(config, opener=opener, clock=clock, sleep=sleep)

    health = manager.wait_for_ready(2.0)

    assert health.state is LlamaHealthState.UNAVAILABLE
    assert "timed out" in health.body.lower()


def test_wait_for_ready_reports_process_exit_during_loading():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b"Loading model"),
        )

    state = {"value": 0.0}

    def clock() -> float:
        return state["value"]

    def sleep(seconds: float) -> None:
        state["value"] += seconds

    process = FakeProcess()
    process.returncode = 7

    manager = LlamaCppServerManager(AppConfig(), opener=opener, clock=clock, sleep=sleep)

    health = manager.wait_for_ready(10.0, process=process)

    assert health.state is LlamaHealthState.UNAVAILABLE
    assert health.status_code == 7
    assert "exited before the model became ready" in health.body


def test_bootstrap_retries_with_more_conservative_settings(tmp_path, monkeypatch):
    installation = _build_installation(tmp_path)
    config = AppConfig()
    manager = LlamaCppServerManager(config)
    launch_calls: list[tuple[int, int, int]] = []

    def discover_installation(self):
        return installation

    def check_health(self):
        return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "")

    def is_port_occupied(self):
        return False

    def launch_server(self, installation_arg):
        launch_calls.append(
            (self._config.llama_context_size, self._config.llama_threads, self._config.llama_max_output_tokens)
        )
        if self._config.llama_context_size > 1024:
            return None
        return FakeProcess()

    def wait_for_ready(self, timeout_seconds, process=None, progress_callback=None):
        if self._config.llama_context_size <= 1024:
            return LlamaCppHealthCheck(LlamaHealthState.READY, 200, "ok")
        return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "startup failed")

    monkeypatch.setattr(LlamaCppServerManager, "discover_installation", discover_installation, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "check_health", check_health, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "_is_port_occupied", is_port_occupied, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "_launch_server", launch_server, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "wait_for_ready", wait_for_ready, raising=False)

    result = manager.bootstrap()

    assert result.ready is True
    assert launch_calls[0][0] == 2048
    assert launch_calls[-1][0] == 1024


def test_bootstrap_reports_failed_recovery(tmp_path, monkeypatch):
    installation = _build_installation(tmp_path)
    config = AppConfig()
    manager = LlamaCppServerManager(config)

    def discover_installation(self):
        return installation

    def check_health(self):
        return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "")

    def is_port_occupied(self):
        return False

    def launch_server(self, installation_arg):
        if self._config.llama_context_size > 1024:
            return None
        return FakeProcess()

    def wait_for_ready(self, timeout_seconds, process=None, progress_callback=None):
        return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "startup failed")

    monkeypatch.setattr(LlamaCppServerManager, "discover_installation", discover_installation, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "check_health", check_health, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "_is_port_occupied", is_port_occupied, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "_launch_server", launch_server, raising=False)
    monkeypatch.setattr(LlamaCppServerManager, "wait_for_ready", wait_for_ready, raising=False)

    result = manager.bootstrap()

    assert result.ready is False
    assert "startup failed" in result.health.body


def test_shutdown_only_stops_owned_server(tmp_path):
    installation = _build_installation(tmp_path)
    owned_process = FakeProcess()
    external_process = FakeProcess()

    manager = LlamaCppServerManager(AppConfig())
    manager.shutdown(
        LlamaCppServerSession(
            installation=installation,
            process=owned_process,
            owns_server=True,
        )
    )
    manager.shutdown(
        LlamaCppServerSession(
            installation=installation,
            process=external_process,
            owns_server=False,
        )
    )

    assert owned_process.terminated is True
    assert external_process.terminated is False


def test_conversation_engine_stream_failure_does_not_commit_history():
    class FailingStreamProvider:
        def stream_response(self, user_message, conversation_history=None, system_prompt=None):
            yield "Partial"
            raise AIProviderStreamError("stream broke")

        def generate_response(self, user_message, conversation_history=None, system_prompt=None):
            raise AIProviderStreamError("stream broke")

    engine = ConversationEngine(provider=FailingStreamProvider())
    chunks: list[str] = []

    turn = engine.stream_message("Explain RAG", emit_chunk=chunks.append)

    assert chunks == ["Partial"]
    assert turn.succeeded is False
    assert turn.reply == "Local brain stream failed. Please try again."
    assert engine.history == ()

from echo_core.config import load_config


def test_load_config_uses_defaults(monkeypatch):
    monkeypatch.delenv("ECHO_NAME", raising=False)
    monkeypatch.delenv("ECHO_VERSION", raising=False)
    monkeypatch.delenv("ECHO_LOG_LEVEL", raising=False)
    monkeypatch.delenv("ECHO_DEFAULT_MODE", raising=False)

    config = load_config()

    assert config.echo_name == "ECHO-7"
    assert config.version == "1.0.0"
    assert config.log_level == "INFO"
    assert config.default_mode == "Text"
    assert config.ai_provider == "auto"
    assert config.llama_host == "127.0.0.1"
    assert config.llama_port == 8080
    assert config.llama_threads == 4
    assert config.llama_gpu_layers == 0
    assert config.llama_startup_timeout_seconds == 180.0
    assert config.llama_request_timeout_seconds == 180.0
    assert config.llama_poll_interval_seconds == 2.0
    assert config.llama_context_size == 2048
    assert config.llama_max_output_tokens == 256
    assert config.llama_context_retry_safety_tokens == 128

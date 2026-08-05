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

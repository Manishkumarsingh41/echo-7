from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_ECHO_NAME = "ECHO-7"
DEFAULT_VERSION = "1.0.0"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MODE = "Text"
DEFAULT_AI_PROVIDER = "auto"
DEFAULT_SYSTEM_PROMPT = (
    "You are ECHO-7, a local-first personal AI companion. Be helpful, concise, "
    "natural, and honest. You may respond in the language used by the user. Do not "
    "claim to remember information that has not been provided in the current context."
)
DEFAULT_LLAMACPP_HOST = "127.0.0.1"
DEFAULT_LLAMACPP_PORT = 8080
DEFAULT_LLAMACPP_CONTEXT_SIZE = 2048
DEFAULT_LLAMACPP_THREADS = 4
DEFAULT_LLAMACPP_GPU_LAYERS = 0
DEFAULT_LLAMACPP_STARTUP_TIMEOUT_SECONDS = 180.0
DEFAULT_LLAMACPP_REQUEST_TIMEOUT_SECONDS = 180.0
DEFAULT_LLAMACPP_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_LLAMACPP_MAX_OUTPUT_TOKENS = 256
DEFAULT_LLAMACPP_CONTEXT_RETRY_SAFETY_TOKENS = 128


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Application settings loaded from environment variables."""

    echo_name: str = DEFAULT_ECHO_NAME
    version: str = DEFAULT_VERSION
    log_level: str = DEFAULT_LOG_LEVEL
    default_mode: str = DEFAULT_MODE
    ai_provider: str = DEFAULT_AI_PROVIDER
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    llama_host: str = DEFAULT_LLAMACPP_HOST
    llama_port: int = DEFAULT_LLAMACPP_PORT
    llama_context_size: int = DEFAULT_LLAMACPP_CONTEXT_SIZE
    llama_threads: int = DEFAULT_LLAMACPP_THREADS
    llama_gpu_layers: int = DEFAULT_LLAMACPP_GPU_LAYERS
    llama_startup_timeout_seconds: float = DEFAULT_LLAMACPP_STARTUP_TIMEOUT_SECONDS
    llama_request_timeout_seconds: float = DEFAULT_LLAMACPP_REQUEST_TIMEOUT_SECONDS
    llama_poll_interval_seconds: float = DEFAULT_LLAMACPP_POLL_INTERVAL_SECONDS
    llama_max_output_tokens: int = DEFAULT_LLAMACPP_MAX_OUTPUT_TOKENS
    llama_context_retry_safety_tokens: int = DEFAULT_LLAMACPP_CONTEXT_RETRY_SAFETY_TOKENS
    llama_runtime_path: str = ""
    llama_model_path: str = ""


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_config() -> AppConfig:
    """Load application configuration from environment variables."""
    return AppConfig(
        echo_name=os.getenv("ECHO_NAME", DEFAULT_ECHO_NAME),
        version=os.getenv("ECHO_VERSION", DEFAULT_VERSION),
        log_level=os.getenv("ECHO_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        default_mode=os.getenv("ECHO_DEFAULT_MODE", DEFAULT_MODE),
        ai_provider=os.getenv("ECHO_AI_PROVIDER", DEFAULT_AI_PROVIDER),
        system_prompt=os.getenv("ECHO_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        llama_host=os.getenv("ECHO_LLAMA_HOST", DEFAULT_LLAMACPP_HOST),
        llama_port=_get_int_env("ECHO_LLAMA_PORT", DEFAULT_LLAMACPP_PORT),
        llama_context_size=_get_int_env(
            "ECHO_LLAMA_CONTEXT_SIZE",
            DEFAULT_LLAMACPP_CONTEXT_SIZE,
        ),
        llama_threads=_get_int_env("ECHO_LLAMA_THREADS", DEFAULT_LLAMACPP_THREADS),
        llama_gpu_layers=_get_int_env(
            "ECHO_LLAMA_GPU_LAYERS",
            DEFAULT_LLAMACPP_GPU_LAYERS,
        ),
        llama_startup_timeout_seconds=_get_float_env(
            "ECHO_LLAMA_STARTUP_TIMEOUT_SECONDS",
            DEFAULT_LLAMACPP_STARTUP_TIMEOUT_SECONDS,
        ),
        llama_request_timeout_seconds=_get_float_env(
            "ECHO_LLAMA_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_LLAMACPP_REQUEST_TIMEOUT_SECONDS,
        ),
        llama_poll_interval_seconds=_get_float_env(
            "ECHO_LLAMA_POLL_INTERVAL_SECONDS",
            DEFAULT_LLAMACPP_POLL_INTERVAL_SECONDS,
        ),
        llama_max_output_tokens=_get_int_env(
            "ECHO_LLAMA_MAX_OUTPUT_TOKENS",
            DEFAULT_LLAMACPP_MAX_OUTPUT_TOKENS,
        ),
        llama_context_retry_safety_tokens=_get_int_env(
            "ECHO_LLAMA_CONTEXT_RETRY_SAFETY_TOKENS",
            DEFAULT_LLAMACPP_CONTEXT_RETRY_SAFETY_TOKENS,
        ),
        llama_runtime_path=os.getenv("ECHO_LLAMA_RUNTIME_PATH", ""),
        llama_model_path=os.getenv("ECHO_LLAMA_MODEL_PATH", ""),
    )

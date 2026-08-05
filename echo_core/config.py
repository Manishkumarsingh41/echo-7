from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_ECHO_NAME = "ECHO-7"
DEFAULT_VERSION = "1.0.0"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MODE = "Text"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Application settings loaded from environment variables."""

    echo_name: str = DEFAULT_ECHO_NAME
    version: str = DEFAULT_VERSION
    log_level: str = DEFAULT_LOG_LEVEL
    default_mode: str = DEFAULT_MODE


def load_config() -> AppConfig:
    """Load application configuration from environment variables."""
    return AppConfig(
        echo_name=os.getenv("ECHO_NAME", DEFAULT_ECHO_NAME),
        version=os.getenv("ECHO_VERSION", DEFAULT_VERSION),
        log_level=os.getenv("ECHO_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        default_mode=os.getenv("ECHO_DEFAULT_MODE", DEFAULT_MODE),
    )

from __future__ import annotations

import sys
from typing import Callable

from echo_core.ai.mock_provider import MockAIProvider
from echo_core.config import load_config
from echo_core.conversation import ConversationEngine, run_text_chat
from echo_core.logging import configure_logging


def build_banner(echo_name: str, mode: str) -> str:
    """Build the startup banner for the current runtime."""
    return (
        "# ================================\n"
        f"{echo_name}\n"
        "Status: ONLINE\n"
        f"Mode: {mode}"
    )


def main() -> int:
    """Run the Phase 1 ECHO-7 text console."""
    config = load_config()
    configure_logging(config.log_level)

    provider = MockAIProvider(echo_name=config.echo_name)
    engine = ConversationEngine(provider=provider)

    print(build_banner(config.echo_name, config.default_mode))
    run_text_chat(engine=engine, input_func=input, output_func=print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

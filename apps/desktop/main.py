from __future__ import annotations

import logging
import sys
from typing import Callable

from echo_core.ai.llama_cpp_provider import LlamaCppProvider
from echo_core.ai.llama_cpp_server import LlamaCppServerManager, LlamaHealthState
from echo_core.ai.mock_provider import MockAIProvider
from echo_core.config import load_config
from echo_core.conversation import (
    ContextWindowSettings,
    ConversationEngine,
    run_streaming_text_chat,
    run_text_chat,
)
from echo_core.logging import configure_logging


def build_banner(echo_name: str) -> str:
    """Build the startup banner for the current runtime."""

    return (
        "# ================================\n"
        f"{echo_name}\n"
        "Searching for ECHO brain..."
    )


def _build_runtime_summary(result) -> list[str]:
    lines: list[str] = []
    if result.installation is not None:
        lines.append("ECHO Drive: Found")
        lines.append("Runtime: llama.cpp")
        lines.append(f"Model: {result.installation.model_label}")
    if result.health.state is LlamaHealthState.LOADING:
        lines.append("Loading local AI...")
        lines.append("This may take up to a few minutes.")
    elif result.health.state is LlamaHealthState.READY:
        lines.append("Brain: ONLINE")
        lines.append("Mode: Text")
    else:
        lines.append("Local ECHO brain unavailable.")
    return lines


def _write_stdout(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _make_loading_progress_callback() -> Callable[[float], None]:
    last_reported_milestone = 0

    def progress_callback(elapsed_seconds: float) -> None:
        nonlocal last_reported_milestone
        milestone = int(elapsed_seconds // 30) * 30
        if milestone >= 30 and milestone != last_reported_milestone:
            print(f"Still loading... {milestone}s")
            last_reported_milestone = milestone

    return progress_callback


def main() -> int:
    """Run the ECHO-7 text console."""

    config = load_config()
    configure_logging(config.log_level)

    session = None
    manager = None
    startup_result = None

    print(build_banner(config.echo_name))

    if config.ai_provider in {"auto", "llama_cpp"}:
        manager = LlamaCppServerManager(config)
        startup_result = manager.bootstrap_with_progress(progress_callback=_make_loading_progress_callback())
        for line in _build_runtime_summary(startup_result):
            print(line)

        if startup_result.ready:
            provider = LlamaCppProvider(
                endpoint=startup_result.endpoint,
                timeout_seconds=config.llama_request_timeout_seconds,
                max_tokens=config.llama_max_output_tokens,
                system_prompt=config.system_prompt,
            )
            session = startup_result.session
            logging.debug("Local ECHO brain online: %s", startup_result.diagnostic or "ready")
        else:
            provider = MockAIProvider(echo_name=config.echo_name)
            logging.warning(
                "Local ECHO brain unavailable: %s",
                startup_result.diagnostic or startup_result.health.body or "unknown startup failure",
            )
            print("Using MockProvider fallback.")
    else:
        provider = MockAIProvider(echo_name=config.echo_name)
        print("MockProvider selected.")

    engine = ConversationEngine(
        provider=provider,
        system_prompt=config.system_prompt,
        context_settings=ContextWindowSettings(
            context_window_tokens=config.llama_context_size,
            output_token_reserve=config.llama_max_output_tokens,
            retry_safety_tokens=config.llama_context_retry_safety_tokens,
        ),
    )

    if startup_result is not None and startup_result.ready:
        run_streaming_text_chat(
            engine=engine,
            input_func=input,
            write_func=_write_stdout,
        )
    else:
        run_text_chat(engine=engine, input_func=input, output_func=print)

    if manager is not None and session is not None and session.owns_server:
        print("Stopping local AI...")
        manager.shutdown(session)
        print("ECHO stopped.")
        print("You can safely eject the USB.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

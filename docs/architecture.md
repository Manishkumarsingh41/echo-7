# ECHO-7 Architecture

## Core Principle

ECHO-7 is designed as a modular local-first companion. The Phase 1 codebase keeps the runtime small while establishing boundaries that future features can extend.

## Current Modules

- `apps/desktop/` - the runnable desktop/text entry point.
- `echo_core/config.py` - environment-driven application settings.
- `echo_core/logging.py` - logging configuration.
- `echo_core/conversation.py` - conversation flow and exit handling.
- `echo_core/ai/` - response provider abstraction, mock fallback, llama.cpp client, and USB server manager.

## Planned Modules

The following folders are reserved for future work and are intentionally minimal in Phase 1:

- `echo_core/memory/`
- `echo_core/speech/`
- `echo_core/vision/`
- `echo_core/knowledge/`
- `echo_core/identity/`
- `echo_core/sync/`
- `echo_core/tools/`

## Extension Model

Future capabilities should plug into the existing interfaces instead of coupling directly to the CLI. The local llama.cpp provider now uses the same response interface as the mock provider, and memory or tool systems can be introduced as separate services behind explicit boundaries.

## Safety Notes

Phase 1 keeps the system text-only and offline. Sensitive features such as microphone access, camera access, automation, sync, and biometric handling remain deferred to later phases and should require explicit user permission when introduced.

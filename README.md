# ECHO-7

ECHO-7 is a local-first persistent personal AI companion. Phase 1 established the clean Python foundation and text-only runtime. Phase 2A adds an optional local llama.cpp integration while preserving the mock provider for testing and fallback.

## Phase 1 Scope

Implemented in this phase:

- Project structure for a modular ECHO core
- Configuration loading from environment variables
- Lightweight logging setup
- A deterministic mock AI provider
- A small conversation engine with exit handling
- A text CLI that starts with `python -m apps.desktop.main`
- Basic pytest coverage
- Optional local llama.cpp provider and USB runtime discovery

Not implemented yet:

- Android support
- Cloud sync
- Voice input or spoken output
- Vision and camera features
- Face recognition
- RAG / document ingestion
- PC automation
- Large local models
- Permanent memory
- Voice, vision, automation, sync, and mobile features

## Architecture

The code is organized so future modules can be added without rewriting the conversation layer.

- `apps/desktop/` contains the runnable desktop entry point.
- `echo_core/config.py` loads application settings.
- `echo_core/logging.py` configures app logging.
- `echo_core/conversation.py` owns the text conversation flow and exit handling.
- `echo_core/ai/` contains the AI provider abstraction and the current mock provider.
- Other `echo_core/*` folders are reserved for future features.

See `docs/architecture.md` for the modular design overview.

## Windows Setup

Create a virtual environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the current shell:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

## Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run ECHO

```powershell
python -m apps.desktop.main
```

Example session:

```text
# ================================
ECHO-7
Status: ONLINE
Mode: Text
You: Hello Echo
ECHO: Hello. I'm ECHO-7.
You: who are you?
ECHO: I'm ECHO-7, your local personal AI companion.
You: exit
ECHO: Shutting down. Goodbye.
```

## Run Tests

```powershell
pytest
```

## Future Roadmap

Phase 2A focuses on the local LLM path only. Later phases will gradually add memory, voice, knowledge retrieval, identity features, sync, and safer tool access. Each capability should plug into the existing core instead of replacing it.

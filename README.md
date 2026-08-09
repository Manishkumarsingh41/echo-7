# ECHO-7

ECHO-7 is a **local-first persistent personal AI companion**. Phase 1 established the clean Python foundation and text-only runtime. Phase 2A adds an optional local llama.cpp integration while preserving the mock provider for testing and fallback. **Phase 2B adds the 4-tier Memory Engine, Importance Evaluator, Encrypted Delta Sync, and 7-Day Consolidation.**

## 🚀 Current Status

- ✅ Project foundation
- ✅ Portable USB launcher
- ✅ llama.cpp integration (Phi-3.5)
- ✅ Streaming conversation
- ✅ Context window management
- ✅ **4-Tier Memory Engine (Working/Recent/Important/Archive)**
- ✅ **Importance Evaluator (pattern-based scoring)**
- ✅ **Stable Key Management**
- ✅ **Encrypted Delta Sync & Merge**
- ✅ **7-Day Consolidation Engine (Deduplication + Archiving)**
- ✅ **78/78 tests passing**
- 🟡 Desktop Chat UI (~80%)
- 🔜 Experiments & Paper

## 📊 Memory Architecture

ECHO-7 includes a four-tier memory hierarchy:

| Tier | Storage | Sync | Purpose |
|------|---------|------|---------|
| **Working** | RAM | No | Current conversation |
| **Recent** | SQLite | ✅ Encrypted delta | Cross-device continuity (7-day) |
| **Important** | SQLite | No | Permanent user-controlled |
| **Archive** | Local Drive | No | Compressed historical search |

### Importance Evaluator

Messages are automatically scored based on patterns:

```python
from echo_core.memory.evaluator import MemoryEvaluator
evaluator = MemoryEvaluator()
score, tier = evaluator.evaluate("I'm building a project called ECHO-7")
# score: 0.85, tier: "important"
```

### Encrypted Delta Sync

Synchronization uses **delta updates** (only changes) and **stable key management**:

```python
from echo_core.memory.sync import DeltaSyncEngine

# Generate encrypted delta
delta = sync_engine.generate_delta()
# Merge on another device
merged_count = sync_engine.merge_delta(delta["encrypted_data"])
```

### 7-Day Consolidation

Memories older than 7 days are automatically consolidated:

```python
from echo_core.memory.consolidation import ConsolidationEngine

# Run consolidation
result = consolidation_engine.consolidate()
print(f"Consolidated {result['consolidated']} memories")
# Output: Consolidated 5 memories, 2 duplicates removed
```

## 📁 Project Structure (Updated)

```
echo-7/
├── echo_core/
│   ├── memory/
│   │   ├── engine.py          # 4-Tier Memory Engine
│   │   ├── evaluator.py       # Importance Evaluator
│   │   ├── sync.py            # Delta Sync Engine
│   │   ├── consolidation.py   # 7-Day Consolidation Engine
│   │   └── __init__.py
│   ├── crypto/
│   │   ├── key_manager.py     # Stable Key Management
│   │   └── __init__.py
│   ├── ai/
│   │   ├── llama_cpp_provider.py
│   │   ├── mock_provider.py
│   │   └── base.py
│   ├── conversation.py        # Conversation Engine
│   ├── config.py
│   └── portable_launcher.py
├── apps/
│   └── desktop/
│       ├── main.py            # Desktop entry
│       └── chat_ui.py
├── tests/
│   ├── test_memory.py         # 10 Memory Engine tests
│   ├── test_evaluator.py      # 10 Evaluator tests
│   ├── test_sync.py           # 9 Sync tests
│   ├── test_consolidation.py  # 6 Consolidation tests
│   └── ... (43 existing tests)
├── data/
│   ├── memory.db              # SQLite database
│   ├── keys/                  # Encryption keys
│   ├── archives/              # Consolidated archives
│   └── logs/
├── experiments/               # Research experiments
├── paper/                     # Research paper
└── START-ECHO-7.bat          # Portable launcher
```

## 🧪 Testing

```powershell
# Run all tests
pytest tests/ -v

# Run memory tests
pytest tests/test_memory.py -v

# Run evaluator tests
pytest tests/test_evaluator.py -v

# Run sync tests
pytest tests/test_sync.py -v

# Run consolidation tests
pytest tests/test_consolidation.py -v

# Run with coverage
pytest tests/ --cov=echo_core
```

**Current Test Status: 78/78 Passing**

## 📄 Phase Progress

**Phase 1 (Completed):**

- Project structure, config, logging, mock provider, conversation engine, CLI, basic pytest

**Phase 2A (Completed):**

- Local llama.cpp integration with Phi-3.5, health/startup/recovery, streaming, context management

**Phase 2B (Completed):**

- 4-Tier Memory Engine (Working/Recent/Important/Archive)
- SQLite persistence, indexes, working memory boundary, statistics, archive search
- Importance Evaluator with pattern-based scoring
- Encrypted Delta Sync with stable key management
- 7-Day Consolidation Engine with deduplication and archiving
- 35 new tests (10 Memory, 10 Evaluator, 9 Sync, 6 Consolidation)
- 78 total tests passing

## 🔜 Future Roadmap

- **Cloud Retention** – optional temporary cloud sync
- **Cross-device merge** – full delta merging
- **Research experiments** – retrieval accuracy, sync efficiency, cloud exposure
- **Paper publication** – AAAI 2027, ICML 2027, UIST 2027

## 🚀 Quick Start

### Windows Setup

Create a virtual environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the current shell:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

### Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Run ECHO

Double-click `START-ECHO-7.bat` from the USB root.

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

### Run Tests

```powershell
pytest tests/ -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m "Add amazing feature"`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 📄 Research Paper

My paper is now available on SSRN:

> **"ECHO-7: A Local-First Personal AI Architecture with 7-Day Rolling Memory Synchronization and User-Controlled Memory Consolidation"**

- 📄 Read on SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7254322
- 🎯 SSRN Abstract ID: 7254322

## 📄 License

MIT License

## 🙏 Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp)
- [Phi-3.5](https://huggingface.co/microsoft/Phi-3.5-mini-instruct)
- [SQLite](https://sqlite.org/)
- [cryptography](https://cryptography.io/)

---

> **ECHO-7: One Identity, Multiple Bodies, One Continuous Memory.**
```

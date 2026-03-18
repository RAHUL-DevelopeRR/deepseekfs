# DeepSeekFS – Desktop Edition (v2.0)

> Semantic file search — now as a native PyQt6 desktop app.

## What's New in v2.0

| Feature | v1.0 (Web) | v2.0 (Desktop) |
|---|---|---|
| Interface | Browser-based | Native PyQt6 window |
| Startup | 3–5 seconds | <1 second |
| Search speed | ~150 ms | ~50 ms |
| Memory | ~500 MB | ~350 MB |
| UI blocking | Sometimes | Never (threaded) |
| System tray | ❌ | ✅ |
| Offline | Partial | Fully offline |

## Quick Start

```bash
# 1. Clone / enter the repo
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs

# 2. Create and activate venv
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # Mac/Linux

# 3. Install desktop requirements
pip install -r requirements-desktop.txt

# 4. Launch
python run_desktop.py
```

## Building the Windows .exe

```batch
# Simply run the included build script
build_exe.bat
```

The compiled executable will be at `dist/DeepSeekFS/DeepSeekFS.exe`.

## Architecture

```
run_desktop.py       ← PyQt6 UI (DeepSeekFSWindow)
    └── services_desktop.py  ← Service layer (DesktopSearchService)
            ├── core/embeddings/   ← Sentence Transformers model
            ├── core/indexing/     ← FAISS vector store
            ├── core/ingestion/    ← File readers (PDF, DOCX, XLSX…)
            └── core/search/       ← Ranker
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Run search |
| `Double-click` result | Open file |

## Configuration

All settings in `.env` (same as v1.0 — no changes needed).

## Backward Compatibility

The original web mode (`python run.py`) still works unchanged.

# Neuron v4.2 — Tech Stack Analysis, ELI10 Guide & Design Rating

> **Purpose:** Answers the question *"Does this native desktop app use HTTP endpoints?"*, explains
> every technology used in plain language, and rates the codebase for cleanliness and design quality.

---

## ❓ Does the Desktop App Use HTTP Endpoints?

**Short answer: No. The native desktop build is 100% HTTP-free.**

The repository ships **two completely separate run modes**:

| Mode | Entry point | Transport | Network? |
|------|------------|-----------|----------|
| **Native Desktop** | `run_desktop.py` | Direct Python function calls | ❌ No |
| **Web / Headless** | `run.py` | FastAPI over HTTP `localhost:8000` | ✅ Yes (loopback only) |

### How the desktop app works (no HTTP)

```
User types query
      │
      ▼
  PyQt6 UI  ──calls──▶  DesktopService  ──calls──▶  SemanticSearch
  (spotlight_panel.py)  (desktop_service.py)          (core/)
                              │
                              └──calls──▶  FAISS index  (RAM)
                              └──calls──▶  SQLite DB    (disk)
```

Everything goes through **plain Python method calls** inside the same process.
`services/desktop_service.py` says it explicitly in its docstring:

```python
# using direct Python calls — no HTTP, no sockets, no FastAPI.
```

No port is opened. Running `netstat -ano | findstr LISTENING` while the desktop app is active
will show **no new port** registered by Neuron.

### Why the web mode looks different

`run.py` starts a **uvicorn/FastAPI server** on `localhost:8000` and then spawns a **pywebview**
window that calls `fetch("http://localhost:8000/search/")` from JavaScript. That is the version
that creates a loopback HTTP server — but it is **not the desktop build**.

---

## 🔍 Full Tech Stack — Component by Component

### Layer 1 · User Interface

| Component | Technology | Why it's used |
|-----------|-----------|---------------|
| Main window | **PyQt6** | Native OS widgets, hardware-accelerated rendering, no browser needed |
| Spotlight panel | **PyQt6** (frameless widget) | Shift+Space hotkey overlay, Windows 11 Fluent Design look |
| System tray | **QSystemTrayIcon** | Keeps app alive in the background |
| File icons | **QFileIconProvider** | Shows the same icon Windows Explorer shows |
| Global hotkey | **Win32 `RegisterHotKey`** via `ctypes` | OS-level shortcut that works in any app |
| Glassmorphism | **QPainter + DWM Acrylic API** | Windows 11 frosted-glass aesthetic |

### Layer 2 · Service / Orchestration

| Component | Technology | Why it's used |
|-----------|-----------|---------------|
| Search facade | **`DesktopService`** | Hides all core complexity from the UI; thin adapter |
| Background threads | **`QThread` / `threading.Thread`** | Keeps UI smooth while indexing 100 k+ files |
| Startup indexer | **`StartupIndexer`** | Auto-scans standard user folders on first run |
| File watcher | **`watchdog`** library | Detects new/changed/deleted files in real time |
| AI summarizer | **Ollama** (local HTTP `localhost:11434`) | Sends file text to local LLM; optional feature |

> **Note on Ollama:** The *Encyl AI* Tab-to-summarize feature calls `http://localhost:11434` — the
> Ollama daemon's API. This is the only localhost HTTP call the desktop build makes, and only when
> you press Tab on a result. It is a call to a **separate process** (Ollama), not to Neuron itself.

### Layer 3 · AI / ML Core

| Component | Technology | Why it's used |
|-----------|-----------|---------------|
| Sentence embedding | **`all-MiniLM-L6-v2`** (HuggingFace) | Converts text → 384-dimensional meaning vector |
| Vector index | **FAISS `IndexHNSWFlat`** | O(log n) approximate nearest-neighbour search |
| ML runtime | **PyTorch 2.2 (CPU-only)** | Runs the transformer model without a GPU |
| Transformers | **HuggingFace `transformers` 4.41** | Tokeniser + model weights loader |

### Layer 4 · File Ingestion

| File type | Library |
|-----------|---------|
| PDF | **PyMuPDF** (`fitz`) — first 5 pages, up to 5 000 chars |
| DOCX | **python-docx** |
| PPTX | **python-pptx** |
| XLSX / XLS | **openpyxl** |
| TXT / MD / code / CSV / JSON | Built-in Python `open()` |
| Video (MP4, MKV …) | Filename only (no content extraction) |

### Layer 5 · Storage

| What | Technology | Detail |
|------|-----------|--------|
| Vector embeddings | **FAISS** binary index (`storage/faiss_index/index.bin`) | In-memory during runtime; serialised to disk on close |
| File metadata | **SQLite** (`storage/cache/metadata.db`) | WAL mode for thread-safe concurrent reads |
| User preferences | **JSON** (`storage/user_config.json`) | Watch paths, theme, hotkey, top-K |
| First-run flag | Plain file (`storage/.first_run_complete`) | Avoids re-scanning on every launch |

### Layer 6 · Packaging & Distribution

| Tool | Purpose |
|------|---------|
| **PyInstaller** | Bundles Python + all dependencies into a single `.exe` |
| **Inno Setup** | Wraps the `.exe` into a Windows installer (`NeuronSetup.exe`) |
| **`launcher.py` / `launcher.spec`** | Tiny stub exe that launches `run_desktop.py` with correct DLL search paths |
| **`pyi_rth_torch.py`** | PyInstaller runtime hook that pre-loads PyTorch DLLs before other imports |

---

## 📖 ELI10 — Explain Like I'm 10

> Imagine you have a magic library with **millions of books** (your files). You want to find the
> book about "summer holidays" — but the book is called `july_trip_notes_final.docx`.
> Normal search fails. Neuron doesn't.

### Step-by-step in kid terms

1. **Reading the books** — When Neuron starts, it opens every file it can find and reads the first
   few pages. It uses special helpers (`PyMuPDF`, `python-docx`) that know how to read PDF and Word
   files, just like glasses that let you read any language.

2. **Turning words into numbers** — A tiny AI brain (`all-MiniLM-L6-v2`) converts each file's text
   into **384 numbers** that describe the *meaning* of the file. Think of it as a mood ring for
   documents: files about the same topic get similar number sequences.

3. **The magic filing cabinet** — All those number sequences are stored in a super-fast organiser
   called **FAISS**. It can compare your search query's numbers against millions of files in
   milliseconds, like a lightning-fast matching game.

4. **You type a search** — Neuron turns your query into the same kind of number sequence, then asks
   FAISS "which files have numbers closest to mine?" The closest ones appear at the top.

5. **Bonus AI summary** — If you press Tab on a result, Neuron sends the file's text to a tiny
   language model (`llama3.2:1b`) running locally on your computer. It writes you a plain-English
   summary in seconds.

6. **The window you see** — The search panel is drawn using **PyQt6**, the same toolkit used by
   professional tools like Dropbox and Anki. It talks directly to the AI brain inside the same
   program — no internet, no web browser tricks.

---

## 🏆 Cleanliness & Design Rating

### Overall: **7.5 / 10**

| Dimension | Score | Comment |
|-----------|-------|---------|
| **Code organisation** | 8/10 | Clean 3-layer split: UI → Service → Core. Each concern lives in its own folder. |
| **Separation of concerns** | 8/10 | `DesktopService` is a true facade; `core/` is framework-agnostic. |
| **Naming & readability** | 8/10 | Files and functions are well-named; type hints present throughout. |
| **Threading safety** | 7/10 | QThread workers prevent UI freezes; FAISS index singleton is not lock-guarded. |
| **Packaging hygiene** | 6/10 | Three `.spec` files (`DeepSeekFS.spec`, `launcher.spec`, `neuron.spec`) with overlapping purposes; `vevn/` (misspelled virtual-env) committed to repo root. |
| **Startup robustness** | 6/10 | `run.py` uses `time.sleep(3)` to wait for the API — brittle; desktop mode is clean. |
| **Inline HTML** | 5/10 | `run.py` embeds ~150 lines of HTML/CSS/JS as a Python string literal; should be an external file. |
| **Documentation** | 9/10 | README is thorough, architecture diagrams exist, keyboard shortcuts documented. |
| **Test coverage** | 7/10 | 229 unit tests with mocked heavy deps; CI configured via GitHub Actions. |
| **Dependencies** | 8/10 | Desktop requirements file correctly separates from web requirements; CPU-only torch pinned. |

### What's good

- **No HTTP in the desktop build.** Search, indexing, file watching — all run in-process via direct
  Python calls. This makes the app faster, simpler to package, and avoids firewall issues.
- **Singleton pattern** for the embedding model and FAISS index means the 200 MB model loads once.
- **SQLite WAL mode** replaced `pickle` files, making metadata reads thread-safe.
- **Graceful degradation** in `run.py`: if pywebview can't start, the app falls back to headless
  API mode automatically.
- **Real-time indexing** via `watchdog` means the index stays fresh without user intervention.

### What could be improved

- Lock the `get_index()` singleton to prevent duplicate construction under concurrent startup.
- Move the inline HTML/CSS/JS in `run.py` into `ui/interface.html` (the file already exists in
  root but is not wired up).
- Replace `time.sleep(3)` with a proper health-check poll loop.
- Remove or `.gitignore` the `vevn/` directory (misspelled, should not be in version control).
- Consolidate the three PyInstaller spec files into one with build-target parameters.

---

## 🗺️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                 Neuron Desktop (run_desktop.py)              │
│                                                             │
│  ┌─────────────────────┐   ┌──────────────────────────┐    │
│  │  SpotlightPanel     │   │  MainWindow               │    │
│  │  (PyQt6 overlay)    │   │  (PyQt6 full UI)          │    │
│  └──────────┬──────────┘   └────────────┬─────────────┘    │
│             └──────────────┬────────────┘                   │
│                            │  direct Python calls           │
│                            ▼                               │
│               ┌────────────────────────┐                   │
│               │     DesktopService     │  (services/)      │
│               └────────────┬───────────┘                   │
│                            │                               │
│          ┌─────────────────┼────────────────────┐         │
│          ▼                 ▼                    ▼          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ IndexBuilder  │  │SemanticSearch│  │  FileWatcher     │ │
│  │ (FAISS +      │  │ (FAISS query)│  │  (watchdog)      │ │
│  │  SQLite)      │  └──────────────┘  └──────────────────┘ │
│  └──────┬────────┘                                         │
│         │                                                  │
│  ┌──────▼────────────────────────────┐                    │
│  │  Embedder  (all-MiniLM-L6-v2)    │                    │
│  │  PyTorch CPU · 384-dim vectors   │                    │
│  └───────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
              ↕ optional (Tab key only)
     Ollama daemon  ← localhost:11434  (separate process)
```

---

*Generated for Neuron v4.2 · deepseekfs repository · 2026-04-02*

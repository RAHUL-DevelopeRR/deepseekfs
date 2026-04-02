<p align="center">
  <img src="assets/HeiNeuron.png" alt="Neuron" width="160"/>
</p>

<h1 align="center">Neuron v4.2</h1>
<p align="center">
  <b>AI-Powered Semantic File Intelligence for Windows</b><br/>
  <i>Search smarter. Understand your files. Summarize anything.</i>
</p>

<p align="center">
  <a href="https://github.com/RAHUL-DevelopeRR/deepseekfs/releases/latest"><img src="https://img.shields.io/badge/⬇_Download-NeuronSetup_v4.2.exe-6366f1?style=for-the-badge&logo=windows" /></a>
  <a href="https://zero-x.live"><img src="https://img.shields.io/badge/🌐_Website-zero--x.live-00d4aa?style=for-the-badge" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-4.2-6366f1?style=flat-square" />
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/python-3.11-green?style=flat-square" />
  <img src="https://img.shields.io/badge/AI-Ollama%20%2B%20Llama%203.2-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/UI-PyQt6%20Fluent-purple?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square" />
</p>

---

## 🧠 What is Neuron?

**Neuron** is a desktop file intelligence engine that brings **semantic search** and **AI-powered file summarization** to Windows. Unlike traditional file search (which matches exact filenames), Neuron understands the *meaning* behind your query.

> Search for *"quarterly revenue report"* and find `Q3_2024_financial_summary.xlsx` — even though the words don't match.

### Key Features

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Search by meaning, not just keywords. Powered by `all-MiniLM-L6-v2` embeddings + FAISS vector index |
| 🧠 **Encyl AI Summarizer** | Press `Tab` on any file → instant AI summary via local `llama3.2:1b` (Ollama) |
| 📁 **Windows 11 UI** | Fluent Design with Segoe Fluent Icons, native context menus, glassmorphism |
| ⚡ **Real-time Indexing** | Watchdog monitors file changes → auto-reindex in background |
| 🔒 **100% Local** | No cloud. No telemetry. Everything runs on your machine |
| 📄 **40+ File Types** | PDF, DOCX, PPTX, TXT, MD, source code, images (metadata) |

---

## 🚀 Quick Start

### Option 1: Installer (Recommended)

1. Download **[NeuronSetup_v4.2.exe](https://github.com/RAHUL-DevelopeRR/deepseekfs/releases/latest)** from Releases
2. Run the installer → check **"Install Ollama"** if you want AI summarization
3. Launch Neuron from Desktop/Start Menu
4. Press `Shift+Space` to open the search panel

### Option 2: From Source

```bash
# Clone
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs.git
cd deepseekfs

# Create venv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements-desktop.txt

# Run
python run_desktop.py
```

### Option 3: Using the Launcher

```bash
# Place Neuron.exe in the project root (same folder as run_desktop.py)
# Double-click Neuron.exe
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Shift + Space` | Toggle Neuron search panel |
| `↑` `↓` | Navigate search results |
| `Enter` | Open selected file |
| `Tab` | Summarize selected file with Encyl AI |
| `Ctrl + C` | Copy file path |
| `Ctrl + Shift + C` | Copy as path (Windows style) |
| `Right-click` | Full Windows 11 context menu |
| `Escape` | Close panel |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                   Neuron Desktop                  │
│              (PyQt6 Fluent Design UI)             │
├──────────────┬───────────────┬────────────────────┤
│  Search Bar  │  File List    │  Properties Panel  │
│  (Semantic)  │  (Shell Icons)│  (Win11 Native)    │
├──────────────┴───────────────┴────────────────────┤
│                  Service Layer                     │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │ Desktop     │ │ Ollama       │ │ Startup    │ │
│  │ Service     │ │ Service      │ │ Indexer    │ │
│  └──────┬──────┘ └──────┬───────┘ └─────┬──────┘ │
├─────────┼───────────────┼────────────────┼────────┤
│         │        Core Engine             │        │
│  ┌──────▼──────┐ ┌──────▼───────┐ ┌─────▼──────┐ │
│  │ Semantic    │ │ Encyl AI     │ │ File       │ │
│  │ Search     │ │ (Ollama LLM) │ │ Watcher    │ │
│  │ (FAISS)    │ │              │ │ (Watchdog) │ │
│  └──────┬──────┘ └──────────────┘ └────────────┘ │
│  ┌──────▼──────┐                                  │
│  │ Embedder    │ ← all-MiniLM-L6-v2 (80MB)       │
│  │ (Sentence   │                                  │
│  │ Transformers)│                                  │
│  └──────┬──────┘                                  │
│  ┌──────▼──────┐                                  │
│  │ SQLite +    │ ← Metadata + SHA256 cache        │
│  │ FAISS Index │ ← Vector similarity search       │
│  └─────────────┘                                  │
└──────────────────────────────────────────────────┘
```

### Search Pipeline

```
User Query → MiniLM Embedding → FAISS Cosine Similarity → Top-K Results
                (384-dim)         (< 5ms for 100K files)
```

### Encyl AI Pipeline

```
File → Content Extraction → Ollama API → llama3.2:1b → Summary
       (PDF/DOCX/TXT)        (local)      (~1GB RAM)    → SHA256 Cache
```

---

## 📦 Building the Installer

### Prerequisites
- Python 3.11 with venv
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (for installer)

### Build Steps

```bash
# 1. Build the launcher exe (30 seconds)
venv\Scripts\pyinstaller.exe launcher.spec --clean --noconfirm

# 2. Copy launcher to project root
copy dist\Neuron.exe .

# 3. Build the installer (5-15 minutes)
"C:\Users\rahul\AppData\Local\Programs\Inno Setup 6\ISCC.exe" neuron_installer.iss

# Output: installer_output\NeuronSetup.exe
```

---

## 🔧 System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 (64-bit) | Windows 11 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 2 GB | 4 GB |
| **CPU** | Any x64 | Intel i5+ / Ryzen 5+ |
| **GPU** | Not required | NVIDIA CUDA (faster AI) |
| **Ollama** | Required for Encyl AI | Pre-installed |

### RAM Breakdown
| Component | RAM Usage |
|---|---|
| Sentence-transformers (MiniLM) | ~200 MB |
| PyQt6 UI + Python runtime | ~100 MB |
| FAISS vector index | ~50 MB |
| Ollama llama3.2:1b (when active) | ~1 GB |
| **Total (with Encyl)** | **~1.3 GB** |

---

## 🧪 Running Tests

```bash
# Unit tests
python -m pytest tests/ -v

# Lint
python -m flake8 core/ services/ ui/ --max-line-length 120

# Type check
python -m mypy core/ services/ --ignore-missing-imports
```

---

## 📁 Project Structure

```
deepseekfs/
├── run_desktop.py          # ← Main entry point (desktop)
├── launcher.py             # PyInstaller launcher stub (produces Neuron.exe)
├── warmup_encyl.py         # Ollama model pre-loader
├── neuron_installer.iss    # Inno Setup installer script
├── neuron.spec             # PyInstaller spec (canonical build)
├── launcher.spec           # PyInstaller spec for launcher stub
├── build_exe.bat           # One-click build helper
├── app/
│   ├── config.py           # Configuration, paths, user preferences
│   └── logger.py           # Logging setup
├── core/
│   ├── embeddings/         # Sentence-transformer embedder (all-MiniLM-L6-v2)
│   ├── indexing/           # FAISS index builder + SQLite metadata
│   ├── ingestion/          # File content extraction (40+ types)
│   ├── search/             # Semantic + keyword search engine
│   ├── time/               # Time-decay recency scoring
│   └── watcher/            # File system monitor (watchdog)
├── services/
│   ├── desktop_service.py  # Main service orchestrator for PyQt6 UI
│   ├── ollama_service.py   # Encyl AI (Ollama / llama3.2:1b integration)
│   └── startup_indexer.py  # Background indexing on startup
├── ui/
│   └── spotlight_panel.py  # PyQt6 Fluent Design search panel
├── docs/
│   ├── refactor_to_9_10.md # Refactor checklist
│   └── pre_install_info.txt
├── assets/
│   └── neuron_icon.ico     # DNA helix app icon
├── storage/                # Runtime data (FAISS index, SQLite, user config)
│   └── user_config.json
│
│   ── Legacy web-mode files (kept for reference, not used by desktop app) ──
├── run.py                  # [DEPRECATED] FastAPI + pywebview entry point
├── app/main.py             # [DEPRECATED] FastAPI application
├── api/                    # [DEPRECATED] REST API routes and schemas
├── Dockerfile              # [DEPRECATED] Web/server deployment
└── docker-compose.yml      # [DEPRECATED] Web/server deployment
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with 🧬 by <a href="https://github.com/RAHUL-DevelopeRR">Rahul</a>
</p>

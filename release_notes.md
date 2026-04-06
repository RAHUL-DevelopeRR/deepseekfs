<p align="center">
  <img src="https://raw.githubusercontent.com/RAHUL-DevelopeRR/deepseekfs/main/assets/neuron_circular.png" alt="Neuron" width="120"/>
</p>

<h2 align="center">🧠 Neuron v4.7</h2>
<p align="center"><b>AI-Powered Semantic File Intelligence for Windows</b></p>

---

## 🚀 What's New in v4.7 — Production Portability Release

### Architecture Overhaul
- **PyInstaller `--onedir` packaging** — The app is now fully self-contained. No Python, no venv, no dependencies needed on the target machine. Just install and run.
- **Bundled AI model** — The `all-MiniLM-L6-v2` embedding model is pre-cached in the installer. **No internet required for first run.**
- **Writable storage fallback** — If the app is installed to a read-only directory (e.g. Program Files), storage automatically falls back to `%LOCALAPPDATA%\Neuron`.

### Bug Fixes

| # | Bug | Fix |
|---|-----|-----|
| 1 | **"pythonw is not installed" on other PCs** | Replaced venv+launcher with PyInstaller frozen bundle — Python runtime is now embedded |
| 2 | **App crashes on machines without python-dotenv** | `dotenv` import is now optional (try/except) |
| 3 | **Search fails on first run (no internet)** | AI model bundled locally — works offline from first launch |
| 4 | **SSL bypass breaks corporate networks** | SSL certificate bypass is now scoped only to model download, not applied globally |
| 5 | **1000+ lines of dead code** | Removed unused `SearchPanel` class from `run_desktop.py` (was never called) |

---

## 📦 Installation

1. Download **NeuronSetup_v4.7.exe** below
2. Run the installer and follow the wizard
3. Press **Shift + Space** anytime to start semantic search

> **Note**: Windows SmartScreen may show a warning for new downloads. Click "More info" → "Run anyway" to proceed.

---

## ⚡ Core Capabilities

| Feature | Description |
|---------|-------------|
| 🧠 Semantic Search | Search files by meaning using neural embeddings |
| 📄 Encyl AI Summarizer | Offline AI summaries via Ollama (press `Tab`) |
| 🪟 Windows 11 Native | Mica/Acrylic UI with Fluent design |
| ⚡ Sub-5ms Search | FAISS HNSW search across 100K+ files |
| 📁 40+ File Types | Supports PDF, DOCX, PPTX, XLSX, code files and more |
| 📅 Memory OS | Activity search, streaks, "Jump back in" suggestions |

---

## 💻 System Requirements

- Windows 10/11 (64-bit)
- Minimum 4GB RAM (8GB recommended)
- 500MB free disk space
- **No internet required** — everything is included

---

<p align="center">100% Offline · No Telemetry · Privacy First</p>
<p align="center">🔗 <a href="https://zero-x.live">zero-x.live</a></p>

# DeepSeekFS 🔍

**Elite Semantic File Search Engine — Google Desktop / Spotlight level**

## 🚀 Quick Start

### Option A — Docker (recommended, works everywhere)

```bash
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs
docker compose up --build
```

The API will be available at **http://localhost:8000** and the interactive docs at **http://localhost:8000/docs**.

### Option B — Python (local, with desktop UI)

```bash
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

### Option B — Python (headless / server mode)

If you don't need the desktop window (e.g. running on a server or WSL), `run.py`
automatically falls back to headless mode and keeps the API alive:

```bash
python run.py          # opens browser UI if possible, otherwise stays headless
```

Or run the API directly with uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The app:
1. **Auto-detects** your Documents, Downloads, Desktop, OneDrive folders
2. **Indexes them in the background** (first run = full scan, subsequent = incremental)
3. **Opens the search UI** immediately — you can search while indexing runs
4. **Watches for new files** and indexes them in real-time

## 🧠 How It Works

```
App starts
    ↓
Detect user folders (Documents, Downloads, Desktop...)
    ↓
First run? → Full scan (background thread)
Seen before? → Incremental scan (only new files)
    ↓
FAISS index updated
    ↓
File watcher activated (real-time updates)
```

## 🎯 Ranking Formula

```
final_score = 0.6 × semantic_similarity
            + 0.25 × time_score
            + 0.15 × frequency_score
```

## 📁 Supported File Types

`.txt` `.pdf` `.docx` `.doc` `.md` `.json` `.csv` `.py` `.js` `.pptx` `.xlsx` `.html`

## 🔗 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search/` | Semantic search |
| POST | `/index/file` | Index single file |
| POST | `/index/directory` | Index folder |
| GET | `/health` | Stats + watch paths |
| GET | `/open?path=...` | Open file in Explorer |
| GET | `/docs` | Swagger UI |

## ⚙️ Configuration

Edit `app/config.py` to add custom watch paths:
```python
WATCH_PATHS = [
    r"D:\Projects",
    r"C:\Users\You\Documents",
]
```

## 📊 Performance

- ⚡ Search: <100ms (FAISS)
- 📝 Indexing: ~10 files/sec
- 💾 Memory: ~500MB (all-MiniLM-L6-v2)
- 🔄 Real-time updates (watchdog)

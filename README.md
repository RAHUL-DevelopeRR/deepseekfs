# DeepSeekFS 🔍

**Elite Semantic File Search Engine — Google Desktop / Spotlight level**

## 🚀 Quick Start

```bash
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python run.py
```

That's it. The app:
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

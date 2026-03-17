# DeepSeekFS 🔍

**Elite File Search Engine with Semantic AI + Time-Based Ranking**

Google Desktop / Spotlight level system. Built with:
- 🧠 Sentence Transformers (semantic understanding)
- ⚡ FAISS (vector search)
- 📂 Watchdog (file monitoring)
- 🔗 FastAPI (backend)
- 🎨 PyWebView (UI)

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create Initial Index
```bash
python -m app.scripts.initial_index --path "C:\Users\YourName\Documents"
```

### 3. Run the System
```bash
python run.py
```

Then open your browser to `http://localhost:8000/ui`

## 📁 Architecture

```
┌─────────────────────┐
│   PyWebView UI      │  ← Search interface
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   FastAPI Backend   │  ← /search, /index, /health
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Semantic Search    │  ← FAISS + Ranking
│  Time Intelligence  │  ← "last week", "recent"
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  FAISS Index        │  ← Vector database
│  Metadata Store     │  ← File info
└─────────────────────┘
```

## 🔧 Configuration

Edit `app/config.py`:
```python
WATCH_PATHS = [
    r"C:\Users\YourName\Documents",
    r"C:\Users\YourName\Downloads",
]
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast + accurate
FAISS_INDEX_PATH = "storage/faiss_index"
```

## 🧠 How It Works

### Ranking Function
```
final_score = 0.6 * semantic_similarity + 
              0.25 * time_score + 
              0.15 * frequency_score
```

### Query Examples
```
"invoice from last week"  → semantic + time
"recent python projects"  → recency boost
"budget spreadsheet"      → pure semantic
```

## 📊 Performance

- ⚡ Search: <100ms (FAISS)
- 📝 Indexing: ~10 files/sec
- 💾 Memory: ~500MB (all-MiniLM-L6-v2)
- 🔄 Real-time updates (watchdog)

## 🛣️ Roadmap

- [ ] Windows Context Menu Integration
- [ ] Global Hotkey (Ctrl+Space)
- [ ] Advanced filters (size, type, date range)
- [ ] Query suggestions
- [ ] Batch operations
- [ ] Cloud sync

## 🧪 Testing

```bash
pytest tests/
```

## 📝 License

MIT

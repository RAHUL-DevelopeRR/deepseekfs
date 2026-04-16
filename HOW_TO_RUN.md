# How to Run Neuron Desktop (v5.0)

## Prerequisites
- Python 3.9 or newer
- Windows / macOS / Linux
- ~2 GB RAM free

---

## 1. Clone the repo

```bash
git clone https://github.com/RAHUL-DevelopeRR/deepseekfs
cd deepseekfs
```

> The desktop code lives on `main`. No branch switching required.

---

## 2. Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements-desktop.txt
```

> First install downloads the `all-MiniLM-L6-v2` sentence-transformer model
> (~90 MB). Subsequent runs use the local cache — fully offline.

---

## 4. Run the app

```bash
python run_desktop.py
```

What happens:

| Step | What you see |
|------|--------------|
| 1 | Window opens immediately |
| 2 | Status bar: “Scanning your files in the background…” |
| 3 | Progress bar fills as files are indexed |
| 4 | Status bar: “✅ Ready — N files in index” |
| 5 | Search button turns blue — you can now search |

You can type a query while indexing is still running — the UI never freezes.

---

## 5. Search

- Type anything in the search box and press **Enter** (or click **🔍 Search**).
- **Double-click** any result row to open the file in your OS default viewer.
- Click **📁 Add Folder** to index an extra directory on the fly.

---

## 6. Build a standalone Windows .exe

```bat
build_exe.bat
```

Output: `dist\Neuron\Neuron.exe` (or `dist\DeepSeekFS\DeepSeekFS.exe` if using
`build_exe.bat` directly).

Distribute the entire `dist\Neuron\` folder. No Python installation
required on the target machine.

For the official Neuron installer (Inno Setup), see `README.md → Building the Installer`.

---

## Customising watched folders

Add or remove folders using the **⚙ Settings** panel inside the running app
(gear icon), or edit `storage/user_config.json` directly.

You can also hard-code paths in `app/config.py` for development:

```python
# Hard-code your own paths instead of the auto-detected ones:
WATCH_PATHS = [
    r"C:\Users\Rahul\Documents",
    r"D:\Projects",
]
```

Or use the **📁 Add Folder** button in the UI at runtime.

---

## Legacy web mode

`python run.py` starts the original FastAPI + pywebview web-mode server.
This requires `requirements.txt` (not `requirements-desktop.txt`) and is
kept for reference only. Desktop users should always use `run_desktop.py`.

---

## Troubleshooting
|---------|-----|
| `ModuleNotFoundError: PyQt6` | `pip install PyQt6` |
| Progress bar stuck at 0% | Check that WATCH_PATHS exist on your machine |
| Search returns no results | Wait for “✅ Ready” before searching |
| Window closes but app still in tray | Right-click tray icon → Quit |
| `.exe` build fails | Run `pip install pyinstaller` first |

---

## Notes

- FAISS index is stored in `storage/faiss_index/` and reused across runs.
- Closing the window **minimises to the system tray**; use tray → Quit to exit.

# Migrating from DeepSeekFS v1.0 → v2.0 (Desktop)

## What Changed

### Removed
- Browser-based UI dependency
- Need to keep a terminal open

### Added
- `run_desktop.py` — native PyQt6 window
- `services_desktop.py` — clean service API
- `requirements-desktop.txt` — PyQt6 + PyInstaller
- `build_exe.bat` — one-click Windows builder

### Unchanged
- All `core/` modules (zero breaking changes)
- All `services/` modules
- `.env` configuration
- `run.py` web mode (still fully functional)

## Migration Steps

```bash
git pull origin desktop-v2
pip install -r requirements-desktop.txt
python run_desktop.py
```

## Rollback

If anything goes wrong, simply run the original:

```bash
python run.py
```

No data or index files are affected.

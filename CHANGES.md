## v4.6.0 — Bug Fix Release

### Fixed
1. **Search Results Not Showing** — `SemanticSearch` now reuses the loaded index
   singleton instead of instantiating a fresh model on every query. Added
   `adjustSize()` + `viewport().update()` after result card insertion so cards
   render visibly in the scroll area. Added "Still indexing…" guard.
2. **~3 Minute Startup Delay** — `QSplashScreen` with Neuron logo now shows
   immediately after `QApplication` is created, before the heavy `DesktopService`
   init. Users see instant feedback.
3. **Transparent neuron_circular Icon** — All uses of `neuron_circular.png` now
   composite the logo onto a white circle background using QPainter + QPainterPath
   clip before setting as tray icon or splash.
4. **Installer Wizard Logo** — `neuron_installer.iss` now sets
   `WizardSmallImageFile=assets\neuron_circular_white.bmp` for the top-right
   corner logo. ImageMagick conversion command documented in `.iss`.
5. **Hotkeys Unreliable** — Replaced raw pointer arithmetic in `HotkeyFilter`
   with a proper `ctypes.Structure` MSG struct. Added 500ms retry for
   `RegisterHotKey` on failure.
6. **Emoji Icons Replaced** — All emoji in `ICON_MAP`, search bar, settings, and
   close buttons replaced with Lucide SVG icons rendered via `QSvgRenderer`.
   New module `ui/icons.py` centralises all icon rendering.

## v4.5.0 — Memory OS Release

### Added
- "Today's Activity" card with daily stats and streak indicator
- Activity Search (`@` prefix mode) with session grouping
- "Memory Lane" button in main panel
- Circular "HeiNeuron" DNA logo branding

## v4.3.0

### Fixed
- PyInstaller launcher fix (DETACHED_PROCESS)
- Activity logger hardening
- Top-level crash guard
## v5.0.0 - Crash-safe Indexing Release

### Fixed
1. **Startup Crash** - resolved merge-conflict markers in
   `core/embeddings/embedder.py` that made the app fail before indexing.
2. **Index Wiped on Watch-path Changes** - `StartupIndexer` and
   `DesktopService.run_indexing()` now keep the existing SQLite/FAISS index and
   scan current folders incrementally when watch roots change.
3. **Watch-path Detection** - Windows profile and OneDrive folders are now
   resolved more robustly, with a home-folder fallback when no content roots are
   found.
4. **Embedding Dependency Robustness** - `sentence-transformers` is updated to
   5.3.0, TensorFlow/Flax imports are disabled for the embedding stack, and a
   deterministic fallback embedder keeps indexing/search alive if MiniLM cannot
   load.
5. **Parser Compatibility** - restored `extract_text()` as a compatibility
   wrapper around `FileParser.parse()`.

### Verified
- Rebuilt the local runtime index: 800 files indexed, SQLite and FAISS counts
  match.
- Desktop service starts cleanly and returns search results.
- Added a regression test for watch-path changes preserving the index.
- `python -m pytest tests -q` passes.

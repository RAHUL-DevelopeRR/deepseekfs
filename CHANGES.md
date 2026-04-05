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

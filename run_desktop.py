"""
Neuron – Desktop Entry Point (v4.7.1)
======================================
Bootstraps the PyQt6 application:
  - Pre-loads torch DLLs when running as frozen exe
  - Shows a splash screen while DesktopService loads
  - Registers global hotkey (Shift+Space)
  - Launches SpotlightPanel (the real UI in ui/spotlight_panel.py)

Usage:
    python run_desktop.py
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════
# MUST BE FIRST — Pre-load ALL PyTorch DLLs before any imports
# ═══════════════════════════════════════════════════════════════
import os, sys, glob, ctypes

# When frozen by PyInstaller, resolve the _MEIPASS temp dir
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _meipass = sys._MEIPASS
    _torch_lib = os.path.join(_meipass, 'torch', 'lib')

    for _p in [_torch_lib, _meipass]:
        if os.path.isdir(_p):
            try:
                os.add_dll_directory(_p)
            except OSError:
                pass

    os.environ['PATH'] = _torch_lib + ';' + _meipass + ';' + os.environ.get('PATH', '')

    _load_order = [
        'c10.dll', 'libiomp5md.dll', 'libiompstubs5md.dll',
        'uv.dll', 'shm.dll', 'torch_global_deps.dll',
        'torch.dll', 'torch_cpu.dll', 'torch_python.dll',
    ]
    _kernel32 = ctypes.WinDLL('kernel32.dll')
    _kernel32.LoadLibraryW.restype = ctypes.c_void_p
    _kernel32.SetDllDirectoryW(_torch_lib)

    for _dll_name in _load_order:
        _dll_path = os.path.join(_torch_lib, _dll_name)
        if os.path.exists(_dll_path):
            _kernel32.LoadLibraryW(_dll_path)

    for _dll_path in glob.glob(os.path.join(_torch_lib, '*.dll')):
        _kernel32.LoadLibraryW(_dll_path)
# ═══════════════════════════════════════════════════════════════

import ctypes
import ctypes.wintypes
import platform
import time
from pathlib import Path

# ── Project root on sys.path ─────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ── Core imports (must happen BEFORE PyQt6) ───────────────────
import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap


# ── Hotkey constants ──────────────────────────────────────────
HOTKEY_ID = 0xBFFF
MOD_SHIFT = 0x0004
VK_SPACE  = 0x20


# ─────────────────────────────────────────────────────────────
# Helpers used by ui/spotlight_panel.py
# ─────────────────────────────────────────────────────────────
def make_white_bg_icon(path: str, size: int = 64) -> QPixmap:
    """Returns a QPixmap with neuron_circular.png on a white circle background."""
    base = QPixmap(size, size)
    base.fill(QColor("white"))
    overlay = QPixmap(path)
    if overlay.isNull():
        return base
    overlay = overlay.scaled(size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(base)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, overlay)
    painter.end()
    return base


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main():
    # ── 1. App object FIRST ──
    app = QApplication(sys.argv)
    app.setApplicationName("Neuron")
    app.setApplicationVersion("4.7.1")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    # ── 2. Splash screen ──
    _assets = Path(__file__).resolve().parent / "assets"
    _splash_path = str(_assets / "neuron_circular.png")
    if Path(_splash_path).exists():
        splash_pix = make_white_bg_icon(_splash_path, 256)
    else:
        splash_pix = QPixmap(256, 256)
        splash_pix.fill(QColor("white"))
    splash = QSplashScreen(splash_pix,
        Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
    splash.showMessage("Neuron is loading…",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#333333"))
    splash.show()
    app.processEvents()

    # ── 3. Cleanup handlers ──
    import atexit, signal
    def _cleanup():
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception as e:
            logger.error(f"Hotkey cleanup failed: {e}")
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, lambda *_: (_cleanup(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), sys.exit(0)))

    # ── 4. Create service (heavy — loads AI model in background) ──
    service = DesktopService()

    # ── 5. Build the main panel (from ui/spotlight_panel.py) ──
    from ui.spotlight_panel import SpotlightPanel, HotkeyFilter

    panel = SpotlightPanel(service)

    # ── 6. Poll until service is ready, then close splash ──
    def _check_ready():
        if service._ready.is_set():
            splash.finish(panel)
        else:
            QTimer.singleShot(300, _check_ready)
    QTimer.singleShot(300, _check_ready)

    # ── 7. Register global hotkey ──
    hotkey_ok = False
    event_filter = None
    if platform.system() == "Windows":
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        time.sleep(0.05)

        hotkey_ok = ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_SHIFT, VK_SPACE
        )
        if hotkey_ok:
            logger.info("Global hotkey registered: Shift+Space")
        else:
            MOD_CTRL = 0x0002
            hotkey_ok = ctypes.windll.user32.RegisterHotKey(
                None, HOTKEY_ID, MOD_CTRL, VK_SPACE
            )
            if hotkey_ok:
                logger.info("Fallback hotkey registered: Ctrl+Space")
            else:
                logger.warning("All hotkey registrations failed")

        if hotkey_ok:
            event_filter = HotkeyFilter(panel.toggle_panel)
            app.installNativeEventFilter(event_filter)

        # Retry once after 500ms
        if not hotkey_ok:
            def _retry_hotkey():
                nonlocal hotkey_ok, event_filter
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
                ok = ctypes.windll.user32.RegisterHotKey(
                    None, HOTKEY_ID, MOD_SHIFT, VK_SPACE
                )
                if ok:
                    logger.info("Hotkey registered on retry")
                    event_filter = HotkeyFilter(panel.toggle_panel)
                    app.installNativeEventFilter(event_filter)
                    hotkey_ok = True
            QTimer.singleShot(500, _retry_hotkey)

    # Show panel on startup
    panel.toggle_panel()

    ret = app.exec()

    if hotkey_ok:
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    sys.exit(ret)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        crash_msg = traceback.format_exc()
        try:
            crash_log = Path(__file__).resolve().parent / "storage" / "crash.log"
            crash_log.parent.mkdir(parents=True, exist_ok=True)
            with open(crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Crash at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(crash_msg)
        except Exception:
            pass
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Neuron failed to start:\n\n{str(exc)[:300]}\n\nCheck storage/crash.log for details.",
                "Neuron — Startup Error",
                0x10,
            )
        except Exception:
            print(crash_msg, file=sys.stderr)
        sys.exit(1)

"""
DeepSeekFS – Desktop Entry Point (v3.0  Start-Menu Style)
==========================================================
Windows 11 Start Menu–inspired floating search panel.
• Shift+Space  → toggle panel  (system-wide hotkey)
• Click outside → auto-hide
• Translucent acrylic/Mica blur-behind
• Card-based search results

Usage:
    python run_desktop.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import sys
import platform
import struct
import subprocess
from pathlib import Path
from typing import List

# Make sure project root is on sys.path regardless of CWD
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ── IMPORTANT: Import core/torch modules BEFORE PyQt6 ────────────────────────
import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QScrollArea, QFrame,
    QSystemTrayIcon, QMenu,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
    QAbstractNativeEventFilter, QByteArray,
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPainterPath,
    QBrush, QPen, QFontDatabase, QGuiApplication,
    QCursor,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PANEL_WIDTH  = 640
PANEL_HEIGHT = 700
CORNER_RADIUS = 12
TASKBAR_OFFSET = 60          # pixels above the bottom of the screen
HOTKEY_ID = 0xBFFF           # unique id for RegisterHotKey
MOD_SHIFT = 0x0004
VK_SPACE  = 0x20
WM_HOTKEY = 0x0312


# ─────────────────────────────────────────────────────────────────────────────
# Win32 hotkey native event filter
# ─────────────────────────────────────────────────────────────────────────────
class HotkeyFilter(QAbstractNativeEventFilter):
    """Intercept WM_HOTKEY from the Windows message queue."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type: QByteArray | bytes, message):
        if event_type == b"windows_generic_MSG" or event_type == b"windows_dispatcher_MSG":
            # message is a sip.voidptr wrapping a MSG*
            # MSG: HWND(8) + UINT(4) + WPARAM(8) + LPARAM(8) ...  on 64-bit
            try:
                msg_ptr = int(message)
                # Offsets: HWND=0(8), message=8(4), wParam=16(8)
                msg_id = ctypes.c_uint.from_address(msg_ptr + 8).value
                if msg_id == WM_HOTKEY:
                    wparam = ctypes.c_ulonglong.from_address(msg_ptr + 16).value
                    if wparam == HOTKEY_ID:
                        self._callback()
                        return True, 0
            except Exception:
                pass
        return False, 0


# ─────────────────────────────────────────────────────────────────────────────
# Background worker: initial indexing
# ─────────────────────────────────────────────────────────────────────────────
class IndexThread(QThread):
    status   = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int)

    def __init__(self, service: DesktopService):
        super().__init__()
        self._svc = service

    def run(self):
        try:
            total = self._svc.run_indexing(
                on_status=self.status.emit,
                on_progress=self.progress.emit,
            )
            self.finished.emit(total)
        except Exception as exc:
            logger.error(f"IndexThread error: {exc}")
            self.status.emit(f"⚠️  Indexing error — {exc}")
            self.finished.emit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Background worker: search
# ─────────────────────────────────────────────────────────────────────────────
class SearchThread(QThread):
    results = pyqtSignal(list)
    error   = pyqtSignal(str)

    def __init__(self, service: DesktopService, query: str, top_k: int = 15):
        super().__init__()
        self._svc   = service
        self._query = query
        self._top_k = top_k

    def run(self):
        try:
            hits = self._svc.search(self._query, self._top_k)
            self.results.emit(hits)
        except Exception as exc:
            logger.error(f"SearchThread error: {exc}")
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Result card widget
# ─────────────────────────────────────────────────────────────────────────────
class ResultCard(QFrame):
    """A single search-result card styled like a Windows 11 list item."""

    clicked = pyqtSignal(str)   # emits file path

    # ── file-type icons ────────────────────────────────────────────────────
    _ICONS = {
        ".pdf": "📄", ".docx": "📝", ".doc": "📝", ".txt": "📃",
        ".py": "🐍", ".js": "⚡", ".json": "🔧", ".csv": "📊",
        ".xlsx": "📊", ".xls": "📊", ".pptx": "📽️", ".html": "🌐",
        ".md": "📑", ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬",
        ".mov": "🎬", ".wmv": "🎬", ".flv": "🎬", ".webm": "🎬",
    }

    def __init__(self, hit: dict, rank: int, parent=None):
        super().__init__(parent)
        self._path = hit.get("path", "")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("resultCard")

        ext  = hit.get("extension", Path(self._path).suffix).lower()
        icon = self._ICONS.get(ext, "📁")
        name = hit.get("name", Path(self._path).name)
        score = hit.get("combined_score", hit.get("score", 0.0))
        semantic = hit.get("semantic_score", 0.0)
        time_s = hit.get("time_score", 0.0)

        # ── layout ────────────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(12)

        # icon
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent;")
        root.addWidget(icon_lbl)

        # text column
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("cardName")
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.95); background: transparent;"
        )
        text_col.addWidget(name_lbl)

        # show shortened path
        path_display = self._path
        try:
            home = str(Path.home())
            if path_display.startswith(home):
                path_display = "~" + path_display[len(home):]
        except Exception:
            pass
        path_lbl = QLabel(path_display)
        path_lbl.setObjectName("cardPath")
        path_lbl.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.40); background: transparent;"
        )
        path_lbl.setMaximumWidth(380)
        text_col.addWidget(path_lbl)

        root.addLayout(text_col, 1)

        # score badge
        score_pct = int(score * 100)
        badge_color = (
            "#4CC764" if score >= 0.75 else
            "#FFB940" if score >= 0.50 else
            "#FF6B6B"
        )
        score_lbl = QLabel(f"{score_pct}%")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_lbl.setFixedSize(48, 26)
        score_lbl.setStyleSheet(f"""
            font-size: 12px; font-weight: 700;
            color: {badge_color};
            background: rgba(255,255,255,0.06);
            border: 1px solid {badge_color}40;
            border-radius: 6px;
        """)
        root.addWidget(score_lbl)

        # extension badge
        ext_lbl = QLabel(ext.upper().replace(".", ""))
        ext_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_lbl.setFixedSize(42, 26)
        ext_lbl.setStyleSheet("""
            font-size: 10px; font-weight: 700;
            color: rgba(120,170,255,0.90);
            background: rgba(0,120,212,0.15);
            border: 1px solid rgba(0,120,212,0.25);
            border-radius: 6px;
        """)
        root.addWidget(ext_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Main panel (Start-menu style)
# ─────────────────────────────────────────────────────────────────────────────
class SearchPanel(QWidget):
    """
    Frameless, translucent overlay panel — appears/disappears like the
    Windows 11 Start Menu.
    """

    def __init__(self, service: DesktopService):
        super().__init__()
        self._svc = service
        self._idx_thread: IndexThread | None = None
        self._srch_thread: SearchThread | None = None
        self._indexed_count = 0
        self._visible = False

        # ── Window flags: frameless tool window, always on top ────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)

        # ── Build UI ─────────────────────────────────────────────────────
        self._build_ui()
        self._build_tray()

        # NOTE: QGraphicsDropShadowEffect removed — it is incompatible
        # with WA_TranslucentBackground and causes UpdateLayeredWindow errors.

        # ── Fade animation ───────────────────────────────────────────────
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(150)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── Start indexing ───────────────────────────────────────────────
        self._kick_indexing()

    # ── Paint: fully transparent so DWM acrylic blur shows through ─────
    def paintEvent(self, event):
        # Do NOT paint any opaque fill — the DWM acrylic/Mica backdrop
        # IS the background.  We only draw a subtle rounded border.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            1.0, 1.0,
            float(self.width()) - 2.0, float(self.height()) - 2.0,
            CORNER_RADIUS, CORNER_RADIUS,
        )
        # Subtle 1px border only
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.drawPath(path)
        painter.end()

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 22, 20, 16)
        root.setSpacing(0)

        # ── Search bar ───────────────────────────────────────────────────
        search_container = QFrame()
        search_container.setObjectName("searchContainer")
        search_container.setStyleSheet("""
            #searchContainer {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 10px;
            }
            #searchContainer:focus-within {
                border-color: rgba(0,120,212,0.60);
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(14, 0, 14, 0)
        search_layout.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 16px; color: rgba(255,255,255,0.45); background: transparent;")
        search_icon.setFixedWidth(24)
        search_layout.addWidget(search_icon)

        self.inp_query = QLineEdit()
        self.inp_query.setPlaceholderText("Search for files, documents, and projects…")
        self.inp_query.setObjectName("searchInput")
        self.inp_query.setStyleSheet("""
            #searchInput {
                border: none;
                background: transparent;
                color: rgba(255,255,255,0.92);
                font-size: 14px;
                padding: 12px 0;
                selection-background-color: rgba(0,120,212,0.40);
            }
            #searchInput::placeholder {
                color: rgba(255,255,255,0.35);
            }
        """)
        self.inp_query.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.inp_query, 1)

        root.addWidget(search_container)
        root.addSpacing(14)

        # ── Divider line ─────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(divider)
        root.addSpacing(10)

        # ── Index status label ───────────────────────────────────────────
        self.lbl_status = QLabel("⏳  Indexing your files…")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setStyleSheet("""
            #statusLabel {
                font-size: 12px;
                color: rgba(255,255,255,0.45);
                background: transparent;
                padding: 0 4px;
            }
        """)
        root.addWidget(self.lbl_status)
        root.addSpacing(8)

        # ── Scrollable results area ──────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0;
            }
        """)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch()

        self.scroll.setWidget(self.results_widget)
        root.addWidget(self.scroll, 1)

        # ── Welcome / empty state ────────────────────────────────────────
        self.lbl_empty = QLabel("Type a query above to search your files")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("""
            font-size: 13px;
            color: rgba(255,255,255,0.25);
            padding: 60px 0;
            background: transparent;
        """)

        # ── Bottom bar ───────────────────────────────────────────────────
        root.addSpacing(8)
        bottom_divider = QFrame()
        bottom_divider.setFixedHeight(1)
        bottom_divider.setStyleSheet("background: rgba(255,255,255,0.06);")
        root.addWidget(bottom_divider)
        root.addSpacing(6)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)

        self.lbl_footer = QLabel("DeepSeekFS")
        self.lbl_footer.setStyleSheet("""
            font-size: 11px; font-weight: 600;
            color: rgba(255,255,255,0.30);
            background: transparent;
        """)
        bottom.addWidget(self.lbl_footer)

        bottom.addStretch()

        hint = QLabel("Shift+Space to toggle  •  Esc to hide")
        hint.setStyleSheet("""
            font-size: 11px;
            color: rgba(255,255,255,0.20);
            background: transparent;
        """)
        bottom.addWidget(hint)

        root.addLayout(bottom)

        # Show the empty-state on first load
        self._show_empty_state()

    def _show_empty_state(self):
        """Clear results and show welcome text."""
        self._clear_results()
        self.results_layout.insertWidget(0, self.lbl_empty)
        self.lbl_empty.show()

    def _clear_results(self):
        """Remove all result cards."""
        while self.results_layout.count() > 0:
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── Result card styling (applied to all cards via parent stylesheet) ──
    _CARD_STYLE = """
        #resultCard {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 8px;
        }
        #resultCard:hover {
            background: rgba(255,255,255,0.08);
            border-color: rgba(0,120,212,0.30);
        }
    """

    # ── System tray ──────────────────────────────────────────────────────
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        menu = QMenu()
        show_action = menu.addAction("🔍  Show   (Shift+Space)")
        show_action.triggered.connect(self.toggle_panel)
        menu.addSeparator()
        quit_action = menu.addAction("❌  Quit DeepSeekFS")
        quit_action.triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.setToolTip("DeepSeekFS — Shift+Space to search")
        self._tray.show()

    # ── Indexing ─────────────────────────────────────────────────────────
    def _kick_indexing(self):
        self.lbl_status.setText("⏳  Indexing your files…")
        self._idx_thread = IndexThread(self._svc)
        self._idx_thread.status.connect(self._on_index_status)
        self._idx_thread.progress.connect(self._on_index_progress)
        self._idx_thread.finished.connect(self._on_index_done)
        self._idx_thread.start()

    def _on_index_status(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_index_progress(self, done: int, total: int):
        if total > 0:
            pct = min(int(done / total * 100), 99)
            self.lbl_status.setText(f"⏳  Indexing… {done}/{total}  ({pct}%)")

    def _on_index_done(self, new_files: int):
        self._indexed_count = self._svc.total_indexed()
        self.lbl_status.setText(
            f"📄 {self._indexed_count:,} files indexed  •  {new_files} new"
        )

    # ── Search ───────────────────────────────────────────────────────────
    def _on_search(self):
        query = self.inp_query.text().strip()
        if not query:
            return
        if self._indexed_count == 0:
            self.lbl_status.setText("⏳  Indexing still in progress — try again shortly")
            return

        self.lbl_status.setText(f"🔍  Searching '{query}'…")
        self._clear_results()

        self._srch_thread = SearchThread(self._svc, query)
        self._srch_thread.results.connect(self._on_results)
        self._srch_thread.error.connect(
            lambda e: self.lbl_status.setText(f"⚠️  Search error: {e}")
        )
        self._srch_thread.start()

    def _on_results(self, hits: list):
        self._clear_results()

        if not hits:
            self.lbl_status.setText("No results found")
            self._show_empty_state()
            self.lbl_empty.setText("No results found — try a different query")
            return

        self.setStyleSheet(self._CARD_STYLE)

        for rank, hit in enumerate(hits):
            card = ResultCard(hit, rank, parent=self.results_widget)
            card.clicked.connect(self._open_file)
            self.results_layout.insertWidget(rank, card)

        # Add stretch at end
        self.results_layout.addStretch()

        n = len(hits)
        q = self.inp_query.text().strip()
        self.lbl_status.setText(
            f"✅  {n} result{'s' if n != 1 else ''} for '{q}'"
        )

    # ── Open file ────────────────────────────────────────────────────────
    def _open_file(self, path: str):
        if not path or not Path(path).exists():
            self.lbl_status.setText(f"⚠️  File not found: {path}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            # Hide panel after opening (like Start Menu)
            self._hide_panel()
        except Exception as exc:
            self.lbl_status.setText(f"⚠️  Open failed: {exc}")

    # ── Show / hide / toggle ─────────────────────────────────────────────
    def toggle_panel(self):
        if self._visible:
            self._hide_panel()
        else:
            self._show_panel()

    def _show_panel(self):
        # Position: centered horizontally, above the taskbar
        screen = QGuiApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - PANEL_WIDTH) // 2
            y = geom.y() + geom.height() - PANEL_HEIGHT - TASKBAR_OFFSET
            self.move(x, y)

        self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.inp_query.setFocus()
        self.inp_query.selectAll()

        # Apply acrylic AFTER the window is mapped
        if platform.system() == "Windows":
            QTimer.singleShot(30, self._apply_acrylic)

        # Fade in
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._visible = True

    def _hide_panel(self):
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._on_fade_out_done)
        self._fade.start()
        self._visible = False

    def _on_fade_out_done(self):
        self.hide()
        try:
            self._fade.finished.disconnect(self._on_fade_out_done)
        except Exception:
            pass

    # ── Click-away dismiss ───────────────────────────────────────────────
    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == event.Type.ActivationChange
                and not self.isActiveWindow()
                and self._visible):
            # Small delay to avoid conflicts with tray menu interactions
            QTimer.singleShot(100, self._deactivation_check)

    def _deactivation_check(self):
        if not self.isActiveWindow() and self._visible:
            self._hide_panel()

    # ── Escape key ───────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._hide_panel()
        else:
            super().keyPressEvent(event)

    # ── Tray events ──────────────────────────────────────────────────────
    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_panel()

    def _quit(self):
        # Unregister the hotkey
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        self._tray.hide()
        QApplication.quit()

    # ── Windows DWM Acrylic ──────────────────────────────────────────────
    def _apply_acrylic(self):
        """Apply acrylic/Mica blur-behind using DWM."""
        try:
            hwnd = int(self.winId())
            self._enable_acrylic(hwnd)
        except Exception as exc:
            logger.warning(f"Acrylic effect unavailable: {exc}")

    @staticmethod
    def _enable_acrylic(hwnd: int):
        """
        Enable the Windows 10/11 acrylic blur-behind effect.
        For frameless windows, we must extend the DWM frame into the
        client area first, then request a backdrop type.
        """
        dwm = ctypes.windll.dwmapi

        # ── Step 1: Extend DWM frame into entire client area ──────────────
        # This is REQUIRED for Mica / Acrylic to work on frameless windows.
        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth",    ctypes.c_int),
                ("cxRightWidth",   ctypes.c_int),
                ("cyTopHeight",    ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        margins = MARGINS(-1, -1, -1, -1)   # -1 = extend into full client
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        # ── Step 2: Dark mode ─────────────────────────────────────────────
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        # ── Step 3: Rounded corners (Win 11) ──────────────────────────────
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        val = ctypes.c_int(2)  # DWMWCP_ROUND
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        # ── Step 4: Request backdrop — Acrylic (3) preferred over Mica ────
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        for backdrop in (3, 4, 2):     # Acrylic → MicaAlt → Mica
            val = ctypes.c_int(backdrop)
            hr = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(val), ctypes.sizeof(val),
            )
            if hr == 0:
                logger.info(f"DWM backdrop type {backdrop} applied successfully")
                return

        # ── Fallback: Win 10 SetWindowCompositionAttribute ────────────────
        logger.info("Using Win10 SetWindowCompositionAttribute fallback")

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState",   ctypes.c_int),
                ("AccentFlags",   ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId",   ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute",  ctypes.c_int),
                ("Data",       ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_uint),
            ]

        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        WCA_ACCENT_POLICY = 19
        # ABGR tint: 0x64_202020 → dark grey at ~40% opacity (glass-like)
        accent = ACCENT_POLICY(
            ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, 0x64202020, 0
        )
        data = WINDOWCOMPOSITIONATTDATA(
            WCA_ACCENT_POLICY,
            ctypes.pointer(accent),
            ctypes.sizeof(accent),
        )
        ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeekFS")
    app.setApplicationVersion("3.0.0")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)    # keep running in tray

    service = DesktopService()
    panel = SearchPanel(service)

    # ── Register global hotkey: Shift+Space ───────────────────────────────
    hotkey_ok = False
    if platform.system() == "Windows":
        hotkey_ok = ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_SHIFT, VK_SPACE
        )
        if hotkey_ok:
            logger.info("✅ Global hotkey registered: Shift+Space")
            event_filter = HotkeyFilter(panel.toggle_panel)
            app.installNativeEventFilter(event_filter)
        else:
            logger.warning("⚠️  Failed to register Shift+Space hotkey "
                           "(may already be in use)")

    # Show once on first launch, then it lives in the tray
    panel._show_panel()

    ret = app.exec()

    # Cleanup
    if hotkey_ok:
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    sys.exit(ret)


if __name__ == "__main__":
    main()

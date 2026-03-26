"""
DeepSeekFS – Desktop Entry Point (v6.0 — Windows 11 Glass UI)
==============================================================
Frameless frosted-glass search panel inspired by Windows 11 Start Menu.
Shift+Space to toggle.  Zero-X DFS branding.

Features:
  - DWM Mica/Acrylic frosted glass background
  - 300ms debounced search (no Enter needed)
  - Keyboard navigation (↑↓ to navigate, Enter to open, Ctrl+C to copy)
  - File-type colored icons
  - Settings panel with watch path management
  - Access-frequency tracking

Usage:
    python run_desktop.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import sys
import platform
import subprocess
import time
from pathlib import Path
from typing import List

# Project root on sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ── IMPORTANT: Import core/torch modules BEFORE PyQt6 ────────────────────────
import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QScrollArea, QFrame,
    QSystemTrayIcon, QMenu, QFileDialog,
    QSizePolicy, QGraphicsDropShadowEffect,
    QSlider, QPushButton, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
    QAbstractNativeEventFilter, QByteArray,
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPainterPath,
    QBrush, QPen, QFontDatabase, QGuiApplication,
    QCursor, QLinearGradient, QClipboard,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PANEL_WIDTH  = 860
PANEL_HEIGHT = 680
CORNER_RADIUS = 16
TASKBAR_OFFSET = 50
HOTKEY_ID = 0xBFFF
MOD_SHIFT = 0x0004
VK_SPACE  = 0x20
WM_HOTKEY = 0x0312

# ── Glass palette ────────────────────────────────────────────────────────────
GLASS_BG       = "rgba(255, 255, 255, 0.07)"
GLASS_FILL     = QColor(255, 255, 255, 18)
GLASS_BORDER   = "rgba(255, 255, 255, 0.15)"
SEARCH_BG      = "rgba(255, 255, 255, 0.12)"
SEARCH_BORDER  = "rgba(255, 255, 255, 0.25)"
SEARCH_FOCUS   = "rgba(255, 255, 255, 0.5)"
CARD_BG        = "rgba(255, 255, 255, 0.08)"
CARD_HOVER     = "rgba(255, 255, 255, 0.16)"
CARD_SELECTED  = "rgba(255, 255, 255, 0.22)"
CARD_BORDER    = "rgba(255, 255, 255, 0.12)"
TEXT_WHITE     = "rgba(255, 255, 255, 0.95)"
TEXT_DIM       = "rgba(255, 255, 255, 0.55)"
TEXT_MUTED     = "rgba(255, 255, 255, 0.35)"
ACCENT_LEFT    = "rgba(255, 255, 255, 0.7)"


# ── File icon themes ─────────────────────────────────────────────────────────
ICON_MAP = {
    ".py":   ("🐍", "#3572A5"), ".ipynb": ("📓", "#3572A5"),
    ".js":   ("⚡", "#F7DF1E"), ".ts":    ("⚡", "#3178C6"),
    ".jsx":  ("⚡", "#F7DF1E"), ".tsx":   ("⚡", "#3178C6"),
    ".rs":   ("🦀", "#DEA584"), ".go":    ("🐹", "#00ADD8"),
    ".java": ("☕", "#B07219"), ".cpp":   ("⚙️", "#00599C"),
    ".c":    ("⚙️", "#555555"), ".h":     ("⚙️", "#555555"),
    ".cs":   ("🔷", "#178600"), ".rb":    ("💎", "#CC342D"),
    ".php":  ("🐘", "#4F5D95"), ".swift": ("🐦", "#FA7343"),
    ".kt":   ("🟣", "#A97BFF"),
    ".md":   ("📄", "#6B7280"), ".txt":   ("📄", "#6B7280"),
    ".log":  ("📋", "#6B7280"),
    ".pdf":  ("📕", "#E53E3E"),
    ".docx": ("📘", "#2B579A"), ".doc":   ("📘", "#2B579A"),
    ".xlsx": ("📗", "#217346"), ".xls":   ("📗", "#217346"),
    ".csv":  ("📊", "#217346"),
    ".pptx": ("📙", "#D24726"), ".ppt":   ("📙", "#D24726"),
    ".json": ("{}", "#F59E0B"), ".xml":   ("<>", "#F59E0B"),
    ".html": ("🌐", "#E34C26"), ".htm":   ("🌐", "#E34C26"),
    ".css":  ("🎨", "#264DE4"),
    ".mp4":  ("🎬", "#8B5CF6"), ".mkv":   ("🎬", "#8B5CF6"),
    ".avi":  ("🎬", "#8B5CF6"), ".mov":   ("🎬", "#8B5CF6"),
    ".wmv":  ("🎬", "#8B5CF6"), ".flv":   ("🎬", "#8B5CF6"),
    ".webm": ("🎬", "#8B5CF6"),
    ".png":  ("🖼️", "#EC4899"), ".jpg":   ("🖼️", "#EC4899"),
    ".jpeg": ("🖼️", "#EC4899"), ".gif":   ("🖼️", "#EC4899"),
    ".webp": ("🖼️", "#EC4899"),
    ".zip":  ("📦", "#92400E"), ".rar":   ("📦", "#92400E"),
    ".7z":   ("📦", "#92400E"),
    ".exe":  ("⚙️", "#6366F1"), ".msi":   ("⚙️", "#6366F1"),
    ".env":  ("🔧", "#4F46E5"), ".ini":   ("🔧", "#4F46E5"),
    ".toml": ("🔧", "#4F46E5"), ".cfg":   ("🔧", "#4F46E5"),
    ".yaml": ("🔧", "#4F46E5"), ".yml":   ("🔧", "#4F46E5"),
}
DEFAULT_ICON = ("📄", "#9CA3AF")


def get_file_icon(ext: str):
    """Return (emoji, accent_color) for a given file extension."""
    return ICON_MAP.get(ext.lower(), DEFAULT_ICON)


# ─────────────────────────────────────────────────────────────────────────────
# Win32 hotkey native event filter
# ─────────────────────────────────────────────────────────────────────────────
class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type: QByteArray | bytes, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg_ptr = int(message)
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
# Background worker: indexing
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
            self.status.emit(f"Indexing error — {exc}")
            self.finished.emit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Background worker: search
# ─────────────────────────────────────────────────────────────────────────────
class SearchThread(QThread):
    results = pyqtSignal(list)
    error   = pyqtSignal(str)

    def __init__(self, service: DesktopService, query: str, top_k: int = 20):
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
    """A single search result styled as a glass card."""
    clicked = pyqtSignal(str)

    def __init__(self, hit: dict, rank: int, parent=None):
        super().__init__(parent)
        self._path = hit.get("path", "")
        self._selected = False
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        ext = hit.get("extension", Path(self._path).suffix).lower()
        emoji, accent = get_file_icon(ext)
        name = hit.get("name", Path(self._path).name)
        score = hit.get("combined_score", hit.get("score", 0.0))
        ext_label = ext.upper().replace(".", "")

        self._normal_style = f"""
            ResultCard {{
                background: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 10px;
            }}
        """
        self._hover_style = f"""
            ResultCard {{
                background: {CARD_HOVER};
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 10px;
            }}
        """
        self._selected_style = f"""
            ResultCard {{
                background: {CARD_SELECTED};
                border: 1px solid rgba(255,255,255,0.3);
                border-left: 3px solid {ACCENT_LEFT};
                border-radius: 10px;
            }}
        """
        self.setStyleSheet(self._normal_style)

        # ── Layout ────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 16, 8)
        root.setSpacing(12)

        # ── Icon ──────────────────────────────────────────────
        icon_frame = QFrame()
        icon_frame.setFixedSize(40, 40)
        icon_frame.setStyleSheet(f"""
            background: {accent}33;
            border-radius: 8px;
            border: none;
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel(emoji)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 18px; background: transparent;")
        icon_layout.addWidget(icon_lbl)
        root.addWidget(icon_frame)

        # ── Text column ──────────────────────────────────────
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"""
            font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            font-size: 14px; font-weight: 600;
            color: {TEXT_WHITE}; background: transparent;
        """)
        text_col.addWidget(name_lbl)

        # Shorten path
        path_display = self._path
        try:
            home = str(Path.home())
            if path_display.startswith(home):
                path_display = "~" + path_display[len(home):]
        except Exception:
            pass
        path_lbl = QLabel(path_display)
        path_lbl.setStyleSheet(f"""
            font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            font-size: 12px; color: {TEXT_DIM}; background: transparent;
        """)
        path_lbl.setMaximumWidth(480)
        text_col.addWidget(path_lbl)

        root.addLayout(text_col, 1)

        # ── Extension badge ──────────────────────────────────
        ext_lbl = QLabel(ext_label)
        ext_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_lbl.setFixedSize(44, 22)
        ext_lbl.setStyleSheet(f"""
            font-size: 10px; font-weight: 700;
            color: white; background: {accent};
            border-radius: 6px; border: none;
        """)
        root.addWidget(ext_lbl)

        # ── Score pill ───────────────────────────────────────
        score_pct = int(score * 100)
        score_lbl = QLabel(f"{score_pct}%")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_lbl.setFixedSize(42, 22)
        score_lbl.setStyleSheet(f"""
            font-size: 11px; font-weight: 600;
            color: {TEXT_WHITE}; background: rgba(255,255,255,0.15);
            border-radius: 6px; border: none;
        """)
        root.addWidget(score_lbl)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(self._selected_style)
        else:
            self.setStyleSheet(self._normal_style)

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet(self._hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._selected:
            self.setStyleSheet(self._normal_style)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Settings panel widget
# ─────────────────────────────────────────────────────────────────────────────
class SettingsPanel(QFrame):
    """In-window settings overlay."""
    closed = pyqtSignal()
    reindex_requested = pyqtSignal()
    watch_paths_changed = pyqtSignal()

    def __init__(self, service: DesktopService, parent=None):
        super().__init__(parent)
        self._svc = service
        self.setStyleSheet(f"""
            SettingsPanel {{
                background: rgba(30, 30, 30, 0.92);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 14px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Settings")
        title.setStyleSheet(f"""
            font-size: 18px; font-weight: 700;
            color: {TEXT_WHITE}; background: transparent;
        """)
        header.addWidget(title)
        header.addStretch()

        close_btn = QLabel("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            font-size: 16px; color: {TEXT_DIM};
            background: rgba(255,255,255,0.08);
            border-radius: 6px;
        """)
        close_btn.mousePressEvent = lambda e: self.closed.emit()
        header.addWidget(close_btn)
        root.addLayout(header)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: rgba(255,255,255,0.1);")
        root.addWidget(div)

        # Stats
        idx_count = service.total_indexed()
        paths = service.get_watch_paths()
        stats_lbl = QLabel(f"{idx_count:,} files indexed across {len(paths)} directories")
        stats_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_DIM}; background: transparent;")
        root.addWidget(stats_lbl)

        # Watch paths
        paths_label = QLabel("Watch Paths")
        paths_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_WHITE}; background: transparent;")
        root.addWidget(paths_label)

        self._paths_container = QVBoxLayout()
        self._paths_container.setSpacing(4)
        for p in paths:
            self._add_path_row(p, is_default=p in config.get_user_watch_paths())
        root.addLayout(self._paths_container)

        # Add folder button
        add_btn = QPushButton("+ Add Folder")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.1);
                border: 1px dashed rgba(255,255,255,0.25);
                border-radius: 8px;
                color: {TEXT_DIM};
                font-size: 12px; font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.15);
                color: {TEXT_WHITE};
            }}
        """)
        add_btn.clicked.connect(self._on_add_folder)
        root.addWidget(add_btn)

        # Re-index button
        reindex_btn = QPushButton("Re-index Now")
        reindex_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reindex_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 120, 212, 0.6);
                border: none; border-radius: 8px;
                color: white; font-size: 12px; font-weight: 700;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background: rgba(0, 120, 212, 0.8);
            }}
        """)
        reindex_btn.clicked.connect(self._on_reindex)
        root.addWidget(reindex_btn)

        # Top-K slider
        topk_row = QHBoxLayout()
        topk_label = QLabel("Results count")
        topk_label.setStyleSheet(f"font-size: 12px; color: {TEXT_DIM}; background: transparent;")
        topk_row.addWidget(topk_label)

        cfg = service.get_config()
        self._topk_value = QLabel(str(cfg.get("top_k", 20)))
        self._topk_value.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {TEXT_WHITE}; background: transparent;")
        topk_row.addStretch()
        topk_row.addWidget(self._topk_value)
        root.addLayout(topk_row)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(5, 50)
        self._slider.setValue(cfg.get("top_k", 20))
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.1);
                height: 4px; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: rgba(0, 120, 212, 0.8);
                width: 16px; height: 16px;
                margin: -6px 0; border-radius: 8px;
            }}
        """)
        self._slider.valueChanged.connect(lambda v: self._topk_value.setText(str(v)))
        self._slider.valueChanged.connect(self._on_topk_changed)
        root.addWidget(self._slider)

        root.addStretch()

    def _add_path_row(self, path: str, is_default: bool):
        row = QHBoxLayout()
        lbl = QLabel(path)
        lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_DIM}; background: transparent;")
        lbl.setMaximumWidth(550)
        row.addWidget(lbl, 1)

        if not is_default:
            rm_btn = QLabel("✕")
            rm_btn.setFixedSize(22, 22)
            rm_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rm_btn.setStyleSheet(f"""
                font-size: 12px; color: {TEXT_DIM};
                background: rgba(255,255,255,0.08);
                border-radius: 4px;
            """)
            rm_btn.mousePressEvent = lambda e, p=path: self._on_remove_path(p)
            row.addWidget(rm_btn)

        self._paths_container.addLayout(row)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Watch")
        if folder:
            if self._svc.add_watch_path(folder):
                self._add_path_row(folder, is_default=False)
                self.watch_paths_changed.emit()

    def _on_remove_path(self, path: str):
        if self._svc.remove_watch_path(path):
            self.watch_paths_changed.emit()
            self.closed.emit()  # close & reopen to refresh list

    def _on_reindex(self):
        self.reindex_requested.emit()
        self.closed.emit()

    def _on_topk_changed(self, value: int):
        cfg = self._svc.get_config()
        cfg["top_k"] = value
        self._svc.save_config(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Main search panel
# ─────────────────────────────────────────────────────────────────────────────
class SearchPanel(QWidget):
    """Frameless frosted-glass search panel with keyboard navigation."""

    def __init__(self, service: DesktopService):
        super().__init__()
        self._svc = service
        self._idx_thread: IndexThread | None = None
        self._srch_thread: SearchThread | None = None
        self._indexed_count = 0
        self._visible = False
        self._selected_index = -1
        self._result_cards: List[ResultCard] = []
        self._settings_panel: SettingsPanel | None = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._on_debounced_search)
        self._is_indexing = False

        # ── Window flags ─────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)

        # ── Build UI ─────────────────────────────────────────
        self._build_ui()
        self._build_tray()

        # Note: QGraphicsDropShadowEffect removed because it conflicts
        # with WA_TranslucentBackground on Windows (UpdateLayeredWindow error).
        # DWM Mica/Acrylic provides the backdrop effect instead.

        # ── Fade animation ───────────────────────────────────
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── Start indexing ───────────────────────────────────
        self._kick_indexing()

    # ── Paint: frosted glass ─────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            1.0, 1.0,
            float(self.width()) - 2.0, float(self.height()) - 2.0,
            CORNER_RADIUS, CORNER_RADIUS,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(GLASS_FILL))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 255, 255, 38), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()

    # ── UI construction ──────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 14)
        root.setSpacing(0)

        # ── Top bar (search + settings gear) ─────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Search bar
        search_container = QFrame()
        search_container.setFixedHeight(56)
        search_container.setStyleSheet(f"""
            QFrame {{
                background: {SEARCH_BG};
                border: 1px solid {SEARCH_BORDER};
                border-radius: 12px;
            }}
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(18, 0, 18, 0)
        search_layout.setSpacing(12)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"font-size: 18px; color: {TEXT_DIM}; background: transparent;")
        search_icon.setFixedWidth(26)
        search_layout.addWidget(search_icon)

        self.inp_query = QLineEdit()
        self.inp_query.setPlaceholderText("Search your files...")
        self.inp_query.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                color: {TEXT_WHITE};
                font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
                font-size: 18px; font-weight: 400;
                padding: 14px 0;
                selection-background-color: rgba(255,255,255,0.2);
            }}
            QLineEdit::placeholder {{
                color: rgba(255,255,255,0.45);
            }}
        """)
        self.inp_query.textChanged.connect(self._on_text_changed)
        self.inp_query.returnPressed.connect(self._open_selected)
        search_layout.addWidget(self.inp_query, 1)

        top_row.addWidget(search_container, 1)

        # Settings button
        settings_btn = QLabel("⚙")
        settings_btn.setFixedSize(44, 44)
        settings_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
            font-size: 20px; color: {TEXT_DIM};
            background: rgba(255,255,255,0.08);
            border-radius: 10px;
        """)
        settings_btn.mousePressEvent = lambda e: self._toggle_settings()
        top_row.addWidget(settings_btn)

        root.addLayout(top_row)
        root.addSpacing(10)

        # ── Result count / status ────────────────────────────
        self.lbl_result_count = QLabel("")
        self.lbl_result_count.setStyleSheet(f"""
            font-size: 12px; color: rgba(255,255,255,0.5);
            background: transparent; padding: 0 4px;
        """)
        root.addWidget(self.lbl_result_count)
        root.addSpacing(6)

        # ── Divider ──────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(divider)
        root.addSpacing(8)

        # ── Scrollable results ───────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 5px; margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15);
                border-radius: 2px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.3); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; height: 0;
            }}
        """)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch()

        self.scroll.setWidget(self.results_widget)
        root.addWidget(self.scroll, 1)

        # ── Empty state ──────────────────────────────────────
        self.lbl_empty = QLabel("Type to search your files")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setStyleSheet(f"""
            font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            font-size: 14px; color: {TEXT_MUTED};
            padding: 50px 20px; background: transparent;
        """)
        self.results_layout.insertWidget(0, self.lbl_empty)

        # ── Bottom bar ───────────────────────────────────────
        root.addSpacing(8)
        bottom_div = QFrame()
        bottom_div.setFixedHeight(1)
        bottom_div.setStyleSheet("background: rgba(255,255,255,0.06);")
        root.addWidget(bottom_div)
        root.addSpacing(6)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)

        self.lbl_status = QLabel("Zero-X DFS")
        self.lbl_status.setStyleSheet(f"""
            font-size: 11px; font-weight: 500;
            color: {TEXT_MUTED}; background: transparent;
        """)
        bottom.addWidget(self.lbl_status)
        bottom.addStretch()

        hint = QLabel("Shift+Space  ·  ↑↓ navigate  ·  Esc close")
        hint.setStyleSheet(f"""
            font-size: 10px; color: rgba(255,255,255,0.2); background: transparent;
        """)
        bottom.addWidget(hint)

        root.addLayout(bottom)

    def _show_empty_state(self):
        self.lbl_empty.show()

    def _hide_empty_state(self):
        self.lbl_empty.hide()

    def _clear_results(self):
        self._result_cards.clear()
        self._selected_index = -1
        while self.results_layout.count() > 0:
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.lbl_empty:
                w.deleteLater()
        self.results_layout.addWidget(self.lbl_empty)

    # ── Settings panel ───────────────────────────────────────
    def _toggle_settings(self):
        if self._settings_panel and self._settings_panel.isVisible():
            self._settings_panel.hide()
            self._settings_panel.deleteLater()
            self._settings_panel = None
            return

        self._settings_panel = SettingsPanel(self._svc, self)
        self._settings_panel.closed.connect(self._close_settings)
        self._settings_panel.reindex_requested.connect(self._on_reindex)
        self._settings_panel.watch_paths_changed.connect(self._on_watch_paths_changed)
        self._settings_panel.setGeometry(20, 70, PANEL_WIDTH - 40, PANEL_HEIGHT - 100)
        self._settings_panel.show()
        self._settings_panel.raise_()

    def _close_settings(self):
        if self._settings_panel:
            self._settings_panel.hide()
            self._settings_panel.deleteLater()
            self._settings_panel = None

    def _on_reindex(self):
        from services.startup_indexer import StartupIndexer
        si = StartupIndexer()
        si._wipe_index("manual re-index requested")
        self._kick_indexing()

    def _on_watch_paths_changed(self):
        config.WATCH_PATHS = config.UserConfig.get_all_watch_paths()

    # ── System tray ──────────────────────────────────────────
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        menu = QMenu()
        show_action = menu.addAction("Show   (Shift+Space)")
        show_action.triggered.connect(self.toggle_panel)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.setToolTip("Zero-X DFS — Shift+Space to search")
        self._tray.show()

    # ── Indexing ─────────────────────────────────────────────
    def _kick_indexing(self):
        self._is_indexing = True
        self.lbl_status.setText("Zero-X DFS  ·  Indexing…")
        self._idx_thread = IndexThread(self._svc)
        self._idx_thread.status.connect(self._on_index_status)
        self._idx_thread.progress.connect(self._on_index_progress)
        self._idx_thread.finished.connect(self._on_index_done)
        self._idx_thread.start()

    def _on_index_status(self, msg: str):
        self.lbl_status.setText(f"Zero-X DFS  ·  {msg}")

    def _on_index_progress(self, done: int, total: int):
        if total > 0:
            pct = min(int(done / total * 100), 99)
            self.lbl_status.setText(f"Zero-X DFS  ·  Indexing… {pct}%")

    def _on_index_done(self, new_files: int):
        self._is_indexing = False
        self._indexed_count = self._svc.total_indexed()
        self.lbl_status.setText(
            f"Zero-X DFS  ·  {self._indexed_count:,} files indexed"
        )

    # ── Debounced search ─────────────────────────────────────
    def _on_text_changed(self, text: str):
        if text.strip():
            self._debounce_timer.start()
        else:
            self._debounce_timer.stop()
            self._clear_results()
            self._show_empty_state()
            self.lbl_result_count.setText("")

    def _on_debounced_search(self):
        query = self.inp_query.text().strip()
        if not query:
            return
        if self._indexed_count == 0 and not self._is_indexing:
            self.lbl_result_count.setText("Index is empty — waiting for indexing…")
            return

        self.lbl_result_count.setText("Searching…")
        cfg = self._svc.get_config()
        top_k = cfg.get("top_k", 20)

        self._srch_thread = SearchThread(self._svc, query, top_k)
        self._srch_thread.results.connect(self._on_results)
        self._srch_thread.error.connect(
            lambda e: self.lbl_result_count.setText(f"Error: {e}")
        )
        self._srch_thread.start()

    def _on_results(self, hits: list):
        self._clear_results()
        self._hide_empty_state()

        if not hits:
            self.lbl_result_count.setText("No results found")
            self.lbl_empty.setText("No results — try different keywords")
            self._show_empty_state()
            return

        self._result_cards = []
        for rank, hit in enumerate(hits):
            card = ResultCard(hit, rank, parent=self.results_widget)
            card.clicked.connect(self._open_file)
            self.results_layout.insertWidget(rank, card)
            self._result_cards.append(card)

        self.results_layout.addStretch()

        n = len(hits)
        q = self.inp_query.text().strip()
        self.lbl_result_count.setText(f"{n} result{'s' if n != 1 else ''} for \"{q}\"")

        # Auto-select first result
        if self._result_cards:
            self._selected_index = 0
            self._result_cards[0].set_selected(True)

    # ── Open file ────────────────────────────────────────────
    def _open_file(self, path: str):
        if not path or not Path(path).exists():
            self.lbl_result_count.setText(f"File not found: {path}")
            return
        try:
            self._svc.record_file_open(path)
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            self._hide_panel()
        except Exception as exc:
            self.lbl_result_count.setText(f"Open failed: {exc}")

    def _open_selected(self):
        if 0 <= self._selected_index < len(self._result_cards):
            card = self._result_cards[self._selected_index]
            self._open_file(card._path)

    def _copy_selected_path(self):
        if 0 <= self._selected_index < len(self._result_cards):
            path = self._result_cards[self._selected_index]._path
            QApplication.clipboard().setText(path)
            self.lbl_result_count.setText(f"Copied: {path}")

    # ── Keyboard navigation ──────────────────────────────────
    def _move_selection(self, delta: int):
        if not self._result_cards:
            return
        old = self._selected_index
        if old >= 0 and old < len(self._result_cards):
            self._result_cards[old].set_selected(False)

        new = max(0, min(len(self._result_cards) - 1, old + delta))
        self._selected_index = new
        self._result_cards[new].set_selected(True)
        self.scroll.ensureWidgetVisible(self._result_cards[new])

    # ── Show / hide / toggle ─────────────────────────────────
    def toggle_panel(self):
        if self._visible:
            self._hide_panel()
        else:
            self._show_panel()

    def _show_panel(self):
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

        if platform.system() == "Windows":
            QTimer.singleShot(30, self._apply_acrylic)

        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._visible = True

    def _hide_panel(self):
        self._close_settings()
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

    # ── Click-away dismiss ───────────────────────────────────
    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == event.Type.ActivationChange
                and not self.isActiveWindow()
                and self._visible):
            QTimer.singleShot(100, self._deactivation_check)

    def _deactivation_check(self):
        if not self.isActiveWindow() and self._visible:
            self._hide_panel()

    # ── Key events ───────────────────────────────────────────
    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self._hide_panel()
        elif key == Qt.Key.Key_Down:
            self._move_selection(1)
        elif key == Qt.Key.Key_Up:
            self._move_selection(-1)
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._open_selected()
        elif key == Qt.Key.Key_C and mods & Qt.KeyboardModifier.ControlModifier:
            self._copy_selected_path()
        else:
            super().keyPressEvent(event)

    # ── Tray events ──────────────────────────────────────────
    def _on_tray_click(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_panel()

    def _quit(self):
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        self._tray.hide()
        QApplication.quit()

    # ── Windows DWM Mica/Acrylic ─────────────────────────────
    def _apply_acrylic(self):
        try:
            hwnd = int(self.winId())
            self._enable_acrylic(hwnd)
        except Exception as exc:
            logger.warning(f"Acrylic effect unavailable: {exc}")

    @staticmethod
    def _enable_acrylic(hwnd: int):
        dwm = ctypes.windll.dwmapi

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth",    ctypes.c_int),
                ("cxRightWidth",   ctypes.c_int),
                ("cyTopHeight",    ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        margins = MARGINS(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        # Immersive dark mode
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        # Rounded corners
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        val = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        # Mica Alt → Acrylic → Mica
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        for backdrop in (4, 3, 2):
            val = ctypes.c_int(backdrop)
            hr = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(val), ctypes.sizeof(val),
            )
            if hr == 0:
                logger.info(f"DWM backdrop type {backdrop} applied")
                return

        # Win10 fallback
        logger.info("Using Win10 acrylic fallback")

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

        accent = ACCENT_POLICY(4, 2, 0x12000000, 0)
        data = WINDOWCOMPOSITIONATTDATA(
            19, ctypes.pointer(accent), ctypes.sizeof(accent),
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
    app.setApplicationVersion("6.0.0")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)

    service = DesktopService()

    # ── Launch the new full interface window ──────────────────
    from ui.main_window import DeepSeekMainWindow
    main_window = DeepSeekMainWindow()
    main_window.show()

    # ── Keep the Shift+Space search panel overlay ────────────
    panel = SearchPanel(service)

    # Register global hotkey: Shift+Space
    hotkey_ok = False
    if platform.system() == "Windows":
        hotkey_ok = ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_SHIFT, VK_SPACE
        )
        if hotkey_ok:
            logger.info("Global hotkey registered: Shift+Space")
            event_filter = HotkeyFilter(panel.toggle_panel)
            app.installNativeEventFilter(event_filter)
        else:
            logger.warning("Failed to register Shift+Space hotkey")

    ret = app.exec()

    if hotkey_ok:
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    sys.exit(ret)


if __name__ == "__main__":
    main()

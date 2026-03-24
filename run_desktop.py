"""
DeepSeekFS – Desktop Entry Point (v4.0  ChatGPT-Inspired)
==========================================================
Vibrant, premium floating search panel with ChatGPT-like
reasoning display before showing search results.

• Shift+Space  → toggle panel  (system-wide hotkey)
• Click outside → auto-hide
• Translucent acrylic/Mica blur-behind
• "Thinking" reasoning animation
• Card-based search results with content snippets

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
import time
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
    QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
    QAbstractNativeEventFilter, QByteArray,
    QSequentialAnimationGroup,
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPainterPath,
    QBrush, QPen, QFontDatabase, QGuiApplication,
    QCursor, QLinearGradient,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
PANEL_WIDTH  = 720
PANEL_HEIGHT = 780
CORNER_RADIUS = 18
TASKBAR_OFFSET = 50          # pixels above the bottom of the screen
HOTKEY_ID = 0xBFFF           # unique id for RegisterHotKey
MOD_SHIFT = 0x0004
VK_SPACE  = 0x20
WM_HOTKEY = 0x0312

# ── Color Palette ────────────────────────────────────────────────────────────
ACCENT_PRIMARY    = "#10A37F"   # ChatGPT green
ACCENT_SECONDARY  = "#8B5CF6"   # Purple accent
ACCENT_WARM       = "#F59E0B"   # Amber
ACCENT_BLUE       = "#3B82F6"   # Blue
ACCENT_PINK       = "#EC4899"   # Pink
BG_DARK           = "rgba(13, 13, 13, 0.92)"
BG_CARD           = "rgba(25, 25, 28, 0.85)"
BG_CARD_HOVER     = "rgba(40, 40, 48, 0.95)"
TEXT_PRIMARY       = "rgba(255, 255, 255, 0.95)"
TEXT_SECONDARY     = "rgba(255, 255, 255, 0.55)"
TEXT_MUTED         = "rgba(255, 255, 255, 0.30)"
BORDER_SUBTLE      = "rgba(255, 255, 255, 0.08)"
BORDER_ACTIVE      = "rgba(16, 163, 127, 0.6)"


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
# Background worker: search (now also returns reasoning metadata)
# ─────────────────────────────────────────────────────────────────────────────
class SearchThread(QThread):
    results = pyqtSignal(dict)   # emits {"hits": [...], "reasoning": {...}}
    error   = pyqtSignal(str)

    def __init__(self, service: DesktopService, query: str, top_k: int = 20):
        super().__init__()
        self._svc   = service
        self._query = query
        self._top_k = top_k

    def run(self):
        try:
            from core.search.query_parser import extract_intent
            from core.time.scoring import extract_time_target

            t0 = time.time()

            # Step 1: Parse intent
            target_time, cleaned_query = extract_time_target(self._query)
            cleaned_query, target_exts = extract_intent(cleaned_query)

            # Step 2: Execute search
            hits = self._svc.search(self._query, self._top_k)
            elapsed = round((time.time() - t0) * 1000)

            # Step 3: Build reasoning payload
            reasoning = {
                "original_query": self._query,
                "cleaned_query": cleaned_query,
                "target_extensions": target_exts,
                "target_time": target_time,
                "elapsed_ms": elapsed,
                "total_hits": len(hits),
            }

            self.results.emit({"hits": hits, "reasoning": reasoning})
        except Exception as exc:
            logger.error(f"SearchThread error: {exc}")
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Result card widget
# ─────────────────────────────────────────────────────────────────────────────
class ResultCard(QFrame):
    """A single search-result card with vibrant styling."""

    clicked = pyqtSignal(str)   # emits file path

    # ── file-type colors & icons ──────────────────────────────────────────
    _TYPE_THEME = {
        ".pdf":  ("📄", "#EF4444", "PDF"),
        ".docx": ("📝", "#3B82F6", "DOCX"),
        ".doc":  ("📝", "#3B82F6", "DOC"),
        ".txt":  ("📃", "#6B7280", "TXT"),
        ".py":   ("🐍", "#10B981", "PY"),
        ".js":   ("⚡", "#F59E0B", "JS"),
        ".json": ("🔧", "#8B5CF6", "JSON"),
        ".csv":  ("📊", "#06B6D4", "CSV"),
        ".xlsx": ("📊", "#059669", "XLSX"),
        ".xls":  ("📊", "#059669", "XLS"),
        ".pptx": ("📽️", "#F97316", "PPTX"),
        ".ppt":  ("📽️", "#F97316", "PPT"),
        ".html": ("🌐", "#EC4899", "HTML"),
        ".md":   ("📑", "#8B5CF6", "MD"),
        ".mp4":  ("🎬", "#EF4444", "MP4"),
        ".mkv":  ("🎬", "#EF4444", "MKV"),
        ".avi":  ("🎬", "#EF4444", "AVI"),
        ".mov":  ("🎬", "#EF4444", "MOV"),
        ".wmv":  ("🎬", "#EF4444", "WMV"),
        ".flv":  ("🎬", "#EF4444", "FLV"),
        ".webm": ("🎬", "#EF4444", "WEBM"),
    }

    def __init__(self, hit: dict, rank: int, parent=None):
        super().__init__(parent)
        self._path = hit.get("path", "")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("resultCard")

        ext  = hit.get("extension", Path(self._path).suffix).lower()
        theme = self._TYPE_THEME.get(ext, ("📁", "#6B7280", ext.upper().replace(".", "")))
        icon_emoji, type_color, type_label = theme
        name = hit.get("name", Path(self._path).name)
        score = hit.get("combined_score", hit.get("score", 0.0))

        # ── layout ────────────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(14)

        # ── Icon with colored background ──────────────────────────────────
        icon_container = QFrame()
        icon_container.setFixedSize(44, 44)
        icon_container.setStyleSheet(f"""
            background: {type_color}20;
            border-radius: 12px;
            border: 1px solid {type_color}40;
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel(icon_emoji)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
        icon_layout.addWidget(icon_lbl)
        root.addWidget(icon_container)

        # ── Text column ───────────────────────────────────────────────────
        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("cardName")
        name_lbl.setStyleSheet(f"""
            font-size: 13px; font-weight: 700;
            color: {TEXT_PRIMARY};
            background: transparent;
        """)
        text_col.addWidget(name_lbl)

        # Shortened path
        path_display = self._path
        try:
            home = str(Path.home())
            if path_display.startswith(home):
                path_display = "~" + path_display[len(home):]
        except Exception:
            pass
        path_lbl = QLabel(path_display)
        path_lbl.setObjectName("cardPath")
        path_lbl.setStyleSheet(f"""
            font-size: 10px; color: {TEXT_SECONDARY};
            background: transparent;
        """)
        path_lbl.setMaximumWidth(400)
        text_col.addWidget(path_lbl)

        root.addLayout(text_col, 1)

        # ── Score badge (vibrant gradient) ────────────────────────────────
        score_pct = int(score * 100)
        if score >= 0.75:
            badge_bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {ACCENT_PRIMARY}, stop:1 #059669)"
        elif score >= 0.50:
            badge_bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {ACCENT_WARM}, stop:1 #D97706)"
        else:
            badge_bg = f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #EF4444, stop:1 #DC2626)"

        score_lbl = QLabel(f"{score_pct}%")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_lbl.setFixedSize(50, 28)
        score_lbl.setStyleSheet(f"""
            font-size: 12px; font-weight: 800;
            color: white;
            background: {badge_bg};
            border-radius: 8px;
        """)
        root.addWidget(score_lbl)

        # ── Extension pill ────────────────────────────────────────────────
        ext_lbl = QLabel(type_label)
        ext_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_lbl.setFixedSize(48, 28)
        ext_lbl.setStyleSheet(f"""
            font-size: 10px; font-weight: 800;
            color: white;
            background: {type_color};
            border-radius: 8px;
        """)
        root.addWidget(ext_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning card (ChatGPT "thinking" bubble)
# ─────────────────────────────────────────────────────────────────────────────
class ReasoningCard(QFrame):
    """Shows what the AI 'thought' about the query."""

    def __init__(self, reasoning: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("reasoningCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # Header
        header = QLabel("🧠 DeepSeekFS Reasoning")
        header.setStyleSheet(f"""
            font-size: 13px; font-weight: 800;
            color: {ACCENT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(header)

        # Build reasoning text
        lines = []
        original = reasoning.get("original_query", "")
        cleaned = reasoning.get("cleaned_query", "")
        exts = reasoning.get("target_extensions", [])
        elapsed = reasoning.get("elapsed_ms", 0)
        total = reasoning.get("total_hits", 0)

        if exts:
            ext_str = ", ".join(exts)
            lines.append(f"📌 Detected file type intent: <b style='color:{ACCENT_WARM}'>{ext_str}</b>")
            if cleaned != original:
                lines.append(f"🔍 Semantic query refined to: <b style='color:{ACCENT_BLUE}'>\"{cleaned}\"</b>")
            lines.append(f"⚡ Filtered {total} results by type + meaning in <b>{elapsed}ms</b>")
        else:
            lines.append(f"🔍 Full semantic search for: <b style='color:{ACCENT_BLUE}'>\"{cleaned}\"</b>")
            lines.append(f"⚡ Found {total} results via neural vector matching in <b>{elapsed}ms</b>")

        body = QLabel("<br>".join(lines))
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setStyleSheet(f"""
            font-size: 12px; line-height: 1.6;
            color: {TEXT_SECONDARY};
            background: transparent;
        """)
        layout.addWidget(body)


# ─────────────────────────────────────────────────────────────────────────────
# Main panel (ChatGPT-inspired)
# ─────────────────────────────────────────────────────────────────────────────
class SearchPanel(QWidget):
    """
    Frameless, vibrant overlay panel with ChatGPT-like reasoning and
    premium aesthetics.
    """

    def __init__(self, service: DesktopService):
        super().__init__()
        self._svc = service
        self._idx_thread: IndexThread | None = None
        self._srch_thread: SearchThread | None = None
        self._indexed_count = 0
        self._visible = False
        self._thinking_dots = 0
        self._thinking_timer: QTimer | None = None

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

        # ── Fade animation ───────────────────────────────────────────────
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(200)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── Start indexing ───────────────────────────────────────────────
        self._kick_indexing()

    # ── Paint: rounded dark background ─────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            1.0, 1.0,
            float(self.width()) - 2.0, float(self.height()) - 2.0,
            CORNER_RADIUS, CORNER_RADIUS,
        )

        # Subtle border glow
        painter.setPen(QPen(QColor(16, 163, 127, 50), 1.5))
        painter.drawPath(path)
        painter.end()

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 18)
        root.setSpacing(0)

        # ── Header with brand ────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(2, 0, 2, 0)

        brand = QLabel("✦ DeepSeekFS")
        brand.setStyleSheet(f"""
            font-size: 18px; font-weight: 800;
            color: {ACCENT_PRIMARY};
            background: transparent;
            letter-spacing: 1px;
        """)
        header_row.addWidget(brand)
        header_row.addStretch()

        version_lbl = QLabel("v4.0 • AI-Powered")
        version_lbl.setStyleSheet(f"""
            font-size: 11px; font-weight: 600;
            color: {TEXT_MUTED};
            background: transparent;
        """)
        header_row.addWidget(version_lbl)

        root.addLayout(header_row)
        root.addSpacing(16)

        # ── Search bar ───────────────────────────────────────────────────
        search_container = QFrame()
        search_container.setObjectName("searchContainer")
        search_container.setStyleSheet(f"""
            #searchContainer {{
                background: rgba(32, 33, 36, 0.8);
                border: 2px solid {BORDER_SUBTLE};
                border-radius: 16px;
            }}
            #searchContainer:focus-within {{
                border-color: {BORDER_ACTIVE};
                background: rgba(32, 33, 36, 0.95);
            }}
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(18, 0, 18, 0)
        search_layout.setSpacing(12)

        # Mic/sparkle icon
        search_icon = QLabel("✨")
        search_icon.setStyleSheet(f"font-size: 18px; color: {ACCENT_PRIMARY}; background: transparent;")
        search_icon.setFixedWidth(28)
        search_layout.addWidget(search_icon)

        self.inp_query = QLineEdit()
        self.inp_query.setPlaceholderText("Ask anything — search files, code, documents…")
        self.inp_query.setObjectName("searchInput")
        self.inp_query.setStyleSheet(f"""
            #searchInput {{
                border: none;
                background: transparent;
                color: {TEXT_PRIMARY};
                font-size: 15px;
                font-weight: 500;
                padding: 16px 0;
                selection-background-color: {ACCENT_PRIMARY}50;
            }}
            #searchInput::placeholder {{
                color: {TEXT_MUTED};
            }}
        """)
        self.inp_query.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.inp_query, 1)

        # Send button
        send_btn = QLabel("➜")
        send_btn.setFixedSize(36, 36)
        send_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"""
            font-size: 18px; font-weight: 800;
            color: white;
            background: {ACCENT_PRIMARY};
            border-radius: 10px;
        """)
        send_btn.mousePressEvent = lambda e: self._on_search()
        search_layout.addWidget(send_btn)

        root.addWidget(search_container)
        root.addSpacing(12)

        # ── Status bar ───────────────────────────────────────────────────
        self.lbl_status = QLabel("⏳  Preparing your AI search engine…")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setStyleSheet(f"""
            #statusLabel {{
                font-size: 12px;
                color: {TEXT_SECONDARY};
                background: transparent;
                padding: 4px 6px;
            }}
        """)
        root.addWidget(self.lbl_status)
        root.addSpacing(6)

        # ── Divider ──────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER_SUBTLE};")
        root.addWidget(divider)
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
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {ACCENT_PRIMARY}40;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT_PRIMARY}80;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}
        """)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(6)
        self.results_layout.addStretch()

        self.scroll.setWidget(self.results_widget)
        root.addWidget(self.scroll, 1)

        # ── Welcome / empty state (PERSISTENT — never deleted) ───────────
        self.lbl_empty = QLabel("Ask me anything — I'll find it in your files 🚀")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setStyleSheet(f"""
            font-size: 14px;
            color: {TEXT_MUTED};
            padding: 50px 20px;
            background: transparent;
        """)
        # Insert into results and keep a reference
        self.results_layout.insertWidget(0, self.lbl_empty)

        # ── Bottom bar ───────────────────────────────────────────────────
        root.addSpacing(8)
        bottom_divider = QFrame()
        bottom_divider.setFixedHeight(1)
        bottom_divider.setStyleSheet(f"background: {BORDER_SUBTLE};")
        root.addWidget(bottom_divider)
        root.addSpacing(6)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)

        self.lbl_footer = QLabel("Powered by MiniLM Neural Engine")
        self.lbl_footer.setStyleSheet(f"""
            font-size: 10px; font-weight: 600;
            color: {TEXT_MUTED};
            background: transparent;
        """)
        bottom.addWidget(self.lbl_footer)

        bottom.addStretch()

        hint = QLabel("Shift+Space to toggle  •  Esc to hide")
        hint.setStyleSheet(f"""
            font-size: 10px;
            color: {TEXT_MUTED};
            background: transparent;
        """)
        bottom.addWidget(hint)

        root.addLayout(bottom)

    def _show_empty_state(self):
        """Show welcome text (lbl_empty is never destroyed)."""
        self.lbl_empty.show()

    def _hide_empty_state(self):
        """Hide the empty label (but don't destroy it!)."""
        self.lbl_empty.hide()

    def _clear_results(self):
        """Remove all result/reasoning cards but KEEP lbl_empty."""
        while self.results_layout.count() > 0:
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.lbl_empty:
                w.deleteLater()

        # Re-add lbl_empty (it's still alive, just needs to be in layout)
        self.results_layout.addWidget(self.lbl_empty)

    # ── Stylesheet for result cards ──────────────────────────────────────
    _CARD_STYLE = f"""
        #resultCard {{
            background: {BG_CARD};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: 14px;
        }}
        #resultCard:hover {{
            background: {BG_CARD_HOVER};
            border: 1px solid {ACCENT_PRIMARY}60;
        }}
        #reasoningCard {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(16, 163, 127, 0.08),
                stop:1 rgba(139, 92, 246, 0.05));
            border: 1px solid {ACCENT_PRIMARY}30;
            border-radius: 14px;
        }}
    """

    # ── System tray ──────────────────────────────────────────────────────
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        menu = QMenu()
        show_action = menu.addAction("✦  Show   (Shift+Space)")
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
            f"✦ {self._indexed_count:,} files indexed  •  {new_files} new  •  Ready"
        )

    # ── Thinking animation ───────────────────────────────────────────────
    def _start_thinking(self, query: str):
        """Show animated thinking state."""
        self._clear_results()
        self._thinking_dots = 0

        self.lbl_empty.setText("🧠 Thinking")
        self.lbl_empty.setStyleSheet(f"""
            font-size: 18px; font-weight: 700;
            color: {ACCENT_PRIMARY};
            padding: 40px 20px;
            background: transparent;
        """)
        self.lbl_empty.show()

        # Animate dots
        self._thinking_timer = QTimer()
        self._thinking_timer.timeout.connect(self._animate_thinking)
        self._thinking_timer.start(300)

    def _animate_thinking(self):
        self._thinking_dots = (self._thinking_dots + 1) % 4
        dots = "." * self._thinking_dots
        steps = [
            "Parsing your intent",
            "Extracting keywords",
            "Scanning neural vectors",
            "Ranking by relevance",
        ]
        step_idx = min(self._thinking_dots, len(steps) - 1)
        self.lbl_empty.setText(f"🧠 Thinking{dots}\n\n{steps[step_idx]}…")

    def _stop_thinking(self):
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None

    # ── Search ───────────────────────────────────────────────────────────
    def _on_search(self):
        query = self.inp_query.text().strip()
        if not query:
            return
        if self._indexed_count == 0:
            self.lbl_status.setText("⏳  Indexing still in progress — try again shortly")
            return

        self.lbl_status.setText(f"🧠  Analyzing: \"{query}\"")
        self._start_thinking(query)

        # Delay to show thinking animation, then fire search
        QTimer.singleShot(600, lambda: self._execute_search(query))

    def _execute_search(self, query):
        self._srch_thread = SearchThread(self._svc, query)
        self._srch_thread.results.connect(self._on_results)
        self._srch_thread.error.connect(
            lambda e: self._on_search_error(e)
        )
        self._srch_thread.start()

    def _on_search_error(self, error: str):
        self._stop_thinking()
        self.lbl_status.setText(f"⚠️  Search error: {error}")

    def _on_results(self, payload: dict):
        self._stop_thinking()
        self._clear_results()
        self._hide_empty_state()

        hits = payload.get("hits", [])
        reasoning = payload.get("reasoning", {})

        # Reset lbl_empty style
        self.lbl_empty.setStyleSheet(f"""
            font-size: 14px;
            color: {TEXT_MUTED};
            padding: 50px 20px;
            background: transparent;
        """)

        if not hits:
            self.lbl_status.setText("No results found")
            self.lbl_empty.setText("No results found — try rephrasing your query 🤔")
            self._show_empty_state()
            return

        self.setStyleSheet(self._CARD_STYLE)

        # Insert reasoning card first
        reasoning_card = ReasoningCard(reasoning, parent=self.results_widget)
        self.results_layout.insertWidget(0, reasoning_card)

        # Insert result cards
        for rank, hit in enumerate(hits):
            card = ResultCard(hit, rank, parent=self.results_widget)
            card.clicked.connect(self._open_file)
            self.results_layout.insertWidget(rank + 1, card)

        # Add stretch at end
        self.results_layout.addStretch()

        n = len(hits)
        elapsed = reasoning.get("elapsed_ms", 0)
        q = self.inp_query.text().strip()
        self.lbl_status.setText(
            f"✦ {n} result{'s' if n != 1 else ''} for \"{q}\"  •  {elapsed}ms"
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
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        self._tray.hide()
        QApplication.quit()

    # ── Windows DWM Acrylic ──────────────────────────────────────────────
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

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        val = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        DWMWA_SYSTEMBACKDROP_TYPE = 38
        for backdrop in (3, 4, 2):
            val = ctypes.c_int(backdrop)
            hr = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(val), ctypes.sizeof(val),
            )
            if hr == 0:
                logger.info(f"DWM backdrop type {backdrop} applied successfully")
                return

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
        accent = ACCENT_POLICY(
            ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, 0x64101010, 0
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
    app.setApplicationVersion("4.0.0")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

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

    # Show once on first launch
    panel._show_panel()

    ret = app.exec()

    if hotkey_ok:
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    sys.exit(ret)


if __name__ == "__main__":
    main()

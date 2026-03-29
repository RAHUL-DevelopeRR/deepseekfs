"""
DeepSeekFS — macOS Tahoe Spotlight Panel (PyQt6)  ·  Premium Edition
=====================================================================
Native Liquid Glass search overlay.  825 × 955 physical px.
Shift+Space to toggle.  Keyboard navigation.  Top-1 % desktop UX.
"""
from __future__ import annotations

import ctypes, ctypes.wintypes, os, sys, platform, subprocess, time, math
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QScrollArea, QFrame,
    QSystemTrayIcon, QMenu, QFileDialog,
    QSizePolicy, QGraphicsDropShadowEffect,
    QSlider, QPushButton, QGraphicsOpacityEffect,
    QGridLayout,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
    QAbstractNativeEventFilter, QByteArray,
    QParallelAnimationGroup, QSequentialAnimationGroup,
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPainterPath,
    QBrush, QPen, QFontDatabase, QGuiApplication,
    QCursor, QLinearGradient, QRadialGradient, QClipboard,
    QPixmap, QPalette,
)

import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService
from services.ollama_service import get_ollama

# ── resolve assets path ──────────────────────────────────────
_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_ICON   = _ASSETS / "icon.ico"

# ═════════════════════════════════════════════════════════════
# DESIGN CONSTANTS  —  Apple-grade visual language
# ═════════════════════════════════════════════════════════════
W, H = 825, 955
R = 24                          # corner radius

HOTKEY_ID = 0xBFFF
MOD_SHIFT = 0x0004
VK_SPACE  = 0x20
WM_HOTKEY = 0x0312

# ── colour tokens ────────────────────────────────────────────
class C:
    """Central palette – every colour used in the UI lives here."""
    # -- panel chrome -------
    PANEL_BG       = QColor(18, 18, 22, 220)        # deep matte black
    PANEL_BORDER   = QColor(255, 255, 255, 18)
    TOP_SHEEN      = QColor(255, 255, 255, 6)
    # -- search bar ---------
    SEARCH_BG      = QColor(255, 255, 255, 10)
    SEARCH_BORDER  = QColor(255, 255, 255, 14)
    SEARCH_GLOW    = QColor(56, 156, 255, 80)       # pulsing blue
    # -- content text -------
    T1  = QColor(255, 255, 255, 235)                 # primary
    T2  = QColor(255, 255, 255, 148)                 # secondary
    T3  = QColor(255, 255, 255, 88)                  # tertiary
    T4  = QColor(255, 255, 255, 46)                  # quaternary
    # -- accents ------------
    BLUE           = "#389CFF"
    BLUE_Q         = QColor(56, 156, 255)
    BLUE_DIM       = QColor(56, 156, 255, 30)
    BLUE_GLOW      = QColor(56, 156, 255, 50)
    GREEN          = QColor(52, 199, 89)
    # -- surface ------------
    CARD_IDLE      = QColor(255, 255, 255, 6)
    CARD_HOVER     = QColor(255, 255, 255, 14)
    CARD_SELECTED  = QColor(56, 156, 255, 28)
    CARD_SEL_BDR   = QColor(56, 156, 255, 55)
    DIVIDER        = QColor(255, 255, 255, 10)

FN  = "'Segoe UI Variable Display', 'Segoe UI', 'Inter', system-ui, sans-serif"
MN  = "'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"

# ── file icon map ────────────────────────────────────────────
_I = {
    ".py":("🐍","#3B82F6","PY"),   ".ipynb":("📓","#8B5CF6","NB"),
    ".js":("⚡","#EAB308","JS"),   ".ts":("🔷","#3B82F6","TS"),
    ".jsx":("⚛️","#22D3EE","JSX"), ".tsx":("⚛️","#3B82F6","TSX"),
    ".rs":("🦀","#E57A44","RS"),   ".go":("🐹","#00ADD8","GO"),
    ".java":("☕","#F59E0B","JV"),  ".cpp":("⚙️","#60A5FA","C++"),
    ".c":("⚙️","#94A3B8","C"),     ".h":("⚙️","#94A3B8","H"),
    ".cs":("🟣","#A78BFA","C#"),   ".rb":("💎","#EF4444","RB"),
    ".php":("🐘","#A78BFA","PHP"), ".swift":("🐦","#F97316","SW"),
    ".kt":("🟣","#A855F6","KT"),   ".html":("🌐","#EF4444","HTM"),
    ".css":("🎨","#38BDF8","CSS"), ".md":("📝","#94A3B8","MD"),
    ".txt":("📄","#94A3B8","TXT"), ".log":("📋","#94A3B8","LOG"),
    ".pdf":("📕","#EF4444","PDF"), ".docx":("📘","#2563EB","DOC"),
    ".doc":("📘","#2563EB","DOC"), ".xlsx":("📗","#22C55E","XLS"),
    ".xls":("📗","#22C55E","XLS"), ".csv":("📊","#22C55E","CSV"),
    ".pptx":("📙","#F97316","PPT"),
    ".json":("{ }","#F5B74A","JSON"), ".xml":("< >","#F5B74A","XML"),
    ".yaml":("🔧","#A78BFA","YML"), ".yml":("🔧","#A78BFA","YML"),
    ".toml":("🔧","#A78BFA","TML"), ".env":("🔐","#A78BFA","ENV"),
    ".ini":("🔧","#94A3B8","INI"), ".cfg":("🔧","#94A3B8","CFG"),
    ".mp4":("🎬","#A855F6","MP4"), ".mkv":("🎬","#A855F6","MKV"),
    ".avi":("🎬","#A855F6","AVI"), ".mov":("🎬","#A855F6","MOV"),
    ".png":("🖼️","#EC4899","PNG"),  ".jpg":("🖼️","#EC4899","JPG"),
    ".jpeg":("🖼️","#EC4899","JPG"), ".gif":("🖼️","#EC4899","GIF"),
    ".webp":("🖼️","#EC4899","WBP"),
    ".zip":("📦","#FBBF24","ZIP"), ".exe":("⚙️","#A78BFA","EXE"),
}
_D = ("📄","#64748B","FILE")

SCOPES = {
    "all": None, "files": None, "folders": "__dir__",
    "code": {".py",".js",".ts",".jsx",".tsx",".rs",".go",".java",".cpp",
             ".c",".h",".cs",".rb",".php",".swift",".kt",".html",".css"},
    "docs": {".md",".txt",".pdf",".docx",".doc",".pptx",".xlsx",".xls",".csv"},
    "media":{".mp4",".mkv",".avi",".mov",".png",".jpg",".jpeg",".gif",".webp",".webm"},
}

def _icon(ext: str):
    return _I.get(ext.lower(), _D)


# ═════════════════════════════════════════════════════════════
# Win32 native hotkey listener
# ═════════════════════════════════════════════════════════════
class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, cb):
        super().__init__()
        self._cb = cb
    def nativeEventFilter(self, et, msg):
        if et in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                ptr = int(msg)
                if ctypes.c_uint.from_address(ptr + 8).value == WM_HOTKEY:
                    if ctypes.c_ulonglong.from_address(ptr + 16).value == HOTKEY_ID:
                        self._cb()
                        return True, 0
            except Exception:
                pass
        return False, 0


# ═════════════════════════════════════════════════════════════
# Background workers
# ═════════════════════════════════════════════════════════════
class IndexThread(QThread):
    status   = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int)
    def __init__(self, svc):
        super().__init__()
        self._s = svc
    def run(self):
        try:
            n = self._s.run_indexing(on_status=self.status.emit,
                                     on_progress=self.progress.emit)
            self.finished.emit(n)
        except Exception as e:
            logger.error(f"IndexThread: {e}")
            self.finished.emit(0)

class SearchThread(QThread):
    results = pyqtSignal(list)
    error   = pyqtSignal(str)
    def __init__(self, svc, q, k=20):
        super().__init__()
        self._s, self._q, self._k = svc, q, k
    def run(self):
        try:    self.results.emit(self._s.search(self._q, self._k))
        except Exception as e: self.error.emit(str(e))

class AskAIThread(QThread):
    """Ask Ollama a question grounded in file search results."""
    answer = pyqtSignal(str)
    error  = pyqtSignal(str)
    def __init__(self, question: str, file_contexts: list):
        super().__init__()
        self._q, self._ctx = question, file_contexts
    def run(self):
        try:
            ai = get_ollama()
            if not ai.is_available():
                self.error.emit("Ollama not running. Start with: ollama serve")
                return
            ans = ai.ask_about_files(self._q, self._ctx)
            self.answer.emit(ans)
        except Exception as e:
            self.error.emit(str(e))

class SummarizeThread(QThread):
    """Summarize a single file via Ollama."""
    summary = pyqtSignal(str, str)  # (path, summary text)
    error   = pyqtSignal(str)
    def __init__(self, path: str):
        super().__init__()
        self._path = path
    def run(self):
        try:
            ai = get_ollama()
            if not ai.is_available():
                self.error.emit("Ollama not running. Start with: ollama serve")
                return
            s = ai.summarize_file(self._path)
            self.summary.emit(self._path, s)
        except Exception as e:
            self.error.emit(str(e))


# ═════════════════════════════════════════════════════════════
# Micro-widgets
# ═════════════════════════════════════════════════════════════

# ── animated blue-glow search field ──────────────────────────
class GlowSearchBar(QFrame):
    """Large search input with a pulsating blue focus glow ring."""
    textChanged = pyqtSignal(str)
    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setObjectName("GlowSearch")

        # outer glow shadow (hidden until focused)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
        self._glow.setColor(C.SEARCH_GLOW)
        self.setGraphicsEffect(self._glow)

        self._glow_anim = QPropertyAnimation(self._glow, b"blurRadius")
        self._glow_anim.setDuration(400)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setStyleSheet(f"""
            #GlowSearch {{
                background: rgba(255,255,255,0.04);
                border: 1.2px solid rgba(255,255,255,0.08);
                border-radius: 16px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 16, 0)
        lay.setSpacing(14)

        # magnifying glass
        mag = QLabel("🔍")
        mag.setFixedWidth(26)
        mag.setStyleSheet("font-size: 18px; background: transparent;")
        mag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(mag)

        # the actual input
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Search files… or type ? to ask Encyl")
        self.inp.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                color: rgba(255,255,255,0.92);
                font-family: {FN}; font-size: 20px; font-weight: 400;
                padding: 14px 0;
                selection-background-color: rgba(56,156,255,0.25);
            }}
            QLineEdit::placeholder {{
                color: rgba(255,255,255,0.25); font-weight: 300;
            }}
        """)
        self.inp.textChanged.connect(self.textChanged.emit)
        self.inp.returnPressed.connect(self.returnPressed.emit)
        lay.addWidget(self.inp, 1)

        # shortcut badges
        for txt in ("⇧", "Space"):
            b = QLabel(txt)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w = max(30, len(txt) * 11)
            b.setFixedSize(w, 24)
            b.setStyleSheet(f"""
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                font-family: {FN}; font-size: 11px; font-weight: 600;
                color: rgba(255,255,255,0.25);
            """)
            lay.addWidget(b)

        # wire focus events
        self.inp.installEventFilter(self)

    # forward focus helpers
    def text(self):          return self.inp.text()
    def setFocus(self):      self.inp.setFocus()
    def selectAll(self):     self.inp.selectAll()
    def clear(self):         self.inp.clear()

    def eventFilter(self, obj, ev):
        if obj is self.inp:
            if ev.type() == ev.Type.FocusIn:
                self.setStyleSheet(f"""
                    #GlowSearch {{
                        background: rgba(255,255,255,0.06);
                        border: 1.2px solid rgba(56,156,255,0.35);
                        border-radius: 16px;
                    }}
                """)
                self._glow_anim.stop()
                self._glow_anim.setStartValue(0)
                self._glow_anim.setEndValue(32)
                self._glow_anim.start()
            elif ev.type() == ev.Type.FocusOut:
                self.setStyleSheet(f"""
                    #GlowSearch {{
                        background: rgba(255,255,255,0.04);
                        border: 1.2px solid rgba(255,255,255,0.08);
                        border-radius: 16px;
                    }}
                """)
                self._glow_anim.stop()
                self._glow_anim.setStartValue(self._glow.blurRadius())
                self._glow_anim.setEndValue(0)
                self._glow_anim.start()
        return False


# ── scope pill ───────────────────────────────────────────────
class ScopePill(QLabel):
    clicked = pyqtSignal(str)

    _CSS_IDLE = f"""
        padding: 5px 16px; border-radius: 14px;
        font-family: {FN}; font-size: 12px; font-weight: 500;
        color: rgba(255,255,255,0.40); background: transparent;
        border: 1px solid transparent;
    """
    _CSS_ACTIVE = f"""
        padding: 5px 16px; border-radius: 14px;
        font-family: {FN}; font-size: 12px; font-weight: 600;
        color: #65B8FF; background: rgba(56,156,255,0.12);
        border: 1px solid rgba(56,156,255,0.22);
    """
    _CSS_HOVER = f"""
        padding: 5px 16px; border-radius: 14px;
        font-family: {FN}; font-size: 12px; font-weight: 500;
        color: rgba(255,255,255,0.70); background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.04);
    """

    def __init__(self, text, key, active=False, parent=None):
        super().__init__(text, parent)
        self._key, self._active = key, active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(self._CSS_ACTIVE if self._active else self._CSS_IDLE)

    def set_active(self, a):
        self._active = a; self._refresh()

    def mousePressEvent(self, e): self.clicked.emit(self._key)
    def enterEvent(self, e):
        if not self._active: self.setStyleSheet(self._CSS_HOVER)
    def leaveEvent(self, e):  self._refresh()


# ── category header ──────────────────────────────────────────
class CatHeader(QFrame):
    def __init__(self, title, count=0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 2)
        t = QLabel(title.upper())
        t.setStyleSheet(f"""
            font-family: {FN}; font-size: 10.5px; font-weight: 700;
            letter-spacing: 1.2px; color: rgba(255,255,255,0.30);
            background: transparent;
        """)
        lay.addWidget(t)
        lay.addStretch()
        if count > 0:
            c = QLabel(f"{count} results")
            c.setStyleSheet(f"font-size: 10px; color: rgba(255,255,255,0.16); background: transparent;")
            lay.addWidget(c)


# ── result row ───────────────────────────────────────────────
class ResultRow(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, hit, top=False, parent=None):
        super().__init__(parent)
        self._path = hit.get("path", "")
        ext = hit.get("extension", Path(self._path).suffix).lower()
        emoji, accent, badge = _icon(ext)
        name = hit.get("name", Path(self._path).name)
        score = hit.get("combined_score", 0.0)
        self._sel = False

        h = 64 if top else 52
        self.setFixedHeight(h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply(False, False)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 0, 14, 0)
        root.setSpacing(14)

        # ── icon chip ──
        isz = 42 if top else 34
        ic = QFrame()
        ic.setFixedSize(isz, isz)
        br = isz // 3
        ic.setStyleSheet(f"""
            background: {accent}18; border: 1px solid {accent}22;
            border-radius: {br}px;
        """)
        il = QVBoxLayout(ic); il.setContentsMargins(0,0,0,0)
        ie = QLabel(emoji)
        ie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ie.setStyleSheet(f"font-size: {'20' if top else '15'}px; background: transparent;")
        il.addWidget(ie)
        root.addWidget(ic)

        # ── text column ──
        tc = QVBoxLayout(); tc.setSpacing(1)
        nf = 14 if top else 13
        nl = QLabel(name)
        nl.setStyleSheet(f"""
            font-family: {FN}; font-size: {nf}px; font-weight: 600;
            color: rgba(255,255,255,0.92); background: transparent;
        """)
        tc.addWidget(nl)
        disp = self._path
        try:
            home = str(Path.home())
            if disp.startswith(home): disp = "~" + disp[len(home):]
        except Exception: pass
        pl = QLabel(disp)
        pl.setStyleSheet(f"""
            font-family: {MN}; font-size: 10.5px;
            color: rgba(255,255,255,0.28); background: transparent;
        """)
        pl.setMaximumWidth(460)
        tc.addWidget(pl)
        root.addLayout(tc, 1)

        # ── badge ──
        bl = QLabel(badge)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.setFixedSize(44, 22)
        bl.setStyleSheet(f"""
            font-size: 10px; font-weight: 700; letter-spacing: 0.6px;
            color: {accent}; background: {accent}14;
            border-radius: 6px; border: 1px solid {accent}1a;
        """)
        root.addWidget(bl)

        # ── score ──
        pct = int(score * 100)
        sc_color = "#4ADE80" if pct >= 80 else "#FBBF24" if pct >= 50 else "#94A3B8"
        sl = QLabel(f"{pct}%")
        sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.setFixedSize(44, 22)
        sl.setStyleSheet(f"""
            font-size: 11px; font-weight: 700;
            color: {sc_color}; background: rgba(255,255,255,0.04);
            border-radius: 6px; border: none;
        """)
        root.addWidget(sl)

        # ── chevron ──
        ch = QLabel("›")
        ch.setStyleSheet(f"color: rgba(255,255,255,0.14); font-size: 18px; font-weight: 300; background: transparent;")
        root.addWidget(ch)

    # ── state management ──
    def _apply(self, sel, hov):
        if sel:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: rgba(56,156,255,0.12);
                    border: 1px solid rgba(56,156,255,0.25);
                    border-radius: 12px;
                }}
            """)
        elif hov:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.04);
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 12px;
                }}
            """)

    def set_selected(self, s):
        self._sel = s; self._apply(s, False)

    def enterEvent(self, e):
        if not self._sel: self._apply(False, True)
    def leaveEvent(self, e):
        self._apply(self._sel, False)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)


# ── action card ──────────────────────────────────────────────
class ActionCard(QFrame):
    action_clicked = pyqtSignal(str)

    def __init__(self, emoji, label, shortcut, aid, parent=None):
        super().__init__(parent)
        self._aid = aid
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(90)
        self.setStyleSheet(f"""
            ActionCard {{
                background: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 14px;
            }}
            ActionCard:hover {{
                background: rgba(255,255,255,0.06);
                border-color: rgba(56,156,255,0.18);
            }}
        """)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(10, 16, 10, 12)
        vb.setSpacing(6)
        vb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # icon in a subtle circle
        ic = QLabel(emoji)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setFixedSize(36, 36)
        ic.setStyleSheet("font-size: 20px; background: rgba(56,156,255,0.08); border-radius: 18px;")
        vb.addWidget(ic, 0, Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"font-family: {FN}; font-size: 11.5px; font-weight: 600; color: rgba(255,255,255,0.72); background: transparent;")
        vb.addWidget(lbl)

        sc = QLabel(shortcut)
        sc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc.setStyleSheet(f"font-family: {MN}; font-size: 9px; color: rgba(255,255,255,0.18); background: transparent;")
        vb.addWidget(sc)

    def mousePressEvent(self, e):
        self.action_clicked.emit(self._aid)


# ── settings overlay ─────────────────────────────────────────
class SettingsOverlay(QFrame):
    closed = pyqtSignal()
    reindex = pyqtSignal()
    paths_changed = pyqtSignal()

    def __init__(self, svc, parent=None):
        super().__init__(parent)
        self._svc = svc
        self.setStyleSheet(f"""
            SettingsOverlay {{
                background: rgba(14,14,18,0.96);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 20px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)

        # header
        hdr = QHBoxLayout()
        t = QLabel("⚙️  Settings")
        t.setStyleSheet(f"font-family: {FN}; font-size: 18px; font-weight: 700; color: rgba(255,255,255,0.92); background: transparent;")
        hdr.addWidget(t); hdr.addStretch()
        x = QLabel("✕"); x.setFixedSize(28,28)
        x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.5); background: rgba(255,255,255,0.06); border-radius: 6px;")
        x.mousePressEvent = lambda e: self.closed.emit()
        hdr.addWidget(x)
        root.addLayout(hdr)

        # divider
        d = QFrame(); d.setFixedHeight(1); d.setStyleSheet("background: rgba(255,255,255,0.06);")
        root.addWidget(d)

        # stats
        cnt = svc.total_indexed()
        ps = svc.get_watch_paths()
        st = QLabel(f"📊  {cnt:,} files indexed  ·  {len(ps)} watch directories")
        st.setStyleSheet(f"font-size: 12px; color: rgba(255,255,255,0.5); background: transparent;")
        root.addWidget(st)

        # watch paths
        wl = QLabel("Watch Paths")
        wl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.80); background: transparent;")
        root.addWidget(wl)
        self._pc = QVBoxLayout(); self._pc.setSpacing(3)
        for p in ps:
            l = QLabel(f"  📂  {p}")
            l.setStyleSheet(f"font-size: 11px; color: rgba(255,255,255,0.35); background: transparent;")
            l.setMaximumWidth(550)
            self._pc.addWidget(l)
        root.addLayout(self._pc)

        # add folder
        ab = QPushButton("＋  Add Folder")
        ab.setCursor(Qt.CursorShape.PointingHandCursor)
        ab.setStyleSheet(f"""
            QPushButton {{ background: rgba(255,255,255,0.04); border: 1px dashed rgba(255,255,255,0.12);
            border-radius: 10px; color: rgba(255,255,255,0.5); font-size: 12px; font-weight: 600; padding: 10px; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.8); }}
        """)
        ab.clicked.connect(self._add)
        root.addWidget(ab)

        # reindex
        rb = QPushButton("🔄  Re-index Now")
        rb.setCursor(Qt.CursorShape.PointingHandCursor)
        rb.setStyleSheet(f"""
            QPushButton {{ background: rgba(56,156,255,0.45); border: none; border-radius: 10px;
            color: white; font-size: 12px; font-weight: 700; padding: 12px; }}
            QPushButton:hover {{ background: rgba(56,156,255,0.65); }}
        """)
        rb.clicked.connect(lambda: (self.reindex.emit(), self.closed.emit()))
        root.addWidget(rb)

        # top-k slider
        cfg = svc.get_config()
        tr = QHBoxLayout()
        tl = QLabel("Results count")
        tl.setStyleSheet(f"font-size: 12px; color: rgba(255,255,255,0.5); background: transparent;")
        tr.addWidget(tl); tr.addStretch()
        self._tv = QLabel(str(cfg.get("top_k", 20)))
        self._tv.setStyleSheet(f"font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.85); background: transparent;")
        tr.addWidget(self._tv)
        root.addLayout(tr)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(5, 50); sl.setValue(cfg.get("top_k", 20))
        sl.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: rgba(255,255,255,0.06); height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {C.BLUE}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
            QSlider::sub-page:horizontal {{ background: rgba(56,156,255,0.3); border-radius: 2px; }}
        """)
        sl.valueChanged.connect(lambda v: (self._tv.setText(str(v)), self._topk(v)))
        root.addWidget(sl)
        root.addStretch()

    def _add(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f and self._svc.add_watch_path(f):
            l = QLabel(f"  📂  {f}")
            l.setStyleSheet(f"font-size: 11px; color: rgba(255,255,255,0.35); background: transparent;")
            self._pc.addWidget(l)
            self.paths_changed.emit()

    def _topk(self, v):
        c = self._svc.get_config(); c["top_k"] = v; self._svc.save_config(c)


# ═════════════════════════════════════════════════════════════
# THE SPOTLIGHT PANEL  —  main widget
# ═════════════════════════════════════════════════════════════
class SpotlightPanel(QWidget):

    def __init__(self, svc: DesktopService):
        super().__init__()
        self._svc = svc
        self._rows: List[ResultRow] = []
        self._all: list = []
        self._sel = -1
        self._scope = "all"
        self._vis = False
        self._indexing = False
        self._idx_count = 0
        self._settings: SettingsOverlay | None = None
        self._it: IndexThread | None = None
        self._st: SearchThread | None = None
        self._ait: AskAIThread | None = None
        self._smt: SummarizeThread | None = None
        self._ai_panel: QFrame | None = None

        self._deb = QTimer(self)
        self._deb.setSingleShot(True)
        self._deb.setInterval(280)
        self._deb.timeout.connect(self._do_search)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Dynamic height — fit the screen
        self._resize_to_screen()

        self._build()
        self._build_tray()

        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._kick_index()

    # ── glass background painting ────────────────────────────
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # main body
        path = QPainterPath()
        path.addRoundedRect(1, 1, self.width()-2, self.height()-2, R, R)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(C.PANEL_BG))
        p.drawPath(path)

        # top sheen gradient
        grad = QLinearGradient(0, 0, 0, 120)
        grad.setColorAt(0, QColor(255, 255, 255, 8))
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        # subtle ambient radial glow top-centre
        rg = QRadialGradient(self.width()/2, 0, 400)
        rg.setColorAt(0, QColor(56, 156, 255, 12))
        rg.setColorAt(1, QColor(56, 156, 255, 0))
        p.setBrush(QBrush(rg))
        p.drawPath(path)

        # border
        p.setPen(QPen(C.PANEL_BORDER, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        p.end()

    # ── build ui ─────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 14)
        root.setSpacing(0)

        # ── SEARCH BAR ──
        self.search = GlowSearchBar(self)
        self.search.textChanged.connect(self._on_text)
        self.search.returnPressed.connect(self._open_sel)
        root.addWidget(self.search)
        root.addSpacing(10)

        # ── SCOPE PILLS ──
        pr = QHBoxLayout()
        pr.setSpacing(4)
        pr.setContentsMargins(4, 0, 4, 0)
        self._pills: list[ScopePill] = []
        for label, key in [("All","all"),("Files","files"),("Folders","folders"),
                           ("Code","code"),("Docs","docs"),("Media","media")]:
            pill = ScopePill(label, key, active=(key=="all"))
            pill.clicked.connect(self._set_scope)
            pr.addWidget(pill)
            self._pills.append(pill)
        pr.addStretch()
        root.addLayout(pr)
        root.addSpacing(8)

        # ── DIVIDER ──
        dv = QFrame(); dv.setFixedHeight(1)
        dv.setStyleSheet("background: rgba(255,255,255,0.06);")
        root.addWidget(dv)
        root.addSpacing(2)

        # ── SCROLL AREA ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 5px; margin: 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.08); min-height: 35px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.16); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; height: 0;
            }}
        """)
        self.rw = QWidget()
        self.rw.setStyleSheet("background: transparent;")
        self.rl = QVBoxLayout(self.rw)
        self.rl.setContentsMargins(0, 0, 0, 0)
        self.rl.setSpacing(2)

        # empty-state
        self.empty = QLabel("Type to search your files\n\nIndexes Desktop · Documents · Downloads\nand more across your machine")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet(f"""
            font-family: {FN}; font-size: 14px; font-weight: 400;
            color: rgba(255,255,255,0.20); padding: 50px 30px;
            line-height: 1.6; background: transparent;
        """)
        self.rl.addWidget(self.empty)

        # ACTION CARDS (visible in empty state)
        self._acw = QWidget(); self._acw.setStyleSheet("background: transparent;")
        al = QVBoxLayout(self._acw); al.setContentsMargins(0,0,0,0); al.setSpacing(6)
        al.addWidget(CatHeader("Quick Actions"))
        ag = QHBoxLayout(); ag.setSpacing(10)
        for em, lb, sc, aid in [("🔄","Re-index","Ctrl R","reindex"),
                                 ("📂","Add Folder","Ctrl O","add_path"),
                                 ("⚙️","Settings","Ctrl ,","settings")]:
            c = ActionCard(em, lb, sc, aid)
            c.action_clicked.connect(self._action)
            ag.addWidget(c)
        al.addLayout(ag)
        self.rl.addWidget(self._acw)

        # SUGGESTIONS
        self._sgw = QWidget(); self._sgw.setStyleSheet("background: transparent;")
        sl2 = QVBoxLayout(self._sgw); sl2.setContentsMargins(0,6,0,0); sl2.setSpacing(2)
        sl2.addWidget(CatHeader("Tips"))
        for em, nm, ds in [
            ("💡", "Semantic search", "Use natural language — \"files about machine learning\""),
            ("🧠", "Hybrid scoring", "Combines vector similarity + keyword + time + depth"),
            ("⏰", "Time filters", "Try \"modified last week\" or \"created today\""),
        ]:
            sf = QFrame(); sf.setFixedHeight(42)
            sf.setStyleSheet("background: transparent; border-radius: 10px;")
            sfl = QHBoxLayout(sf); sfl.setContentsMargins(16,4,16,4); sfl.setSpacing(14)
            si = QLabel(em); si.setFixedSize(28,28)
            si.setAlignment(Qt.AlignmentFlag.AlignCenter)
            si.setStyleSheet("font-size: 15px; background: rgba(56,156,255,0.06); border-radius: 8px;")
            sfl.addWidget(si)
            tc = QVBoxLayout(); tc.setSpacing(0)
            n = QLabel(nm)
            n.setStyleSheet(f"font-family: {FN}; font-size: 12.5px; font-weight: 600; color: rgba(255,255,255,0.70); background: transparent;")
            tc.addWidget(n)
            d = QLabel(ds)
            d.setStyleSheet(f"font-family: {MN}; font-size: 9.5px; color: rgba(255,255,255,0.22); background: transparent;")
            tc.addWidget(d)
            sfl.addLayout(tc, 1)
            sl2.addWidget(sf)
        self.rl.addWidget(self._sgw)
        self.rl.addStretch()

        self.scroll.setWidget(self.rw)
        root.addWidget(self.scroll, 1)

        # ── STATUS LINE ──
        self.status = QLabel("")
        self.status.setStyleSheet(f"font-size: 11px; color: rgba(255,255,255,0.22); background: transparent; padding: 3px 6px;")
        root.addWidget(self.status)

        # ── BOTTOM BAR ──
        root.addSpacing(4)
        bd = QFrame(); bd.setFixedHeight(1)
        bd.setStyleSheet("background: rgba(255,255,255,0.04);")
        root.addWidget(bd)
        root.addSpacing(6)

        bb = QHBoxLayout()
        bb.setContentsMargins(6, 0, 6, 0)

        # brand with gradient
        brand = QLabel("DeepSeekFS")
        brand.setStyleSheet(f"""
            font-family: {FN}; font-size: 11.5px; font-weight: 800;
            color: #389CFF; background: transparent;
        """)
        bb.addWidget(brand)
        bb.addSpacing(6)

        # green pulse dot
        dot = QLabel("●")
        dot.setStyleSheet("font-size: 7px; color: #34C759; background: transparent;")
        bb.addWidget(dot)
        bb.addSpacing(4)

        self.idx_lbl = QLabel("Indexing…")
        self.idx_lbl.setStyleSheet(f"font-size: 10px; color: rgba(255,255,255,0.18); background: transparent;")
        bb.addWidget(self.idx_lbl)
        bb.addStretch()

        for txt in ["↑↓ nav", "↵ open", "Tab Encyl", "?query ask", "^C copy", "Esc close"]:
            h = QLabel(txt)
            h.setStyleSheet(f"font-size: 9px; color: rgba(255,255,255,0.14); background: transparent;")
            bb.addWidget(h)
            if txt != "Esc close":
                sep = QLabel("·")
                sep.setStyleSheet("color: rgba(255,255,255,0.10); font-size: 9px; background: transparent;")
                bb.addWidget(sep)

        # Ollama status
        ai = get_ollama()
        ai_ok = ai.is_available()
        self.ai_lbl = QLabel("🧠 Encyl" if ai_ok else "🧠 ✗")
        self.ai_lbl.setStyleSheet(f"font-size: 9px; color: {'rgba(52,199,89,0.7)' if ai_ok else 'rgba(255,255,255,0.14)'}; background: transparent; margin-left: 8px;")
        self.ai_lbl.setToolTip("Encyl AI connected — type ? to ask" if ai_ok else "Encyl offline — start Ollama with 'ollama serve'")
        bb.addWidget(self.ai_lbl)

        root.addLayout(bb)

    # ═════════════════════════════════════════════════════════
    # RESULTS MANAGEMENT
    # ═════════════════════════════════════════════════════════
    def _clear(self):
        self._rows.clear(); self._sel = -1
        while self.rl.count() > 0:
            it = self.rl.takeAt(0)
            w = it.widget()
            if w and w not in (self.empty, self._acw, self._sgw):
                w.deleteLater()

    def _show_empty(self, msg=None):
        if msg: self.empty.setText(msg)
        self.empty.show(); self._acw.show(); self._sgw.show()

    def _hide_empty(self):
        self.empty.hide(); self._acw.hide(); self._sgw.hide()

    def _populate(self, hits):
        self._clear()
        self._hide_empty()
        if not hits:
            self.status.setText("No results found")
            self._show_empty("No matching files — try different keywords")
            self.rl.addWidget(self.empty)
            self.rl.addWidget(self._acw)
            self.rl.addWidget(self._sgw)
            self.rl.addStretch()
            return

        # Top Hit
        self.rl.addWidget(CatHeader("Top Hit"))
        top = ResultRow(hits[0], top=True, parent=self.rw)
        top.clicked.connect(self._open)
        self.rl.addWidget(top)
        self._rows.append(top)

        # Remaining
        rest = hits[1:]
        if rest:
            self.rl.addWidget(CatHeader("Files", len(rest)))
            for h in rest:
                r = ResultRow(h, parent=self.rw)
                r.clicked.connect(self._open)
                self.rl.addWidget(r)
                self._rows.append(r)

        self.rl.addWidget(self._acw)
        self.rl.addWidget(self._sgw)
        self.rl.addStretch()

        q = self.search.text().strip()
        n = len(hits)
        self.status.setText(f'{n} result{"s" if n != 1 else ""} for "{q}"')
        if self._rows:
            self._sel = 0; self._rows[0].set_selected(True)

    # ── scope ────────────────────────────────────────────────
    def _set_scope(self, k):
        self._scope = k
        for p in self._pills: p.set_active(p._key == k)
        if self._all:    self._filter()
        elif self.search.text().strip(): self._deb.start()

    def _filter(self):
        exts = SCOPES.get(self._scope)
        if exts == "__dir__": filtered = []
        elif exts: filtered = [h for h in self._all if h.get("extension","").lower() in exts]
        else: filtered = self._all
        self._populate(filtered)

    # ── actions ──────────────────────────────────────────────
    def _action(self, aid):
        if aid == "reindex":   self._reindex()
        elif aid == "add_path":
            f = QFileDialog.getExistingDirectory(self, "Select Folder")
            if f and self._svc.add_watch_path(f):
                config.WATCH_PATHS = config.UserConfig.get_all_watch_paths()
                self._reindex()
        elif aid == "settings": self._toggle_settings()

    def _toggle_settings(self):
        if self._settings and self._settings.isVisible():
            self._settings.hide(); self._settings.deleteLater(); self._settings = None; return
        self._settings = SettingsOverlay(self._svc, self)
        self._settings.closed.connect(self._close_settings)
        self._settings.reindex.connect(self._reindex)
        self._settings.paths_changed.connect(
            lambda: setattr(config, 'WATCH_PATHS', config.UserConfig.get_all_watch_paths()))
        self._settings.setGeometry(22, 80, self.width() - 44, self.height() - 110)
        self._settings.show(); self._settings.raise_()

    def _close_settings(self):
        if self._settings:
            self._settings.hide(); self._settings.deleteLater(); self._settings = None

    def _reindex(self):
        from services.startup_indexer import StartupIndexer
        StartupIndexer()._wipe_index("manual")
        self._kick_index()

    # ── tray ─────────────────────────────────────────────────
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        # Set the actual icon
        if _ICON.exists():
            self._tray.setIcon(QIcon(str(_ICON)))
            QApplication.setWindowIcon(QIcon(str(_ICON)))
        m = QMenu()
        m.setStyleSheet("""
            QMenu { background: #1a1a1e; color: #e0e0e0; border: 1px solid #333; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background: rgba(56,156,255,0.3); }
            QMenu::separator { height: 1px; background: #333; margin: 4px 8px; }
        """)
        m.addAction("🔍  Show  (Shift+Space)").triggered.connect(self.toggle_panel)
        m.addAction("🔄  Re-index").triggered.connect(self._reindex)
        m.addAction("⚙️  Settings").triggered.connect(self._toggle_settings)
        m.addSeparator()
        m.addAction("❌  Quit").triggered.connect(self._quit)
        self._tray.setContextMenu(m)
        self._tray.activated.connect(
            lambda r: self.toggle_panel() if r in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self._tray.setToolTip("DeepSeekFS — Shift+Space to search")
        self._tray.show()

    # ── indexing ─────────────────────────────────────────────
    def _kick_index(self):
        self._indexing = True
        self.idx_lbl.setText("Indexing…")
        self._it = IndexThread(self._svc)
        self._it.status.connect(lambda m: self.idx_lbl.setText(m))
        self._it.progress.connect(
            lambda d, t: self.idx_lbl.setText(f"Indexing… {min(int(d/t*100),99)}%") if t > 0 else None)
        self._it.finished.connect(self._idx_done)
        self._it.start()

    def _idx_done(self, n):
        self._indexing = False
        self._idx_count = self._svc.total_indexed()
        self.idx_lbl.setText(f"{self._idx_count:,} files indexed")

    # ── search ───────────────────────────────────────────────
    def _on_text(self, t):
        if t.strip():
            self._deb.start()
        else:
            self._deb.stop(); self._all.clear(); self._clear()
            self.rl.addWidget(self.empty); self.rl.addWidget(self._acw)
            self.rl.addWidget(self._sgw); self.rl.addStretch()
            self._show_empty(); self.status.setText("")

    def _do_search(self):
        q = self.search.text().strip()
        if not q: return

        # ── "? question" → Ask AI mode ──
        if q.startswith("?"):
            question = q[1:].strip()
            if not question: return
            self._ask_ai(question)
            return

        # ── normal search ──
        self._dismiss_ai_panel()
        if self._idx_count == 0 and not self._indexing:
            self.status.setText("Index empty — waiting for indexing…"); return
        self.status.setText("Searching…")
        cfg = self._svc.get_config()
        self._st = SearchThread(self._svc, q, cfg.get("top_k", 20))
        self._st.results.connect(self._on_results)
        self._st.error.connect(lambda e: self.status.setText(f"Error: {e}"))
        self._st.start()

    def _on_results(self, hits):
        self._all = hits; self._filter()

    # ── AI BRAIN ─────────────────────────────────────────────
    def _ask_ai(self, question: str):
        """Search for relevant files, then ask Ollama about them."""
        self.status.setText("🧠 Encyl is reading your files…")
        # First, search for relevant files
        cfg = self._svc.get_config()
        try:
            from core.search.semantic_search import SemanticSearch
            hits = SemanticSearch().search(question, top_k=cfg.get("top_k", 10))
        except Exception:
            hits = []

        if not hits:
            self.status.setText("No files found for AI context")
            return

        # Show search results AND ask AI
        self._all = hits
        self._filter()

        self.status.setText("🧠 Encyl is thinking…")
        self._ait = AskAIThread(question, hits)
        self._ait.answer.connect(lambda ans: self._show_ai_answer(question, ans))
        self._ait.error.connect(self._handle_encyl_error)
        self._ait.start()

    def _summarize_selected(self):
        """Summarize the currently selected file via Ollama."""
        if not (0 <= self._sel < len(self._rows)):
            self.status.setText("Select a file first, then press Tab to summarize")
            return
        # Check Encyl availability
        ai = get_ollama()
        ai.reset_availability()  # force re-check
        if not ai.is_available():
            self.status.setText("⚠ Encyl offline — run 'ollama serve' in terminal")
            self.ai_lbl.setText("🧠 ✗")
            self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.14); background: transparent; margin-left: 8px;")
            return
        # Update status to show it's connected
        self.ai_lbl.setText("🧠 Encyl")
        self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(52,199,89,0.7); background: transparent; margin-left: 8px;")

        path = self._rows[self._sel]._path
        self.status.setText(f"🧠 Encyl is summarizing {Path(path).name}…")
        self._smt = SummarizeThread(path)
        self._smt.summary.connect(self._show_ai_summary)
        self._smt.error.connect(self._handle_encyl_error)
        self._smt.start()

    def _show_ai_answer(self, question: str, answer: str):
        """Display AI answer in a panel above results."""
        self._dismiss_ai_panel()
        self._ai_panel = QFrame(self.rw)
        self._ai_panel.setStyleSheet(f"""
            QFrame {{
                background: rgba(56,156,255,0.06);
                border: 1px solid rgba(56,156,255,0.18);
                border-radius: 14px;
            }}
        """)
        vb = QVBoxLayout(self._ai_panel)
        vb.setContentsMargins(18, 14, 18, 14)
        vb.setSpacing(8)

        # header
        hdr = QHBoxLayout()
        hl = QLabel("🧠 Encyl Answer")
        hl.setStyleSheet(f"font-family: {FN}; font-size: 11px; font-weight: 700; color: #65B8FF; background: transparent;")
        hdr.addWidget(hl)
        hdr.addStretch()
        x = QLabel("✕"); x.setFixedSize(22, 22)
        x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.4); background: rgba(255,255,255,0.06); border-radius: 4px;")
        x.mousePressEvent = lambda e: self._dismiss_ai_panel()
        hdr.addWidget(x)
        vb.addLayout(hdr)

        # question
        ql = QLabel(f'" {question} "')
        ql.setWordWrap(True)
        ql.setStyleSheet(f"font-family: {FN}; font-size: 11px; font-style: italic; color: rgba(255,255,255,0.40); background: transparent;")
        vb.addWidget(ql)

        # answer
        al = QLabel(answer)
        al.setWordWrap(True)
        al.setStyleSheet(f"font-family: {FN}; font-size: 12.5px; font-weight: 400; color: rgba(255,255,255,0.85); background: transparent; line-height: 1.5;")
        al.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        vb.addWidget(al)

        # insert at top of results layout
        self.rl.insertWidget(0, self._ai_panel)
        self.status.setText(f'🧠 Encyl answered "{question[:40]}…"')

    def _show_ai_summary(self, path: str, summary: str):
        """Display AI summary for a single file."""
        self._dismiss_ai_panel()
        name = Path(path).name
        self._ai_panel = QFrame(self.rw)
        self._ai_panel.setStyleSheet(f"""
            QFrame {{
                background: rgba(52,199,89,0.06);
                border: 1px solid rgba(52,199,89,0.18);
                border-radius: 14px;
            }}
        """)
        vb = QVBoxLayout(self._ai_panel)
        vb.setContentsMargins(18, 14, 18, 14)
        vb.setSpacing(8)

        hdr = QHBoxLayout()
        hl = QLabel(f"🧠 Encyl Summary — {name}")
        hl.setStyleSheet(f"font-family: {FN}; font-size: 11px; font-weight: 700; color: #4ADE80; background: transparent;")
        hdr.addWidget(hl)
        hdr.addStretch()
        x = QLabel("✕"); x.setFixedSize(22, 22)
        x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.4); background: rgba(255,255,255,0.06); border-radius: 4px;")
        x.mousePressEvent = lambda e: self._dismiss_ai_panel()
        hdr.addWidget(x)
        vb.addLayout(hdr)

        al = QLabel(summary)
        al.setWordWrap(True)
        al.setStyleSheet(f"font-family: {FN}; font-size: 12.5px; font-weight: 400; color: rgba(255,255,255,0.85); background: transparent; line-height: 1.5;")
        al.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        vb.addWidget(al)

        self.rl.insertWidget(0, self._ai_panel)
        self.status.setText(f"🧠 Encyl summarized {name}")

    def _dismiss_ai_panel(self):
        if self._ai_panel:
            self._ai_panel.hide()
            self._ai_panel.deleteLater()
            self._ai_panel = None

    def _handle_encyl_error(self, error_msg: str):
        """User-friendly error messages for Encyl failures."""
        if "timed out" in error_msg.lower():
            self.status.setText("⏳ Encyl is warming up — try again in a few seconds")
        elif "not running" in error_msg.lower() or "connection" in error_msg.lower():
            self.status.setText("⚠ Encyl offline — run 'ollama serve' in terminal")
            self.ai_lbl.setText("🧠 ✗")
            self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.14); background: transparent; margin-left: 8px;")
        else:
            self.status.setText(f"⚠ Encyl error: {error_msg[:60]}")

    # ── file open ────────────────────────────────────────────
    def _open(self, path):
        if not path or not Path(path).exists():
            self.status.setText(f"Not found: {path}"); return
        try:
            self._svc.record_file_open(path)
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
            self._hide()
        except Exception as e:
            self.status.setText(f"Open failed: {e}")

    def _open_sel(self):
        if 0 <= self._sel < len(self._rows):
            self._open(self._rows[self._sel]._path)

    def _copy_sel(self):
        if 0 <= self._sel < len(self._rows):
            p = self._rows[self._sel]._path
            QApplication.clipboard().setText(p)
            self.status.setText(f"Copied: {p}")

    # ── keyboard nav ─────────────────────────────────────────
    def _move(self, d):
        if not self._rows: return
        old = self._sel
        if 0 <= old < len(self._rows): self._rows[old].set_selected(False)
        nw = max(0, min(len(self._rows)-1, old + d))
        self._sel = nw; self._rows[nw].set_selected(True)
        self.scroll.ensureWidgetVisible(self._rows[nw])

    # ── show / hide / toggle ─────────────────────────────────
    def toggle_panel(self):
        if self._vis: self._hide()
        else:         self._show()

    def _resize_to_screen(self):
        """Compute panel size from available screen — 90% height, capped at H."""
        scr = QGuiApplication.primaryScreen()
        if scr:
            avail = scr.availableGeometry()
            ph = min(H, int(avail.height() * 0.90))
            pw = min(W, int(avail.width() * 0.92))
        else:
            ph, pw = H, W
        self.setFixedSize(pw, ph)

    def _show(self):
        self._resize_to_screen()
        scr = QGuiApplication.primaryScreen()
        pw, ph = self.width(), self.height()
        if scr:
            g = scr.availableGeometry()
            self.move(g.x() + (g.width() - pw) // 2, g.y() + (g.height() - ph) // 2)
        self.setWindowOpacity(0.0)
        self.show(); self.activateWindow()
        self.search.setFocus(); self.search.selectAll()
        if platform.system() == "Windows":
            QTimer.singleShot(30, self._acrylic)
        self._fade.stop()
        self._fade.setStartValue(0.0); self._fade.setEndValue(1.0)
        self._fade.start()
        self._vis = True

    def _hide(self):
        self._close_settings()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._on_hidden)
        self._fade.start()
        self._vis = False

    def _on_hidden(self):
        self.hide()
        try: self._fade.finished.disconnect(self._on_hidden)
        except: pass


    # NOTE: No changeEvent override — panel stays until Shift+Space or Esc.
    # This is intentional: the user explicitly requested persistent overlay.

    # ── Tab intercept (Qt steals Tab before keyPressEvent) ─────
    def event(self, e):
        """Override event() to catch Tab key before Qt uses it for focus cycling."""
        from PyQt6.QtCore import QEvent
        if e.type() == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Tab:
                self._summarize_selected()
                return True
        return super().event(e)

    def keyPressEvent(self, e):
        k, m = e.key(), e.modifiers()
        if   k == Qt.Key.Key_Escape:                          self._hide()
        elif k == Qt.Key.Key_Down:                             self._move(1)
        elif k == Qt.Key.Key_Up:                               self._move(-1)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):       self._open_sel()
        elif k == Qt.Key.Key_I and m & Qt.KeyboardModifier.ControlModifier: self._summarize_selected()
        elif k == Qt.Key.Key_C and m & Qt.KeyboardModifier.ControlModifier: self._copy_sel()
        elif k == Qt.Key.Key_R and m & Qt.KeyboardModifier.ControlModifier: self._reindex()
        elif k == Qt.Key.Key_O and m & Qt.KeyboardModifier.ControlModifier: self._action("add_path")
        elif k == Qt.Key.Key_Comma and m & Qt.KeyboardModifier.ControlModifier: self._toggle_settings()
        else: super().keyPressEvent(e)

    def _quit(self):
        try: ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except: pass
        self._tray.hide(); QApplication.quit()

    # ── DWM Acrylic ──────────────────────────────────────────
    def _acrylic(self):
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            class MARGINS(ctypes.Structure):
                _fields_ = [("l",ctypes.c_int),("r",ctypes.c_int),
                            ("t",ctypes.c_int),("b",ctypes.c_int)]
            dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(-1,-1,-1,-1)))
            for attr, val in [(20,1),(33,2)]:
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
            for bd in (4, 3, 2):
                v = ctypes.c_int(bd)
                if dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(v), ctypes.sizeof(v)) == 0:
                    return
            class ACCENT(ctypes.Structure):
                _fields_ = [("s",ctypes.c_int),("f",ctypes.c_int),
                            ("c",ctypes.c_uint),("a",ctypes.c_int)]
            class WCA(ctypes.Structure):
                _fields_ = [("a",ctypes.c_int),("d",ctypes.POINTER(ACCENT)),
                            ("sz",ctypes.c_uint)]
            ac = ACCENT(4, 2, 0x12000000, 0)
            ctypes.windll.user32.SetWindowCompositionAttribute(
                hwnd, ctypes.byref(WCA(19, ctypes.pointer(ac), ctypes.sizeof(ac))))
        except Exception as e:
            logger.warning(f"Acrylic: {e}")

"""
Neuron â€” AI File Intelligence Panel (PyQt6)  Â·  Windows 11 Explorer Edition
============================================================================
Windows 11 dark theme explorer with Encyl AI summarization.
Shift+Space to toggle.  Keyboard navigation.  Win11-native design language.
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
    QGridLayout, QProgressBar, QCheckBox,
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
from PyQt6.QtWidgets import QFileIconProvider
from PyQt6.QtCore import QFileInfo
from services.ollama_service import get_ollama
from ui.memory_lane_panel import MemoryLanePanel
from ui.memoryos_panel import MemoryOSPanel
from ui.activity_panel import ActivityPanel
from ui.icons import icon_pixmap, icon_label

# â”€â”€ resolve assets path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_ICON   = _ASSETS / "neuron_icon.ico" if (_ASSETS / "neuron_icon.ico").exists() else _ASSETS / "icon.ico"

# â”€â”€ Windows shell icon provider (real file icons) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_FILE_ICON_PROVIDER = None

def _get_shell_icon(file_path: str, size: int = 16) -> QPixmap:
    """Get the actual Windows shell icon for a file (what Explorer shows)."""
    global _FILE_ICON_PROVIDER
    try:
        if _FILE_ICON_PROVIDER is None:
            _FILE_ICON_PROVIDER = QFileIconProvider()
        fi = QFileInfo(file_path)
        icon = _FILE_ICON_PROVIDER.icon(fi)
        return icon.pixmap(QSize(size, size))
    except Exception:
        return QPixmap()
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DESIGN CONSTANTS  â€”  Windows 11 Explorer visual language
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
W, H = 920, 720
R = 8                          # corner radius (Win11 uses subtle rounding)

HOTKEY_ID = 0xBFFF
FALLBACK_HOTKEY_ID = 0xBFFD
MOD_SHIFT = 0x0004
MOD_CTRL  = 0x0002
VK_SPACE  = 0x20
VK_R      = 0x52
VK_SHIFT  = 0x10
VK_CTRL   = 0x11
WM_HOTKEY = 0x0312

# â”€â”€ colour tokens â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class C:
    """Central palette â€“ Windows 11 dark theme."""
    # -- panel chrome (Win11 dark) -------
    PANEL_BG       = QColor(25, 25, 25, 245)         # #191919
    PANEL_BORDER   = QColor(51, 51, 51, 200)
    TOP_SHEEN      = QColor(255, 255, 255, 4)
    # -- search bar ---------
    SEARCH_BG      = QColor(255, 255, 255, 8)
    SEARCH_BORDER  = QColor(255, 255, 255, 10)
    SEARCH_GLOW    = QColor(0, 120, 212, 80)         # Win11 accent blue
    # -- content text -------
    T1  = QColor(255, 255, 255, 235)                 # primary
    T2  = QColor(153, 153, 153, 255)                 # secondary #999
    T3  = QColor(102, 102, 102, 255)                 # tertiary #666
    T4  = QColor(255, 255, 255, 36)                  # quaternary
    # -- accents (Win11) ----
    BLUE           = "#0078D4"
    BLUE_Q         = QColor(0, 120, 212)
    BLUE_DIM       = QColor(0, 120, 212, 50)
    BLUE_GLOW      = QColor(0, 120, 212, 50)
    GREEN          = QColor(52, 199, 89)
    # -- surface (Win11) ----
    CARD_IDLE      = QColor(255, 255, 255, 0)
    CARD_HOVER     = QColor(45, 45, 45, 255)         # #2D2D2D
    CARD_SELECTED  = QColor(0, 120, 212, 50)
    CARD_SEL_BDR   = QColor(0, 120, 212, 90)
    DIVIDER        = QColor(51, 51, 51, 255)          # #333

FN  = "'Segoe UI Variable Display', 'Segoe UI', 'Inter', system-ui, sans-serif"
MN  = "'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"

# â”€â”€ file icon map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_I = {
    ".py":("code","#3B82F6","PY"),   ".ipynb":("notebook","#8B5CF6","NB"),
    ".js":("zap","#EAB308","JS"),   ".ts":("code","#3B82F6","TS"),
    ".jsx":("atom","#22D3EE","JSX"), ".tsx":("atom","#3B82F6","TSX"),
    ".rs":("code","#E57A44","RS"),   ".go":("code","#00ADD8","GO"),
    ".java":("coffee","#F59E0B","JV"),  ".cpp":("settings","#60A5FA","C++"),
    ".c":("settings","#94A3B8","C"),     ".h":("settings","#94A3B8","H"),
    ".cs":("code","#A78BFA","C#"),   ".rb":("diamond","#EF4444","RB"),
    ".php":("code","#A78BFA","PHP"), ".swift":("zap","#F97316","SW"),
    ".kt":("code","#A855F6","KT"),   ".html":("globe","#EF4444","HTM"),
    ".css":("palette","#38BDF8","CSS"), ".md":("file-text","#94A3B8","MD"),
    ".txt":("file-text","#94A3B8","TXT"), ".log":("clipboard","#94A3B8","LOG"),
    ".pdf":("file-text","#EF4444","PDF"), ".docx":("book-open","#2563EB","DOC"),
    ".doc":("book-open","#2563EB","DOC"), ".xlsx":("bar-chart-2","#22C55E","XLS"),
    ".xls":("bar-chart-2","#22C55E","XLS"), ".csv":("bar-chart-2","#22C55E","CSV"),
    ".pptx":("bar-chart-2","#F97316","PPT"),
    ".json":("hash","#F5B74A","JSON"), ".xml":("code","#F5B74A","XML"),
    ".yaml":("wrench","#A78BFA","YML"), ".yml":("wrench","#A78BFA","YML"),
    ".toml":("wrench","#A78BFA","TML"), ".env":("lock","#A78BFA","ENV"),
    ".ini":("wrench","#94A3B8","INI"), ".cfg":("wrench","#94A3B8","CFG"),
    ".mp4":("film","#A855F6","MP4"), ".mkv":("film","#A855F6","MKV"),
    ".avi":("film","#A855F6","AVI"), ".mov":("film","#A855F6","MOV"),
    ".png":("image","#EC4899","PNG"),  ".jpg":("image","#EC4899","JPG"),
    ".jpeg":("image","#EC4899","JPG"), ".gif":("image","#EC4899","GIF"),
    ".webp":("image","#EC4899","WBP"),
    ".zip":("package","#FBBF24","ZIP"), ".exe":("terminal","#A78BFA","EXE"),
}
_D = ("file","#64748B","FILE")

SCOPES = {
    "all": None, "files": None, "folders": "__dir__",
    "code": {".py",".js",".ts",".jsx",".tsx",".rs",".go",".java",".cpp",
             ".c",".h",".cs",".rb",".php",".swift",".kt",".html",".css"},
    "docs": {".md",".txt",".pdf",".docx",".doc",".pptx",".xlsx",".xls",".csv"},
    "media":{".mp4",".mkv",".avi",".mov",".png",".jpg",".jpeg",".gif",".webp",".webm"},
    "memoryos": "__memoryos__",
    "activity": "__activity__",
}

def _icon(ext: str):
    return _I.get(ext.lower(), _D)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Win32 native hotkey listener
# BUG5-FIX: uses proper ctypes.Structure MSG struct
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
import ctypes as _ct

class _MSG(_ct.Structure):
    """Correct Win32 MSG struct â€” avoids MSVC/MinGW padding fragility."""
    _fields_ = [
        ("hwnd",    _ct.c_void_p),
        ("message", _ct.c_uint),
        ("wParam",  _ct.c_ulonglong),
        ("lParam",  _ct.c_longlong),
        ("time",    _ct.c_ulong),
        ("pt_x",    _ct.c_long),
        ("pt_y",    _ct.c_long),
    ]

class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(
        self,
        cb,
        hotkey_id=None,
        virtual_key=VK_SPACE,
        modifier_keys=None,
        debounce_ms=250,
    ):
        super().__init__()
        self._cb = cb
        self._hotkey_id = hotkey_id if hotkey_id is not None else HOTKEY_ID
        self._virtual_key = virtual_key
        self._modifier_keys = list(modifier_keys or [VK_SHIFT])
        self._debounce_s = max(0.05, debounce_ms / 1000.0)
        self._last_fire = 0.0
        self._armed = True
        self._rearm_scheduled = False

    def nativeEventFilter(self, et, msg):
        if et in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                m = _ct.cast(int(msg), _ct.POINTER(_MSG)).contents
                if m.message == WM_HOTKEY and m.wParam == self._hotkey_id:
                    if not self._armed or (time.monotonic() - self._last_fire) < self._debounce_s:
                        self._schedule_rearm()
                        return True, 0
                    self._armed = False
                    self._last_fire = time.monotonic()
                    self._cb()
                    self._schedule_rearm()
                    return True, 0
            except Exception:
                pass
        return False, 0

    def _schedule_rearm(self):
        if self._rearm_scheduled:
            return
        self._rearm_scheduled = True
        QTimer.singleShot(80, self._maybe_rearm)

    def _maybe_rearm(self):
        self._rearm_scheduled = False
        if self._keys_still_down():
            self._schedule_rearm()
            return
        self._armed = True

    def _keys_still_down(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            user32 = _ct.windll.user32
            keys = [self._virtual_key, *self._modifier_keys]
            return any(user32.GetAsyncKeyState(key) & 0x8000 for key in keys)
        except Exception:
            return False


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Background workers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
    def __init__(self, svc, q, k=20, use_llm=False):
        super().__init__()
        self._s, self._q, self._k, self._llm = svc, q, k, use_llm
    def run(self):
        try:    self.results.emit(self._s.search(self._q, self._k, use_llm_rerank=self._llm))
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Micro-widgets
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# â”€â”€ animated blue-glow search field â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class GlowSearchBar(QFrame):
    """Windows 11 compact search bar â€” clean, professional."""
    textChanged = pyqtSignal(str)
    returnPressed = pyqtSignal()
    tabPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("GlowSearch")

        # subtle focus glow
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
        self._glow.setColor(C.SEARCH_GLOW)
        self.setGraphicsEffect(self._glow)

        self._glow_anim = QPropertyAnimation(self._glow, b"blurRadius")
        self._glow_anim.setDuration(300)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setStyleSheet(f"""
            #GlowSearch {{
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 4px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)

        # the actual input â€” clean, no emoji
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Search")
        self.inp.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                color: rgba(255,255,255,0.90);
                font-family: {FN}; font-size: 13px; font-weight: 400;
                padding: 0;
                selection-background-color: rgba(0,120,212,0.30);
            }}
            QLineEdit::placeholder {{
                color: rgba(255,255,255,0.30); font-weight: 400;
            }}
        """)
        self.inp.textChanged.connect(self.textChanged.emit)
        self.inp.returnPressed.connect(self.returnPressed.emit)
        lay.addWidget(self.inp, 1)

        # search icon (Segoe Fluent Icons â€” same as Win11 Explorer)
        search_icon = QLabel("\uE721")
        search_icon.setFixedWidth(20)
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_icon.setStyleSheet("font-family: 'Segoe Fluent Icons'; font-size: 12px; color: rgba(255,255,255,0.35); background: transparent;")
        lay.addWidget(search_icon)

        # wire focus events
        self.inp.installEventFilter(self)

    # forward focus helpers
    def text(self):          return self.inp.text()
    def setFocus(self):      self.inp.setFocus()
    def selectAll(self):     self.inp.selectAll()
    def clear(self):         self.inp.clear()

    def eventFilter(self, obj, ev):
        if obj is self.inp:
            # â”€â”€ Intercept Tab key for Encyl summarize â”€â”€
            if ev.type() == ev.Type.KeyPress:
                key = ev.key()
                if key == Qt.Key.Key_Tab:
                    self.tabPressed.emit()
                    return True  # consume the event
                elif key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Escape):
                    # Forward navigation keys to parent panel
                    parent = self.parent()
                    while parent and not hasattr(parent, 'keyPressEvent'):
                        parent = parent.parent()
                    if parent:
                        parent.keyPressEvent(ev)
                        return True
            elif ev.type() == ev.Type.FocusIn:
                self.setStyleSheet(f"""
                    #GlowSearch {{
                        background: rgba(255,255,255,0.08);
                        border: 1px solid rgba(0,120,212,0.50);
                        border-radius: 4px;
                    }}
                """)
                self._glow_anim.stop()
                self._glow_anim.setStartValue(0)
                self._glow_anim.setEndValue(32)
                self._glow_anim.start()
            elif ev.type() == ev.Type.FocusOut:
                self.setStyleSheet(f"""
                    #GlowSearch {{
                        background: rgba(255,255,255,0.06);
                        border: 1px solid rgba(255,255,255,0.08);
                        border-radius: 4px;
                    }}
                """)
                self._glow_anim.stop()
                self._glow_anim.setStartValue(self._glow.blurRadius())
                self._glow_anim.setEndValue(0)
                self._glow_anim.start()
        return False


# â”€â”€ scope pill â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ column header (Win11 style) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ColumnHeader(QFrame):
    """Windows 11 File Explorer column header bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(f"""
            ColumnHeader {{
                background: rgba(255,255,255,0.02);
                border-bottom: 1px solid #333;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(0)

        cols = [("Name", 320), ("Date modified", 160), ("Type", 140), ("Size", 80)]
        for label, w in cols:
            lbl = QLabel(label)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet(f"""
                font-family: {FN}; font-size: 11px; font-weight: 600;
                color: rgba(255,255,255,0.50); background: transparent;
                padding-left: 4px;
            """)
            lay.addWidget(lbl)
        lay.addStretch()


# â”€â”€ category header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class CatHeader(QFrame):
    def __init__(self, title, count=0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 2)
        t = QLabel(title.upper())
        t.setStyleSheet(f"""
            font-family: {FN}; font-size: 10px; font-weight: 700;
            letter-spacing: 1px; color: rgba(255,255,255,0.25);
            background: transparent;
        """)
        lay.addWidget(t)
        lay.addStretch()
        if count > 0:
            c = QLabel(f"{count} results")
            c.setStyleSheet(f"font-size: 10px; color: rgba(255,255,255,0.14); background: transparent;")
            lay.addWidget(c)


# â”€â”€ helper: get file metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _file_meta(path_str):
    """Get date modified, type name, size for a file."""
    p = Path(path_str)
    ext = p.suffix.lower()
    # Type name
    _type_names = {
        ".py":"Python File",".js":"JavaScript",".ts":"TypeScript",".html":"HTML Document",
        ".css":"Stylesheet",".json":"JSON File",".md":"Markdown",".txt":"Text File",
        ".pdf":"PDF Document",".docx":"DOCX Document",".doc":"DOC Document",
        ".pptx":"PPTX Presentation",".xlsx":"Excel Spreadsheet",".xls":"Excel Spreadsheet",
        ".csv":"CSV File",".mp4":"MP4 Video",".mkv":"MKV Video",".avi":"AVI Video",
        ".mov":"MOV Video",".webm":"WebM Video",".png":"PNG Image",".jpg":"JPEG Image",
        ".jpeg":"JPEG Image",".gif":"GIF Image",".wav":"WAV Audio",".mp3":"MP3 Audio",
        ".zip":"ZIP Archive",".exe":"Application",".env":"Environment File",
        ".ini":"Configuration",".xml":"XML File",".log":"Log File",
        ".java":"Java File",".cpp":"C++ File",".c":"C File",".go":"Go File",
        ".rs":"Rust File",".yaml":"YAML File",".yml":"YAML File",".toml":"TOML File",
    }
    type_name = _type_names.get(ext, f"{ext[1:].upper()} File" if ext else "File")
    # Date + size
    try:
        stat = p.stat()
        from datetime import datetime
        date_str = datetime.fromtimestamp(stat.st_mtime).strftime("%d-%m-%Y %H:%M")
        size = stat.st_size
        if size < 1024: size_str = f"{size} B"
        elif size < 1024**2: size_str = f"{size//1024:,} KB"
        elif size < 1024**3: size_str = f"{size/1024**2:.1f} MB"
        else: size_str = f"{size/1024**3:.1f} GB"
    except Exception:
        date_str = "â€”"
        size_str = "â€”"
    return date_str, type_name, size_str


# â”€â”€ result row (Win11 Explorer style) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ResultRow(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, hit, top=False, parent=None):
        super().__init__(parent)
        self._path = hit.get("path", "")
        ext = hit.get("extension", Path(self._path).suffix).lower()
        icon_name, accent, badge = _icon(ext)
        name = hit.get("name", Path(self._path).name)
        self._sel = False

        h = 30
        self.setFixedHeight(h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply(False, False)

        # Get file metadata
        date_str, type_name, size_str = _file_meta(self._path)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 0, 12, 0)
        root.setSpacing(0)

        # â”€â”€ Icon (real Windows shell icon) â”€â”€
        ic = QLabel()
        ic.setFixedSize(20, 20)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background: transparent; padding: 0; margin: 0;")
        pixmap = _get_shell_icon(self._path, 16)
        if not pixmap.isNull():
            ic.setPixmap(pixmap)
        else:
            ic.setPixmap(icon_pixmap(icon_name, 16, accent))
        root.addWidget(ic)

        # â”€â”€ Name column (320px) â”€â”€
        nl = QLabel(name)
        nl.setFixedWidth(298)
        nl.setStyleSheet(f"""
            font-family: {FN}; font-size: 12px; font-weight: {'600' if top else '400'};
            color: {'#60CDFF' if top else 'rgba(255,255,255,0.88)'}; background: transparent;
            padding-left: 6px;
        """)
        root.addWidget(nl)

        # â”€â”€ Date modified column (160px) â”€â”€
        dl = QLabel(date_str)
        dl.setFixedWidth(160)
        dl.setStyleSheet(f"""
            font-family: {FN}; font-size: 11px; font-weight: 400;
            color: rgba(255,255,255,0.45); background: transparent;
            padding-left: 4px;
        """)
        root.addWidget(dl)

        # â”€â”€ Type column (140px) â”€â”€
        tl = QLabel(type_name)
        tl.setFixedWidth(140)
        tl.setStyleSheet(f"""
            font-family: {FN}; font-size: 11px; font-weight: 400;
            color: rgba(255,255,255,0.45); background: transparent;
            padding-left: 4px;
        """)
        root.addWidget(tl)

        # â”€â”€ Size column (80px) â”€â”€
        szl = QLabel(size_str)
        szl.setFixedWidth(80)
        szl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        szl.setStyleSheet(f"""
            font-family: {FN}; font-size: 11px; font-weight: 400;
            color: rgba(255,255,255,0.40); background: transparent;
        """)
        root.addWidget(szl)
        root.addStretch()

    # â”€â”€ state management (Win11 selection colors) â”€â”€
    def _apply(self, sel, hov):
        if sel:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: rgba(0,120,212,0.25);
                    border: 1px solid rgba(0,120,212,0.40);
                    border-radius: 4px;
                }}
            """)
        elif hov:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: rgba(255,255,255,0.04);
                    border: 1px solid transparent;
                    border-radius: 4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ResultRow {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
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
        elif e.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(e.globalPosition().toPoint())

    def _show_context_menu(self, pos):
        """Full Windows 11 context menu â€” uses Segoe Fluent Icons (system icons)."""
        # â”€â”€ Segoe Fluent Icons codepoints (same as Windows 11 Explorer) â”€â”€
        SFI = "Segoe Fluent Icons"
        ICO_CUT     = "\uE8C6"
        ICO_COPY    = "\uE8C8"
        ICO_RENAME  = "\uE8AC"
        ICO_SHARE   = "\uE72D"
        ICO_DELETE  = "\uE74D"
        ICO_OPEN    = "\uE8E5"
        ICO_OPENWITH= "\uE17D"
        ICO_FOLDER  = "\uE8B7"
        ICO_PROPS   = "\uE946"
        ICO_STAR    = "\uE734"
        ICO_COMPRESS= "\uE7B8"
        ICO_LINK    = "\uE71B"
        ICO_ADMIN   = "\uE7EF"
        ICO_MORE    = "\uE712"
        ICO_COPYPATH= "\uE8C8"
        ICO_BRAIN   = "\uE945"
        ICO_EDIT    = "\uE70F"

        def _fluent_icon(codepoint, size=14, color="rgba(255,255,255,0.80)"):
            """Render a Segoe Fluent Icons glyph to QIcon."""
            px = QPixmap(size + 4, size + 4)
            px.fill(QColor(0, 0, 0, 0))
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            font = QFont(SFI, size)
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, codepoint)
            p.end()
            return QIcon(px)

        menu = QMenu(self)
        menu_css = f"""
            QMenu {{
                background: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 8px;
                padding: 4px 0;
                font-family: {FN};
                font-size: 12px;
                min-width: 280px;
            }}
            QMenu::item {{
                padding: 7px 16px 7px 8px;
                color: rgba(255,255,255,0.90);
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.06);
            }}
            QMenu::separator {{
                height: 1px;
                background: #3D3D3D;
                margin: 4px 12px;
            }}
            QMenu::item:disabled {{
                color: rgba(255,255,255,0.25);
            }}
        """
        menu.setStyleSheet(menu_css)

        # â”€â”€ Top toolbar: Cut | Copy | Rename | Share | Delete â”€â”€
        from PyQt6.QtWidgets import QWidgetAction
        toolbar = QFrame()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet("background: transparent; border: none;")
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(16, 4, 16, 4)
        tb_lay.setSpacing(2)

        tb_btn_css = f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 6px;
                color: rgba(255,255,255,0.75); font-family: {FN};
                font-size: 10px; padding: 4px 2px;
                min-width: 48px; min-height: 42px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.06); }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.03); }}
        """

        def _make_tb_btn(icon_char, label, callback):
            btn = QPushButton()
            btn_lay = QVBoxLayout(btn)
            btn_lay.setContentsMargins(0, 2, 0, 2)
            btn_lay.setSpacing(2)
            sym = QLabel(icon_char)
            sym.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sym.setStyleSheet(f"font-family: '{SFI}'; font-size: 14px; color: rgba(255,255,255,0.75); background: transparent;")
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"font-family: {FN}; font-size: 9px; color: rgba(255,255,255,0.50); background: transparent;")
            btn_lay.addWidget(sym)
            btn_lay.addWidget(lbl)
            btn.setStyleSheet(tb_btn_css)
            btn.clicked.connect(callback)
            btn.clicked.connect(menu.close)
            return btn

        tb_lay.addWidget(_make_tb_btn(ICO_CUT, "Cut", self._cut_file))
        tb_lay.addWidget(_make_tb_btn(ICO_COPY, "Copy", self._copy_file))
        tb_lay.addWidget(_make_tb_btn(ICO_RENAME, "Rename", self._rename_file))
        tb_lay.addWidget(_make_tb_btn(ICO_SHARE, "Share", self._share_file))
        tb_lay.addWidget(_make_tb_btn(ICO_DELETE, "Delete", self._delete_file))

        toolbar_action = QWidgetAction(menu)
        toolbar_action.setDefaultWidget(toolbar)
        menu.addAction(toolbar_action)

        menu.addSeparator()

        # â”€â”€ Open (with file's own shell icon) â”€â”€
        file_icon = QIcon()
        pixmap = _get_shell_icon(self._path, 16)
        if not pixmap.isNull():
            file_icon = QIcon(pixmap)
        a_open = menu.addAction(file_icon, "Open")
        a_open.setShortcut("Enter")
        a_open.triggered.connect(lambda: self.clicked.emit(self._path))

        # â”€â”€ Open with â†’ submenu â”€â”€
        open_with = menu.addMenu("Open with")
        open_with.setIcon(_fluent_icon(ICO_OPENWITH))
        open_with.setStyleSheet(menu_css)
        a_notepad = open_with.addAction("Notepad")
        a_notepad.triggered.connect(lambda: subprocess.Popen(["notepad.exe", self._path]))
        a_choose = open_with.addAction("Choose another app")
        a_choose.triggered.connect(self._open_with_dialog)

        # â”€â”€ Open file location â”€â”€
        a_folder = menu.addAction(_fluent_icon(ICO_FOLDER), "Open file location")
        a_folder.triggered.connect(self._open_location)

        ext = Path(self._path).suffix.lower()
        if ext == ".exe":
            menu.addSeparator()
            a_admin = menu.addAction(_fluent_icon(ICO_ADMIN), "Run as administrator")
            a_admin.triggered.connect(self._run_as_admin)

        menu.addSeparator()

        # â”€â”€ Add to Favorites â”€â”€
        a_fav = menu.addAction(_fluent_icon(ICO_STAR), "Add to Favorites")
        a_fav.setEnabled(False)  # placeholder

        # â”€â”€ Compress to... â”€â”€
        a_compress = menu.addAction(_fluent_icon(ICO_COMPRESS), "Compress to...")
        a_compress.setEnabled(False)  # placeholder

        # â”€â”€ Copy as path â”€â”€
        a_copy_path = menu.addAction(_fluent_icon(ICO_LINK), "Copy as path")
        a_copy_path.setShortcut("Ctrl+Shift+C")
        a_copy_path.triggered.connect(self._copy_path)

        # â”€â”€ Properties â”€â”€
        a_props = menu.addAction(_fluent_icon(ICO_PROPS), "Properties")
        a_props.setShortcut("Alt+Enter")
        a_props.triggered.connect(self._show_properties)

        menu.addSeparator()

        # â”€â”€ Summarize with Encyl (Neuron exclusive) â”€â”€
        a_encyl = menu.addAction(_fluent_icon(ICO_BRAIN), "Summarize with Encyl")
        a_encyl.triggered.connect(lambda: self._trigger_encyl())

        # â”€â”€ Edit in Notepad â”€â”€
        a_edit = menu.addAction(_fluent_icon(ICO_EDIT), "Edit in Notepad")
        a_edit.triggered.connect(lambda: subprocess.Popen(["notepad.exe", self._path]))

        menu.addSeparator()

        # â”€â”€ Show more options â”€â”€
        a_more = menu.addAction(_fluent_icon(ICO_MORE), "Show more options")
        a_more.triggered.connect(self._show_legacy_menu)

        menu.exec(pos)

    # â”€â”€ Context menu action handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _trigger_encyl(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, '_summarize_selected'):
                parent._summarize_selected()
                break
            parent = parent.parent()

    def _open_location(self):
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{self._path}"')

    def _copy_path(self):
        QApplication.clipboard().setText(self._path)

    def _copy_name(self):
        QApplication.clipboard().setText(Path(self._path).name)

    def _copy_file(self):
        """Copy file to clipboard (Windows shell clipboard format)."""
        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     f"Set-Clipboard -Path '{self._path}'"],
                    capture_output=True, timeout=5
                )
            except Exception:
                QApplication.clipboard().setText(self._path)

    def _cut_file(self):
        """Cut = copy + mark for move (just copies path for now)."""
        self._copy_file()

    def _delete_file(self):
        """Send file to Recycle Bin using Windows shell."""
        if platform.system() == "Windows":
            try:
                import ctypes
                from ctypes import wintypes
                # Use SHFileOperation to send to recycle bin
                class SHFILEOPSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", ctypes.c_uint),
                        ("pFrom", ctypes.c_wchar_p),
                        ("pTo", ctypes.c_wchar_p),
                        ("fFlags", ctypes.c_ushort),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", ctypes.c_wchar_p),
                    ]
                FO_DELETE = 3
                FOF_ALLOWUNDO = 0x40
                FOF_NOCONFIRMATION = 0x10
                op = SHFILEOPSTRUCT()
                op.wFunc = FO_DELETE
                op.pFrom = self._path + '\0'
                op.fFlags = FOF_ALLOWUNDO  # Send to recycle bin, with confirmation
                ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            except Exception:
                pass

    def _rename_file(self):
        """Open rename dialog."""
        from PyQt6.QtWidgets import QInputDialog
        name = Path(self._path).name
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=name)
        if ok and new_name and new_name != name:
            try:
                new_path = Path(self._path).parent / new_name
                Path(self._path).rename(new_path)
            except Exception:
                pass

    def _share_file(self):
        """Open Windows Share dialog."""
        if platform.system() == "Windows":
            try:
                subprocess.Popen(
                    ["powershell", "-Command",
                     f"explorer.exe shell:sendto"],
                    shell=True
                )
            except Exception:
                pass

    def _run_as_admin(self):
        """Run executable as administrator."""
        if platform.system() == "Windows":
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", self._path, None, None, 1
                )
            except Exception:
                pass

    def _open_with_dialog(self):
        """Open Windows 'Open with' dialog."""
        if platform.system() == "Windows":
            try:
                subprocess.Popen(
                    f'rundll32.exe shell32.dll,OpenAs_RunDLL "{self._path}"'
                )
            except Exception:
                pass

    def _show_properties(self):
        """Open Windows file Properties dialog."""
        if platform.system() == "Windows":
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "properties", self._path, None, None, 1
                )
            except Exception:
                pass

    def _show_legacy_menu(self):
        """Open legacy Windows context menu (Shift+Right-click behavior)."""
        if platform.system() == "Windows":
            try:
                folder = str(Path(self._path).parent)
                subprocess.Popen(f'explorer /select,"{self._path}"')
            except Exception:
                pass


# â”€â”€ action card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ActionCard(QFrame):
    action_clicked = pyqtSignal(str)

    def __init__(self, icon_name, label, shortcut, aid, parent=None):
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
        ic = icon_label(icon_name or "activity", 20, "#60CDFF")
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


# â”€â”€ suggestion chip (for "Jump back in") â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SuggestionChip(QFrame):
    """Compact file suggestion chip with icon and truncated name."""
    clicked = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._path = file_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            SuggestionChip {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 0 12px;
            }}
            SuggestionChip:hover {{
                background: rgba(0,120,212,0.15);
                border-color: rgba(0,120,212,0.30);
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 12, 0)
        lay.setSpacing(6)

        # Icon
        ic = QLabel()
        ic.setFixedSize(16, 16)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _get_shell_icon(file_path, 16)
        if not pixmap.isNull():
            ic.setPixmap(pixmap)
        else:
            ic.setPixmap(icon_pixmap("file", 16, "#94A3B8"))
        lay.addWidget(ic)

        # Name (truncated)
        name = Path(file_path).name
        if len(name) > 30:
            name = name[:27] + "..."
        lbl = QLabel(name)
        lbl.setStyleSheet(f"""
            font-family: {FN}; font-size: 11px; font-weight: 500;
            color: rgba(255,255,255,0.75); background: transparent;
        """)
        lay.addWidget(lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)

# â”€â”€ settings overlay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        t = QLabel("Settings")
        t.setStyleSheet(f"font-family: {FN}; font-size: 18px; font-weight: 700; color: rgba(255,255,255,0.92); background: transparent;")
        hdr.addWidget(icon_label("settings", 20, "#E0E0E0"))
        hdr.addWidget(t); hdr.addStretch()
        x = icon_label("x", 16, "#C8C8C8"); x.setFixedSize(28,28)
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
        st = QLabel(f"{cnt:,} files indexed  ·  {len(ps)} watch directories")
        st.setStyleSheet(f"font-size: 12px; color: rgba(255,255,255,0.5); background: transparent;")
        root.addWidget(st)

        # watch paths
        wl = QLabel("Watch Paths")
        wl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.80); background: transparent;")
        root.addWidget(wl)
        self._pc = QVBoxLayout(); self._pc.setSpacing(3)
        for p in ps:
            l = QLabel(f"  {p}")
            l.setStyleSheet(f"font-size: 11px; color: rgba(255,255,255,0.35); background: transparent;")
            l.setMaximumWidth(550)
            self._pc.addWidget(l)
        root.addLayout(self._pc)

        # add folder
        ab = QPushButton("Add Folder")
        ab.setIcon(QIcon(icon_pixmap("folder-plus", 16, "#B8C8FF")))
        ab.setCursor(Qt.CursorShape.PointingHandCursor)
        ab.setStyleSheet(f"""
            QPushButton {{ background: rgba(255,255,255,0.04); border: 1px dashed rgba(255,255,255,0.12);
            border-radius: 10px; color: rgba(255,255,255,0.5); font-size: 12px; font-weight: 600; padding: 10px; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.8); }}
        """)
        ab.clicked.connect(self._add)
        root.addWidget(ab)

        # reindex
        rb = QPushButton("Re-index Now")
        rb.setIcon(QIcon(icon_pixmap("refresh-cw", 16, "#FFFFFF")))
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
            l = QLabel(f"  {f}")
            l.setStyleSheet(f"font-size: 11px; color: rgba(255,255,255,0.35); background: transparent;")
            self._pc.addWidget(l)
            self.paths_changed.emit()

    def _topk(self, v):
        c = self._svc.get_config(); c["top_k"] = v; self._svc.save_config(c)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# THE SPOTLIGHT PANEL  â€”  main widget
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

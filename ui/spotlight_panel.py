"""

Neuron — AI File Intelligence Panel (PyQt6)  ·  Windows 11 Explorer Edition

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

    QGridLayout, QProgressBar,

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

from PyQt6.QtWidgets import QFileIconProvider

from PyQt6.QtCore import QFileInfo

from ui.activity_panel import ActivityPanel

from ui.memory_lane_panel import MemoryLanePanel

from ui.memoryos_panel import MemoryOSPanel



from ui.icons import icon_pixmap, icon_label
from ui.icon_helpers import make_white_bg_icon
from ui.spotlight_components import (

    C, R, SCOPES, _ICON,

    IndexThread, SearchThread, AskAIThread, SummarizeThread,

    GlowSearchBar, ScopePill, ColumnHeader, CatHeader, ResultRow,

    ActionCard, SuggestionChip, SettingsOverlay,

)



# ── Module constants ─────────────────────────────────────────────────────

FN = "'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"

MN = "'Cascadia Code', 'Consolas', monospace"

_ASSETS = Path(__file__).resolve().parent.parent / "assets"



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

        self._memory_lane: MemoryLanePanel | None = None

        self._it: IndexThread | None = None

        self._st: SearchThread | None = None

        self._llm_st: SearchThread | None = None  # LLM re-rank background thread

        self._ait: AskAIThread | None = None

        self._smt: SummarizeThread | None = None

        self._ai_panel: QFrame | None = None

        self._llm_active: bool = False  # True while LLM re-ranking



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



        self._refresh_idx_count()



        # Live-refresh timer: poll idx count while service-owned indexing runs

        self._live_refresh_timer = QTimer(self)

        self._live_refresh_timer.setInterval(3000)

        self._live_refresh_timer.timeout.connect(self._refresh_idx_count)

        self._live_refresh_timer.start()



        # Pre-warm Ollama model in background (reduces first-request latency)

        try:

            ai = get_ollama()

            ai.pre_warm()

        except Exception:

            pass



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

        root.setContentsMargins(16, 14, 16, 10)

        root.setSpacing(0)



        # ── NAVIGATION BAR (Win11 style) ──

        nav = QHBoxLayout()

        nav.setSpacing(2)

        nav.setContentsMargins(0, 0, 0, 8)



        nav_btn_css = f"""

            QPushButton {{

                background: rgba(255,255,255,0.04); border: none; border-radius: 6px;

                color: rgba(255,255,255,0.55); font-size: 14px; padding: 6px;

                min-width: 32px; min-height: 28px;

            }}

            QPushButton:hover {{ background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.85); }}

            QPushButton:pressed {{ background: rgba(255,255,255,0.06); }}

            QPushButton:disabled {{ color: rgba(255,255,255,0.15); }}

        """

        self._history: list[str] = []

        self._hist_idx = -1



        self._btn_back = QPushButton("")
        self._btn_back.setIcon(QIcon(icon_pixmap("chevron-left", 16, "#D0D0D0")))

        self._btn_back.setStyleSheet(nav_btn_css)

        self._btn_back.setToolTip("Back (previous search)")

        self._btn_back.setEnabled(False)

        self._btn_back.clicked.connect(self._nav_back)

        nav.addWidget(self._btn_back)



        self._btn_fwd = QPushButton("")
        self._btn_fwd.setIcon(QIcon(icon_pixmap("chevron-right", 16, "#D0D0D0")))

        self._btn_fwd.setStyleSheet(nav_btn_css)

        self._btn_fwd.setToolTip("Forward (next search)")

        self._btn_fwd.setEnabled(False)

        self._btn_fwd.clicked.connect(self._nav_forward)

        nav.addWidget(self._btn_fwd)



        self._btn_up = QPushButton("")
        self._btn_up.setIcon(QIcon(icon_pixmap("chevron-up", 16, "#D0D0D0")))

        self._btn_up.setStyleSheet(nav_btn_css)

        self._btn_up.setToolTip("Up (clear search, show recent)")

        self._btn_up.clicked.connect(self._nav_up)

        nav.addWidget(self._btn_up)



        self._btn_refresh = QPushButton("")
        self._btn_refresh.setIcon(QIcon(icon_pixmap("refresh-cw", 16, "#D0D0D0")))

        self._btn_refresh.setStyleSheet(nav_btn_css)

        self._btn_refresh.setToolTip("Refresh (re-run search / re-index)")

        self._btn_refresh.clicked.connect(self._nav_refresh)

        nav.addWidget(self._btn_refresh)



        self._btn_memory = QPushButton("")

        self._btn_memory.setStyleSheet(nav_btn_css)

        self._btn_memory.setToolTip("Memory Lane — daily activity recap")

        self._btn_memory.clicked.connect(self._toggle_memory_lane)

        nav.addWidget(self._btn_memory)



        nav.addSpacing(12)



        # ── SEARCH BAR (right-aligned in nav) ──

        self.search = GlowSearchBar(self)

        self.search.textChanged.connect(self._on_text)

        self.search.returnPressed.connect(self._open_sel)

        self.search.tabPressed.connect(self._summarize_selected)

        nav.addWidget(self.search, 1)



        root.addLayout(nav)



        # ── ENCYL LOADING BAR (hidden by default) ──

        self._encyl_loading = QFrame()

        self._encyl_loading.setFixedHeight(36)

        self._encyl_loading.setStyleSheet(f"""

            QFrame {{

                background: rgba(0,120,212,0.08);

                border: 1px solid rgba(0,120,212,0.15);

                border-radius: 6px;

            }}

        """)

        el_lay = QHBoxLayout(self._encyl_loading)

        el_lay.setContentsMargins(12, 0, 12, 0)

        self._encyl_spinner = icon_label("refresh-cw", 16, "#0078D4")

        self._encyl_spinner.setStyleSheet(f"font-size: 14px; color: #0078D4; background: transparent;")

        el_lay.addWidget(self._encyl_spinner)

        self._encyl_status = QLabel("Encyl is reading...")

        self._encyl_status.setStyleSheet(f"font-family: {FN}; font-size: 11px; color: rgba(255,255,255,0.7); background: transparent;")

        el_lay.addWidget(self._encyl_status, 1)

        self._encyl_pbar = QFrame()

        self._encyl_pbar.setFixedSize(80, 4)

        self._encyl_pbar.setStyleSheet("background: rgba(0,120,212,0.3); border-radius: 2px;")

        el_lay.addWidget(self._encyl_pbar)

        self._encyl_loading.hide()

        root.addWidget(self._encyl_loading)



        # ── ENCYL LOADING ANIMATION TIMER ──

        self._encyl_timer = QTimer(self)

        self._encyl_timer.setInterval(2000)

        self._encyl_phase = 0

        self._encyl_phases = [

            "Reading file contents...",

            " Processing with Encyl...",

            " Generating summary...",

            " Almost done...",

        ]

        self._encyl_timer.timeout.connect(self._advance_encyl_phase)



        root.addSpacing(6)



        # ── SCOPE PILLS ──

        pr = QHBoxLayout()

        pr.setSpacing(4)

        pr.setContentsMargins(4, 0, 4, 0)

        self._pills: list[ScopePill] = []

        for label, key in [("All","all"),("Files","files"),("Folders","folders"),

                           ("Code","code"),("Docs","docs"),("Media","media"),

                           ("MemoryOS","memoryos"),

                           ("Activity","activity")]:

            pill = ScopePill(label, key, active=(key=="all"))

            pill.clicked.connect(self._set_scope)

            pr.addWidget(pill)

            self._pills.append(pill)

        pr.addStretch()

        root.addLayout(pr)

        root.addSpacing(8)



        # ── JUMP BACK IN SUGGESTIONS ──

        self._jbi_widget = QWidget()

        self._jbi_widget.setStyleSheet("background: transparent;")

        jbi_lay = QVBoxLayout(self._jbi_widget)

        jbi_lay.setContentsMargins(0, 0, 0, 6)

        jbi_lay.setSpacing(6)



        jbi_header = QLabel("JUMP BACK IN")

        jbi_header.setStyleSheet(f"""

            font-family: {FN}; font-size: 10px; font-weight: 700;

            letter-spacing: 1px; color: rgba(255,255,255,0.25);

            background: transparent; padding-left: 12px;

        """)

        jbi_lay.addWidget(jbi_header)



        # Container for suggestion chips

        self._jbi_chips_container = QWidget()

        self._jbi_chips_container.setStyleSheet("background: transparent;")

        self._jbi_chips_layout = QHBoxLayout(self._jbi_chips_container)

        self._jbi_chips_layout.setContentsMargins(12, 0, 12, 0)

        self._jbi_chips_layout.setSpacing(8)

        self._jbi_chips_layout.addStretch()

        jbi_lay.addWidget(self._jbi_chips_container)



        self._jbi_widget.hide()

        root.addWidget(self._jbi_widget)



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



        # TODAY'S ACTIVITY CARD (visible in empty state)

        self._today_card = QFrame()

        self._today_card.setStyleSheet(f"""

            QFrame {{

                background: rgba(0,120,212,0.04);

                border: 1px solid rgba(0,120,212,0.10);

                border-radius: 10px;

            }}

        """)

        tc_lay = QVBoxLayout(self._today_card)

        tc_lay.setContentsMargins(16, 12, 16, 12)

        tc_lay.setSpacing(6)

        tc_hdr = QHBoxLayout()

        tc_title = QLabel(" Today's Activity")

        tc_title.setStyleSheet(f"font-family: {FN}; font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.65); background: transparent;")

        tc_hdr.addWidget(tc_title)

        tc_hdr.addStretch()

        self._today_streak = QLabel("")

        self._today_streak.setStyleSheet(f"font-family: {FN}; font-size: 10px; color: rgba(255,180,50,0.8); background: transparent;")

        tc_hdr.addWidget(self._today_streak)

        tc_lay.addLayout(tc_hdr)

        # Activity stats row

        self._today_stats = QLabel("Loading...")

        self._today_stats.setStyleSheet(f"font-family: {FN}; font-size: 11px; color: rgba(255,255,255,0.35); background: transparent;")

        tc_lay.addWidget(self._today_stats)

        # "Try @query" hint

        tc_hint = QLabel(" Type @yesterday or @last week to search your activity")

        tc_hint.setStyleSheet(f"font-family: {MN}; font-size: 9px; color: rgba(0,120,212,0.50); background: transparent;")

        tc_lay.addWidget(tc_hint)

        self.rl.addWidget(self._today_card)



        # ACTION CARDS (visible in empty state)

        self._acw = QWidget(); self._acw.setStyleSheet("background: transparent;")

        al = QVBoxLayout(self._acw); al.setContentsMargins(0,0,0,0); al.setSpacing(6)

        al.addWidget(CatHeader("Quick Actions"))

        ag = QHBoxLayout(); ag.setSpacing(10)

        for em, lb, sc, aid in [("refresh-cw","Re-index","Ctrl R","reindex"),

                                 ("folder-plus","Add Folder","Ctrl O","add_path"),

                                 ("settings","Settings","Ctrl ,","settings")]:

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

            ("search", "Semantic search", "Use natural language — \"files about machine learning\""),

            ("activity", "Hybrid scoring", "Combines vector similarity + keyword + time + depth"),

            ("clock", "Time filters", "Try \"modified last week\" or \"created today\""),

            ("bar-chart-2", "Activity search", "Type @yesterday to see your recent work sessions"),

        ]:

            sf = QFrame(); sf.setFixedHeight(42)

            sf.setStyleSheet("background: transparent; border-radius: 10px;")

            sfl = QHBoxLayout(sf); sfl.setContentsMargins(16,4,16,4); sfl.setSpacing(14)

            si = icon_label(em, 16, "#60CDFF"); si.setFixedSize(28,28)

            si.setAlignment(Qt.AlignmentFlag.AlignCenter)

            si.setStyleSheet("font-size: 15px; background: rgba(56,156,255,0.06); border-radius: 8px;")

            sfl.addWidget(si)

            tc2 = QVBoxLayout(); tc2.setSpacing(0)

            n = QLabel(nm)

            n.setStyleSheet(f"font-family: {FN}; font-size: 12.5px; font-weight: 600; color: rgba(255,255,255,0.70); background: transparent;")

            tc2.addWidget(n)

            d = QLabel(ds)

            d.setStyleSheet(f"font-family: {MN}; font-size: 9.5px; color: rgba(255,255,255,0.22); background: transparent;")

            tc2.addWidget(d)

            sfl.addLayout(tc2, 1)

            sl2.addWidget(sf)

        self.rl.addWidget(self._sgw)

        self.rl.addStretch()



        self.scroll.setWidget(self.rw)

        root.addWidget(self.scroll, 1)



        # ── MEMORYOS CHAT PANEL (hidden by default, shown when MemoryOS pill is clicked) ──

        self._mos_panel = MemoryOSPanel(self)

        root.addWidget(self._mos_panel, 1)



        # ── ACTIVITY PANEL (hidden by default, shown when Activity pill is clicked) ──

        self._activity_panel = ActivityPanel(self)

        self._activity_panel.hide()

        root.addWidget(self._activity_panel, 1)



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

        brand = QLabel("Neuron")

        brand.setStyleSheet(f"""

            font-family: {FN}; font-size: 11.5px; font-weight: 800;

            color: #0078D4; background: transparent;

        """)

        bb.addWidget(brand)

        bb.addSpacing(6)



        # green pulse dot

        dot = icon_label("check-circle", 10, "#34C759")

        dot.setStyleSheet("font-size: 7px; color: #34C759; background: transparent;")

        bb.addWidget(dot)

        bb.addSpacing(4)



        self.idx_lbl = QLabel("Indexing…")

        self.idx_lbl.setStyleSheet(f"font-size: 10px; color: rgba(255,255,255,0.18); background: transparent;")

        bb.addWidget(self.idx_lbl)



        # Streak indicator

        self._streak_lbl = QLabel("")

        self._streak_lbl.setStyleSheet(f"font-size: 10px; color: rgba(255,180,50,0.6); background: transparent; margin-left: 6px;")

        bb.addWidget(self._streak_lbl)

        bb.addStretch()



        for txt in ["Up/Down nav", "Enter open", "Tab Encyl", "? ask", "Ctrl+C copy", "Esc close"]:

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

        ai_color = "rgba(52,199,89,0.7)" if ai_ok else "rgba(255,255,255,0.14)"
        self.ai_icon = icon_label("cpu", 10, "#34C759" if ai_ok else "#666666")
        self.ai_icon.setToolTip("Encyl AI connected — type ? to ask" if ai_ok else "Encyl offline — model unavailable")
        bb.addWidget(self.ai_icon)

        self.ai_lbl = QLabel("Encyl")

        self.ai_lbl.setStyleSheet(f"font-size: 9px; color: {ai_color}; background: transparent; margin-left: 2px;")

        self.ai_lbl.setToolTip("Encyl AI connected — type ? to ask" if ai_ok else "Encyl offline — model unavailable")

        bb.addWidget(self.ai_lbl)



        root.addLayout(bb)



    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # RESULTS MANAGEMENT

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _clear(self):

        self._rows.clear(); self._sel = -1

        while self.rl.count() > 0:

            it = self.rl.takeAt(0)

            w = it.widget()

            if w and w not in (self.empty, self._acw, self._sgw, self._today_card):

                w.deleteLater()



    def _show_empty(self, msg=None):

        if msg: self.empty.setText(msg)

        self.empty.show(); self._acw.show(); self._sgw.show()

        self._today_card.show()

        self._refresh_today_card()



    def _hide_empty(self):

        self.empty.hide(); self._acw.hide(); self._sgw.hide()

        self._today_card.hide()



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



        # Column header (Win11 Explorer style)

        self.rl.addWidget(ColumnHeader(self.rw))



        # All rows in flat list (no Top Hit / Files separation)

        for i, h in enumerate(hits):

            r = ResultRow(h, top=(i == 0), parent=self.rw)

            r.clicked.connect(self._open)

            self.rl.addWidget(r)

            self._rows.append(r)



        # "You might want to revisit..." section

        q = self.search.text().strip()

        if q:

            self._add_revisit_suggestions(q)



        self.rl.addWidget(self._acw)

        self.rl.addWidget(self._sgw)

        self.rl.addStretch()



        n = len(hits)

        self.status.setText(f'{n} result{"s" if n != 1 else ""} for "{q}"')

        if self._rows:

            self._sel = 0; self._rows[0].set_selected(True)



    # ── scope ────────────────────────────────────────────────

    def _set_scope(self, k):

        self._scope = k

        for p in self._pills: p.set_active(p._key == k)



        if k == "memoryos":

            self._exit_activity_mode()

            self._enter_memoryos_mode()

            return

        elif k == "activity":

            self._exit_memoryos_mode()

            self._enter_activity_mode()

            return

        else:

            self._exit_memoryos_mode()

            self._exit_activity_mode()



        if self._all:    self._filter()

        elif self.search.text().strip(): self._deb.start()



    def _filter(self):

        exts = SCOPES.get(self._scope)

        if exts == "__dir__": filtered = []

        elif exts: filtered = [h for h in self._all if h.get("extension","").lower() in exts]

        else: filtered = self._all

        self._populate(filtered)



    # ── "Jump back in" suggestions ───────────────────────────

    def _populate_jump_back_in(self):

        """Populate 'Jump back in' suggestions with recent files."""

        # Clear existing chips

        while self._jbi_chips_layout.count() > 1:  # Keep the stretch

            item = self._jbi_chips_layout.takeAt(0)

            if item.widget():

                item.widget().deleteLater()



        try:

            recent_files = self._svc.get_recent_files(limit=5)

            if recent_files:

                for file_data in recent_files:

                    file_path = file_data.get('file_path')

                    if file_path and Path(file_path).exists():

                        chip = SuggestionChip(file_path, self._jbi_chips_container)

                        chip.clicked.connect(self._open)

                        self._jbi_chips_layout.insertWidget(

                            self._jbi_chips_layout.count() - 1, chip

                        )

                self._jbi_widget.show()

            else:

                self._jbi_widget.hide()

        except Exception as e:

            logger.warning(f"Failed to populate Jump back in: {e}")

            self._jbi_widget.hide()



    def _add_revisit_suggestions(self, query: str):

        """Add 'You might want to revisit...' section to results."""

        try:

            suggestions = self._svc.get_revisit_suggestions(query, exclude_days=2, limit=3)

            if not suggestions:

                return



            # Add spacing

            spacer = QWidget()

            spacer.setFixedHeight(16)

            spacer.setStyleSheet("background: transparent;")

            self.rl.addWidget(spacer)



            # Add header

            header = CatHeader("You might want to revisit...", len(suggestions), self.rw)

            self.rl.addWidget(header)



            # Add suggestion rows (visually different from main results)

            for suggestion in suggestions:

                file_path = suggestion.get('file_path')

                if file_path and Path(file_path).exists():

                    # Create a minimal dict compatible with ResultRow

                    hit = {

                        'path': file_path,

                        'name': Path(file_path).name,

                        'extension': Path(file_path).suffix,

                    }

                    r = ResultRow(hit, top=False, parent=self.rw)

                    r.clicked.connect(self._open)

                    # Make it visually distinct (dimmed)

                    r.setStyleSheet("""

                        ResultRow {

                            background: transparent;

                            border: 1px solid transparent;

                            border-radius: 4px;

                            opacity: 0.6;

                        }

                        ResultRow:hover {

                            background: rgba(255,255,255,0.03);

                            border: 1px solid transparent;

                            opacity: 1.0;

                        }

                    """)

                    self.rl.addWidget(r)

                    self._rows.append(r)



        except Exception as e:

            logger.warning(f"Failed to add revisit suggestions: {e}")



    # ── Activity Search (Memory OS) ──────────────────────────

    def _do_activity_search(self, query: str):

        """Handle @ activity queries like '@yesterday' or '@last week python files'."""

        import datetime

        self._dismiss_ai_panel()

        self._stop_encyl_loading()

        self._clear()

        self._hide_empty()



        now = datetime.datetime.now()

        # Parse time range from query

        time_range, keyword = self._parse_time_range(query, now)



        try:

            events = self._svc.get_recent_events(limit=500)

            if not events:

                self._show_empty("No activity recorded yet — use Neuron to build your timeline")

                self.rl.addWidget(self.empty)

                self.rl.addWidget(self._today_card)

                self.rl.addWidget(self._acw)

                self.rl.addWidget(self._sgw)

                self.rl.addStretch()

                self.status.setText("No activity events found")

                return



            # Filter events by time range

            filtered = []

            for ev in events:

                ts = ev.get('timestamp', '')

                if not ts:

                    continue

                try:

                    ev_time = datetime.datetime.fromisoformat(ts)

                except (ValueError, TypeError):

                    continue

                if time_range:

                    start, end = time_range

                    if not (start <= ev_time <= end):

                        continue

                # Keyword filter (on file path)

                if keyword:

                    fp = ev.get('file_path', '').lower()

                    et = ev.get('event_type', '').lower()

                    if keyword.lower() not in fp and keyword.lower() not in et:

                        continue

                filtered.append(ev)



            if not filtered:

                q_display = f"@{query}"

                self._show_empty(f"No activity matching \"{q_display}\"\\n\\nTry: @yesterday, @last week, @today python")

                self.rl.addWidget(self.empty)

                self.rl.addWidget(self._today_card)

                self.rl.addWidget(self._acw)

                self.rl.addWidget(self._sgw)

                self.rl.addStretch()

                self.status.setText(f'No activity for "@{query}"')

                return



            self._show_activity_results(filtered, query)



        except Exception as e:

            logger.error(f"Activity search error: {e}")

            self.status.setText(f"Activity search error: {e}")



    def _show_activity_results(self, events: list, query: str):

        """Display activity events grouped by session (30-min gaps)."""

        import datetime, collections



        # Group events into sessions (30-min gap = new session)

        sessions = []

        current_session = []

        last_time = None



        for ev in events:

            try:

                ev_time = datetime.datetime.fromisoformat(ev.get('timestamp', ''))

            except (ValueError, TypeError):

                continue

            if last_time and (last_time - ev_time).total_seconds() > 1800:

                if current_session:

                    sessions.append(current_session)

                current_session = []

            current_session.append(ev)

            last_time = ev_time



        if current_session:

            sessions.append(current_session)



        # Display sessions

        total_events = sum(len(s) for s in sessions)

        self.status.setText(

            f'{total_events} event{"s" if total_events != 1 else ""} '

            f'in {len(sessions)} session{"s" if len(sessions) != 1 else ""} '

            f'for "@{query}"'

        )



        for si, session in enumerate(sessions):

            if not session:

                continue

            first_ev = session[0]

            last_ev = session[-1]

            try:

                start_time = datetime.datetime.fromisoformat(first_ev.get('timestamp', ''))

                end_time = datetime.datetime.fromisoformat(last_ev.get('timestamp', ''))

            except (ValueError, TypeError):

                continue



            # Session header

            day_str = start_time.strftime("%A, %b %d")

            time_str = f"{start_time.strftime('%I:%M %p')} – {end_time.strftime('%I:%M %p')}"

            duration = start_time - end_time

            dur_min = max(1, int(abs(duration.total_seconds()) / 60))

            dur_str = f"{dur_min}min" if dur_min < 60 else f"{dur_min // 60}h {dur_min % 60}m"



            session_hdr = QFrame()

            session_hdr.setStyleSheet(f"""

                QFrame {{

                    background: rgba(0,120,212,0.06);

                    border: 1px solid rgba(0,120,212,0.12);

                    border-radius: 8px;

                    margin-top: {'0' if si == 0 else '8'}px;

                }}

            """)

            sh_lay = QHBoxLayout(session_hdr)

            sh_lay.setContentsMargins(12, 8, 12, 8)



            sh_icon = QLabel("")

            sh_icon.setStyleSheet("font-size: 14px; background: transparent;")

            sh_lay.addWidget(sh_icon)



            sh_info = QVBoxLayout()

            sh_info.setSpacing(0)

            sh_title = QLabel(f"{day_str}  ·  {time_str}")

            sh_title.setStyleSheet(f"font-family: {FN}; font-size: 11.5px; font-weight: 600; color: rgba(255,255,255,0.70); background: transparent;")

            sh_info.addWidget(sh_title)

            sh_detail = QLabel(f"{len(session)} events · {dur_str}")

            sh_detail.setStyleSheet(f"font-family: {MN}; font-size: 9px; color: rgba(255,255,255,0.30); background: transparent;")

            sh_info.addWidget(sh_detail)

            sh_lay.addLayout(sh_info, 1)



            self.rl.addWidget(session_hdr)



            # Deduplicate files in session

            seen_paths = set()

            for ev in session:

                fp = ev.get('file_path', '')

                if not fp or fp in seen_paths:

                    continue

                seen_paths.add(fp)

                if not Path(fp).exists():

                    continue



                event_type = ev.get('event_type', 'access')

                type_emoji = {"open": "folder-open", "search": "search", "summarize": "cpu",

                              "index": "hard-drive", "access": "eye"}.get(event_type, "file")



                hit = {

                    'path': fp,

                    'name': Path(fp).name,

                    'extension': Path(fp).suffix,

                }

                r = ResultRow(hit, top=False, parent=self.rw)

                r.clicked.connect(self._open)

                self.rl.addWidget(r)

                self._rows.append(r)



        self.rl.addStretch()

        if self._rows:

            self._sel = 0

            self._rows[0].set_selected(True)



    def _parse_time_range(self, query: str, now):

        """Parse natural language time from activity query.



        Returns (time_range, keyword) where time_range is (start, end) or None.

        """

        import datetime

        q = query.lower().strip()

        keyword = ""



        # Extract time keywords

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)



        time_patterns = [

            ("today", (today_start, now)),

            ("yesterday", (today_start - datetime.timedelta(days=1), today_start)),

            ("this week", (today_start - datetime.timedelta(days=today_start.weekday()), now)),

            ("last week", (

                today_start - datetime.timedelta(days=today_start.weekday() + 7),

                today_start - datetime.timedelta(days=today_start.weekday()),

            )),

            ("this month", (today_start.replace(day=1), now)),

            ("last month", (

                (today_start.replace(day=1) - datetime.timedelta(days=1)).replace(day=1),

                today_start.replace(day=1),

            )),

        ]



        # Day name matching (e.g., "last sunday", "monday")

        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        for i, day_name in enumerate(day_names):

            if day_name in q:

                # Find the most recent occurrence of this day

                days_ago = (now.weekday() - i) % 7

                if days_ago == 0 and "last" in q:

                    days_ago = 7

                target_day = today_start - datetime.timedelta(days=days_ago)

                time_patterns.append((day_name, (target_day, target_day + datetime.timedelta(days=1))))

                break



        # Time of day refinement (e.g., "after 10 pm")

        time_range = None

        for pattern, tr in time_patterns:

            if pattern in q:

                time_range = tr

                # Remove the time pattern from query to extract keyword

                keyword = q.replace(pattern, "").strip()

                # Remove filler words

                for w in ["last", "this", "after", "before", "on", "in"]:

                    keyword = keyword.replace(w, "").strip()

                break



        # Handle "N days ago"

        if not time_range:

            import re

            m = re.search(r'(\d+)\s*days?\s*ago', q)

            if m:

                days = int(m.group(1))

                target_day = today_start - datetime.timedelta(days=days)

                time_range = (target_day, target_day + datetime.timedelta(days=1))

                keyword = re.sub(r'\d+\s*days?\s*ago', '', q).strip()



        if not time_range:

            # No time pattern found — treat entire query as keyword, search all time

            keyword = q



        return time_range, keyword



    def _refresh_today_card(self):

        """Update the Today's Activity card with current stats."""

        try:

            stats = self._svc.get_daily_stats()

            streak = self._svc.get_streak_days()



            if stats:

                searches = stats.get('search_count', 0)

                opens = stats.get('open_count', 0)

                summaries = stats.get('summarize_count', 0)

                total = searches + opens + summaries

                parts = []

                if searches: parts.append(f"{searches} search{'es' if searches != 1 else ''}")

                if opens: parts.append(f"{opens} file{'s' if opens != 1 else ''} opened")

                if summaries: parts.append(f"{summaries} summar{'ies' if summaries != 1 else 'y'}")

                if parts:

                    self._today_stats.setText(" · ".join(parts))

                else:

                    self._today_stats.setText("No activity yet today — start searching!")

            else:

                self._today_stats.setText("No activity yet today — start searching!")



            if streak > 0:

                self._today_streak.setText(f"{streak} day{'s' if streak != 1 else ''} streak")

            else:

                self._today_streak.setText("")

        except Exception as e:

            logger.warning(f"Failed to refresh today card: {e}")

            self._today_stats.setText("Activity tracking active")



    def _refresh_streak(self):

        """Update streak indicator in the bottom bar."""

        try:

            streak = self._svc.get_streak_days()

            if streak > 0:

                self._streak_lbl.setText(f"{streak}d streak")

            else:

                self._streak_lbl.setText("")

        except Exception:

            pass





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



    def _toggle_memory_lane(self):

        """Toggle Memory Lane daily recap panel."""

        if self._memory_lane and self._memory_lane.isVisible():

            self._memory_lane.hide(); self._memory_lane.deleteLater(); self._memory_lane = None

            return

        self._memory_lane = MemoryLanePanel(self._svc, self)

        self._memory_lane.closed.connect(self._close_memory_lane)

        self._memory_lane.file_clicked.connect(self._open)

        self._memory_lane.setGeometry(22, 80, self.width() - 44, self.height() - 110)

        self._memory_lane.show(); self._memory_lane.raise_()



    def _close_memory_lane(self):

        """Close Memory Lane panel."""

        if self._memory_lane:

            self._memory_lane.hide(); self._memory_lane.deleteLater(); self._memory_lane = None



    def _reindex(self):

        try:

            from services.startup_indexer import StartupIndexer

            si = StartupIndexer()

            si.reindex_in_background("manual")

        except Exception as e:

            from app.logger import logger

            logger.error(f"Re-index failed: {e}")



    # ── tray ─────────────────────────────────────────────────

    def _build_tray(self):

        self._tray = QSystemTrayIcon(self)

        # BUG3-FIX: use white-background circular icon for tray

        _circ = str(_ASSETS / "neuron_circular.png")

        if Path(_circ).exists():

            tray_pix = make_white_bg_icon(_circ, 64)

            self._tray.setIcon(QIcon(tray_pix))

            QApplication.setWindowIcon(QIcon(tray_pix))

        elif _ICON.exists():

            self._tray.setIcon(QIcon(str(_ICON)))

            QApplication.setWindowIcon(QIcon(str(_ICON)))

        m = QMenu()

        m.setStyleSheet("""

            QMenu { background: #1a1a1e; color: #e0e0e0; border: 1px solid #333; border-radius: 8px; padding: 4px; }

            QMenu::item { padding: 6px 20px; border-radius: 4px; }

            QMenu::item:selected { background: rgba(56,156,255,0.3); }

            QMenu::separator { height: 1px; background: #333; margin: 4px 8px; }

        """)

        m.addAction("Show  (Shift+Space / Ctrl+Alt+N)").triggered.connect(self.toggle_panel)

        m.addAction("Memory Lane").triggered.connect(self._toggle_memory_lane)

        m.addAction("Re-index").triggered.connect(self._reindex)

        m.addAction("Settings").triggered.connect(self._toggle_settings)

        m.addSeparator()

        m.addAction("Quit").triggered.connect(self._quit)

        self._tray.setContextMenu(m)

        self._tray.activated.connect(

            lambda r: self.toggle_panel() if r in (

                QSystemTrayIcon.ActivationReason.Trigger,

                QSystemTrayIcon.ActivationReason.DoubleClick) else None)

        self._tray.setToolTip("Neuron — Shift+Space or Ctrl+Alt+N to search")

        self._tray.show()

        self._update_tray_tooltip()



    def _update_tray_tooltip(self):

        """Update tray tooltip with streak info."""

        try:

            streak = self._svc.get_streak_days()

            if streak > 0:

                tooltip = f"Neuron — Shift+Space or Ctrl+Alt+N to search\n{streak} day{'s' if streak != 1 else ''} streak"

            else:

                tooltip = "Neuron — Shift+Space or Ctrl+Alt+N to search"

            self._tray.setToolTip(tooltip)

        except Exception:

            self._tray.setToolTip("Neuron — Shift+Space or Ctrl+Alt+N to search")



    # ── indexing ─────────────────────────────────────────────

    def _refresh_idx_count(self):

        """Poll the real DB count and update label. Runs every 3s."""

        try:

            cnt = self._svc.total_indexed()

            if cnt != self._idx_count:

                self._idx_count = cnt

                if not self._indexing:

                    self.idx_lbl.setText(f"{cnt:,} files indexed")

                # Update tray

                self._update_tray_tooltip()

        except Exception:

            pass



    def _kick_index(self):

        # Show existing count immediately before starting thread

        try:

            existing = self._svc.total_indexed()

            self._idx_count = existing

            if existing > 0:

                self.idx_lbl.setText(f"{existing:,} files indexed")

            else:

                self.idx_lbl.setText("Indexing…")

        except Exception:

            self.idx_lbl.setText("Indexing…")



        self._indexing = True

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

        # Stop live refresh — indexing is done

        try:

            self._live_refresh_timer.stop()

        except Exception:

            pass

        # Update tray tooltip with streak

        self._update_tray_tooltip()



    # ── Navigation (â† → ↑ ↻) ────────────────────────────────

    def _nav_back(self):

        if self._hist_idx > 0:

            self._hist_idx -= 1

            q = self._history[self._hist_idx]

            self.search.inp.blockSignals(True)

            self.search.inp.setText(q)

            self.search.inp.blockSignals(False)

            self._do_search()

            self._update_nav_btns()



    def _nav_forward(self):

        if self._hist_idx < len(self._history) - 1:

            self._hist_idx += 1

            q = self._history[self._hist_idx]

            self.search.inp.blockSignals(True)

            self.search.inp.setText(q)

            self.search.inp.blockSignals(False)

            self._do_search()

            self._update_nav_btns()



    def _nav_up(self):

        self.search.inp.clear()

        self._on_text("")



    def _nav_refresh(self):

        q = self.search.text().strip()

        if q:

            self._do_search()

        else:

            self._reindex()



    def _update_nav_btns(self):

        self._btn_back.setEnabled(self._hist_idx > 0)

        self._btn_fwd.setEnabled(self._hist_idx < len(self._history) - 1)



    def _push_history(self, query: str):

        if not query: return

        # If we navigated back and type new query, truncate forward history

        if self._hist_idx < len(self._history) - 1:

            self._history = self._history[:self._hist_idx + 1]

        # Don't duplicate consecutive queries

        if not self._history or self._history[-1] != query:

            self._history.append(query)

        self._hist_idx = len(self._history) - 1

        self._update_nav_btns()



    # ── Encyl Loading Animation ──────────────────────────────

    def _start_encyl_loading(self, msg: str = ""):

        self._encyl_phase = 0

        self._encyl_status.setText(msg or self._encyl_phases[0])

        self._encyl_loading.show()

        self._encyl_timer.start()



    def _advance_encyl_phase(self):

        self._encyl_phase = min(self._encyl_phase + 1, len(self._encyl_phases) - 1)

        self._encyl_status.setText(self._encyl_phases[self._encyl_phase])

        # Animate progress bar width

        widths = [20, 40, 60, 72]

        w = widths[min(self._encyl_phase, len(widths)-1)]

        self._encyl_pbar.setFixedWidth(w)



    def _stop_encyl_loading(self):

        self._encyl_timer.stop()

        self._encyl_loading.hide()

        self._encyl_pbar.setFixedWidth(80)



    # ── search ───────────────────────────────────────────────

    def _on_text(self, t):

        if t.strip():

            self._deb.start()

            # Hide "Jump back in" when user starts typing

            self._jbi_widget.hide()

        else:

            # Fully reset when search bar is cleared

            self._deb.stop()

            self._all.clear()

            self._dismiss_ai_panel()

            self._stop_encyl_loading()

            self._clear()

            self.rl.addWidget(self.empty)

            self.rl.addWidget(self._today_card)

            self.rl.addWidget(self._acw)

            self.rl.addWidget(self._sgw)

            self.rl.addStretch()

            self._show_empty()

            self.status.setText("")

            # Show "Jump back in" when search is cleared

            self._populate_jump_back_in()



    def _do_search(self):

        q = self.search.text().strip()

        if not q: return



        # Track search history for navigation

        self._push_history(q)



        # ── "? question" → Ask AI mode ──

        if q.startswith("?"):

            question = q[1:].strip()

            if not question: return

            self._start_encyl_loading("Encyl is searching your files...")

            self._ask_ai(question)

            return



        # ── "@ query" → Activity search mode (Memory OS) ──

        if q.startswith("@"):

            activity_query = q[1:].strip()

            if not activity_query: return

            self._do_activity_search(activity_query)

            return



        # ── normal search (Phase 1: fast FAISS) ──

        self._dismiss_ai_panel()

        self._stop_encyl_loading()

        if self._idx_count == 0 and not self._indexing:

            self.status.setText("Index empty — waiting for indexing…"); return

        self.status.setText("Searching…")

        cfg = self._svc.get_config()

        self._st = SearchThread(self._svc, q, cfg.get("top_k", 20), use_llm=False)

        self._st.results.connect(self._on_results)

        self._st.error.connect(lambda e: self.status.setText(f"Error: {e}"))

        self._st.start()



    def _on_results(self, hits):

        self._all = hits; self._filter()

        # Phase 2: trigger LLM re-rank in background (if available)

        q = self.search.text().strip()

        if q and len(hits) >= 2 and not q.startswith("?"):

            self._start_llm_rerank(q, len(hits))



    def _start_llm_rerank(self, query: str, result_count: int):

        """Phase 2: Background LLM re-ranking for deeper content understanding."""

        try:

            from core.search.llm_reranker import get_reranker

            reranker = get_reranker()

            if not reranker.is_available():

                return  # No Ollama — skip silently

        except Exception:

            return



        self._llm_active = True

        self.status.setText(f"AI enhancing {result_count} results…")

        cfg = self._svc.get_config()

        self._llm_st = SearchThread(self._svc, query, cfg.get("top_k", 20), use_llm=True)

        self._llm_st.results.connect(self._on_llm_results)

        self._llm_st.error.connect(lambda e: self._on_llm_done())

        self._llm_st.start()



    def _on_llm_results(self, hits):

        """Silently update results with LLM-reranked order."""

        self._all = hits; self._filter()

        self._on_llm_done()

        llm_count = sum(1 for h in hits if h.get("llm_score") is not None)

        if llm_count:

            self.status.setText(f"AI-enhanced • {len(hits)} results")

        else:

            self.status.setText(f"{len(hits)} results")



    def _on_llm_done(self):

        self._llm_active = False



    # ── AI BRAIN ─────────────────────────────────────────────

    def _ask_ai(self, question: str):

        """Search for relevant files, then ask Ollama about them."""

        self.status.setText("Encyl is reading your files…")

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



        self.status.setText("Encyl is thinking…")

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

            self.status.setText("Encyl offline — model unavailable")

            self.ai_lbl.setText("Encyl")

            self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.14); background: transparent; margin-left: 2px;")

            return

        # Update status to show it's connected

        self.ai_lbl.setText("Encyl")

        self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(52,199,89,0.7); background: transparent; margin-left: 2px;")



        path = self._rows[self._sel]._path

        name = Path(path).name

        self.status.setText(f"Encyl is summarizing {name}…")

        self._start_encyl_loading(f"Reading {name}...")

        self._smt = SummarizeThread(path)

        self._smt.summary.connect(self._show_ai_summary)

        self._smt.error.connect(self._handle_encyl_error)

        self._smt.start()



    def _show_ai_answer(self, question: str, answer: str):

        """Display AI answer in a panel above results."""

        self._stop_encyl_loading()

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

        hl = QLabel("Encyl Answer")

        hl.setStyleSheet(f"font-family: {FN}; font-size: 11px; font-weight: 700; color: #65B8FF; background: transparent;")

        hdr.addWidget(hl)

        hdr.addStretch()

        x = icon_label("x", 14, "#C8C8C8"); x.setFixedSize(22, 22)

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

        self.status.setText(f'Encyl answered "{question[:40]}…"')



    def _show_ai_summary(self, path: str, summary: str):

        """Display AI summary for a single file."""

        self._stop_encyl_loading()

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

        hl = QLabel(f"Encyl Summary — {name}")

        hl.setStyleSheet(f"font-family: {FN}; font-size: 11px; font-weight: 700; color: #4ADE80; background: transparent;")

        hdr.addWidget(hl)

        hdr.addStretch()

        x = icon_label("x", 14, "#C8C8C8"); x.setFixedSize(22, 22)

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

        self.status.setText(f"Encyl summarized {name}")



    def _dismiss_ai_panel(self):

        if self._ai_panel:

            self._ai_panel.hide()

            self._ai_panel.deleteLater()

            self._ai_panel = None



    def _handle_encyl_error(self, error_msg: str):

        """User-friendly error messages for Encyl failures."""

        self._stop_encyl_loading()

        if "timed out" in error_msg.lower():

            self.status.setText("Encyl is warming up — try again in a few seconds")

        elif "not running" in error_msg.lower() or "connection" in error_msg.lower():

            self.status.setText("Encyl offline — model unavailable")

            self.ai_lbl.setText("Encyl")

            self.ai_lbl.setStyleSheet("font-size: 9px; color: rgba(255,255,255,0.14); background: transparent; margin-left: 2px;")

        else:

            self.status.setText(f"Encyl error: {error_msg[:60]}")



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

    def activate_from_hotkey(self):

        """Show or refocus the panel from a global hotkey.

        Global hotkeys can emit duplicate events while keys are held, depending
        on keyboard layout, IME, and Windows focus state. Treating the hotkey as
        show/focus keeps the panel from opening and immediately disappearing.
        """

        logger.info(f"Panel: hotkey activation received (visible={self._vis})")

        if self._vis:

            self._fade.stop()

            if not self.isVisible():

                self.show()

            self.raise_()

            self.activateWindow()

            self.search.setFocus()

            self.search.selectAll()

            return

        self._show()



    def _resize_to_screen(self):

        """Compute panel size from available screen — 90% height, capped at H."""

        W, H = 720, 900

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



        # Reset stale state if search bar is empty

        if not self.search.text().strip():

            self._all.clear()

            self._dismiss_ai_panel()

            self._clear()

            self.rl.addWidget(self.empty)

            self.rl.addWidget(self._today_card)

            self.rl.addWidget(self._acw)

            self.rl.addWidget(self._sgw)

            self.rl.addStretch()

            self._show_empty()

            self.status.setText("")

            # Populate "Jump back in" suggestions

            self._populate_jump_back_in()

            # Update streak

            self._refresh_streak()



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

        logger.info("Panel: tray quit requested")

        self._tray.hide(); QApplication.quit()



    # ── DWM Acrylic ──────────────────────────────────────────

    # ── MemoryOS Mode (delegates to ui/memoryos_panel.py) ────────

    def _enter_memoryos_mode(self):

        """Switch to MemoryOS chat mode."""

        try:

            self.scroll.hide()

            self._jbi_widget.hide()

            self._mos_panel.activate()

            self.search.inp.setPlaceholderText("Ask MemoryOS... (e.g. 'organize my Downloads')")

            self.status.setText("MemoryOS - Agent Mode")

        except Exception as e:

            logger.error(f"MemoryOS mode failed: {e}")



    def _exit_memoryos_mode(self):

        """Switch back to search mode."""

        try:

            if self._mos_panel.is_active:

                self._mos_panel.deactivate()

            self.scroll.show()

            self.search.inp.setPlaceholderText("Search files, folders, content...")

            self.status.setText(f"{self._idx_count:,} files indexed")

        except Exception as e:

            logger.error(f"Exit MemoryOS mode failed: {e}")



    def _enter_activity_mode(self):

        """Switch to Activity timeline view."""

        try:

            self.scroll.hide()

            self._jbi_widget.hide()

            self._activity_panel.show()

            self._activity_panel._force_refresh()

            self.search.inp.setPlaceholderText("Activity Timeline")

            self.status.setText("Activity - Event Log")

        except Exception as e:

            logger.error(f"Activity mode failed: {e}")



    def _exit_activity_mode(self):

        """Exit Activity timeline view."""

        try:

            self._activity_panel.hide()

            self.scroll.show()

        except Exception as e:

            logger.error(f"Exit Activity mode failed: {e}")



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

"""
DeepSeekFS – Desktop Entry Point (v2.0 PyQt6 Monolithic)
=========================================================
Replaces run.py + FastAPI + pywebview with a single native PyQt6 window.
All business logic is called directly — zero HTTP, zero network sockets.

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
from pathlib import Path
from typing import List

# Make sure project root is on sys.path regardless of CWD
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QStatusBar, QSystemTrayIcon,
    QMenu, QMessageBox, QFileDialog,
)
from PyQt6.QtCore  import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui   import QFont, QColor, QIcon, QPalette

import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService


# ─────────────────────────────────────────────────────────────────────────────
# Background worker: initial indexing
# ─────────────────────────────────────────────────────────────────────────────
class IndexThread(QThread):
    """
    Runs StartupIndexer._run() in a background thread.
    Emits:
      status(str)       – human-readable message for the status bar
      progress(int,int) – (files_done, files_total) for the progress bar
      finished(int)     – total new files indexed
    """
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
    """
    Calls the search engine in a background thread so the UI never blocks.
    Emits:
      results(list)  – list of result dicts
      error(str)     – on failure
    """
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
# Main window
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """
    Single monolithic window: search box + results table + progress bar + tray.
    No HTTP, no localhost, no browser. Everything is a direct Python call.
    """

    APP_STYLE = """
    /* ── Global: transparent so acrylic shows through ────────────── */
    QMainWindow {
        background: transparent;
    }
    QWidget#central {
        background: rgba(20, 20, 30, 180);
    }

    /* ── Header labels ──────────────────────────────────────────── */
    QLabel#title {
        font-size: 22px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.95);
    }
    QLabel#subtitle {
        font-size: 12px;
        color: rgba(255, 255, 255, 0.50);
    }

    /* ── Search input ───────────────────────────────────────────── */
    QLineEdit {
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.92);
        background: rgba(255, 255, 255, 0.06);
        selection-background-color: rgba(99, 140, 255, 0.45);
    }
    QLineEdit:focus {
        border-color: rgba(99, 140, 255, 0.60);
        background: rgba(255, 255, 255, 0.10);
    }
    QLineEdit::placeholder {
        color: rgba(255, 255, 255, 0.35);
    }

    /* ── Search button ──────────────────────────────────────────── */
    QPushButton#btn_search {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(67, 97, 238, 220),
            stop:1 rgba(99, 140, 255, 220)
        );
        color: #ffffff;
        border: 1px solid rgba(99, 140, 255, 0.30);
        border-radius: 8px;
        padding: 10px 28px;
        font-size: 14px;
        font-weight: 600;
    }
    QPushButton#btn_search:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(80, 115, 255, 240),
            stop:1 rgba(120, 160, 255, 240)
        );
        border-color: rgba(120, 160, 255, 0.50);
    }
    QPushButton#btn_search:pressed {
        background: rgba(50, 80, 200, 240);
    }
    QPushButton#btn_search:disabled {
        background: rgba(255, 255, 255, 0.08);
        color: rgba(255, 255, 255, 0.30);
        border-color: rgba(255, 255, 255, 0.06);
    }

    /* ── Folder button ──────────────────────────────────────────── */
    QPushButton#btn_folder {
        background: rgba(255, 255, 255, 0.06);
        color: rgba(150, 180, 255, 0.90);
        border: 1px solid rgba(99, 140, 255, 0.30);
        border-radius: 8px;
        padding: 8px 18px;
        font-size: 13px;
    }
    QPushButton#btn_folder:hover {
        background: rgba(99, 140, 255, 0.15);
        border-color: rgba(99, 140, 255, 0.50);
    }

    /* ── Results table ──────────────────────────────────────────── */
    QTableWidget {
        background: rgba(255, 255, 255, 0.04);
        color: rgba(255, 255, 255, 0.88);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        gridline-color: rgba(255, 255, 255, 0.06);
        font-size: 13px;
        alternate-background-color: rgba(255, 255, 255, 0.03);
    }
    QTableWidget::item {
        padding: 8px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    QTableWidget::item:selected {
        background: rgba(99, 140, 255, 0.30);
        color: #ffffff;
    }
    QTableWidget::item:hover {
        background: rgba(255, 255, 255, 0.06);
    }
    QHeaderView::section {
        background: rgba(255, 255, 255, 0.06);
        color: rgba(255, 255, 255, 0.70);
        font-weight: 600;
        padding: 8px 10px;
        border: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.10);
    }

    /* ── Progress bar ───────────────────────────────────────────── */
    QProgressBar {
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 6px;
        text-align: center;
        font-size: 11px;
        height: 18px;
        color: rgba(255, 255, 255, 0.80);
        background: rgba(255, 255, 255, 0.05);
    }
    QProgressBar::chunk {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(67, 97, 238, 200),
            stop:1 rgba(120, 160, 255, 200)
        );
        border-radius: 5px;
    }

    /* ── Status bar ─────────────────────────────────────────────── */
    QStatusBar {
        font-size: 12px;
        color: rgba(255, 255, 255, 0.55);
        background: transparent;
    }

    /* ── Scrollbars ─────────────────────────────────────────────── */
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
        height: 0;
    }
    QScrollBar:horizontal {
        background: transparent;
        height: 8px;
        margin: 0;
    }
    QScrollBar::handle:horizontal {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
        width: 0;
    }

    /* ── Tooltips ───────────────────────────────────────────────── */
    QToolTip {
        background: rgba(30, 30, 45, 230);
        color: rgba(255, 255, 255, 0.90);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 4px;
        padding: 4px 8px;
    }

    /* ── Message box ────────────────────────────────────────────── */
    QMessageBox {
        background: rgba(25, 25, 40, 245);
        color: rgba(255, 255, 255, 0.90);
    }
    QMessageBox QLabel {
        color: rgba(255, 255, 255, 0.90);
    }
    QMessageBox QPushButton {
        background: rgba(255, 255, 255, 0.08);
        color: rgba(255, 255, 255, 0.90);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 6px;
        padding: 6px 20px;
    }
    QMessageBox QPushButton:hover {
        background: rgba(99, 140, 255, 0.20);
    }
    """

    COLS = ["#", "File Name", "Score", "Semantic", "Time", "Freq", "Type", "Full Path"]

    def __init__(self, service: DesktopService):
        super().__init__()
        self._svc          = service
        self._idx_thread   : IndexThread  | None = None
        self._srch_thread  : SearchThread | None = None
        self._indexed_count = 0

        self.setWindowTitle("DeepSeekFS — Semantic File Search")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)

        # Enable translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(self.APP_STYLE)

        self._build_ui()
        self._build_tray()
        self._kick_indexing()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 8)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title    = QLabel("🔍  DeepSeekFS", objectName="title")
        subtitle = QLabel("Semantic file search — local, offline, instant",
                          objectName="subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignBottom)
        hdr.addWidget(title)
        hdr.addSpacing(12)
        hdr.addWidget(subtitle)
        hdr.addStretch()
        root.addLayout(hdr)

        # Search row
        search_row = QHBoxLayout()
        self.inp_query = QLineEdit()
        self.inp_query.setPlaceholderText(
            "Search ‘resume’, ‘python project’, ‘SWOT analysis’…  (Enter to search)"
        )
        self.inp_query.setMinimumHeight(44)
        self.inp_query.returnPressed.connect(self._on_search)

        self.btn_search = QPushButton("🔍  Search", objectName="btn_search")
        self.btn_search.setMinimumHeight(44)
        self.btn_search.setMinimumWidth(130)
        self.btn_search.clicked.connect(self._on_search)
        self.btn_search.setEnabled(False)   # enabled once index is ready

        self.btn_folder = QPushButton("📁  Add Folder", objectName="btn_folder")
        self.btn_folder.setMinimumHeight(44)
        self.btn_folder.clicked.connect(self._on_add_folder)

        search_row.addWidget(self.inp_query, 1)
        search_row.addWidget(self.btn_search)
        search_row.addWidget(self.btn_folder)
        root.addLayout(search_row)

        # Results table
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch)      # Path column stretches
        self.table.doubleClicked.connect(self._on_open_file)
        # column widths
        for c, w in [(0,35),(1,220),(2,70),(3,80),(4,60),(5,50),(6,55)]:
            self.table.setColumnWidth(c, w)
        root.addWidget(self.table, 1)

        # Progress bar (hidden during normal search)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.progress.setFormat("Indexing…  %p%")
        root.addWidget(self.progress)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("⏳  Starting up…")

    def _build_tray(self):
        """System tray: double-click to show/hide; right-click to quit."""
        self._tray = QSystemTrayIcon(self)
        menu = QMenu()
        menu.addAction("Show / Hide", self._toggle_window)
        menu.addSeparator()
        menu.addAction("Quit DeepSeekFS", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    # ── Indexing ──────────────────────────────────────────────────────────────
    def _kick_indexing(self):
        self.btn_search.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.showMessage("📂  Scanning your files in the background…")

        self._idx_thread = IndexThread(self._svc)
        self._idx_thread.status.connect(self.status.showMessage)
        self._idx_thread.progress.connect(self._on_index_progress)
        self._idx_thread.finished.connect(self._on_index_done)
        self._idx_thread.start()

    def _on_index_progress(self, done: int, total: int):
        if total > 0:
            pct = min(int(done / total * 100), 99)
            self.progress.setValue(pct)
            self.progress.setFormat(f"Indexing…  {done}/{total}  ({pct}%)")

    def _on_index_done(self, new_files: int):
        self._indexed_count = self._svc.total_indexed()
        self.progress.setValue(100)
        self.progress.setFormat(f"✅  {self._indexed_count:,} files indexed")
        self.status.showMessage(
            f"✅  Ready — {self._indexed_count:,} files in index  •  "
            f"{new_files} new this session  •  double-click a result to open"
        )
        self.btn_search.setEnabled(True)
        self.inp_query.setFocus()

    def _on_add_folder(self):
        """Let user pick an extra folder and index it on the fly."""
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to index")
        if not folder:
            return
        config.WATCH_PATHS.append(folder)
        self.status.showMessage(f"📁  Indexing {folder}…")
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._kick_indexing()

    # ── Search ────────────────────────────────────────────────────────────────
    def _on_search(self):
        query = self.inp_query.text().strip()
        if not query:
            return
        if self._indexed_count == 0:
            self.status.showMessage("⏳  Indexing still in progress — try again shortly")
            return
        self.table.setRowCount(0)
        self.btn_search.setEnabled(False)
        self.status.showMessage(f"🔍  Searching for ‘{query}’…")

        self._srch_thread = SearchThread(self._svc, query)
        self._srch_thread.results.connect(self._on_results)
        self._srch_thread.error.connect(
            lambda e: (self.status.showMessage(f"⚠️  Search error: {e}"),
                       self.btn_search.setEnabled(True))
        )
        self._srch_thread.start()

    def _on_results(self, hits: list):
        self.table.setRowCount(0)
        for row_idx, h in enumerate(hits):
            self.table.insertRow(row_idx)
            score = h.get("combined_score", h.get("score", 0.0))
            color = (
                QColor("#6fcf97") if score >= 0.75 else
                QColor("#f2c94c") if score >= 0.50 else
                QColor("#eb5757")
            )
            cells = [
                str(row_idx + 1),
                h.get("name",  Path(h.get("path","")).name),
                f"{score*100:.1f}%",
                f"{h.get('semantic_score', 0)*100:.1f}%",
                f"{h.get('time_score',     0)*100:.1f}%",
                f"{h.get('frequency_score',0)*100:.1f}%",
                h.get("extension", Path(h.get("path","")).suffix),
                h.get("path", ""),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, h.get("path", ""))
                if col == 2:                  # score column: colour-coded
                    item.setForeground(color)
                    item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                elif col == 1:                # file name: brighter
                    item.setForeground(QColor(255, 255, 255, 230))
                self.table.setItem(row_idx, col, item)

        n = len(hits)
        self.status.showMessage(
            f"✅  {n} result{'s' if n!=1 else ''} for ‘{self.inp_query.text().strip()}’"
            f"   —  double-click to open"
        )
        self.btn_search.setEnabled(True)

    # ── Open file ─────────────────────────────────────────────────────────────
    def _on_open_file(self):
        row = self.table.currentRow()
        if row < 0:
            return
        path = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Not found", f"File no longer exists:\n{path}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    # ── Tray ─────────────────────────────────────────────────────────────────
    def _toggle_window(self):
        self.hide() if self.isVisible() else self.show()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    def _quit(self):
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """Minimise to tray instead of quitting."""
        if self._tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def showEvent(self, event):
        """Apply acrylic effect once the window has a valid HWND."""
        super().showEvent(event)
        if platform.system() == "Windows":
            try:
                self._enable_acrylic(int(self.winId()))
            except Exception as exc:
                logger.warning(f"Acrylic effect unavailable: {exc}")

    # ── Windows DWM Acrylic ───────────────────────────────────────────────────
    @staticmethod
    def _enable_acrylic(hwnd: int):
        """
        Enable the Windows 10/11 acrylic (or Mica) blur-behind effect
        using DwmSetWindowAttribute.  Falls back gracefully.
        """
        # --- attempt 1: Windows 11 Mica / Mica Alt (build 22621+) -----------
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dwm = ctypes.windll.dwmapi

        # Turn on dark mode for the title bar
        val = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val),
        )

        # Try Mica Alt (value 4) → falls back to Acrylic (3) → Mica (2)
        for backdrop in (4, 3, 2):
            val = ctypes.c_int(backdrop)
            hr = dwm.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(val), ctypes.sizeof(val),
            )
            if hr == 0:  # S_OK
                return

        # --- attempt 2: SetWindowCompositionAttribute (Win 10 acrylic) ------
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState",   ctypes.c_int),
                ("AccentFlags",   ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId",   ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data",      ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_uint),
            ]

        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        WCA_ACCENT_POLICY = 19
        # ABGR tint: 0xB0_14141E  →  dark navy at ~69 % opacity
        accent = ACCENT_POLICY(
            ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, 0xB014141E, 0
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
    app.setApplicationVersion("2.0.0")
    app.setStyle("Fusion")           # crisp on every OS

    service = DesktopService()
    win = MainWindow(service)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

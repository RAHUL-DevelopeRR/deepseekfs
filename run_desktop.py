"""
DeepSeekFS – Desktop Entry Point (v2.0 PyQt6 Monolithic)
=========================================================
Replaces run.py + FastAPI + pywebview with a single native PyQt6 window.
All business logic is called directly — zero HTTP, zero network sockets.

Usage:
    python run_desktop.py
"""
from __future__ import annotations

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
from PyQt6.QtGui   import QFont, QColor, QIcon

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
    QMainWindow, QWidget#central { background:#f0f2f5; }

    QLabel#title {
        font-size:22px; font-weight:700; color:#1a1a2e;
    }
    QLabel#subtitle { font-size:12px; color:#6c757d; }

    QLineEdit {
        border:2px solid #dee2e6;
        border-radius:8px;
        padding:10px 14px;
        font-size:14px;
        color: #1a1a2e;
        background:#ffffff;
    }
    QLineEdit:focus { border-color:#4361ee; background:#fafbff; }

    QPushButton#btn_search {
        background:#4361ee;
        color:#ffffff;
        border:none;
        border-radius:8px;
        padding:10px 28px;
        font-size:14px;
        font-weight:600;
    }
    QPushButton#btn_search:hover   { background:#3451d1; }
    QPushButton#btn_search:pressed { background:#2541c0; }
    QPushButton#btn_search:disabled{ background:#adb5bd; }

    QPushButton#btn_folder {
        background:#ffffff;
        color:#4361ee;
        border:2px solid #4361ee;
        border-radius:8px;
        padding:8px 18px;
        font-size:13px;
    }
    QPushButton#btn_folder:hover { background:#eef0fd; }

    QTableWidget {
        background:#ffffff;
        color:#1a1a2e;
        border:1px solid #dee2e6;
        border-radius:8px;
        gridline-color:#f1f3f5;
        font-size:13px;
    }
    QTableWidget::item          { padding:8px 10px; }
    QTableWidget::item:selected { background:#4361ee; color:#ffffff; }
    QHeaderView::section {
        background:#f8f9fa;
        font-weight:600;
        padding:8px 10px;
        border:none;
        border-bottom:2px solid #dee2e6;
    }

    QProgressBar {
        border:1px solid #dee2e6;
        border-radius:6px;
        text-align:center;
        font-size:11px;
        height:18px;
    }
    QProgressBar::chunk { background:#4361ee; border-radius:5px; }

    QStatusBar { font-size:12px; color:#6c757d; }
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
        self.table.setAlternatingRowColors(False)
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
                QColor("#2d6a4f") if score >= 0.75 else
                QColor("#b5500a") if score >= 0.50 else
                QColor("#c0392b")
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

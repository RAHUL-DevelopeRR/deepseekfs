import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QProgressBar, QListWidget,
    QListWidgetItem, QFileDialog, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QColor
import threading
import os

# ── Indexing background thread ───────────────────────────────────────────────
class IndexingThread(QThread):
    progress = pyqtSignal(int, str)   # percent, message
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, service, paths):
        super().__init__()
        self.service = service
        self.paths = paths

    def run(self):
        try:
            self.service.start_indexing(
                self.paths,
                on_progress=lambda p, m: self.progress.emit(p, m),
                on_done=lambda ok, m: self.finished.emit(ok, m)
            )
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Search background thread ─────────────────────────────────────────────────
class SearchThread(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, service, query):
        super().__init__()
        self.service = service
        self.query = query

    def run(self):
        try:
            results = self.service.search(self.query)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ── Main Window ──────────────────────────────────────────────────────────────
class DeepSeekFSWindow(QMainWindow):
    """Main PyQt6 desktop window for DeepSeekFS."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSeekFS – Semantic File Search")
        self.resize(900, 620)
        self._service = None
        self._search_thread = None
        self._index_thread = None
        self._init_ui()
        self._init_tray()
        self._load_service()

    # ── UI setup ─────────────────────────────────────────────────────────────
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("🔍 DeepSeekFS – Semantic File Search")
        header.setStyleSheet("font-size:20px; font-weight:bold; color:#2d6cdf;")
        root.addWidget(header)

        # Search bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search your files semantically…")
        self.search_input.setMinimumHeight(36)
        self.search_input.returnPressed.connect(self._do_search)
        self.btn_search = QPushButton("Search")
        self.btn_search.setMinimumHeight(36)
        self.btn_search.clicked.connect(self._do_search)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.btn_search)
        root.addLayout(search_row)

        # Results list
        self.result_list = QListWidget()
        self.result_list.setAlternatingRowColors(True)
        self.result_list.itemDoubleClicked.connect(self._open_file)
        root.addWidget(self.result_list, 1)

        # Status + progress
        self.status_label = QLabel("Ready.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root.addWidget(self.status_label)
        root.addWidget(self.progress_bar)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self.btn_index = QPushButton("📁 Index Folder")
        self.btn_index.clicked.connect(self._pick_folder)
        self.btn_rebuild = QPushButton("🔄 Rebuild Index")
        self.btn_rebuild.clicked.connect(self._rebuild)
        self.btn_stats = QPushButton("📊 Index Stats")
        self.btn_stats.clicked.connect(self._show_stats)
        btn_row.addWidget(self.btn_index)
        btn_row.addWidget(self.btn_rebuild)
        btn_row.addWidget(self.btn_stats)
        root.addLayout(btn_row)

        # Stylesheet
        self.setStyleSheet("""
            QMainWindow { background: #f5f5f5; }
            QPushButton {
                background: #2d6cdf; color: white;
                border-radius: 6px; padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover { background: #1a4fad; }
            QLineEdit {
                border: 1px solid #ccc; border-radius: 6px;
                padding: 4px 10px; font-size: 13px;
            }
            QListWidget { border: 1px solid #ddd; border-radius: 6px; }
        """)

    def _init_tray(self):
        self.tray = QSystemTrayIcon(self)
        menu = QMenu()
        menu.addAction("Show", self.show)
        menu.addAction("Quit", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    # ── Service loading ───────────────────────────────────────────────────────
    def _load_service(self):
        try:
            from services_desktop import get_service
            self._service = get_service()
            self.status_label.setText("Service loaded. Ready to search.")
        except Exception as e:
            self.status_label.setText(f"Service error: {e}")

    # ── Search ────────────────────────────────────────────────────────────────
    def _do_search(self):
        query = self.search_input.text().strip()
        if not query or not self._service:
            return
        self.result_list.clear()
        self.status_label.setText("Searching…")
        self._search_thread = SearchThread(self._service, query)
        self._search_thread.results_ready.connect(self._show_results)
        self._search_thread.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self._search_thread.start()

    def _show_results(self, results):
        self.result_list.clear()
        for r in results:
            score = r.get("score", 0)
            path = r.get("path", "")
            item = QListWidgetItem(f"[{score:.2f}]  {path}")
            if score >= 0.75:
                item.setForeground(QColor("#2a9d2a"))
            elif score >= 0.5:
                item.setForeground(QColor("#e6a817"))
            else:
                item.setForeground(QColor("#cc3333"))
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.result_list.addItem(item)
        self.status_label.setText(f"{len(results)} result(s) found.")

    def _open_file(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and self._service:
            self._service.open_file(path)

    # ── Indexing ──────────────────────────────────────────────────────────────
    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Index")
        if folder:
            self._start_indexing([folder])

    def _rebuild(self):
        if self._service:
            self._service.rebuild_index()
            self.status_label.setText("Index rebuilt.")

    def _start_indexing(self, paths):
        if not self._service:
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._index_thread = IndexingThread(self._service, paths)
        self._index_thread.progress.connect(
            lambda p, m: (self.progress_bar.setValue(p), self.status_label.setText(m))
        )
        self._index_thread.finished.connect(self._on_index_done)
        self._index_thread.start()

    def _on_index_done(self, ok, msg):
        self.progress_bar.setVisible(False)
        self.status_label.setText(msg)

    def _show_stats(self):
        if self._service:
            stats = self._service.get_index_stats()
            QMessageBox.information(self, "Index Stats", str(stats))


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeekFS")
    win = DeepSeekFSWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

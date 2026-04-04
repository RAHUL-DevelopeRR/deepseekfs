"""Memory Lane — Daily Activity Recap Panel (PyQt6)

Shows a chronological view of user activity:
- Files touched today
- Top queries / topics
- Most important files with timestamps
- Switch between Today / Yesterday / Last 7 days
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import app.config as config
from app.logger import logger
from services.desktop_service import DesktopService


# ── colour tokens (match spotlight_panel) ────────────────────
class C:
    PANEL_BG = QColor(25, 25, 25, 245)
    T1 = QColor(255, 255, 255, 235)
    T2 = QColor(153, 153, 153, 255)
    T3 = QColor(102, 102, 102, 255)
    BLUE_Q = QColor(0, 120, 212)
    CARD_HOVER = QColor(45, 45, 45, 255)
    DIVIDER = QColor(51, 51, 51, 255)


FN = "'Segoe UI Variable Display', 'Segoe UI', 'Inter', system-ui, sans-serif"
MN = "'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace"


class MemoryLanePanel(QFrame):
    """Daily activity recap panel — view your digital footprint."""

    closed = pyqtSignal()
    file_clicked = pyqtSignal(str)

    def __init__(self, svc: DesktopService, parent=None):
        super().__init__(parent)
        self._svc = svc
        self._current_date = datetime.now()

        self.setStyleSheet(f"""
            MemoryLanePanel {{
                background: rgba(25, 25, 25, 250);
                border: 1px solid rgba(51, 51, 51, 200);
                border-radius: 12px;
            }}
        """)

        self._build_ui()
        self._load_stats(self._current_date)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── HEADER ──
        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("Memory Lane")
        title.setStyleSheet(f"""
            font-family: {FN}; font-size: 18px; font-weight: 700;
            color: rgba(255,255,255,0.90); background: transparent;
        """)
        header.addWidget(title)
        header.addStretch()

        # Date navigation buttons
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedSize(32, 28)
        self._btn_prev.setStyleSheet(self._btn_css())
        self._btn_prev.clicked.connect(self._prev_day)
        header.addWidget(self._btn_prev)

        self._date_label = QLabel("Today")
        self._date_label.setStyleSheet(f"""
            font-family: {FN}; font-size: 12px; font-weight: 600;
            color: rgba(255,255,255,0.70); background: transparent;
            padding: 0 12px;
        """)
        header.addWidget(self._date_label)

        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedSize(32, 28)
        self._btn_next.setStyleSheet(self._btn_css())
        self._btn_next.clicked.connect(self._next_day)
        header.addWidget(self._btn_next)

        self._btn_today = QPushButton("Today")
        self._btn_today.setFixedSize(60, 28)
        self._btn_today.setStyleSheet(self._btn_css())
        self._btn_today.clicked.connect(self._goto_today)
        header.addWidget(self._btn_today)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 4px;
                color: rgba(255,255,255,0.40); font-size: 16px;
            }}
            QPushButton:hover {{ background: rgba(255,0,0,0.15); color: rgba(255,100,100,0.90); }}
        """)
        btn_close.clicked.connect(self.closed.emit)
        header.addWidget(btn_close)

        root.addLayout(header)

        # ── DIVIDER ──
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(div)

        # ── SCROLL AREA ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 6, 0, 0)
        self.content_layout.setSpacing(16)

        self.scroll.setWidget(self.content_widget)
        root.addWidget(self.scroll, 1)

    def _btn_css(self):
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.04); border: none; border-radius: 4px;
                color: rgba(255,255,255,0.55); font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.85); }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.06); }}
        """

    def _load_stats(self, date: datetime):
        """Load and display statistics for a given date."""
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Update date label
        today = datetime.now().date()
        if date.date() == today:
            self._date_label.setText("Today")
        elif date.date() == today - timedelta(days=1):
            self._date_label.setText("Yesterday")
        else:
            self._date_label.setText(date.strftime("%B %d, %Y"))

        # Enable/disable next button
        self._btn_next.setEnabled(date.date() < today)

        try:
            stats = self._svc.get_daily_stats(date)

            # ── SUMMARY CARDS ──
            summary = QHBoxLayout()
            summary.setSpacing(12)

            cards_data = [
                ("📁", "Files Accessed", str(stats.get('files_accessed', 0))),
                ("🔍", "Searches", str(stats.get('searches_performed', 0))),
                ("📊", "Total Events", str(stats.get('total_events', 0))),
            ]

            for icon, label, value in cards_data:
                card = self._create_stat_card(icon, label, value)
                summary.addWidget(card)

            self.content_layout.addLayout(summary)

            # ── TOP QUERIES ──
            top_queries = stats.get('top_queries', [])
            if top_queries:
                self.content_layout.addWidget(self._create_section_header("Top Searches"))
                for query_data in top_queries[:5]:
                    query_text = query_data.get('query_text', '')
                    count = query_data.get('count', 0)
                    if query_text:
                        item = self._create_query_item(query_text, count)
                        self.content_layout.addWidget(item)

            # ── TOP FILES ──
            top_files = stats.get('top_files', [])
            if top_files:
                self.content_layout.addWidget(self._create_section_header("Most Accessed Files"))
                for file_data in top_files[:10]:
                    file_path = file_data.get('file_path', '')
                    count = file_data.get('count', 0)
                    if file_path and Path(file_path).exists():
                        item = self._create_file_item(file_path, count)
                        self.content_layout.addWidget(item)

            # Empty state
            if not top_queries and not top_files:
                empty = QLabel("No activity recorded for this day")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet(f"""
                    font-family: {FN}; font-size: 13px; font-weight: 400;
                    color: rgba(255,255,255,0.25); padding: 50px;
                """)
                self.content_layout.addWidget(empty)

            self.content_layout.addStretch()

        except Exception as e:
            logger.error(f"Memory Lane: failed to load stats: {e}")
            error = QLabel("Failed to load activity data")
            error.setStyleSheet(f"color: rgba(255,100,100,0.7); font-size: 12px;")
            self.content_layout.addWidget(error)

    def _create_stat_card(self, icon: str, label: str, value: str) -> QFrame:
        """Create a summary statistics card."""
        card = QFrame()
        card.setFixedHeight(80)
        card.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        layout.addWidget(icon_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            font-family: {FN}; font-size: 20px; font-weight: 700;
            color: rgba(255,255,255,0.85); background: transparent;
        """)
        layout.addWidget(value_label)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            font-family: {FN}; font-size: 10px; font-weight: 500;
            color: rgba(255,255,255,0.35); background: transparent;
        """)
        layout.addWidget(label_widget)

        return card

    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header label."""
        header = QLabel(text.upper())
        header.setStyleSheet(f"""
            font-family: {FN}; font-size: 10px; font-weight: 700;
            letter-spacing: 1px; color: rgba(255,255,255,0.30);
            background: transparent; padding: 8px 4px 4px 4px;
        """)
        return header

    def _create_query_item(self, query_text: str, count: int) -> QFrame:
        """Create a query item row."""
        item = QFrame()
        item.setFixedHeight(36)
        item.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 6px;
            }}
            QFrame:hover {{
                background: rgba(255,255,255,0.04);
            }}
        """)

        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Icon
        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon)

        # Query text
        query_label = QLabel(query_text)
        query_label.setStyleSheet(f"""
            font-family: {MN}; font-size: 11px; font-weight: 500;
            color: rgba(255,255,255,0.75); background: transparent;
        """)
        layout.addWidget(query_label, 1)

        # Count badge
        count_label = QLabel(f"{count}×")
        count_label.setStyleSheet(f"""
            font-family: {FN}; font-size: 10px; font-weight: 600;
            color: rgba(0,120,212,0.80); background: rgba(0,120,212,0.12);
            padding: 2px 8px; border-radius: 10px;
        """)
        layout.addWidget(count_label)

        return item

    def _create_file_item(self, file_path: str, count: int) -> QFrame:
        """Create a file item row (clickable)."""
        item = QFrame()
        item.setFixedHeight(36)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setProperty("file_path", file_path)
        item.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 6px;
            }}
            QFrame:hover {{
                background: rgba(0,120,212,0.10);
                border-color: rgba(0,120,212,0.20);
            }}
        """)

        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Icon
        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon)

        # File name
        name = Path(file_path).name
        if len(name) > 50:
            name = name[:47] + "..."
        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            font-family: {FN}; font-size: 11px; font-weight: 500;
            color: rgba(255,255,255,0.75); background: transparent;
        """)
        layout.addWidget(name_label, 1)

        # Count badge
        count_label = QLabel(f"{count}×")
        count_label.setStyleSheet(f"""
            font-family: {FN}; font-size: 10px; font-weight: 600;
            color: rgba(52,199,89,0.80); background: rgba(52,199,89,0.12);
            padding: 2px 8px; border-radius: 10px;
        """)
        layout.addWidget(count_label)

        # Connect click
        item.mousePressEvent = lambda e: self._on_file_clicked(file_path) if e.button() == Qt.MouseButton.LeftButton else None

        return item

    def _on_file_clicked(self, path: str):
        """Handle file item click."""
        self.file_clicked.emit(path)

    def _prev_day(self):
        """Navigate to previous day."""
        self._current_date -= timedelta(days=1)
        self._load_stats(self._current_date)

    def _next_day(self):
        """Navigate to next day."""
        self._current_date += timedelta(days=1)
        self._load_stats(self._current_date)

    def _goto_today(self):
        """Navigate to today."""
        self._current_date = datetime.now()
        self._load_stats(self._current_date)

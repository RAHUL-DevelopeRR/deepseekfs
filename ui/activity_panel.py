"""
Neuron — Activity Panel
=========================
Dedicated UI tab showing structured agent events.

Features:
  - Real-time event timeline (auto-refreshes every 3s)
  - Filter by event type
  - Task-specific drill-down
  - Stats header (total events, tool calls, errors)
  - Clear button

Architecture:
  - Reads from EventStore (SQLite) — no direct agent coupling
  - QTimer for periodic refresh
  - Thread-safe signal updates
"""
from __future__ import annotations

import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from app.logger import logger

FN = "'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"


# ── Event type display ────────────────────────────────────────

_TYPE_ICONS = {
    "tool_call":       "🔧",
    "tool_result":     "📋",
    "llm_inference":   "🧠",
    "search":          "🔍",
    "task_created":    "📝",
    "task_step":       "▶️",
    "task_completed":  "✅",
    "task_failed":     "❌",
    "plan_generated":  "📊",
    "watcher_trigger": "👁️",
    "plugin_loaded":   "🔌",
    "user_input":      "💬",
    "error":           "⚠️",
}

_STATUS_COLORS = {
    "success": "#4dd0a0",
    "started": "#a78bfa",
    "failed":  "#ff6b6b",
    "blocked": "#ff8c42",
    "denied":  "#ff8c42",
    "running": "#7c8aff",
}


class ActivityPanel(QFrame):
    """Dedicated Activity tab showing structured event timeline."""

    _sig_refresh = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._filter_type = "all"
        self._sig_refresh.connect(self._do_refresh)
        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # ── Header row ────────────────────────────────
        header = QHBoxLayout()

        title = QLabel("Activity Timeline")
        title.setStyleSheet(f"""
            font-family: {FN};
            font-size: 15px;
            font-weight: 700;
            color: rgba(255,255,255,0.9);
        """)
        header.addWidget(title)
        header.addStretch()

        # Stats labels
        self._stats_label = QLabel("—")
        self._stats_label.setStyleSheet(f"""
            font-family: {FN};
            font-size: 11px;
            color: rgba(255,255,255,0.45);
        """)
        header.addWidget(self._stats_label)

        layout.addLayout(header)

        # ── Filter row ────────────────────────────────
        filter_row = QHBoxLayout()

        self._filter = QComboBox()
        self._filter.addItem("All Events", "all")
        self._filter.addItem("🔧 Tool Calls", "tool_call")
        self._filter.addItem("🧠 LLM Inference", "llm_inference")
        self._filter.addItem("🔍 Searches", "search")
        self._filter.addItem("📝 Tasks", "task_created")
        self._filter.addItem("⚠️ Errors", "error")
        self._filter.setFixedWidth(180)
        self._filter.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255,255,255,0.06);
                color: white;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 4px 8px;
                font-family: {FN};
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: #1e1e2e;
                color: white;
                selection-background-color: rgba(167,139,250,0.3);
            }}
        """)
        self._filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter)
        filter_row.addStretch()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(70, 28)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,100,100,0.15);
                color: #ff6b6b;
                border: 1px solid rgba(255,100,100,0.2);
                border-radius: 6px;
                font-family: {FN};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(255,100,100,0.25);
            }}
        """)
        clear_btn.clicked.connect(self._on_clear)
        filter_row.addWidget(clear_btn)

        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.6);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.12);
            }}
        """)
        refresh_btn.clicked.connect(self._force_refresh)
        filter_row.addWidget(refresh_btn)

        layout.addLayout(filter_row)

        # ── Event list ────────────────────────────────
        self._events_view = QTextEdit()
        self._events_view.setReadOnly(True)
        self._events_view.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0,0,0,0.2);
                color: rgba(255,255,255,0.8);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 8px;
                padding: 8px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 11px;
                selection-background-color: rgba(167,139,250,0.3);
            }}
        """)
        layout.addWidget(self._events_view, 1)

    def _start_timer(self):
        """Auto-refresh every 3 seconds."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._force_refresh)
        self._timer.start(3000)

    def _on_filter_changed(self, index: int):
        self._filter_type = self._filter.itemData(index)
        self._force_refresh()

    def _force_refresh(self):
        self._sig_refresh.emit()

    def _do_refresh(self):
        """Fetch and render events from the store."""
        try:
            from services.events import get_event_store
            store = get_event_store()

            # Stats
            stats = store.stats()
            self._stats_label.setText(
                f"{stats['total_events']} events · "
                f"{stats['tool_calls']} tools · "
                f"{stats['errors']} errors · "
                f"{stats['tasks']} tasks"
            )

            # Events
            if self._filter_type == "all":
                events = store.query_recent(100)
            else:
                events = store.query_by_type(self._filter_type, 100)

            if not events:
                self._events_view.setHtml(
                    '<div style="color: rgba(255,255,255,0.3); padding: 20px; text-align: center;">'
                    'No events yet. Use MemoryOS to generate activity.</div>'
                )
                return

            html = self._render_events(events)
            self._events_view.setHtml(html)

        except Exception as e:
            logger.warning(f"ActivityPanel: refresh failed: {e}")

    def _render_events(self, events: list) -> str:
        """Render events as styled HTML."""
        lines = []
        for ev in events:
            icon = _TYPE_ICONS.get(ev["event_type"], "•")
            status_color = _STATUS_COLORS.get(ev["status"], "rgba(255,255,255,0.5)")
            ts = datetime.fromtimestamp(ev["timestamp"]).strftime("%H:%M:%S")

            # Duration badge
            dur = ""
            if ev["duration_ms"] > 0:
                dur = f' <span style="color: rgba(255,255,255,0.3);">{ev["duration_ms"]}ms</span>'

            # Tool name
            tool = ""
            if ev["tool_name"]:
                tool = f' <span style="color: #a78bfa;">{ev["tool_name"]}</span>'

            # Summary
            summary = ev.get("input_summary", "") or ev.get("output_summary", "")
            summary_html = ""
            if summary:
                safe = summary[:150].replace("<", "&lt;").replace(">", "&gt;")
                summary_html = f'<br/><span style="color: rgba(255,255,255,0.35); margin-left: 24px;">{safe}</span>'

            # Task ID
            task_badge = ""
            if ev["task_id"]:
                task_badge = (
                    f' <span style="background: rgba(167,139,250,0.15); '
                    f'color: #a78bfa; padding: 1px 5px; border-radius: 3px; '
                    f'font-size: 10px;">{ev["task_id"][:8]}</span>'
                )

            lines.append(
                f'<div style="padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.04);">'
                f'<span style="color: rgba(255,255,255,0.3);">{ts}</span> '
                f'{icon}{tool}{task_badge}{dur} '
                f'<span style="color: {status_color};">■</span>'
                f'{summary_html}'
                f'</div>'
            )

        return "".join(lines)

    def _on_clear(self):
        """Clear all events."""
        try:
            from services.events import get_event_store
            get_event_store().clear()
            self._force_refresh()
        except Exception as e:
            logger.warning(f"ActivityPanel: clear failed: {e}")

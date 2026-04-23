"""
Neuron -- MemoryOS Chat Panel (v2)
===================================
Intelligent chat interface with auto-routing.

Modes:
  [Auto]   - Model decides (default, like Claude/GPT)
  [Query]  - Force semantic file search
  [Action] - Force tool calling / file operations

Architecture:
  - Auto mode uses keyword detection to route (no LLM needed)
  - pyqtSignal for thread-safe cross-thread UI updates
  - Background thread for inference, main thread for rendering
"""
from __future__ import annotations

import threading

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget,
    QTextEdit, QLineEdit, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.logger import logger

FN = "'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"

# Mode colors (used for pills + response border)
MODE_COLORS = {
    "auto":   ("#a78bfa", "rgba(167,139,250,0.3)"),   # Purple (smart)
    "query":  ("#4dd0a0", "rgba(60,200,160,0.3)"),     # Green-teal
    "action": ("#ff8c42", "rgba(255,140,66,0.3)"),     # Orange
}

MODE_LABELS = {
    "auto":   "Auto",
    "query":  "Query",
    "action": "Action",
}

MODE_PLACEHOLDERS = {
    "auto":   "Ask anything... (model decides how to handle it)",
    "query":  "Search your files... (e.g. 'find my Python projects')",
    "action": "Give a task... (e.g. 'organize my Downloads by type')",
}


class MemoryOSPanel(QFrame):
    """Three-mode MemoryOS chat interface with streaming."""

    _sig_response = pyqtSignal(str, str)  # (html, mode)
    _sig_error = pyqtSignal(str)
    _sig_token = pyqtSignal(str)          # streaming token
    _sig_stream_end = pyqtSignal()        # streaming complete

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._active = False
        self._mode = "auto"  # Default mode (model decides)
        self._streaming = False  # True while tokens are arriving
        self._stream_mode = ""  # Mode during current stream

        # RLHF feedback state
        self._last_query = ""
        self._last_response = ""
        self._last_intent = ""
        self._last_confidence = 0.0

        self._sig_response.connect(self._on_response)
        self._sig_error.connect(self._on_error)
        self._sig_token.connect(self._on_token)
        self._sig_stream_end.connect(self._on_stream_end)

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Mode selector pills
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        mode_row.addStretch()

        self._mode_btns = {}
        for mode_key in ("auto", "query", "action"):
            btn = QPushButton(MODE_LABELS[mode_key])
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("mode", mode_key)
            btn.clicked.connect(lambda checked, m=mode_key: self._set_mode(m))
            self._mode_btns[mode_key] = btn
            mode_row.addWidget(btn)

        mode_row.addStretch()
        layout.addLayout(mode_row)
        self._update_mode_styles()

        # Chat display
        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0,0,0,0.25);
                color: rgba(255,255,255,0.85);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
                padding: 12px;
                font-family: {FN};
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.10); border-radius: 2px;
            }}
        """)
        self._chat.setHtml(self._welcome_html())
        layout.addWidget(self._chat, stretch=1)

        # RLHF feedback bar (inline, between chat and input)
        self._build_feedback_bar(layout)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText(MODE_PLACEHOLDERS["auto"])
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.06);
                color: #fff;
                border: 1px solid rgba(100,100,255,0.25);
                border-radius: 8px;
                padding: 8px 12px;
                font-family: {FN}; font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: rgba(100,150,255,0.5);
                background: rgba(255,255,255,0.08);
            }}
        """)
        self._input.returnPressed.connect(self.send)
        input_row.addWidget(self._input, stretch=1)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(60, 34)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(56,156,255,0.3);
                color: #65B8FF;
                border: 1px solid rgba(56,156,255,0.25);
                border-radius: 8px;
                font-family: {FN}; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(56,156,255,0.5); color: #fff;
            }}
        """)
        send_btn.clicked.connect(self.send)
        input_row.addWidget(send_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(50, 34)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.4);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 8px;
                font-family: {FN}; font-size: 11px;
            }}
            QPushButton:hover {{
                background: rgba(255,80,80,0.2); color: #ff8888;
            }}
        """)
        clear_btn.clicked.connect(self.clear)
        input_row.addWidget(clear_btn)

        layout.addLayout(input_row)
        self.hide()

    # ── Mode Selector ─────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode = mode
        self._input.setPlaceholderText(MODE_PLACEHOLDERS[mode])
        self._update_mode_styles()
        self._input.setFocus()

    def _update_mode_styles(self):
        for key, btn in self._mode_btns.items():
            color, bg = MODE_COLORS[key]
            if key == self._mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {bg};
                        color: {color};
                        border: 1px solid {color};
                        border-radius: 12px;
                        padding: 2px 14px;
                        font-family: {FN}; font-size: 11px; font-weight: 700;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(255,255,255,0.04);
                        color: rgba(255,255,255,0.35);
                        border: 1px solid rgba(255,255,255,0.06);
                        border-radius: 12px;
                        padding: 2px 14px;
                        font-family: {FN}; font-size: 11px; font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background: rgba(255,255,255,0.08);
                        color: rgba(255,255,255,0.6);
                    }}
                """)

    # ── Public API ────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True
        self.show()
        self._input.setFocus()

    def deactivate(self):
        self._active = False
        self.hide()

    def send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._input.setEnabled(False)
        self._hide_feedback_bar()  # Hide previous feedback bar

        # Store for feedback
        self._last_query = text
        self._last_response = ""

        mode_label = MODE_LABELS[self._mode].upper()
        self._append_message("You", text, color="#65B8FF", badge=mode_label)
        self._set_status(f"Thinking ({mode_label})...")

        current_mode = self._mode
        threading.Thread(
            target=self._run_agent,
            args=(text, current_mode),
            daemon=True,
        ).start()

    def clear(self):
        self._chat.clear()
        self._chat.setHtml(self._welcome_html())
        try:
            from services.memory_os import get_memory_os
            get_memory_os().clear_history()
        except Exception:
            pass
        self._set_status("Ready")

    # ── Agent Execution (background thread) ───────────────────

    def _run_agent(self, text: str, mode: str):
        try:
            from services.memory_os import get_memory_os
            agent = get_memory_os()
            agent.on_confirmation_needed = lambda name, desc, args: True

            # Wire streaming callback → emits signal per token
            self._stream_mode = mode
            agent.on_token = lambda token: self._sig_token.emit(token)

            logger.info(f"MemoryOSPanel: [{mode.upper()}] {text!r}")
            response = agent.chat(text, mode=mode)
            logger.info(f"MemoryOSPanel: Response ({len(response) if response else 0} chars)")

            # Store response for feedback
            self._last_response = response or ""

            # Disconnect streaming
            agent.on_token = None

            if not response or not response.strip():
                response = "(No response generated. Try rephrasing your query.)"

            # If we were streaming, signal end instead of full response
            if self._streaming:
                self._sig_stream_end.emit()
            else:
                safe = (
                    response
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>")
                )
                self._sig_response.emit(safe, mode)

        except Exception as e:
            logger.error(f"MemoryOS agent error: {e}", exc_info=True)
            agent_ref = None
            try:
                from services.memory_os import get_memory_os
                agent_ref = get_memory_os()
                agent_ref.on_token = None
            except Exception:
                pass
            self._sig_error.emit(str(e))

    def _on_token(self, token: str):
        """Handle a single streaming token (main thread, signal-safe)."""
        if not self._streaming:
            # First token — create the response block header
            self._streaming = True
            color, _ = MODE_COLORS.get(self._stream_mode, ("#7c8aff", "rgba(100,120,255,0.3)"))
            label = MODE_LABELS.get(self._stream_mode, "MemoryOS")
            self._append_html(
                f'<div style="color: rgba(255,255,255,0.85); margin: 6px 0; '
                f'padding: 8px; background: rgba(255,255,255,0.03); '
                f'border-radius: 6px; border-left: 3px solid {color};">'
                f'<b style="color: {color};">{label}:</b><br>'
            )
            self._set_status(f"Streaming...")

        # Append token — use insertText to preserve whitespace
        # (insertHtml strips leading/trailing spaces, causing the no-space bug)
        text = token.replace("\r", "")
        cursor = self._chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._chat.setTextCursor(cursor)
        cursor.insertText(text)
        vbar = self._chat.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _on_stream_end(self):
        """Streaming complete — close the response block."""
        self._streaming = False
        # Close the div tag
        cursor = self._chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._chat.setTextCursor(cursor)
        cursor.insertHtml("</div>")

        self._input.setEnabled(True)
        self._input.setFocus()
        self._set_status("Ready")
        self._show_feedback_bar()  # Show 👍/👎 after stream ends

    def _on_response(self, safe_html: str, mode: str):
        color, _ = MODE_COLORS.get(mode, ("#7c8aff", "rgba(100,120,255,0.3)"))
        label = MODE_LABELS.get(mode, "MemoryOS")

        logger.info(f"MemoryOSPanel: _on_response [{mode}] ({len(safe_html)} chars)")
        self._append_html(
            f'<div style="color: rgba(255,255,255,0.85); margin: 6px 0; '
            f'padding: 8px; background: rgba(255,255,255,0.03); '
            f'border-radius: 6px; border-left: 3px solid {color};">'
            f'<b style="color: {color};">{label}:</b><br>{safe_html}</div>'
        )
        self._input.setEnabled(True)
        self._input.setFocus()
        self._set_status("Ready")
        self._show_feedback_bar()  # Show 👍/👎 after response

    def _on_error(self, error_msg: str):
        self._append_html(
            f'<p style="color: #ff6666; margin: 4px 0;">'
            f'<b>Error:</b> {error_msg}</p>'
        )
        self._input.setEnabled(True)
        self._set_status("Error")

    # ── HTML Helpers ──────────────────────────────────────────

    def _append_message(self, sender: str, text: str, color: str = "#fff", badge: str = ""):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        badge_html = (
            f' <span style="background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.4); '
            f'border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: 600;">'
            f'{badge}</span>'
        ) if badge else ""
        self._append_html(
            f'<p style="color: {color}; margin: 4px 0;">'
            f'<b>{sender}:</b>{badge_html} {safe}</p>'
        )

    def _append_html(self, html: str):
        try:
            self._chat.append('')
            cursor = self._chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._chat.setTextCursor(cursor)
            self._chat.insertHtml(html)
            vbar = self._chat.verticalScrollBar()
            vbar.setValue(vbar.maximum())
        except Exception as e:
            logger.error(f"MemoryOSPanel: append failed: {e}")

    def _set_status(self, state: str):
        try:
            parent = self.parent()
            while parent is not None:
                if hasattr(parent, 'status'):
                    parent.status.setText(f"MemoryOS - {state}")
                    break
                parent = parent.parent()
        except Exception:
            pass

    # ── RLHF Feedback Bar ─────────────────────────────────────

    def _build_feedback_bar(self, layout: QVBoxLayout):
        """Create the inline feedback bar (hidden by default)."""
        self._feedback_bar = QWidget()
        self._feedback_bar.setFixedHeight(32)
        self._feedback_bar.setStyleSheet("background: transparent;")
        self._feedback_bar.hide()

        bar_layout = QHBoxLayout(self._feedback_bar)
        bar_layout.setContentsMargins(8, 2, 8, 2)
        bar_layout.setSpacing(6)

        lbl = QLabel("Was this helpful?")
        lbl.setStyleSheet(
            f"color: rgba(255,255,255,0.3); font-family: {FN}; "
            f"font-size: 11px; background: transparent;"
        )
        bar_layout.addWidget(lbl)

        self._btn_thumbs_up = QPushButton("👍")
        self._btn_thumbs_up.setFixedSize(28, 24)
        self._btn_thumbs_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_thumbs_up.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: rgba(76,175,80,0.2);
                border-color: rgba(76,175,80,0.4);
            }}
        """)
        self._btn_thumbs_up.clicked.connect(lambda: self._record_feedback(positive=True))
        bar_layout.addWidget(self._btn_thumbs_up)

        self._btn_thumbs_down = QPushButton("👎")
        self._btn_thumbs_down.setFixedSize(28, 24)
        self._btn_thumbs_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_thumbs_down.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: rgba(244,67,54,0.2);
                border-color: rgba(244,67,54,0.4);
            }}
        """)
        self._btn_thumbs_down.clicked.connect(lambda: self._record_feedback(positive=False))
        bar_layout.addWidget(self._btn_thumbs_down)

        self._feedback_label = QLabel("")
        self._feedback_label.setStyleSheet(
            f"color: rgba(255,255,255,0.25); font-family: {FN}; "
            f"font-size: 10px; background: transparent;"
        )
        bar_layout.addWidget(self._feedback_label)

        bar_layout.addStretch()
        layout.addWidget(self._feedback_bar)

    def _show_feedback_bar(self):
        """Show the feedback bar after a response."""
        if hasattr(self, '_feedback_bar'):
            self._feedback_label.setText("")
            self._btn_thumbs_up.setEnabled(True)
            self._btn_thumbs_down.setEnabled(True)
            self._feedback_bar.show()

    def _hide_feedback_bar(self):
        """Hide the feedback bar."""
        if hasattr(self, '_feedback_bar'):
            self._feedback_bar.hide()

    def _record_feedback(self, positive: bool):
        """Record user feedback via the RLHF store."""
        if not self._last_query or not self._last_response:
            return

        try:
            from services.feedback import get_feedback_store, Rating
            store = get_feedback_store()
            rating = Rating.POSITIVE if positive else Rating.NEGATIVE
            store.record(
                query=self._last_query,
                response=self._last_response,
                rating=rating,
                mode=self._mode,
                intent=self._last_intent,
                confidence=self._last_confidence,
            )

            # Visual confirmation
            emoji = "👍" if positive else "👎"
            self._feedback_label.setText(f"  {emoji} Feedback recorded")
            self._btn_thumbs_up.setEnabled(False)
            self._btn_thumbs_down.setEnabled(False)

            logger.info(
                f"RLHF: {'positive' if positive else 'negative'} for "
                f"'{self._last_query[:40]}'"
            )
        except Exception as e:
            logger.error(f"RLHF feedback failed: {e}")

    @staticmethod
    def _welcome_html() -> str:
        return (
            '<div style="color: rgba(255,255,255,0.35); font-style: italic; padding: 8px;">'
            '<b style="font-size: 14px;">&#x1F9E0; Welcome to MemoryOS</b><br><br>'
            '<span style="font-style: normal;">Intelligent modes:</span><br>'
            '<b style="color: #a78bfa;">Auto</b> &#8212; Model decides how to handle your request (default)<br>'
            '<b style="color: #4dd0a0;">Query</b> &#8212; Force file search by meaning<br>'
            '<b style="color: #ff8c42;">Action</b> &#8212; Force file operations &amp; shell commands<br><br>'
            '<span style="font-style: normal;">Just type &mdash; the AI routes automatically.</span></div>'
        )

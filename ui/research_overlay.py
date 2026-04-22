"""
Neuron — Research Overlay (Stealth Mode)
=========================================
Transparent, always-on-top floating panel with:
- Parrot.ai-style stealth mode (WDA_EXCLUDEFROMCAPTURE)
- Real-time speech detection via WASAPI + Vosk
- AI answer streaming from LLMEngine
- Draggable, resizable, opacity control

When stealth mode is ON:
- Window is INVISIBLE to Zoom, Teams, Meet, Discord, OBS
- Window is INVISIBLE to screenshots and recordings
- Window is VISIBLE only on the physical monitor

FOR RESEARCH PURPOSE ONLY.
"""
from __future__ import annotations

import ctypes
import threading
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QSlider, QFrame, QSizeGrip,
)

from app.logger import logger

# Windows constants
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class ResearchOverlay(QWidget):
    """Stealth research overlay — Parrot.ai architecture.
    
    Features:
    - Always on top, frameless, semi-transparent
    - Stealth mode: invisible to ALL screen capture
    - Speech detection: WASAPI loopback (interviewer only)
    - AI answers: streaming from LLMEngine
    - Draggable + resizable
    - Hotkey: Ctrl+Shift+R
    """
    
    speech_detected = pyqtSignal(str)       # Final sentence
    speech_partial = pyqtSignal(str)        # Partial recognitions
    answer_token = pyqtSignal(str)          # Streaming AI token
    answer_complete = pyqtSignal(str)       # Full AI answer
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._stealth_enabled = False
        self._listening = False
        self._drag_pos: Optional[QPoint] = None
        self._speech_service = None
        self._current_answer = ""
        
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
    
    def _setup_window(self):
        """Configure window flags for stealth overlay."""
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |  # Always on top
            Qt.WindowType.FramelessWindowHint |    # No title bar
            Qt.WindowType.Tool                     # No taskbar icon
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Default size and position (bottom-right of screen)
        self.setFixedWidth(420)
        self.setMinimumHeight(300)
        self.setMaximumHeight(600)
        self.resize(420, 350)
        
        # Position at bottom-right
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.width() - 440, geo.height() - 370)
    
    def _setup_ui(self):
        """Build the overlay UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main container with rounded corners and dark background
        self._container = QFrame()
        self._container.setObjectName("overlayContainer")
        self._container.setStyleSheet("""
            QFrame#overlayContainer {
                background-color: rgba(15, 15, 20, 220);
                border: 1px solid rgba(100, 100, 255, 80);
                border-radius: 12px;
            }
        """)
        
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(6)
        
        # ── Title bar ──
        title_bar = QHBoxLayout()
        
        self._status_label = QLabel("🎙 Neuron Research")
        self._status_label.setStyleSheet("color: #7c8aff; font-size: 12px; font-weight: bold;")
        title_bar.addWidget(self._status_label)
        
        title_bar.addStretch()
        
        # Stealth toggle button
        self._stealth_btn = QPushButton("👁 Stealth")
        self._stealth_btn.setFixedSize(80, 24)
        self._stealth_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 80, 180);
                color: #aaa;
                border: 1px solid rgba(100, 100, 130, 100);
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 110, 200);
                color: #fff;
            }
        """)
        self._stealth_btn.clicked.connect(self.toggle_stealth)
        title_bar.addWidget(self._stealth_btn)
        
        # Listen toggle
        self._listen_btn = QPushButton("▶ Listen")
        self._listen_btn.setFixedSize(70, 24)
        self._listen_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 120, 60, 180);
                color: #ccc;
                border: 1px solid rgba(60, 150, 80, 100);
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(50, 140, 70, 200);
                color: #fff;
            }
        """)
        self._listen_btn.clicked.connect(self.toggle_listening)
        title_bar.addWidget(self._listen_btn)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff4444;
            }
        """)
        close_btn.clicked.connect(self.hide)
        title_bar.addWidget(close_btn)
        
        container_layout.addLayout(title_bar)
        
        # ── Speech detected area ──
        self._speech_label = QLabel("Waiting for speech...")
        self._speech_label.setStyleSheet("""
            color: #8CA0FF;
            font-size: 11px;
            font-style: italic;
            padding: 4px 8px;
            background-color: rgba(30, 30, 50, 150);
            border-radius: 6px;
        """)
        self._speech_label.setWordWrap(True)
        self._speech_label.setMaximumHeight(60)
        container_layout.addWidget(self._speech_label)
        
        # ── AI answer area ──
        self._answer_text = QTextEdit()
        self._answer_text.setReadOnly(True)
        self._answer_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(20, 20, 30, 180);
                color: #e0e0e0;
                border: 1px solid rgba(80, 80, 110, 80);
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
        """)
        self._answer_text.setPlaceholderText("AI response will appear here...")
        container_layout.addWidget(self._answer_text, stretch=1)
        
        # ── Opacity slider ──
        opacity_bar = QHBoxLayout()
        
        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet("color: #666; font-size: 10px;")
        opacity_bar.addWidget(opacity_label)
        
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(85)
        self._opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(60, 60, 80, 150);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #7c8aff;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self._opacity_slider.valueChanged.connect(self._update_opacity)
        opacity_bar.addWidget(self._opacity_slider, stretch=1)
        
        self._opacity_value = QLabel("85%")
        self._opacity_value.setStyleSheet("color: #666; font-size: 10px;")
        opacity_bar.addWidget(self._opacity_value)
        
        container_layout.addLayout(opacity_bar)
        
        # ── Disclaimer ──
        disclaimer = QLabel("⚠ For research purposes only")
        disclaimer.setStyleSheet("color: #555; font-size: 9px; font-style: italic;")
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(disclaimer)
        
        layout.addWidget(self._container)
    
    def _connect_signals(self):
        """Connect internal signals."""
        self.speech_detected.connect(self._on_speech_final)
        self.speech_partial.connect(self._on_speech_partial)
        self.answer_token.connect(self._on_answer_token)
        self.answer_complete.connect(self._on_answer_complete)
    
    # ── Stealth Mode ──────────────────────────────────────────
    
    def toggle_stealth(self):
        """Toggle stealth mode (invisible to screen capture)."""
        if self._stealth_enabled:
            self.disable_stealth()
        else:
            self.enable_stealth()
    
    def enable_stealth(self):
        """Make window invisible to ALL screen sharing/recording."""
        try:
            hwnd = int(self.winId())
            result = ctypes.windll.user32.SetWindowDisplayAffinity(
                ctypes.c_void_p(hwnd),
                ctypes.c_ulong(WDA_EXCLUDEFROMCAPTURE)
            )
            self._stealth_enabled = bool(result)
            
            if self._stealth_enabled:
                logger.info("ResearchOverlay: Stealth mode ENABLED — invisible to screen capture")
                self._stealth_btn.setText("🛡 Stealth ON")
                self._stealth_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(40, 120, 200, 200);
                        color: #fff;
                        border: 1px solid rgba(60, 150, 255, 150);
                        border-radius: 6px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: rgba(50, 140, 220, 220);
                    }
                """)
            else:
                logger.warning("ResearchOverlay: Stealth mode failed to enable")
                
        except Exception as e:
            logger.error(f"ResearchOverlay: Stealth error: {e}")
            self._stealth_enabled = False
    
    def disable_stealth(self):
        """Make window visible to screen sharing again."""
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(
                ctypes.c_void_p(hwnd),
                ctypes.c_ulong(WDA_NONE)
            )
            self._stealth_enabled = False
            logger.info("ResearchOverlay: Stealth mode DISABLED")
            
            self._stealth_btn.setText("👁 Stealth")
            self._stealth_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(60, 60, 80, 180);
                    color: #aaa;
                    border: 1px solid rgba(100, 100, 130, 100);
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(80, 80, 110, 200);
                    color: #fff;
                }
            """)
        except Exception as e:
            logger.error(f"ResearchOverlay: Disable stealth error: {e}")
    
    # ── Speech Listening ──────────────────────────────────────
    
    def toggle_listening(self):
        """Start/stop speech recognition."""
        if self._listening:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        """Start capturing system audio for speech recognition."""
        try:
            from services.speech_service import get_speech_service
            self._speech_service = get_speech_service()
            
            # Wire up callbacks (using signals for thread safety)
            self._speech_service.on_partial = lambda t: self.speech_partial.emit(t)
            self._speech_service.on_final = lambda t: self.speech_detected.emit(t)
            self._speech_service.on_status = lambda s: self._status_label.setText(s)
            self._speech_service.on_error = lambda e: self._speech_label.setText(f"❌ {e}")
            
            if self._speech_service.start():
                self._listening = True
                self._listen_btn.setText("⏹ Stop")
                self._listen_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(180, 40, 40, 180);
                        color: #fff;
                        border: 1px solid rgba(200, 60, 60, 100);
                        border-radius: 6px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
            else:
                self._speech_label.setText("Speech recognition unavailable. Install: pip install vosk pyaudiowpatch")
                
        except ImportError:
            self._speech_label.setText("Install speech deps: pip install vosk pyaudiowpatch")
        except Exception as e:
            self._speech_label.setText(f"Error: {e}")
    
    def stop_listening(self):
        """Stop speech recognition."""
        if self._speech_service:
            self._speech_service.stop()
        self._listening = False
        self._status_label.setText("🎙 Neuron Research")
        self._listen_btn.setText("▶ Listen")
        self._listen_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 120, 60, 180);
                color: #ccc;
                border: 1px solid rgba(60, 150, 80, 100);
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
    
    # ── Signal Handlers ───────────────────────────────────────
    
    def _on_speech_partial(self, text: str):
        """Update partial speech recognition."""
        self._speech_label.setText(f'💬 "{text}..."')
    
    def _on_speech_final(self, text: str):
        """Handle complete sentence — send to LLM for answer."""
        self._speech_label.setText(f'🗣 "{text}"')
        self._answer_text.clear()
        self._current_answer = ""
        
        # Send to LLM in background thread
        threading.Thread(
            target=self._generate_answer,
            args=(text,),
            daemon=True
        ).start()
    
    def _generate_answer(self, question: str):
        """Generate AI answer for the detected question."""
        try:
            from services.llm_engine import get_llm_engine
            engine = get_llm_engine()
            
            system = (
                "You are a helpful assistant. Answer the following question concisely and clearly. "
                "Give direct, practical answers. If it's a coding question, include code. "
                "Keep your answer under 200 words."
            )
            
            # Stream tokens
            for token in engine.generate_stream(question, system, max_tokens=300):
                self.answer_token.emit(token)
            
            self.answer_complete.emit(self._current_answer)
            
        except Exception as e:
            self.answer_token.emit(f"\n[Error: {e}]")
    
    def _on_answer_token(self, token: str):
        """Append a token to the answer display."""
        self._current_answer += token
        self._answer_text.insertPlainText(token)
        # Auto-scroll to bottom
        scrollbar = self._answer_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_answer_complete(self, full_answer: str):
        """Handle completed answer."""
        self._status_label.setText("🎙 Listening..." if self._listening else "🎙 Neuron Research")
    
    # ── Opacity ───────────────────────────────────────────────
    
    def _update_opacity(self, value: int):
        """Update window transparency."""
        self.setWindowOpacity(value / 100.0)
        self._opacity_value.setText(f"{value}%")
    
    # ── Dragging ──────────────────────────────────────────────
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
    
    # ── Paint (rounded corners background) ────────────────────
    
    def paintEvent(self, event):
        """Custom paint for transparent background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

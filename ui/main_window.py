"""
DeepSeekFS – Full Interface Window (PyQt6)
==========================================
Pure PyQt6 recreation of the HTML interface design.
Three-panel layout: sidebar, main content (bento grid), inspector.
Top navbar + bottom status bar.
"""
from __future__ import annotations

import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QScrollArea, QFrame,
    QSystemTrayIcon, QMenu, QGridLayout,
    QSizePolicy, QGraphicsDropShadowEffect,
    QPushButton, QGraphicsOpacityEffect, QSpacerItem,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QPoint, QRect,
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPainter, QPainterPath,
    QBrush, QPen, QFontDatabase, QGuiApplication,
    QCursor, QLinearGradient, QPixmap,
)


# ─────────────────────────────────────────────────────────────────────────────
# Color Constants (Material Design 3 palette from the HTML)
# ─────────────────────────────────────────────────────────────────────────────
C_SURFACE          = "#131317"
C_SURFACE_CONTAINER = "#1f1f23"
C_SURFACE_HIGH     = "#2a2a2e"
C_SURFACE_HIGHEST  = "#353439"
C_SURFACE_LOW      = "#1b1b1f"
C_SURFACE_LOWEST   = "#0e0e12"
C_MAIN_BG          = "#1A1A1E"
C_SIDEBAR_BG       = "#2D2D32"
C_PRIMARY          = "#00F5D4"     # Cyan accent
C_PRIMARY_DIM      = "#00dfc1"
C_SECONDARY        = "#c9bfff"     # Lavender
C_SECONDARY_CONTAINER = "#4720ca"  # Purple
C_TERTIARY_DIM     = "#ffb59f"     # Orange
C_ON_SURFACE       = "#e4e1e7"
C_ON_SECONDARY     = "#2e009c"
C_OUTLINE          = "#83948f"
C_OUTLINE_VARIANT  = "#3a4a46"
C_TEXT_MUTED       = "#64748b"     # slate-400
C_TEXT_MUTED2      = "#475569"     # slate-500
C_TEXT_DARK        = "#1e293b"     # slate-800

# Fonts
FONT_INTER = "Inter"
FONT_MONO  = "JetBrains Mono"


def _font(family: str, size: int, weight: int = 400) -> QFont:
    f = QFont(family, size)
    f.setWeight(weight)
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Top Navigation Bar
# ─────────────────────────────────────────────────────────────────────────────
class TopNavBar(QFrame):
    """Fixed header: logo, nav tabs, search bar, settings, avatar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            TopNavBar {{
                background: rgba(19, 19, 23, 0.80);
                border: none;
                border-bottom: 1px solid rgba(58, 74, 70, 0.10);
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 0, 24, 0)
        root.setSpacing(0)

        # ── Left: Logo + Nav ──
        left = QHBoxLayout()
        left.setSpacing(32)

        logo = QLabel("DeepSeekFS")
        logo.setFont(_font(FONT_INTER, 16, QFont.Weight.Black))
        logo.setStyleSheet(f"color: {C_PRIMARY}; background: transparent; letter-spacing: -1px;")
        left.addWidget(logo)

        nav = QHBoxLayout()
        nav.setSpacing(4)

        btn_explorer = QLabel("Explorer")
        btn_explorer.setFont(_font(FONT_INTER, 11, QFont.Weight.Medium))
        btn_explorer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_explorer.setFixedSize(90, 32)
        btn_explorer.setStyleSheet(f"""
            background: {C_SIDEBAR_BG};
            color: {C_PRIMARY};
            border-radius: 16px;
            padding: 0 16px;
        """)
        nav.addWidget(btn_explorer)

        for tab_name in ("Hybrid Search", "Recent"):
            tab = QLabel(tab_name)
            tab.setFont(_font(FONT_INTER, 11, QFont.Weight.Medium))
            tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab.setStyleSheet(f"""
                color: {C_TEXT_MUTED};
                background: transparent;
                padding: 0 16px;
            """)
            tab.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            nav.addWidget(tab)

        left.addLayout(nav)
        root.addLayout(left)

        # ── Center: Search bar ──
        root.addStretch(1)
        search_frame = QFrame()
        search_frame.setFixedSize(400, 40)
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(53, 52, 57, 0.5);
                border: 1px solid rgba(58, 74, 70, 0.30);
                border-radius: 20px;
            }}
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 0, 12, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("background: transparent; font-size: 12px;")
        search_icon.setFixedWidth(20)
        search_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filesystem...")
        self.search_input.setFont(_font(FONT_INTER, 11))
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {C_ON_SURFACE};
                font-size: 13px;
                padding: 0;
            }}
            QLineEdit::placeholder {{
                color: {C_OUTLINE};
            }}
        """)
        search_layout.addWidget(self.search_input, 1)

        # Shortcut badges
        for key in ("⌘", "K"):
            kbd = QLabel(key)
            kbd.setFont(_font(FONT_INTER, 8))
            kbd.setAlignment(Qt.AlignmentFlag.AlignCenter)
            kbd.setFixedSize(22, 20)
            kbd.setStyleSheet(f"""
                background: {C_SURFACE_CONTAINER};
                color: {C_OUTLINE};
                border: 1px solid rgba(58, 74, 70, 0.50);
                border-radius: 4px;
                font-size: 9px;
            """)
            search_layout.addWidget(kbd)

        root.addWidget(search_frame)
        root.addStretch(1)

        # ── Right: Settings + Avatar ──
        right = QHBoxLayout()
        right.setSpacing(16)

        settings_btn = QLabel("⚙")
        settings_btn.setFont(_font(FONT_INTER, 18))
        settings_btn.setStyleSheet(f"color: {C_TEXT_MUTED}; background: transparent;")
        settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        right.addWidget(settings_btn)

        avatar = QFrame()
        avatar.setFixedSize(32, 32)
        avatar.setStyleSheet(f"""
            background: {C_OUTLINE_VARIANT};
            border: 1px solid rgba(58, 74, 70, 0.50);
            border-radius: 16px;
        """)
        right.addWidget(avatar)

        root.addLayout(right)


# ─────────────────────────────────────────────────────────────────────────────
# Left Sidebar
# ─────────────────────────────────────────────────────────────────────────────
class SideNavBar(QFrame):
    """Left panel: filesystem tree + quick files + NEW VOLUME button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(256)
        self.setStyleSheet(f"""
            SideNavBar {{
                background: {C_SIDEBAR_BG};
                border: none;
                border-right: 1px solid rgba(58, 74, 70, 0.10);
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 24, 24, 4)
        header_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        tree_icon = QLabel("⑂")
        tree_icon.setFont(_font(FONT_MONO, 11))
        tree_icon.setStyleSheet(f"color: {C_PRIMARY}; background: transparent;")
        title_row.addWidget(tree_icon)
        title = QLabel("FILESYSTEM CORE")
        title.setFont(_font(FONT_MONO, 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_PRIMARY}; background: transparent; letter-spacing: 3px;")
        title_row.addWidget(title)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        version = QLabel("v2.4.0-stable")
        version.setFont(_font(FONT_MONO, 8))
        version.setStyleSheet(f"color: {C_TEXT_MUTED2}; background: transparent; letter-spacing: 2px;")
        header_layout.addWidget(version)

        root.addWidget(header)

        # ── Nav items ──
        nav_items = [
            ("📁", "ROOT",      True),
            ("📄", "DOCUMENTS", False),
            ("⑂",  "PROJECTS",  False),
            ("📦", "ARCHIVES",  False),
        ]
        for icon, label, active in nav_items:
            item = QFrame()
            item.setFixedHeight(44)
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(24, 0, 24, 0)
            item_layout.setSpacing(12)

            icon_lbl = QLabel(icon)
            icon_lbl.setFont(_font(FONT_INTER, 12))
            icon_lbl.setStyleSheet("background: transparent;")
            item_layout.addWidget(icon_lbl)

            text_lbl = QLabel(label)
            text_lbl.setFont(_font(FONT_MONO, 9, QFont.Weight.Bold if active else QFont.Weight.Normal))
            text_lbl.setStyleSheet(f"""
                background: transparent;
                color: {"" + C_PRIMARY if active else C_TEXT_MUTED2};
                letter-spacing: 3px;
            """)
            item_layout.addWidget(text_lbl)
            item_layout.addStretch()

            if active:
                item.setStyleSheet(f"""
                    QFrame {{
                        background: {C_SURFACE};
                        border-left: 2px solid {C_PRIMARY};
                    }}
                """)
            else:
                item.setStyleSheet("QFrame { background: transparent; }")
                item.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            root.addWidget(item)

        # ── Quick files ──
        spacer = QWidget()
        spacer.setFixedHeight(32)
        root.addWidget(spacer)

        files = [
            ("main.py",     C_PRIMARY),
            ("config.json", C_SECONDARY),
        ]
        for fname, dot_color in files:
            file_row = QFrame()
            file_row.setFixedHeight(32)
            file_row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            file_row.setStyleSheet("QFrame { background: transparent; }")
            fr_layout = QHBoxLayout(file_row)
            fr_layout.setContentsMargins(24, 0, 24, 0)
            fr_layout.setSpacing(12)

            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(f"""
                background: {dot_color};
                border-radius: 3px;
            """)
            fr_layout.addWidget(dot)

            name = QLabel(fname)
            name.setFont(_font(FONT_INTER, 11))
            name.setStyleSheet(f"color: {C_TEXT_MUTED}; background: transparent;")
            fr_layout.addWidget(name)
            fr_layout.addStretch()

            root.addWidget(file_row)

        root.addStretch(1)

        # ── NEW VOLUME button ──
        btn_container = QWidget()
        btn_container.setStyleSheet("background: transparent;")
        bc_layout = QVBoxLayout(btn_container)
        bc_layout.setContentsMargins(24, 0, 24, 24)

        new_vol = QPushButton("NEW VOLUME")
        new_vol.setFont(_font(FONT_MONO, 8, QFont.Weight.Bold))
        new_vol.setFixedHeight(36)
        new_vol.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        new_vol.setStyleSheet(f"""
            QPushButton {{
                background: {C_SURFACE};
                border: 1px solid rgba(58, 74, 70, 0.30);
                color: {C_PRIMARY};
                border-radius: 4px;
                letter-spacing: 3px;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background: {C_PRIMARY};
                color: {C_SURFACE};
            }}
        """)
        bc_layout.addWidget(new_vol)
        root.addWidget(btn_container)


# ─────────────────────────────────────────────────────────────────────────────
# Bento Card (single file card)
# ─────────────────────────────────────────────────────────────────────────────
class BentoCard(QFrame):
    """A glass card for a file in the bento grid."""

    def __init__(self, icon_text: str, icon_color: str, badge_text: str,
                 badge_color: str, title: str, description: str,
                 size: str, time: str, border_class: str = "cyan",
                 parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        border_colors = {
            "cyan":   f"rgba(0, 245, 212, 0.15)",
            "violet": f"rgba(123, 97, 255, 0.15)",
            "orange": f"rgba(255, 181, 159, 0.15)",
        }
        bc = border_colors.get(border_class, border_colors["cyan"])

        self.setStyleSheet(f"""
            BentoCard {{
                background: rgba(31, 31, 35, 0.6);
                border: 1px solid {bc};
                border-radius: 12px;
            }}
            BentoCard:hover {{
                background: {C_SURFACE_HIGHEST};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        # Top row: icon + badge
        top = QHBoxLayout()
        icon_lbl = QLabel(icon_text)
        icon_lbl.setFont(_font(FONT_INTER, 24))
        icon_lbl.setStyleSheet(f"color: {icon_color}; background: transparent;")
        top.addWidget(icon_lbl)
        top.addStretch()

        badge = QLabel(badge_text)
        badge.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(22)
        badge.setStyleSheet(f"""
            background: rgba({self._hex_to_rgb(badge_color)}, 0.10);
            color: {badge_color};
            border: none;
            border-radius: 11px;
            padding: 0 10px;
            letter-spacing: 2px;
        """)
        top.addWidget(badge)
        layout.addLayout(top)

        layout.addSpacing(12)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setFont(_font(FONT_MONO, 11))
        title_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        layout.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setFont(_font(FONT_INTER, 10))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {C_OUTLINE}; background: transparent; line-height: 1.6;")
        layout.addWidget(desc_lbl)

        layout.addStretch(1)
        layout.addSpacing(16)

        # Bottom: size + time
        bottom = QHBoxLayout()
        size_lbl = QLabel(size)
        size_lbl.setFont(_font(FONT_MONO, 8))
        size_lbl.setStyleSheet(f"color: rgba(131, 148, 143, 0.60); background: transparent;")
        bottom.addWidget(size_lbl)
        bottom.addStretch()
        time_lbl = QLabel(time)
        time_lbl.setFont(_font(FONT_MONO, 8))
        time_lbl.setStyleSheet(f"color: rgba(131, 148, 143, 0.60); background: transparent;")
        bottom.addWidget(time_lbl)
        layout.addLayout(bottom)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        if len(h) == 6:
            return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
        return "255, 255, 255"


# ─────────────────────────────────────────────────────────────────────────────
# Featured Card (large card with code preview)
# ─────────────────────────────────────────────────────────────────────────────
class FeaturedCard(QFrame):
    """Wide glass card with code preview + stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(f"""
            FeaturedCard {{
                background: rgba(31, 31, 35, 0.6);
                border: 1px solid rgba(0, 245, 212, 0.15);
                border-radius: 12px;
            }}
            FeaturedCard:hover {{
                background: {C_SURFACE_HIGHEST};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # ── Left: Code preview ──
        code_frame = QFrame()
        code_frame.setFixedWidth(200)
        code_frame.setMinimumHeight(160)
        code_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE_LOWEST};
                border: 1px solid rgba(58, 74, 70, 0.20);
                border-radius: 8px;
            }}
        """)
        code_layout = QVBoxLayout(code_frame)
        code_layout.setContentsMargins(16, 16, 16, 16)
        code_layout.setSpacing(2)

        code_lines = [
            "def index_vector(data):",
            "    result = []",
            "    for item in data:",
            "        # High-perf slice",
            "        v = process(item)",
            "        result.append(v)",
        ]
        for line in code_lines:
            cl = QLabel(line)
            cl.setFont(_font(FONT_MONO, 9))
            cl.setStyleSheet(f"color: rgba(0, 245, 212, 0.80); background: transparent;")
            code_layout.addWidget(cl)
        code_layout.addStretch()

        layout.addWidget(code_frame)

        # ── Right: Info ──
        info = QVBoxLayout()
        info.setSpacing(8)

        # Badge row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        check = QLabel("✓")
        check.setFont(_font(FONT_INTER, 10))
        check.setStyleSheet(f"color: {C_PRIMARY}; background: transparent;")
        badge_row.addWidget(check)
        badge_text = QLabel("OPTIMIZED MODULE")
        badge_text.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
        badge_text.setStyleSheet(f"color: {C_PRIMARY}; background: transparent; letter-spacing: 1px;")
        badge_row.addWidget(badge_text)
        badge_row.addStretch()
        info.addLayout(badge_row)

        # Title
        title = QLabel("Vectorization Engine")
        title.setFont(_font(FONT_INTER, 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        info.addWidget(title)

        # Description
        desc = QLabel("Current efficiency rating: 98.4%. Processed 1.2M nodes in the last cycle without latency spikes.")
        desc.setFont(_font(FONT_INTER, 11))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C_OUTLINE}; background: transparent;")
        info.addWidget(desc)

        info.addStretch()

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(16)

        for icon_txt, stat_txt in [("💾", "256MB RAM"), ("⚡", "12ms LATENCY")]:
            stat_item = QHBoxLayout()
            stat_item.setSpacing(4)
            si = QLabel(icon_txt)
            si.setFont(_font(FONT_INTER, 10))
            si.setStyleSheet("background: transparent;")
            stat_item.addWidget(si)
            sv = QLabel(stat_txt)
            sv.setFont(_font(FONT_MONO, 8))
            sv.setStyleSheet(f"color: {C_OUTLINE}; background: transparent;")
            stat_item.addWidget(sv)
            stats.addLayout(stat_item)

        stats.addStretch()
        info.addLayout(stats)

        layout.addLayout(info, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Main Content Panel (center area)
# ─────────────────────────────────────────────────────────────────────────────
class MainContentPanel(QFrame):
    """Center panel: project header + bento grid of file cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            MainContentPanel {{
                background: {C_MAIN_BG};
                border: none;
            }}
        """)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.12);
                border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent; height: 0;
            }}
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(24)

        # ── Project Header ──
        header = QHBoxLayout()

        header_left = QVBoxLayout()
        header_left.setSpacing(6)

        title = QLabel("Project Obsidian")
        title.setFont(_font(FONT_INTER, 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; letter-spacing: -0.5px;")
        header_left.addWidget(title)

        tag_row = QHBoxLayout()
        tag_row.setSpacing(12)

        tag = QLabel("HYBRID INDEXED")
        tag.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setFixedHeight(22)
        tag.setStyleSheet(f"""
            background: rgba(0, 245, 212, 0.10);
            color: {C_PRIMARY};
            border: 1px solid rgba(0, 245, 212, 0.20);
            border-radius: 11px;
            padding: 0 10px;
        """)
        tag_row.addWidget(tag)

        path_lbl = QLabel("/root/dev/obsidian-arch")
        path_lbl.setFont(_font(FONT_MONO, 10))
        path_lbl.setStyleSheet(f"color: {C_OUTLINE}; background: transparent;")
        tag_row.addWidget(path_lbl)
        tag_row.addStretch()
        header_left.addLayout(tag_row)

        header.addLayout(header_left, 1)

        # View toggle buttons
        view_btns = QHBoxLayout()
        view_btns.setSpacing(4)

        grid_btn = QPushButton("⊞")
        grid_btn.setFixedSize(36, 36)
        grid_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_SURFACE_HIGH};
                color: {C_OUTLINE};
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }}
            QPushButton:hover {{ color: white; }}
        """)
        view_btns.addWidget(grid_btn)

        list_btn = QPushButton("☰")
        list_btn.setFixedSize(36, 36)
        list_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(42, 42, 46, 0.40);
                color: rgba(131, 148, 143, 0.50);
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }}
        """)
        view_btns.addWidget(list_btn)
        header.addLayout(view_btns)

        content_layout.addLayout(header)

        # ── Bento Grid: Top row (3 cards) ──
        grid_row1 = QHBoxLayout()
        grid_row1.setSpacing(24)

        card1 = BentoCard(
            icon_text="▶", icon_color=C_PRIMARY,
            badge_text="PYTHON", badge_color=C_PRIMARY,
            title="core_engine.py",
            description="Neural indexing logic for hybrid vector search optimization.",
            size="12.4 KB", time="2h ago",
            border_class="cyan",
        )
        grid_row1.addWidget(card1, 1)

        card2 = BentoCard(
            icon_text="⟷", icon_color=C_SECONDARY,
            badge_text="JSON", badge_color=C_SECONDARY,
            title="schema.json",
            description="Metadata definitions for multi-tenant filesystem isolation.",
            size="4.1 KB", time="5m ago",
            border_class="violet",
        )
        grid_row1.addWidget(card2, 1)

        card3 = BentoCard(
            icon_text="🖼", icon_color=C_TERTIARY_DIM,
            badge_text="PNG", badge_color=C_TERTIARY_DIM,
            title="blueprint_v2.png",
            description="",
            size="2.8 MB", time="Yesterday",
            border_class="orange",
        )
        grid_row1.addWidget(card3, 1)

        content_layout.addLayout(grid_row1)

        # ── Bento Grid: Featured card (spans 2 cols) ──
        featured = FeaturedCard()
        content_layout.addWidget(featured)

        content_layout.addStretch(1)

        scroll.setWidget(content)

        # Set scroll area layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


# ─────────────────────────────────────────────────────────────────────────────
# Right Inspector Panel
# ─────────────────────────────────────────────────────────────────────────────
class InspectorPanel(QFrame):
    """Right panel: Analysis tabs, resource bars, signals, action buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(288)
        self.setStyleSheet(f"""
            InspectorPanel {{
                background: {C_SURFACE_LOW};
                border: none;
                border-left: 1px solid rgba(58, 74, 70, 0.10);
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tabs ──
        tabs = QHBoxLayout()
        tabs.setSpacing(0)

        tab_names = ["ANALYSIS", "METADATA", "SIGNALS"]
        for i, name in enumerate(tab_names):
            tab = QLabel(name)
            tab.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
            tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab.setFixedHeight(44)
            if i == 0:
                tab.setStyleSheet(f"""
                    color: {C_PRIMARY};
                    background: rgba(42, 42, 46, 0.50);
                    border-bottom: 2px solid {C_PRIMARY};
                """)
            else:
                tab.setStyleSheet(f"""
                    color: {C_OUTLINE};
                    background: transparent;
                    border-bottom: 1px solid rgba(58, 74, 70, 0.10);
                """)
                tab.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            tabs.addWidget(tab, 1)

        root.addLayout(tabs)

        # ── Content scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.10); border-radius: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent; height: 0;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(32)

        # ── Resource Distribution ──
        res_section = QVBoxLayout()
        res_section.setSpacing(16)

        res_title = QLabel("RESOURCE DISTRIBUTION")
        res_title.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
        res_title.setStyleSheet(f"color: {C_OUTLINE}; background: transparent; letter-spacing: 3px;")
        res_section.addWidget(res_title)

        # Progress bars
        for label, pct in [("Compute", 82), ("IO Throughput", 45)]:
            bar_section = QVBoxLayout()
            bar_section.setSpacing(4)

            bar_header = QHBoxLayout()
            bl = QLabel(label)
            bl.setFont(_font(FONT_MONO, 8))
            bl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
            bar_header.addWidget(bl)
            bar_header.addStretch()
            bv = QLabel(f"{pct}%")
            bv.setFont(_font(FONT_MONO, 8))
            bv.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
            bar_header.addWidget(bv)
            bar_section.addLayout(bar_header)

            # Progress bar track
            track = QFrame()
            track.setFixedHeight(6)
            track.setStyleSheet(f"""
                background: {C_SURFACE_HIGHEST};
                border-radius: 3px;
            """)
            track_layout = QHBoxLayout(track)
            track_layout.setContentsMargins(0, 0, 0, 0)
            track_layout.setSpacing(0)

            fill = QFrame()
            fill.setFixedHeight(6)
            fill.setStyleSheet(f"""
                border-radius: 3px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_PRIMARY}, stop:1 {C_SECONDARY}
                );
            """)
            # Use stretch factors to simulate percentage
            track_layout.addWidget(fill, pct)
            spacer_widget = QWidget()
            spacer_widget.setStyleSheet("background: transparent;")
            track_layout.addWidget(spacer_widget, 100 - pct)

            bar_section.addWidget(track)
            res_section.addLayout(bar_section)

        cl.addLayout(res_section)

        # ── Active Signals ──
        sig_section = QVBoxLayout()
        sig_section.setSpacing(12)

        sig_title = QLabel("ACTIVE SIGNALS")
        sig_title.setFont(_font(FONT_INTER, 8, QFont.Weight.Bold))
        sig_title.setStyleSheet(f"color: {C_OUTLINE}; background: transparent; letter-spacing: 3px;")
        sig_section.addWidget(sig_title)

        # Signal badges in flow layout
        signals_data = [
            ("LOCKED_WRITE",    C_PRIMARY,      f"rgba(0, 245, 212, 0.30)"),
            ("SYNC_PENDING",    C_SECONDARY,    f"rgba(201, 191, 255, 0.30)"),
            ("ENCRYPTED_AES256", C_TERTIARY_DIM, f"rgba(255, 181, 159, 0.30)"),
        ]

        sig_flow = QHBoxLayout()
        sig_flow.setSpacing(8)
        for sig_text, sig_color, sig_border in signals_data:
            sig = QLabel(sig_text)
            sig.setFont(_font(FONT_MONO, 8))
            sig.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sig.setFixedHeight(28)
            sig.setStyleSheet(f"""
                background: {C_SURFACE_HIGHEST};
                color: {sig_color};
                border: 1px solid {sig_border};
                border-radius: 4px;
                padding: 0 8px;
            """)
            sig_flow.addWidget(sig)

        # Wrap signals in rows
        sig_row1 = QHBoxLayout()
        sig_row1.setSpacing(8)
        sig_row2 = QHBoxLayout()
        sig_row2.setSpacing(8)

        for i, (sig_text, sig_color, sig_border) in enumerate(signals_data):
            sig = QLabel(sig_text)
            sig.setFont(_font(FONT_MONO, 8))
            sig.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sig.setFixedHeight(28)
            sig.setStyleSheet(f"""
                background: {C_SURFACE_HIGHEST};
                color: {sig_color};
                border: 1px solid {sig_border};
                border-radius: 4px;
                padding: 0 8px;
            """)
            if i < 2:
                sig_row1.addWidget(sig)
            else:
                sig_row2.addWidget(sig)

        sig_row1.addStretch()
        sig_row2.addStretch()
        sig_section.addLayout(sig_row1)
        sig_section.addLayout(sig_row2)

        cl.addLayout(sig_section)

        cl.addStretch(1)

        # ── Action Buttons ──
        btn_section = QVBoxLayout()
        btn_section.setSpacing(12)

        open_btn = QPushButton("Open in Workspace")
        open_btn.setFont(_font(FONT_INTER, 10, QFont.Weight.Bold))
        open_btn.setFixedHeight(44)
        open_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_SECONDARY_CONTAINER}, stop:1 {C_SECONDARY}
                );
                color: {C_ON_SECONDARY};
                border: none;
                border-radius: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_SECONDARY}, stop:1 {C_SECONDARY_CONTAINER}
                );
            }}
        """)
        btn_section.addWidget(open_btn)

        share_btn = QPushButton("Share Access")
        share_btn.setFont(_font(FONT_INTER, 10, QFont.Weight.Bold))
        share_btn.setFixedHeight(44)
        share_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        share_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: white;
                border: 1px solid rgba(58, 74, 70, 0.50);
                border-radius: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {C_SURFACE_HIGHEST};
            }}
        """)
        btn_section.addWidget(share_btn)

        cl.addLayout(btn_section)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Footer / Status Bar
# ─────────────────────────────────────────────────────────────────────────────
class StatusFooter(QFrame):
    """Bottom status bar with system metrics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            StatusFooter {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0.3, y2:0,
                    stop:0 rgba(0, 245, 212, 0.20),
                    stop:1 {C_SURFACE}
                );
                border: none;
                border-top: 1px solid transparent;
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 0, 16, 0)
        root.setSpacing(0)

        # ── Left metrics ──
        left = QHBoxLayout()
        left.setSpacing(24)

        # Pulse dot
        dot = QFrame()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background: {C_PRIMARY}; border-radius: 3px;")
        left.addWidget(dot)

        self.latency_lbl = QLabel("LATENCY: 12MS")
        self.latency_lbl.setFont(_font(FONT_MONO, 8, QFont.Weight.DemiBold))
        self.latency_lbl.setStyleSheet(f"color: {C_PRIMARY}; background: transparent; letter-spacing: 2px;")
        left.addWidget(self.latency_lbl)

        sync_lbl = QLabel("SYNC: ACTIVE")
        sync_lbl.setFont(_font(FONT_MONO, 8, QFont.Weight.DemiBold))
        sync_lbl.setStyleSheet(f"color: {C_TEXT_MUTED2}; background: transparent; letter-spacing: 2px;")
        left.addWidget(sync_lbl)

        sep = QLabel("|")
        sep.setStyleSheet(f"color: {C_TEXT_DARK}; background: transparent;")
        left.addWidget(sep)

        uptime_lbl = QLabel("UPTIME: 142H 12M")
        uptime_lbl.setFont(_font(FONT_MONO, 8, QFont.Weight.DemiBold))
        uptime_lbl.setStyleSheet(f"color: {C_TEXT_MUTED2}; background: transparent; letter-spacing: 2px;")
        left.addWidget(uptime_lbl)

        root.addLayout(left)
        root.addStretch(1)

        # ── Right metrics ──
        right = QHBoxLayout()
        right.setSpacing(24)

        self.index_lbl = QLabel("INDEX: 1,402,991 NODES")
        self.index_lbl.setFont(_font(FONT_MONO, 8, QFont.Weight.DemiBold))
        self.index_lbl.setStyleSheet(f"color: {C_TEXT_MUTED2}; background: transparent; letter-spacing: 2px;")
        right.addWidget(self.index_lbl)

        ready_lbl = QLabel("DEEPSEEK_FILESYSTEM_OS_CORE_READY")
        ready_lbl.setFont(_font(FONT_MONO, 8, QFont.Weight.DemiBold))
        ready_lbl.setStyleSheet(f"color: {C_PRIMARY}; background: transparent; letter-spacing: 2px;")
        right.addWidget(ready_lbl)

        root.addLayout(right)


# ─────────────────────────────────────────────────────────────────────────────
# Main Window (assembles all panels)
# ─────────────────────────────────────────────────────────────────────────────
class DeepSeekMainWindow(QWidget):
    """Full interface window assembling all panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeepSeekFS | Core Filesystem")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        self.setStyleSheet(f"background: {C_SURFACE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top Nav
        self.navbar = TopNavBar()
        root.addWidget(self.navbar)

        # Middle: sidebar + content + inspector
        middle = QHBoxLayout()
        middle.setSpacing(0)

        self.sidebar = SideNavBar()
        middle.addWidget(self.sidebar)

        self.content = MainContentPanel()
        middle.addWidget(self.content, 1)

        self.inspector = InspectorPanel()
        middle.addWidget(self.inspector)

        root.addLayout(middle, 1)

        # Footer
        self.footer = StatusFooter()
        root.addWidget(self.footer)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────────────────────────────────────
def _test():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DeepSeekMainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _test()

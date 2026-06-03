"""
Lucide Icon System for Neuron Desktop App
==========================================

Provides programmatic SVG-based icons rendered via PyQt6's QSvgRenderer.
All icons use the Lucide 24x24 viewBox with stroke-based rendering.

Usage:
    from ui.icons import icon_pixmap, icon_label, icon_text

    pixmap = icon_pixmap("settings", size=20, color="#E0E0E0")
    label  = icon_label("refresh-cw", size=24, color="#4FC3F7")
    name   = icon_text("folder-plus")  # returns "folder-plus"
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QByteArray

# Try to import QSvgRenderer; flag availability
try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

# ---------------------------------------------------------------------------
# SVG path data registry — each value is the inner SVG elements (paths,
# lines, circles, polylines, polygons, rects) for a Lucide icon.
# All icons assume viewBox="0 0 24 24", stroke-based, no fill.
# ---------------------------------------------------------------------------

_SVG_PATHS: dict[str, str] = {
    # ── Navigation & Actions ──────────────────────────────────────────
    "refresh-cw": (
        "<polyline points='23 4 23 10 17 10'/>"
        "<polyline points='1 20 1 14 7 14'/>"
        "<path d='M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15'/>"
    ),
    "folder-plus": (
        "<path d='M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z'/>"
        "<line x1='12' y1='11' x2='12' y2='17'/>"
        "<line x1='9' y1='14' x2='15' y2='14'/>"
    ),
    "settings": (
        "<circle cx='12' cy='12' r='3'/>"
        "<path d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 "
        "2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 "
        "1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 "
        "1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 "
        "1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 "
        "2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 "
        "0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 "
        "1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 "
        "1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 "
        "1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 "
        "2h-.09a1.65 1.65 0 0 0-1.51 1z'/>"
    ),
    "search": (
        "<circle cx='11' cy='11' r='8'/>"
        "<line x1='21' y1='21' x2='16.65' y2='16.65'/>"
    ),
    "bar-chart-2": (
        "<line x1='18' y1='20' x2='18' y2='10'/>"
        "<line x1='12' y1='20' x2='12' y2='4'/>"
        "<line x1='6' y1='20' x2='6' y2='14'/>"
    ),
    "clock": (
        "<circle cx='12' cy='12' r='10'/>"
        "<polyline points='12 6 12 12 16 14'/>"
    ),
    "activity": (
        "<polyline points='22 12 18 12 15 21 9 3 6 12 2 12'/>"
    ),

    # ── AI / CPU ──────────────────────────────────────────────────────
    "cpu": (
        "<rect x='4' y='4' width='16' height='16' rx='2' ry='2'/>"
        "<rect x='9' y='9' width='6' height='6'/>"
        "<line x1='9' y1='1' x2='9' y2='4'/>"
        "<line x1='15' y1='1' x2='15' y2='4'/>"
        "<line x1='9' y1='20' x2='9' y2='23'/>"
        "<line x1='15' y1='20' x2='15' y2='23'/>"
        "<line x1='20' y1='9' x2='23' y2='9'/>"
        "<line x1='20' y1='14' x2='23' y2='14'/>"
        "<line x1='1' y1='9' x2='4' y2='9'/>"
        "<line x1='1' y1='14' x2='4' y2='14'/>"
    ),

    # ── File Types ────────────────────────────────────────────────────
    "file-text": (
        "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/>"
        "<polyline points='14 2 14 8 20 8'/>"
        "<line x1='16' y1='13' x2='8' y2='13'/>"
        "<line x1='16' y1='17' x2='8' y2='17'/>"
        "<polyline points='10 9 9 9 8 9'/>"
    ),
    "file": (
        "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/>"
        "<polyline points='14 2 14 8 20 8'/>"
    ),
    "folder": (
        "<path d='M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z'/>"
    ),
    "folder-open": (
        "<path d='M5 19a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4l2 2h4a2 2 0 0 1 2 2v1"
        "M5 19h14a2 2 0 0 0 2-2l1-9H4l1 9z'/>"
    ),
    "image": (
        "<rect x='3' y='3' width='18' height='18' rx='2' ry='2'/>"
        "<circle cx='8.5' cy='8.5' r='1.5'/>"
        "<polyline points='21 15 16 10 5 21'/>"
    ),
    "film": (
        "<rect x='2' y='2' width='20' height='20' rx='2.18' ry='2.18'/>"
        "<line x1='7' y1='2' x2='7' y2='22'/>"
        "<line x1='17' y1='2' x2='17' y2='22'/>"
        "<line x1='2' y1='12' x2='22' y2='12'/>"
        "<line x1='2' y1='7' x2='7' y2='7'/>"
        "<line x1='2' y1='17' x2='7' y2='17'/>"
        "<line x1='17' y1='7' x2='22' y2='7'/>"
        "<line x1='17' y1='17' x2='22' y2='17'/>"
    ),
    "book-open": (
        "<path d='M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z'/>"
        "<path d='M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z'/>"
    ),
    "package": (
        "<line x1='16.5' y1='9.4' x2='7.5' y2='4.21'/>"
        "<path d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8"
        "a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'/>"
        "<polyline points='3.27 6.96 12 12.01 20.73 6.96'/>"
        "<line x1='12' y1='22.08' x2='12' y2='12'/>"
    ),

    # ── Status & Feedback ─────────────────────────────────────────────
    "alert-triangle": (
        "<path d='M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 "
        "3.86a2 2 0 0 0-3.42 0z'/>"
        "<line x1='12' y1='9' x2='12' y2='13'/>"
        "<line x1='12' y1='17' x2='12.01' y2='17'/>"
    ),
    "sparkles": (
        "<path d='M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0"
        "-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0"
        " 1.275-1.275L12 3z'/>"
    ),
    "x": (
        "<line x1='18' y1='6' x2='6' y2='18'/>"
        "<line x1='6' y1='6' x2='18' y2='18'/>"
    ),
    "check-circle": (
        "<path d='M22 11.08V12a10 10 0 1 1-5.93-9.14'/>"
        "<polyline points='22 4 12 14.01 9 11.01'/>"
    ),
    "x-circle": (
        "<circle cx='12' cy='12' r='10'/>"
        "<line x1='15' y1='9' x2='9' y2='15'/>"
        "<line x1='9' y1='9' x2='15' y2='15'/>"
    ),
    "info": (
        "<circle cx='12' cy='12' r='10'/>"
        "<line x1='12' y1='16' x2='12' y2='12'/>"
        "<line x1='12' y1='8' x2='12.01' y2='8'/>"
    ),
    "thumbs-up": (
        "<path d='M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0"
        "-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3'/>"
    ),
    "thumbs-down": (
        "<path d='M10 15V19a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0"
        " 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17'/>"
    ),

    # ── Tools & Tasks ─────────────────────────────────────────────────
    "wrench": (
        "<path d='M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1"
        "-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z'/>"
    ),
    "clipboard": (
        "<path d='M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'/>"
        "<rect x='8' y='2' width='8' height='4' rx='1' ry='1'/>"
    ),
    "edit-3": (
        "<path d='M12 20h9'/>"
        "<path d='M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z'/>"
    ),
    "play": (
        "<polygon points='5 3 19 12 5 21 5 3'/>"
    ),

    # ── Monitoring & Misc ─────────────────────────────────────────────
    "eye": (
        "<path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'/>"
        "<circle cx='12' cy='12' r='3'/>"
    ),
    "plug": (
        "<path d='M12 22v-5'/>"
        "<path d='M9 8V1h6v7'/>"
        "<path d='M8 8h8'/>"
        "<path d='M12 17a5 5 0 0 0 5-5V8H7v4a5 5 0 0 0 5 5z'/>"
    ),
    "message-circle": (
        "<path d='M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1"
        "-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1"
        " 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z'/>"
    ),
    "mic": (
        "<path d='M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z'/>"
        "<path d='M19 10v2a7 7 0 0 1-14 0v-2'/>"
        "<line x1='12' y1='19' x2='12' y2='23'/>"
        "<line x1='8' y1='23' x2='16' y2='23'/>"
    ),
    "shield": (
        "<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/>"
    ),
    "flame": (
        "<path d='M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 "
        "2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 "
        "1-3a2.5 2.5 0 0 0 2.5 2.5z'/>"
    ),
    "zap": (
        "<polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/>"
    ),
    "code": (
        "<polyline points='16 18 22 12 16 6'/>"
        "<polyline points='8 6 2 12 8 18'/>"
    ),
    "hash": (
        "<line x1='4' y1='9' x2='20' y2='9'/>"
        "<line x1='4' y1='15' x2='20' y2='15'/>"
        "<line x1='10' y1='3' x2='8' y2='21'/>"
        "<line x1='16' y1='3' x2='14' y2='21'/>"
    ),
    "globe": (
        "<circle cx='12' cy='12' r='10'/>"
        "<line x1='2' y1='12' x2='22' y2='12'/>"
        "<path d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10"
        " 15.3 15.3 0 0 1 4-10z'/>"
    ),
    "palette": (
        "<circle cx='13.5' cy='6.5' r='0.5' fill='currentColor'/>"
        "<circle cx='17.5' cy='10.5' r='0.5' fill='currentColor'/>"
        "<circle cx='8.5' cy='7.5' r='0.5' fill='currentColor'/>"
        "<circle cx='6.5' cy='12' r='0.5' fill='currentColor'/>"
        "<path d='M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 "
        "0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 "
        "1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z'/>"
    ),
    "lock": (
        "<rect x='3' y='11' width='18' height='11' rx='2' ry='2'/>"
        "<path d='M7 11V7a5 5 0 0 1 10 0v4'/>"
    ),
    "coffee": (
        "<path d='M18 8h1a4 4 0 0 1 0 8h-1'/>"
        "<path d='M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z'/>"
        "<line x1='6' y1='1' x2='6' y2='4'/>"
        "<line x1='10' y1='1' x2='10' y2='4'/>"
        "<line x1='14' y1='1' x2='14' y2='4'/>"
    ),
    "diamond": (
        "<path d='M2.7 10.3a2.41 2.41 0 0 0 0 3.41l7.59 7.59a2.41 2.41 0 0 0 3.41 0l7.59"
        "-7.59a2.41 2.41 0 0 0 0-3.41L13.7 2.71a2.41 2.41 0 0 0-3.41 0z'/>"
    ),
    "terminal": (
        "<polyline points='4 17 10 11 4 5'/>"
        "<line x1='12' y1='19' x2='20' y2='19'/>"
    ),

    # ── Clipboard / Edit Actions ──────────────────────────────────────
    "copy": (
        "<rect x='9' y='9' width='13' height='13' rx='2' ry='2'/>"
        "<path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'/>"
    ),
    "external-link": (
        "<path d='M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'/>"
        "<polyline points='15 3 21 3 21 9'/>"
        "<line x1='10' y1='14' x2='21' y2='3'/>"
    ),
    "scissors": (
        "<circle cx='6' cy='6' r='3'/>"
        "<circle cx='6' cy='18' r='3'/>"
        "<line x1='20' y1='4' x2='8.12' y2='15.88'/>"
        "<line x1='14.47' y1='14.48' x2='20' y2='20'/>"
        "<line x1='8.12' y1='8.12' x2='12' y2='12'/>"
    ),
    "type": (
        "<polyline points='4 7 4 4 20 4 20 7'/>"
        "<line x1='9' y1='20' x2='15' y2='20'/>"
        "<line x1='12' y1='4' x2='12' y2='20'/>"
    ),
    "share-2": (
        "<circle cx='18' cy='5' r='3'/>"
        "<circle cx='6' cy='12' r='3'/>"
        "<circle cx='18' cy='19' r='3'/>"
        "<line x1='8.59' y1='13.51' x2='15.42' y2='17.49'/>"
        "<line x1='15.41' y1='6.51' x2='8.59' y2='10.49'/>"
    ),
    "trash-2": (
        "<polyline points='3 6 5 6 21 6'/>"
        "<path d='M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2'/>"
        "<line x1='10' y1='11' x2='10' y2='17'/>"
        "<line x1='14' y1='11' x2='14' y2='17'/>"
    ),
    "link": (
        "<path d='M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71'/>"
        "<path d='M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'/>"
    ),
    "list": (
        "<line x1='8' y1='6' x2='21' y2='6'/>"
        "<line x1='8' y1='12' x2='21' y2='12'/>"
        "<line x1='8' y1='18' x2='21' y2='18'/>"
        "<line x1='3' y1='6' x2='3.01' y2='6'/>"
        "<line x1='3' y1='12' x2='3.01' y2='12'/>"
        "<line x1='3' y1='18' x2='3.01' y2='18'/>"
    ),
    "more-horizontal": (
        "<circle cx='12' cy='12' r='1'/>"
        "<circle cx='19' cy='12' r='1'/>"
        "<circle cx='5' cy='12' r='1'/>"
    ),

    # ── Misc Symbols ──────────────────────────────────────────────────
    "star": (
        "<polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 "
        "5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/>"
    ),
    "heart": (
        "<path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0"
        "-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z'/>"
    ),
    "hard-drive": (
        "<line x1='22' y1='12' x2='2' y2='12'/>"
        "<path d='M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0"
        " 16.76 4H7.24a2 2 0 0 0-1.79 1.11z'/>"
        "<line x1='6' y1='16' x2='6.01' y2='16'/>"
        "<line x1='10' y1='16' x2='10.01' y2='16'/>"
    ),
    "volume-2": (
        "<polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'/>"
        "<path d='M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07'/>"
    ),
    "lightbulb": (
        "<path d='M9 18h6'/>"
        "<path d='M10 22h4'/>"
        "<path d='M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z'/>"
    ),
    "archive": (
        "<polyline points='21 8 21 21 3 21 3 8'/>"
        "<rect x='1' y='3' width='22' height='5'/>"
        "<line x1='10' y1='12' x2='14' y2='12'/>"
    ),

    # ── Notebook (same as book-open, aliased) ─────────────────────────
    "notebook": (
        "<path d='M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z'/>"
        "<path d='M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z'/>"
    ),

    # ── React / Atom ──────────────────────────────────────────────────
    "atom": (
        "<circle cx='12' cy='12' r='1'/>"
        "<path d='M20.2 20.2c2.04-2.03.02-7.36-4.5-11.9-4.54-4.52-9.87-6.54-11.9-4.5"
        "-2.04 2.03-.02 7.36 4.5 11.9 4.54 4.52 9.87 6.54 11.9 4.5z'/>"
        "<path d='M15.7 15.7c4.52-4.54 6.54-9.87 4.5-11.9-2.03-2.04-7.36-.02-11.9 4.5"
        "-4.52 4.54-6.54 9.87-4.5 11.9 2.03 2.04 7.36.02 11.9-4.5z'/>"
    ),

    # ── Navigation Chevrons ───────────────────────────────────────────
    "chevron-left": "<polyline points='15 18 9 12 15 6'/>",
    "chevron-right": "<polyline points='9 18 15 12 9 6'/>",
    "chevron-up": "<polyline points='18 15 12 9 6 15'/>",
    "chevron-down": "<polyline points='6 9 12 15 18 9'/>",
}

# ---------------------------------------------------------------------------
# SVG template — matches Lucide's default 24×24 viewBox, stroke-based style
# ---------------------------------------------------------------------------
_SVG_TEMPLATE = (
    "<svg xmlns='http://www.w3.org/2000/svg' "
    "width='{size}' height='{size}' viewBox='0 0 24 24' "
    "fill='none' stroke='{color}' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "{paths}"
    "</svg>"
)


def _build_svg(name: str, size: int, color: str) -> str:
    """Build a complete SVG XML string for the given icon."""
    paths = _SVG_PATHS.get(name, "")
    if not paths:
        # Unknown icon — render a small "?" circle as fallback
        paths = (
            "<circle cx='12' cy='12' r='10'/>"
            "<text x='12' y='16' text-anchor='middle' "
            f"font-size='12' fill='{color}' stroke='none'>?</text>"
        )
    # For palette icon, replace 'currentColor' fills with actual color
    paths = paths.replace("fill='currentColor'", f"fill='{color}'")
    return _SVG_TEMPLATE.format(size=size, color=color, paths=paths)


def _fallback_pixmap(size: int, color: str) -> QPixmap:
    """Create a simple colored-square pixmap when SVG rendering is unavailable."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    painter.setPen(Qt.PenStyle.NoPen)
    c.setAlpha(180)
    painter.setBrush(c)
    margin = max(1, size // 6)
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 3, 3)
    painter.end()
    return pixmap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def icon_pixmap(name: str, size: int = 20, color: str = "#E0E0E0") -> QPixmap:
    """
    Render a Lucide icon as a QPixmap.

    Args:
        name:  Icon name (e.g. "settings", "refresh-cw").
        size:  Pixel size of the output pixmap (square).
        color: Stroke color as a hex string.

    Returns:
        A QPixmap with the rendered icon on a transparent background.
    """
    if not _HAS_SVG:
        return _fallback_pixmap(size, color)

    svg_xml = _build_svg(name, size, color)
    svg_bytes = QByteArray(svg_xml.encode("utf-8"))

    renderer = QSvgRenderer(svg_bytes)
    if not renderer.isValid():
        return _fallback_pixmap(size, color)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    return pixmap


def icon_label(name: str, size: int = 20, color: str = "#E0E0E0") -> QLabel:
    """
    Return a QLabel displaying the specified Lucide icon.

    Args:
        name:  Icon name (e.g. "folder-plus", "search").
        size:  Pixel size of the icon.
        color: Stroke color as a hex string.

    Returns:
        A QLabel with the icon pixmap set, transparent background,
        and fixed size matching the icon dimensions.
    """
    label = QLabel()
    label.setPixmap(icon_pixmap(name, size, color))
    label.setFixedSize(size, size)
    label.setStyleSheet("background: transparent; border: none;")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def icon_text(name: str) -> str:
    """
    Return a plain-text fallback for the icon name.
    This avoids any emoji/unicode — just returns the icon identifier.

    Args:
        name: Icon name.

    Returns:
        The icon name string (for use as tooltip or fallback text).
    """
    return name


def available_icons() -> list[str]:
    """Return a sorted list of all registered icon names."""
    return sorted(_SVG_PATHS.keys())


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    print(f"SVG renderer available: {_HAS_SVG}")
    print(f"Total icons registered: {len(_SVG_PATHS)}")
    print(f"Icon names: {', '.join(available_icons())}")
    print()

    # Test rendering a subset of icons at different sizes
    test_icons = ["settings", "search", "refresh-cw", "folder-plus", "sparkles",
                  "check-circle", "x-circle", "zap", "code", "star", "eye"]
    test_sizes = [16, 20, 24]

    all_ok = True
    for icon_name in test_icons:
        for sz in test_sizes:
            pm = icon_pixmap(icon_name, size=sz, color="#E0E0E0")
            ok = not pm.isNull() and pm.width() == sz and pm.height() == sz
            status = "OK" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"  [{status}] {icon_name:20s} @ {sz}px  ->  {pm.width()}x{pm.height()}")

    # Test icon_label
    lbl = icon_label("settings", size=20, color="#4FC3F7")
    lbl_ok = lbl.pixmap() is not None and not lbl.pixmap().isNull()
    print(f"\n  icon_label('settings'): {'OK' if lbl_ok else 'FAIL'}")

    # Test icon_text
    txt = icon_text("refresh-cw")
    print(f"  icon_text('refresh-cw'): '{txt}' {'OK' if txt == 'refresh-cw' else 'FAIL'}")

    # Test unknown icon fallback
    pm_unknown = icon_pixmap("nonexistent-icon", size=20)
    print(f"  fallback for unknown icon: {'OK' if not pm_unknown.isNull() else 'FAIL'}")

    print(f"\n{'All tests passed!' if all_ok else 'Some tests FAILED.'}")
    sys.exit(0 if all_ok else 1)

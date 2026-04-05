"""
ui/icons.py — Lucide SVG icon library for Neuron (MIT-licensed paths).
Provides render_svg_icon() and ICON_MAP for file-type icons.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtSvg import QSvgRenderer

# ── Lucide icon SVG strings (viewBox="0 0 24 24", stroke-based) ──────────────
_SVG_TMPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{color}" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

ICONS = {
    "search":   '<path d="m21 21-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>',
    "settings": ('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25'
                 'a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73'
                 'l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 '
                 '2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 '
                 '1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73'
                 'l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0'
                 '-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 '
                 '2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0'
                 'l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
                 '<circle cx="12" cy="12" r="3"/>'),
    "close":    '<path d="M18 6 6 18M6 6l12 12"/>',
    "file":     '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>',
    "python":   '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 12h8M12 8v8"/>',
    "js":       '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="10" y1="13" x2="10" y2="17"/><path d="M14 13v4c0 1-1 2-2 2s-2-1-2-2"/>',
    "image":    '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
    "video":    '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>',
    "pdf":      '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="9" y2="17"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="15" y1="15" x2="15" y2="17"/>',
    "doc":      '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>',
    "archive":  '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>',
    "config":   '<circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>',
    "folder":   '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "code":     '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
}

# Extension → icon key + accent color
EXT_ICON_MAP: dict[str, tuple[str, str]] = {
    ".py":    ("python",  "#3B82F6"), ".ipynb": ("python",  "#8B5CF6"),
    ".js":    ("js",      "#EAB308"), ".ts":    ("js",      "#3B82F6"),
    ".jsx":   ("js",      "#22D3EE"), ".tsx":   ("js",      "#3B82F6"),
    ".rs":    ("code",    "#E57A44"), ".go":    ("code",    "#00ADD8"),
    ".java":  ("code",    "#F59E0B"), ".cpp":   ("code",    "#60A5FA"),
    ".c":     ("code",    "#94A3B8"), ".h":     ("code",    "#94A3B8"),
    ".cs":    ("code",    "#A78BFA"), ".rb":    ("code",    "#EF4444"),
    ".php":   ("code",    "#A78BFA"), ".swift": ("code",    "#F97316"),
    ".kt":    ("code",    "#A855F6"), ".html":  ("code",    "#EF4444"),
    ".css":   ("code",    "#38BDF8"), ".md":    ("doc",     "#94A3B8"),
    ".txt":   ("file",    "#94A3B8"), ".log":   ("file",    "#94A3B8"),
    ".pdf":   ("pdf",     "#EF4444"), ".docx":  ("doc",     "#2563EB"),
    ".doc":   ("doc",     "#2563EB"), ".xlsx":  ("doc",     "#22C55E"),
    ".xls":   ("doc",     "#22C55E"), ".csv":   ("doc",     "#22C55E"),
    ".pptx":  ("doc",     "#F97316"),
    ".json":  ("config",  "#F5B74A"), ".xml":   ("config",  "#F5B74A"),
    ".yaml":  ("config",  "#A78BFA"), ".yml":   ("config",  "#A78BFA"),
    ".toml":  ("config",  "#A78BFA"), ".env":   ("config",  "#A78BFA"),
    ".ini":   ("config",  "#94A3B8"), ".cfg":   ("config",  "#94A3B8"),
    ".mp4":   ("video",   "#A855F6"), ".mkv":   ("video",   "#A855F6"),
    ".avi":   ("video",   "#A855F6"), ".mov":   ("video",   "#A855F6"),
    ".png":   ("image",   "#EC4899"), ".jpg":   ("image",   "#EC4899"),
    ".jpeg":  ("image",   "#EC4899"), ".gif":   ("image",   "#EC4899"),
    ".webp":  ("image",   "#EC4899"),
    ".zip":   ("archive", "#FBBF24"), ".rar":   ("archive", "#FBBF24"),
    ".7z":    ("archive", "#FBBF24"),
    ".exe":   ("config",  "#A78BFA"), ".msi":   ("config",  "#A78BFA"),
}
_DEFAULT_ICON = ("file", "#64748B")


def render_svg_icon(icon_key: str, size: int = 18, color: str = "#FFFFFF") -> QPixmap:
    """Render a Lucide SVG icon to a QPixmap at the given size and color."""
    body = ICONS.get(icon_key, ICONS["file"])
    svg_str = _SVG_TMPL.format(color=color, body=body)
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix


def get_ext_icon(ext: str, size: int = 18) -> tuple[QPixmap, str]:
    """Return (QPixmap, accent_color) for a file extension."""
    icon_key, color = EXT_ICON_MAP.get(ext.lower(), _DEFAULT_ICON)
    return render_svg_icon(icon_key, size, color), color

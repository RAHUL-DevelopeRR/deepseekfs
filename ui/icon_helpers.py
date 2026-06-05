"""Side-effect-free icon helpers for desktop UI modules."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap


def make_circular_splash(path: str, size: int = 280) -> QPixmap:
    """Return a circular pixmap with a transparent background."""
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)

    overlay = QPixmap(path)
    if overlay.isNull():
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#0078D4"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return result

    scaled = overlay.scaled(
        size,
        size,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return result


def make_white_bg_icon(path: str, size: int = 64) -> QPixmap:
    """Return an icon pixmap on a white circular background."""
    base = QPixmap(size, size)
    base.fill(QColor("white"))

    overlay = QPixmap(path)
    if overlay.isNull():
        return base

    overlay = overlay.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    painter = QPainter(base)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, overlay)
    painter.end()
    return base

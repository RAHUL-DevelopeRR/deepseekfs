"""Tests for MemoryOS Markdown rendering in the PyQt chat panel."""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_markdown_renderer_formats_code_fences():
    from ui.memoryos_panel import _markdown_to_html

    rendered = _markdown_to_html(
        "Here is code:\n\n```java\nMap<String, Integer> map = new HashMap<>();\n```"
    )

    assert "<pre" in rendered
    assert "language-java" in rendered
    assert "HashMap" in rendered
    assert "```" not in rendered


def test_markdown_renderer_escapes_raw_html():
    from ui.memoryos_panel import _markdown_to_html

    rendered = _markdown_to_html("<script>alert('x')</script>")

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


@pytest.fixture(scope="module")
def qt_app():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_stream_end_replaces_raw_markdown_with_rendered_output(qt_app):
    from ui.memoryos_panel import MemoryOSPanel

    panel = MemoryOSPanel()
    panel._stream_mode = "chat"
    panel._on_token("```java\n")
    panel._on_token("class Demo {}\n")
    panel._on_token("```")
    panel._last_response = "```java\nclass Demo {}\n```"

    panel._on_stream_end()

    plain = panel._chat.toPlainText()
    html = panel._chat.toHtml()
    assert "class Demo {}" in plain
    assert "```" not in plain
    assert "class Demo" in html

"""
Unit tests for core/ingestion/file_parser.py
Covers: FileParser.parse(), individual _parse_* methods, and get_file_metadata().
"""
import os
import sys
import json
import csv
import tempfile
import textwrap
import pytest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.ingestion.file_parser import FileParser


# ── Helper: write a temp file, run parser, clean up ──────────────────────
def _parse_temp(suffix: str, content: bytes | str, *, encoding="utf-8") -> str | None:
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False,
        mode="wb" if isinstance(content, bytes) else "w",
        encoding=None if isinstance(content, bytes) else encoding,
    ) as f:
        f.write(content)
        path = f.name
    try:
        return FileParser.parse(path)
    finally:
        os.unlink(path)


class TestParsePlainText:
    """Tests for .txt and .md files."""

    def test_txt_returns_content(self):
        result = _parse_temp(".txt", "Hello, world!")
        assert result is not None
        assert "Hello" in result

    def test_txt_truncated_at_5000(self):
        big = "x" * 10_000
        result = _parse_temp(".txt", big)
        assert result is not None
        assert len(result) <= 5000

    def test_md_returns_content(self):
        result = _parse_temp(".md", "# Heading\n\nSome markdown content.")
        assert result is not None
        assert "Heading" in result

    def test_empty_txt_returns_empty_string(self):
        result = _parse_temp(".txt", "")
        assert result == ""

    def test_unicode_content(self):
        result = _parse_temp(".txt", "Ünïcödé téxt with emojis 🚀")
        assert result is not None


class TestParseJSON:
    """Tests for .json files (treated as plain text)."""

    def test_json_file_returns_text(self):
        data = json.dumps({"key": "value", "number": 42})
        result = _parse_temp(".json", data)
        assert result is not None
        assert "key" in result

    def test_json_file_large_truncated(self):
        data = json.dumps({"data": "x" * 6000})
        result = _parse_temp(".json", data)
        assert result is not None
        assert len(result) <= 5000


class TestParseCSV:
    """Tests for .csv files."""

    def test_csv_returns_content(self):
        content = "name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        result = _parse_temp(".csv", content)
        assert result is not None
        assert "Alice" in result or "name" in result

    def test_csv_long_file_truncated(self):
        lines = ["col1,col2,col3"] + [f"a,b,c" for _ in range(200)]
        content = "\n".join(lines)
        result = _parse_temp(".csv", content)
        assert result is not None
        assert len(result) <= 5000

    def test_csv_empty_file(self):
        result = _parse_temp(".csv", "")
        # Empty CSV returns empty string or None — both acceptable
        assert result is None or result == ""


class TestParseHTML:
    """Tests for .html and .htm files."""

    def test_html_strips_tags(self):
        html = "<html><body><p>Hello from HTML</p></body></html>"
        result = _parse_temp(".html", html)
        assert result is not None
        assert "Hello from HTML" in result
        assert "<p>" not in result

    def test_html_excludes_script_content(self):
        html = "<html><body><script>alert('xss')</script><p>Safe content</p></body></html>"
        result = _parse_temp(".html", html)
        assert result is not None
        assert "xss" not in result
        assert "Safe content" in result

    def test_html_excludes_style_content(self):
        html = "<html><head><style>.cls {color:red}</style></head><body><p>Visible</p></body></html>"
        result = _parse_temp(".html", html)
        assert result is not None
        assert "color:red" not in result
        assert "Visible" in result

    def test_htm_extension_works(self):
        html = "<html><body><p>HTM file</p></body></html>"
        result = _parse_temp(".htm", html)
        assert result is not None
        assert "HTM file" in result

    def test_html_result_truncated_at_5000(self):
        big_html = "<html><body>" + "<p>" + "word " * 2000 + "</p></body></html>"
        result = _parse_temp(".html", big_html)
        assert result is not None
        assert len(result) <= 5000


class TestParseConfigFiles:
    """Tests for config-type files: .env, .ini, .toml, .cfg, .yaml, .yml"""

    def test_env_file(self):
        result = _parse_temp(".env", "API_KEY=secret\nDEBUG=true\n")
        assert result is not None
        assert "API_KEY" in result

    def test_ini_file(self):
        result = _parse_temp(".ini", "[section]\nkey=value\n")
        assert result is not None
        assert "section" in result

    def test_toml_file(self):
        result = _parse_temp(".toml", '[package]\nname = "myapp"\nversion = "1.0"\n')
        assert result is not None
        assert "myapp" in result

    def test_yaml_file(self):
        result = _parse_temp(".yaml", "name: project\nversion: 1.0\n")
        assert result is not None
        assert "project" in result

    def test_yml_file(self):
        result = _parse_temp(".yml", "key: value\n")
        assert result is not None
        assert "key" in result

    def test_config_truncated_at_2000(self):
        big_config = "KEY=VALUE\n" * 300  # ~3000 chars
        result = _parse_temp(".ini", big_config)
        assert result is not None
        assert len(result) <= 2000


class TestParseCodeFiles:
    """Tests for source code files."""

    def test_py_file(self):
        result = _parse_temp(".py", "def hello():\n    return 'world'\n")
        assert result is not None
        assert "hello" in result

    def test_js_file(self):
        result = _parse_temp(".js", "function greet() { return 'hi'; }")
        assert result is not None
        assert "greet" in result

    def test_ts_file(self):
        result = _parse_temp(".ts", "const x: number = 42;")
        assert result is not None
        assert "number" in result

    def test_go_file(self):
        result = _parse_temp(".go", "package main\nfunc main() {}\n")
        assert result is not None
        assert "main" in result

    def test_java_file(self):
        result = _parse_temp(".java", "public class Main { public static void main(String[] args) {} }")
        assert result is not None
        assert "Main" in result


class TestParseLogFiles:
    """Tests for .log files (last 200 lines)."""

    def test_log_returns_content(self):
        content = "2024-01-01 ERROR something failed\n2024-01-01 INFO ok\n"
        result = _parse_temp(".log", content)
        assert result is not None
        assert "ERROR" in result

    def test_log_large_file_returns_last_lines(self):
        lines = [f"INFO log line {i}" for i in range(500)]
        content = "\n".join(lines)
        result = _parse_temp(".log", content)
        assert result is not None
        # Should contain last lines (close to 499)
        assert "499" in result

    def test_log_truncated_at_5000_chars(self):
        content = "x" * 10_000
        result = _parse_temp(".log", content)
        assert result is not None
        assert len(result) <= 5000


class TestParseVideoMetadata:
    """Tests for video file metadata extraction."""

    def test_mp4_returns_metadata(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00")  # dummy binary content
            path = f.name
        try:
            result = FileParser.parse(path)
        finally:
            os.unlink(path)
        assert result is not None
        assert "Video file" in result

    def test_mkv_returns_metadata(self):
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as f:
            f.write(b"\x00")
            path = f.name
        try:
            result = FileParser.parse(path)
        finally:
            os.unlink(path)
        assert result is not None

    def test_video_metadata_contains_filename(self):
        # File name info should appear in extracted metadata
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", prefix="my_test_video_", delete=False
        ) as f:
            f.write(b"\x00")
            path = f.name
        try:
            result = FileParser.parse(path)
        finally:
            os.unlink(path)
        assert result is not None
        assert "my" in result.lower() or "test" in result.lower() or "video" in result.lower()


class TestParseJupyterNotebook:
    """Tests for .ipynb Jupyter notebook files."""

    def test_notebook_extracts_cells(self):
        nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "cells": [
                {"cell_type": "markdown", "source": ["# Title\n", "Some text"], "metadata": {}},
                {"cell_type": "code", "source": ["x = 42\n", "print(x)"], "metadata": {}},
            ],
            "metadata": {},
        }
        result = _parse_temp(".ipynb", json.dumps(nb))
        assert result is not None
        assert "Title" in result
        assert "42" in result

    def test_empty_notebook(self):
        nb = {"nbformat": 4, "nbformat_minor": 5, "cells": [], "metadata": {}}
        result = _parse_temp(".ipynb", json.dumps(nb))
        # Empty notebook returns empty string or None
        assert result is None or result == ""

    def test_notebook_skips_empty_cells(self):
        nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "cells": [
                {"cell_type": "code", "source": [], "metadata": {}},
                {"cell_type": "markdown", "source": ["Real content"], "metadata": {}},
            ],
            "metadata": {},
        }
        result = _parse_temp(".ipynb", json.dumps(nb))
        assert result is not None
        assert "Real content" in result


class TestUnsupportedExtension:
    """Unknown extensions should return None."""

    def test_unknown_extension_returns_none(self):
        result = _parse_temp(".xyz_unknown", "some content")
        assert result is None

    def test_binary_unknown_extension_returns_none(self):
        result = _parse_temp(".bin", b"\x00\x01\x02\x03")
        assert result is None


class TestGetFileMetadata:
    """Tests for FileParser.get_file_metadata()."""

    def test_metadata_keys_present(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test content")
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert "path" in meta
        assert "name" in meta
        assert "size" in meta
        assert "modified_time" in meta
        assert "created_time" in meta
        assert "extension" in meta

    def test_metadata_path_matches(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("hello")
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert meta["path"] == path

    def test_metadata_extension_is_lowercase(self):
        with tempfile.NamedTemporaryFile(suffix=".TXT", delete=False, mode="w") as f:
            f.write("hello")
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert meta["extension"] == ".txt"

    def test_metadata_size_is_correct(self):
        content = "hello world"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write(content)
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert meta["size"] == len(content.encode())

    def test_metadata_name_is_basename(self):
        with tempfile.NamedTemporaryFile(
            suffix=".txt", prefix="myfile_", delete=False, mode="w"
        ) as f:
            f.write("data")
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert meta["name"] == os.path.basename(path)

    def test_metadata_modified_time_is_float(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("data")
            path = f.name
        try:
            meta = FileParser.get_file_metadata(path)
        finally:
            os.unlink(path)
        assert isinstance(meta["modified_time"], float)


class TestParseErrorHandling:
    """FileParser.parse() must not propagate exceptions."""

    def test_nonexistent_file_returns_none(self):
        result = FileParser.parse("/nonexistent/path/file.txt")
        assert result is None

    def test_parse_never_raises(self):
        try:
            FileParser.parse("/dev/null")
        except Exception as e:
            pytest.fail(f"FileParser.parse raised an exception: {e}")


# ── Top-level extract_text alias used in legacy tests ─────────────────────
class TestExtractTextAlias:
    """The module also exposes extract_text as an alias for FileParser.parse."""

    def test_extract_text_callable(self):
        from core.ingestion.file_parser import extract_text
        assert callable(extract_text)

    def test_extract_text_returns_text(self):
        from core.ingestion.file_parser import extract_text
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("alias test")
            path = f.name
        try:
            result = extract_text(path)
        finally:
            os.unlink(path)
        assert result is not None
        assert "alias" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

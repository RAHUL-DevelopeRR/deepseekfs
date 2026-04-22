"""
Neuron — Validation Tests
============================
Tests tool argument validation and parsing.

Covers:
  - Type coercion (str->int, str->bool, path normalization)
  - Required field enforcement
  - Default injection
  - Multi-format argument parsing (JSON, key=value, raw)
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.validation.schema import validate_tool_args, parse_arguments
from services.tools import ToolParam


class TestValidation:
    """Test argument validation and coercion."""

    def test_valid_string(self):
        params = [ToolParam("name", "string", "A name", required=True)]
        ok, cleaned, err = validate_tool_args("test", params, {"name": "hello"})
        assert ok
        assert cleaned["name"] == "hello"

    def test_missing_required(self):
        params = [ToolParam("path", "path", "File path", required=True)]
        ok, _, err = validate_tool_args("test", params, {})
        assert not ok
        assert "missing required" in err.lower()

    def test_default_injection(self):
        params = [
            ToolParam("path", "path", "File path", required=True),
            ToolParam("max_chars", "integer", "Max", required=False, default=4000),
        ]
        ok, cleaned, _ = validate_tool_args("test", params, {"path": "/foo"})
        assert ok
        assert cleaned["max_chars"] == 4000

    def test_integer_coercion(self):
        params = [ToolParam("count", "integer", "Count")]
        ok, cleaned, _ = validate_tool_args("test", params, {"count": "42"})
        assert ok
        assert cleaned["count"] == 42

    def test_integer_with_suffix(self):
        params = [ToolParam("timeout", "integer", "Timeout")]
        ok, cleaned, _ = validate_tool_args("test", params, {"timeout": "30s"})
        assert ok
        assert cleaned["timeout"] == 30

    def test_boolean_coercion_true(self):
        params = [ToolParam("flag", "boolean", "Flag")]
        ok, cleaned, _ = validate_tool_args("test", params, {"flag": "true"})
        assert ok
        assert cleaned["flag"] is True

    def test_boolean_coercion_false(self):
        params = [ToolParam("flag", "boolean", "Flag")]
        ok, cleaned, _ = validate_tool_args("test", params, {"flag": "no"})
        assert ok
        assert cleaned["flag"] is False

    def test_path_normalization_windows(self):
        params = [ToolParam("path", "path", "Path")]
        ok, cleaned, _ = validate_tool_args("test", params, {"path": "C:/Users/test"})
        assert ok
        assert "\\" in cleaned["path"]

    def test_optional_skipped(self):
        params = [
            ToolParam("required", "string", "R", required=True),
            ToolParam("optional", "string", "O", required=False),
        ]
        ok, cleaned, _ = validate_tool_args("test", params, {"required": "yes"})
        assert ok
        assert "optional" not in cleaned


class TestParseArguments:
    """Test multi-format argument parsing."""

    def test_json(self):
        result = parse_arguments('{"path": "/foo", "content": "bar"}')
        assert result["path"] == "/foo"
        assert result["content"] == "bar"

    def test_key_value(self):
        result = parse_arguments('path=/foo content="hello world"')
        assert result["path"] == "/foo"
        assert result["content"] == "hello world"

    def test_raw_string(self):
        result = parse_arguments("just a plain string")
        assert result["_raw"] == "just a plain string"

    def test_empty_string(self):
        result = parse_arguments("")
        assert result == {}

    def test_none_input(self):
        result = parse_arguments(None)
        assert result == {}

    def test_malformed_json(self):
        result = parse_arguments("{bad json")
        assert "_raw" in result or len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

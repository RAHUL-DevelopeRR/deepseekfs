"""
Neuron — Schema Validation
============================
Validates and coerces tool arguments against ToolParam schemas.
Catches malformed LLM outputs before they reach tool execution.

Principles:
  - Fail fast with clear error messages
  - Type coercion (str->int, str->bool) for LLM flexibility
  - Required field enforcement with default injection
  - Path normalization for Windows compatibility
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple


# ── Type coercion map ─────────────────────────────────────────

def _coerce_string(value: Any) -> str:
    return str(value)


def _coerce_path(value: Any) -> str:
    s = str(value).strip().strip("'\"")
    # Normalize forward slashes to backslash on Windows paths
    if len(s) >= 2 and s[1] == ":":
        s = s.replace("/", "\\")
    return s


def _coerce_integer(value: Any) -> int:
    if isinstance(value, str):
        # Handle "30s" -> 30, "100KB" -> 100
        cleaned = re.sub(r"[^0-9.\-]", "", value)
        return int(float(cleaned)) if cleaned else 0
    return int(value)


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


_COERCERS = {
    "string":  _coerce_string,
    "path":    _coerce_path,
    "integer": _coerce_integer,
    "boolean": _coerce_boolean,
}


# ── Public API ────────────────────────────────────────────────

def validate_tool_args(
    tool_name: str,
    params: list,               # List[ToolParam]
    raw_args: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], str]:
    """Validate and coerce tool arguments against parameter schema.
    
    Args:
        tool_name: Name of the tool (for error messages)
        params: List of ToolParam definitions from the tool
        raw_args: Raw arguments from the LLM
    
    Returns:
        (is_valid, cleaned_args, error_message)
        
    Design:
        - Strict on required fields
        - Lenient on types (coerces where possible)
        - Never mutates input
    """
    cleaned = {}
    errors = []

    for p in params:
        value = raw_args.get(p.name)

        # ── Required check ────────────────────────────
        if value is None and p.required:
            if p.default is not None:
                value = p.default
            else:
                errors.append(f"missing required: '{p.name}'")
                continue
        elif value is None:
            if p.default is not None:
                value = p.default
            else:
                continue  # Optional, no default — skip

        # ── Type coercion ─────────────────────────────
        coercer = _COERCERS.get(p.type, _coerce_string)
        try:
            value = coercer(value)
        except (ValueError, TypeError):
            errors.append(
                f"'{p.name}': expected {p.type}, got {type(value).__name__}"
            )
            continue

        cleaned[p.name] = value

    if errors:
        msg = f"{tool_name}: {'; '.join(errors)}"
        return False, cleaned, msg

    return True, cleaned, ""


def parse_arguments(raw: str) -> Dict[str, Any]:
    """Parse tool arguments from various LLM output formats.
    
    Handles (in priority order):
      1. Valid JSON: {"path": "/foo", "content": "bar"}
      2. Key=value:  path=/foo content=bar
      3. Raw string: treated as unnamed input
    """
    if not raw or not raw.strip():
        return {}

    raw = raw.strip()

    # 1. JSON
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 2. Key=value (handles quoted values)
    if "=" in raw:
        args = {}
        for match in re.finditer(
            r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))', raw
        ):
            key = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            args[key] = value
        if args:
            return args

    # 3. Raw string
    return {"_raw": raw}

"""Model/runtime diagnostics for the bundled local LLM."""
from __future__ import annotations

import ctypes
import os
import platform
import sys
from pathlib import Path
from typing import Any


NTSTATUS_ILLEGAL_INSTRUCTION = -1073741795
NTSTATUS_ILLEGAL_INSTRUCTION_HEX = "0xC000001D"


def _win_processor_feature(feature_id: int) -> bool | None:
    if os.name != "nt":
        return None
    try:
        return bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(feature_id))
    except Exception:
        return None


def get_cpu_runtime_profile() -> dict[str, Any]:
    """Return cheap CPU/runtime facts useful in beta support reports."""
    sse2 = _win_processor_feature(10)  # PF_XMMI64_INSTRUCTIONS_AVAILABLE
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "windows_sse2_probe": sse2,
        "path": os.environ.get("PATH", ""),
    }


def is_illegal_instruction_error(error: object) -> bool:
    text = str(error or "").lower()
    return (
        str(NTSTATUS_ILLEGAL_INSTRUCTION) in text
        or NTSTATUS_ILLEGAL_INSTRUCTION_HEX.lower() in text
        or "illegal instruction" in text
        or "c000001d" in text
    )


def normalize_model_error(error: object) -> str:
    """Turn raw native/backend errors into user-facing support text."""
    if not error:
        return "The local AI model is not loaded."

    raw = str(error)
    if is_illegal_instruction_error(raw):
        return (
            "The bundled local AI runtime cannot run on this CPU "
            f"({NTSTATUS_ILLEGAL_INSTRUCTION_HEX}, illegal instruction). "
            "The model file may be installed correctly, but the native "
            "llama.cpp backend used by this beta build requires CPU "
            "instructions this device does not expose. File search and folder "
            "summaries still work; offline MemoryOS generation needs a "
            "compatible CPU/backend build."
        )

    low = raw.lower()
    if "model file not found" in low or "gguf model not found" in low or "not found" in low:
        return (
            "The local Qwen GGUF model was not found. Reinstall Neuron or run "
            "`neufs doctor --load` to see the model search paths."
        )

    if "too small" in low or "corrupt" in low or "invalid model" in low:
        return (
            "The local model file looks incomplete or corrupted. Reinstall "
            "Neuron so the bundled GGUF model is copied again."
        )

    return raw


def format_ai_unavailable(error: object) -> str:
    return f"AI unavailable: {normalize_model_error(error)}"


def build_model_diagnostics(load: bool = False, allow_download: bool = False) -> dict[str, Any]:
    """Build a support report for model discovery and optional load testing."""
    from services.model_manager import (
        get_llm_model_path,
        get_model_search_dirs,
        LLM_MODEL_FILE,
        LLM_MODEL_REPO,
    )

    model_path = get_llm_model_path()
    payload: dict[str, Any] = {
        "ok": True,
        "runtime": get_cpu_runtime_profile(),
        "expected_model_file": LLM_MODEL_FILE,
        "expected_model_repo": LLM_MODEL_REPO,
        "model_available": model_path is not None,
        "model_path": str(model_path) if model_path else None,
        "model_size_mb": round(model_path.stat().st_size / (1024 * 1024), 1) if model_path else None,
        "model_search_dirs": [str(p) for p in get_model_search_dirs()],
        "load_attempted": bool(load),
        "loaded": None,
        "load_error": None,
        "load_error_normalized": None,
    }

    if not load:
        return payload

    try:
        from services.llm_client import LLMWorkerClient

        engine = LLMWorkerClient()
        loaded = engine.load_model(allow_download=allow_download)
        payload["loaded"] = bool(loaded)
        payload["load_error"] = engine.load_error
        payload["load_error_normalized"] = normalize_model_error(engine.load_error) if engine.load_error else None
        payload["ok"] = bool(loaded)
        try:
            engine.unload()
        except Exception:
            pass
    except Exception as exc:
        payload["loaded"] = False
        payload["load_error"] = str(exc)
        payload["load_error_normalized"] = normalize_model_error(exc)
        payload["ok"] = False

    return payload

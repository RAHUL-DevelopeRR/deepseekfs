from services.model_health import (
    NTSTATUS_ILLEGAL_INSTRUCTION_HEX,
    format_ai_unavailable,
    is_illegal_instruction_error,
    normalize_model_error,
)


def test_model_health_detects_illegal_instruction_status():
    raw = "[WinError -1073741795] Windows Error 0xc000001d"

    assert is_illegal_instruction_error(raw)
    assert "cannot run on this CPU" in normalize_model_error(raw)
    assert NTSTATUS_ILLEGAL_INSTRUCTION_HEX in normalize_model_error(raw)


def test_model_health_formats_missing_model_cleanly():
    msg = format_ai_unavailable("Qwen 2.5 Coder GGUF model not found")

    assert msg.startswith("AI unavailable:")
    assert "local Qwen GGUF model was not found" in msg
    assert "[WinError" not in msg


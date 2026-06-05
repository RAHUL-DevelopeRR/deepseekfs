"""Model discovery and offline startup tests."""

from pathlib import Path


def _sparse_file(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.truncate(size)
    return path


def test_model_manager_prefers_cached_exact_qwen(monkeypatch, tmp_path):
    from services import model_manager

    exact = _sparse_file(
        tmp_path / model_manager.LLM_MODEL_FILE,
        model_manager._MIN_GGUF_SIZE_BYTES + 1,
    )
    alt = _sparse_file(
        tmp_path / "qwen2.5-coder-0.5b-instruct-q4_0.gguf",
        model_manager._MIN_GGUF_SIZE_BYTES + 1024,
    )

    monkeypatch.setenv("NEURON_MODEL_DIRS", str(tmp_path))

    assert model_manager.get_llm_model_path() == exact
    assert alt.exists()


def test_model_manager_ignores_partial_downloads(monkeypatch, tmp_path):
    from services import model_manager

    _sparse_file(tmp_path / "qwen2.5-coder-3b-instruct-q5_k_m.gguf.incomplete", 1024)
    _sparse_file(tmp_path / "tiny.gguf", 1024)

    monkeypatch.setenv("NEURON_MODEL_DIRS", str(tmp_path))
    monkeypatch.setenv("NEURON_MODEL_DIRS_ONLY", "1")

    assert model_manager.get_llm_model_path() is None


def test_llm_load_model_does_not_download_by_default(monkeypatch):
    from services.llm_engine import LLMEngine
    import services.model_manager as model_manager

    called = {"download": False}

    def fake_download(*_args, **_kwargs):
        called["download"] = True
        raise AssertionError("download should not be called")

    monkeypatch.setattr(model_manager, "get_llm_model_path", lambda: None)
    monkeypatch.setattr(model_manager, "download_llm_model", fake_download)

    engine = LLMEngine()

    assert engine.load_model() is False
    assert called["download"] is False
    assert "not found" in (engine.load_error or "").lower()

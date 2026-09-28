from services import model_manager


def test_frozen_download_uses_user_writable_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(model_manager.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert model_manager.get_models_dir() == tmp_path / "Neuron" / "models"

"""
Neuron — Profile Manager Tests
=================================
Tests the file-based profile system.

Covers:
  - Profile creation and serialization
  - CRUD operations
  - Active profile switching
  - Username-gated weight modification
  - Export/import
"""
import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.profiles.models import Profile, ScoringWeights, LLMSettings
from services.profiles.manager import ProfileManager


@pytest.fixture
def manager():
    """Create a temporary profile manager."""
    d = tempfile.mkdtemp(prefix="neuron_profiles_")
    m = ProfileManager(profiles_dir=Path(d))
    yield m
    shutil.rmtree(d, ignore_errors=True)


class TestScoringWeights:
    """Test scoring weight model."""

    def test_default_weights(self):
        w = ScoringWeights.default()
        assert w.semantic == 0.55
        assert w.validate()

    def test_valid_weights(self):
        w = ScoringWeights(semantic=0.6, time=0.15, size=0.1, depth=0.1, access=0.05)
        assert w.validate()

    def test_invalid_weights(self):
        w = ScoringWeights(semantic=0.9, time=0.5, size=0.1, depth=0.1, access=0.1)
        assert not w.validate()

    def test_serialization(self):
        w = ScoringWeights(semantic=0.7, time=0.1, size=0.1, depth=0.05, access=0.05)
        d = w.to_dict()
        w2 = ScoringWeights.from_dict(d)
        assert w2.semantic == 0.7


class TestProfile:
    """Test profile model."""

    def test_default_profile(self):
        p = Profile.default()
        assert p.name == "default"
        assert p.scoring.validate()

    def test_serialization(self):
        p = Profile(name="dev", top_k=30, theme="dark")
        d = p.to_dict()
        p2 = Profile.from_dict(d)
        assert p2.name == "dev"
        assert p2.top_k == 30

    def test_llm_settings(self):
        p = Profile(name="test")
        assert p.llm.temperature == 0.5
        assert p.llm.max_tokens_chat == 512


class TestProfileManager:
    """Test profile CRUD operations."""

    def test_default_exists(self, manager):
        assert "default" in manager.list_profiles()

    def test_create_profile(self, manager):
        p = manager.create("developer")
        assert p.name == "developer"
        assert "developer" in manager.list_profiles()

    def test_load_profile(self, manager):
        manager.create("researcher")
        loaded = manager.load("researcher")
        assert loaded is not None
        assert loaded.name == "researcher"

    def test_save_and_load(self, manager):
        p = Profile(name="custom", top_k=50)
        manager.save(p)
        loaded = manager.load("custom")
        assert loaded.top_k == 50

    def test_delete_profile(self, manager):
        manager.create("temp")
        assert manager.delete("temp")
        assert "temp" not in manager.list_profiles()

    def test_cannot_delete_default(self, manager):
        assert not manager.delete("default")

    def test_active_profile(self, manager):
        manager.create("dev")
        assert manager.set_active("dev")
        assert manager.get_active_name() == "dev"

    def test_active_fallback(self, manager):
        assert manager.get_active_name() == "default"

    def test_modify_weights_wrong_username(self, manager):
        ok, msg = manager.modify_weights(
            "default",
            ScoringWeights(semantic=0.7, time=0.1, size=0.1, depth=0.05, access=0.05),
            "wrong_user_12345",
        )
        assert not ok
        assert "mismatch" in msg.lower()

    def test_modify_weights_correct_username(self, manager):
        expected_user = os.getenv("USERNAME", os.getenv("USER", ""))
        if not expected_user:
            pytest.skip("No USERNAME env var")

        ok, msg = manager.modify_weights(
            "default",
            ScoringWeights(semantic=0.7, time=0.1, size=0.1, depth=0.05, access=0.05),
            expected_user,
        )
        assert ok

        loaded = manager.load("default")
        assert loaded.scoring.semantic == 0.7

    def test_modify_weights_invalid_sum(self, manager):
        expected_user = os.getenv("USERNAME", os.getenv("USER", ""))
        if not expected_user:
            pytest.skip("No USERNAME env var")

        ok, msg = manager.modify_weights(
            "default",
            ScoringWeights(semantic=0.9, time=0.5, size=0.1, depth=0.1, access=0.1),
            expected_user,
        )
        assert not ok
        assert "sum" in msg.lower()

    def test_export_profile(self, manager):
        json_str = manager.export_profile("default")
        assert json_str is not None
        assert "default" in json_str

    def test_import_profile(self, manager):
        json_str = manager.export_profile("default")
        import json
        data = json.loads(json_str)
        data["name"] = "imported"
        ok, name = manager.import_profile(json.dumps(data))
        assert ok
        assert name == "imported"
        assert "imported" in manager.list_profiles()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Unit tests for app/config.py
Covers: constants, UserConfig load/save/add/remove, path resolution, defaults.
"""
import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app.config as config
from app.config import UserConfig


class TestConfigConstants:
    """Verify module-level constants are present and well-formed."""

    def test_base_dir_is_path(self):
        assert isinstance(config.BASE_DIR, Path)

    def test_storage_dir_is_subdir_of_base(self):
        assert config.STORAGE_DIR.parent == config.BASE_DIR

    def test_faiss_index_dir_created(self):
        assert config.FAISS_INDEX_DIR.exists()

    def test_cache_dir_created(self):
        assert config.CACHE_DIR.exists()

    def test_supported_extensions_is_set(self):
        assert isinstance(config.SUPPORTED_EXTENSIONS, set)
        assert len(config.SUPPORTED_EXTENSIONS) > 0

    def test_common_extensions_present(self):
        for ext in (".txt", ".pdf", ".py", ".docx", ".md"):
            assert ext in config.SUPPORTED_EXTENSIONS

    def test_skip_dirs_is_set(self):
        assert isinstance(config.SKIP_DIRS, set)
        assert "venv" in config.SKIP_DIRS
        assert ".git" in config.SKIP_DIRS
        assert "__pycache__" in config.SKIP_DIRS
        assert "node_modules" in config.SKIP_DIRS

    def test_model_name_is_string(self):
        assert isinstance(config.MODEL_NAME, str)
        assert len(config.MODEL_NAME) > 0

    def test_embedding_dim_is_positive(self):
        assert isinstance(config.EMBEDDING_DIM, int)
        assert config.EMBEDDING_DIM > 0

    def test_top_k_is_positive_int(self):
        assert isinstance(config.TOP_K, int)
        assert config.TOP_K > 0

    def test_similarity_threshold_in_range(self):
        assert 0.0 <= config.SIMILARITY_THRESHOLD <= 1.0

    def test_api_host_is_string(self):
        assert isinstance(config.API_HOST, str)

    def test_api_port_is_int(self):
        assert isinstance(config.API_PORT, int)
        assert config.API_PORT > 0

    def test_max_file_size_large(self):
        # Should be at least 1 GB
        assert config.MAX_FILE_SIZE_BYTES >= 1 * 1024 * 1024 * 1024


class TestUserConfigDefaults:
    """UserConfig.DEFAULTS must have correct types."""

    def test_defaults_is_dict(self):
        assert isinstance(UserConfig.DEFAULTS, dict)

    def test_extra_watch_paths_default_is_list(self):
        assert isinstance(UserConfig.DEFAULTS["extra_watch_paths"], list)

    def test_excluded_paths_default_is_list(self):
        assert isinstance(UserConfig.DEFAULTS["excluded_paths"], list)

    def test_top_k_default_positive(self):
        assert isinstance(UserConfig.DEFAULTS["top_k"], int)
        assert UserConfig.DEFAULTS["top_k"] > 0

    def test_theme_default_is_string(self):
        assert isinstance(UserConfig.DEFAULTS["theme"], str)

    def test_hotkey_default_is_string(self):
        assert isinstance(UserConfig.DEFAULTS["hotkey"], str)


class TestUserConfigLoadSave:
    """UserConfig.load() and save() round-trip through a temp file."""

    def _with_temp_config(self, data: dict):
        """Context manager: temporarily redirect CONFIG_PATH to a temp file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            json.dump(data, f)
            path = Path(f.name)

        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = path
        try:
            yield path
        finally:
            UserConfig.CONFIG_PATH = original
            path.unlink(missing_ok=True)

    def test_load_returns_dict(self):
        cfg = UserConfig.load()
        assert isinstance(cfg, dict)

    def test_load_includes_all_default_keys(self):
        cfg = UserConfig.load()
        for key in UserConfig.DEFAULTS:
            assert key in cfg

    def test_save_and_load_round_trip(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)

        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = tmp_path
        try:
            cfg = UserConfig.load()
            cfg["top_k"] = 99
            UserConfig.save(cfg)
            reloaded = UserConfig.load()
            assert reloaded["top_k"] == 99
        finally:
            UserConfig.CONFIG_PATH = original
            tmp_path.unlink(missing_ok=True)

    def test_load_merges_missing_defaults(self):
        """If config file is missing keys, defaults are used."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            json.dump({"top_k": 5}, f)
            tmp_path = Path(f.name)

        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = tmp_path
        try:
            cfg = UserConfig.load()
            assert cfg["top_k"] == 5
            assert "extra_watch_paths" in cfg
        finally:
            UserConfig.CONFIG_PATH = original
            tmp_path.unlink(missing_ok=True)

    def test_load_with_corrupt_json_returns_defaults(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("{ invalid json }")
            tmp_path = Path(f.name)

        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = tmp_path
        try:
            cfg = UserConfig.load()
            for key in UserConfig.DEFAULTS:
                assert key in cfg
        finally:
            UserConfig.CONFIG_PATH = original
            tmp_path.unlink(missing_ok=True)

    def test_load_missing_file_returns_defaults(self):
        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = Path("/nonexistent/path/user_config.json")
        try:
            cfg = UserConfig.load()
            for key in UserConfig.DEFAULTS:
                assert key in cfg
        finally:
            UserConfig.CONFIG_PATH = original

    def test_save_creates_valid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = Path(f.name)

        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = tmp_path
        try:
            UserConfig.save({"top_k": 15, "theme": "dark"})
            loaded = json.loads(tmp_path.read_text(encoding="utf-8"))
            assert loaded["top_k"] == 15
            assert loaded["theme"] == "dark"
        finally:
            UserConfig.CONFIG_PATH = original
            tmp_path.unlink(missing_ok=True)


class TestUserConfigWatchPaths:
    """add_watch_path / remove_watch_path logic."""

    def _setup_temp_config(self):
        """Return (original_path, temp_path) for teardown."""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        tmp_path = Path(tmp.name)
        tmp_path.write_text(json.dumps({**UserConfig.DEFAULTS}), encoding="utf-8")
        original = UserConfig.CONFIG_PATH
        UserConfig.CONFIG_PATH = tmp_path
        return original, tmp_path

    def _teardown_temp_config(self, original, tmp_path):
        UserConfig.CONFIG_PATH = original
        tmp_path.unlink(missing_ok=True)

    def test_add_existing_path_returns_true(self):
        original, tmp_path = self._setup_temp_config()
        try:
            result = UserConfig.add_watch_path(str(ROOT))
            assert result is True
        finally:
            self._teardown_temp_config(original, tmp_path)

    def test_add_nonexistent_path_returns_false(self):
        original, tmp_path = self._setup_temp_config()
        try:
            result = UserConfig.add_watch_path("/this/path/does/not/exist")
            assert result is False
        finally:
            self._teardown_temp_config(original, tmp_path)

    def test_add_duplicate_path_returns_false(self):
        original, tmp_path = self._setup_temp_config()
        try:
            UserConfig.add_watch_path(str(ROOT))
            result = UserConfig.add_watch_path(str(ROOT))
            assert result is False
        finally:
            self._teardown_temp_config(original, tmp_path)

    def test_remove_added_path_returns_true(self):
        original, tmp_path = self._setup_temp_config()
        try:
            UserConfig.add_watch_path(str(ROOT))
            result = UserConfig.remove_watch_path(str(ROOT))
            assert result is True
        finally:
            self._teardown_temp_config(original, tmp_path)

    def test_remove_nonexistent_path_returns_false(self):
        original, tmp_path = self._setup_temp_config()
        try:
            result = UserConfig.remove_watch_path("/does/not/exist/at/all")
            assert result is False
        finally:
            self._teardown_temp_config(original, tmp_path)

    def test_add_then_remove_path_not_in_extras(self):
        original, tmp_path = self._setup_temp_config()
        try:
            UserConfig.add_watch_path(str(ROOT))
            UserConfig.remove_watch_path(str(ROOT))
            cfg = UserConfig.load()
            extras_resolved = {
                str(Path(p).resolve())
                for p in cfg.get("extra_watch_paths", [])
            }
            assert str(Path(ROOT).resolve()) not in extras_resolved
        finally:
            self._teardown_temp_config(original, tmp_path)


class TestGetUserWatchPaths:
    """get_user_watch_paths only returns existing directories."""

    def test_returns_list(self):
        paths = config.get_user_watch_paths()
        assert isinstance(paths, list)

    def test_all_paths_exist(self):
        paths = config.get_user_watch_paths()
        for p in paths:
            assert Path(p).exists(), f"Path does not exist: {p}"

    def test_all_paths_are_strings(self):
        paths = config.get_user_watch_paths()
        for p in paths:
            assert isinstance(p, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

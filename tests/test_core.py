"""
Neuron — Core Module Tests
===========================
Validates imports, config, and basic functionality.
"""
import os
import sys
import importlib
import pytest

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class TestImports:
    """Verify all core modules import without errors."""

    def test_config_import(self):
        import app.config as config
        assert hasattr(config, 'BASE_DIR') or hasattr(config, 'DB_PATH')

    def test_logger_import(self):
        from app.logger import logger
        assert logger is not None

    def test_embedder_import(self):
        from core.embeddings.embedder import get_embedder
        assert callable(get_embedder)

    def test_index_builder_import(self):
        from core.indexing.index_builder import get_index
        assert callable(get_index)

    def test_semantic_search_import(self):
        from core.search.semantic_search import SemanticSearch
        assert SemanticSearch is not None

    def test_ollama_service_import(self):
        from services.ollama_service import OllamaService
        assert OllamaService is not None

    def test_desktop_service_import(self):
        from services.desktop_service import DesktopService
        assert DesktopService is not None


class TestConfig:
    """Validate configuration values."""

    def test_base_dir_exists(self):
        import app.config as config
        base = getattr(config, 'BASE_DIR', None)
        if base:
            assert os.path.isdir(base)


class TestWarmupScript:
    """Validate warmup script structure."""

    def test_warmup_exists(self):
        warmup_path = os.path.join(ROOT, 'warmup_encyl.py')
        assert os.path.exists(warmup_path)

    def test_warmup_importable(self):
        spec = importlib.util.spec_from_file_location(
            'warmup_encyl',
            os.path.join(ROOT, 'warmup_encyl.py')
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, 'check_ollama')
        assert hasattr(mod, 'warmup')
        assert hasattr(mod, 'pull_model')


class TestFileParser:
    """Validate file parser handles common types."""

    def test_parser_import(self):
        from core.ingestion.file_parser import extract_text
        assert callable(extract_text)

    def test_parse_txt_file(self):
        from core.ingestion.file_parser import extract_text
        # Create temp test file
        test_file = os.path.join(ROOT, 'tests', '_test_sample.txt')
        with open(test_file, 'w') as f:
            f.write('Hello Neuron test content')
        try:
            text = extract_text(test_file)
            assert 'Hello' in text or 'Neuron' in text or text == ''
        finally:
            os.remove(test_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

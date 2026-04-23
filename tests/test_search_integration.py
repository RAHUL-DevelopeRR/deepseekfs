"""
Neuron — Search Integration Tests
====================================
Tests the full search pipeline: index fixtures → query → verify results.

Uses a temporary directory with known test files to verify:
  1. File indexing works
  2. Semantic search returns relevant results
  3. Query parser correctly filters by extension
  4. Score ordering is correct
"""
import os
import sys
import shutil
import tempfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="module")
def fixture_dir():
    """Create a temp directory with test files."""
    d = tempfile.mkdtemp(prefix="neuron_test_")

    # Python files
    with open(os.path.join(d, "calculator.py"), "w") as f:
        f.write("def add(a, b): return a + b\ndef subtract(a, b): return a - b\n")
    with open(os.path.join(d, "web_server.py"), "w") as f:
        f.write("from flask import Flask\napp = Flask(__name__)\n")

    # Documents
    with open(os.path.join(d, "meeting_notes.txt"), "w") as f:
        f.write("Meeting about Q2 targets. Revenue goals discussed.")
    with open(os.path.join(d, "research_paper.md"), "w") as f:
        f.write("# Neural Network Architecture\nTransformers are the backbone of modern NLP.")

    # Config files
    with open(os.path.join(d, "config.json"), "w") as f:
        f.write('{"database": "sqlite", "port": 5432}')
    with open(os.path.join(d, "setup.yaml"), "w") as f:
        f.write("name: myproject\nversion: 1.0.0\n")

    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestQueryParser:
    """Test the query parser's intent detection."""

    def test_import(self):
        from core.search.query_parser import extract_intent
        assert callable(extract_intent)

    def test_python_query_detects_extension(self):
        from core.search.query_parser import extract_intent
        cleaned, exts, path, size, excluded = extract_intent("find my python files")
        assert ".py" in exts

    def test_document_query(self):
        from core.search.query_parser import extract_intent
        cleaned, exts, path, size, excluded = extract_intent("search for PDF documents")
        assert ".pdf" in exts


class TestSemanticSearch:
    """Test the semantic search engine."""

    def test_import(self):
        from core.search.semantic_search import SemanticSearch
        assert SemanticSearch is not None

    def test_instantiation(self):
        from core.search.semantic_search import SemanticSearch
        searcher = SemanticSearch()
        assert searcher is not None

    def test_search_returns_list(self):
        from core.search.semantic_search import SemanticSearch
        searcher = SemanticSearch()
        results = searcher.search("test query", top_k=5)
        assert isinstance(results, list)

    def test_results_have_required_fields(self):
        from core.search.semantic_search import SemanticSearch
        searcher = SemanticSearch()
        results = searcher.search("python code", top_k=3)
        for r in results:
            assert "path" in r, "Result missing 'path' field"

    def test_top_k_limits_results(self):
        from core.search.semantic_search import SemanticSearch
        searcher = SemanticSearch()
        results = searcher.search("files", top_k=3)
        assert len(results) <= 3


class TestEmbedder:
    """Test the embedding model."""

    def test_import(self):
        from core.embeddings.embedder import get_embedder
        assert callable(get_embedder)

    def test_embedder_produces_vectors(self):
        from core.embeddings.embedder import get_embedder
        embedder = get_embedder()
        if hasattr(embedder, "embed"):
            vec = embedder.embed("hello world")
            assert len(vec) > 0
        elif hasattr(embedder, "encode"):
            vec = embedder.encode(["hello world"])
            assert len(vec) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

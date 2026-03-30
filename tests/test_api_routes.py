"""
Unit and integration tests for API routes.
Uses FastAPI's TestClient (requires httpx + fastapi).
Tests are skipped gracefully if fastapi/httpx are not installed.

Heavy ML/FAISS dependencies are mocked in sys.modules before any
application imports, so tests work in a lightweight CI environment.
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── Stub out heavy dependencies that are unavailable in lightweight CI ───
_HEAVY_MODULES = [
    "faiss",
    "torch",
    "sentence_transformers",
    "transformers",
    "watchdog",
    "watchdog.observers",
    "watchdog.events",
    "PyQt6",
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
]
for _mod in _HEAVY_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ── Optional import guard ─────────────────────────────────────────────────
try:
    from fastapi.testclient import TestClient
    import httpx  # noqa: F401 — ensure starlette async backend available
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="fastapi / httpx not installed — skipping API route tests"
)


# ── Shared mock objects ───────────────────────────────────────────────────
def _make_mock_index():
    mock_index = MagicMock()
    mock_faiss_index = MagicMock()
    mock_faiss_index.ntotal = 0
    mock_index.index = mock_faiss_index
    mock_index.get_index_stats.return_value = {
        "total_files": 0,
        "index_vectors": 0,
        "storage_mb": 0,
    }
    mock_index.search_raw.return_value = ([], [])
    mock_index.get_metadata_by_faiss_id.return_value = None
    return mock_index


def _make_mock_embedder():
    mock_embedder = MagicMock()
    mock_embedder.encode_single.return_value = [0.0] * 384
    return mock_embedder


# ── Fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    """Return a TestClient wired to the FastAPI app with heavy deps patched."""
    mock_index = _make_mock_index()
    mock_embedder = _make_mock_embedder()

    with patch("core.indexing.index_builder.get_index", return_value=mock_index), \
         patch("core.embeddings.embedder.get_embedder", return_value=mock_embedder), \
         patch("services.startup_indexer.StartupIndexer"), \
         patch("core.watcher.file_watcher.FileWatcher"):
        # Import app.main inside the patched context so singletons use mocks
        import importlib
        import app.main as app_module
        importlib.reload(app_module)
        from fastapi.testclient import TestClient as _TC
        with _TC(app_module.app, raise_server_exceptions=False) as c:
            yield c


# ── Pydantic schemas ──────────────────────────────────────────────────────
class TestSchemas:
    """Validate Pydantic request / response models."""

    def test_search_request_valid(self):
        from api.schemas.request import SearchRequest
        req = SearchRequest(query="python files", top_k=5, use_time_ranking=True)
        assert req.query == "python files"
        assert req.top_k == 5

    def test_search_request_defaults(self):
        from api.schemas.request import SearchRequest
        req = SearchRequest(query="test")
        assert req.top_k == 10
        assert req.use_time_ranking is True

    def test_search_request_query_too_short_raises(self):
        from api.schemas.request import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_search_request_query_too_long_raises(self):
        from api.schemas.request import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="x" * 501)

    def test_search_request_top_k_too_large_raises(self):
        from api.schemas.request import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="test", top_k=101)

    def test_search_request_top_k_zero_raises(self):
        from api.schemas.request import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="test", top_k=0)

    def test_index_request_valid(self):
        from api.schemas.request import IndexRequest
        req = IndexRequest(file_path="/some/path/file.txt")
        assert req.file_path == "/some/path/file.txt"

    def test_index_request_empty_path_raises(self):
        from api.schemas.request import IndexRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IndexRequest(file_path="")

    def test_index_directory_request_defaults(self):
        from api.schemas.request import IndexDirectoryRequest
        req = IndexDirectoryRequest(directory_path="/some/dir")
        assert req.recursive is True

    def test_search_response_model(self):
        from api.schemas.response import SearchResponse, SearchResult
        result = SearchResult(
            path="/test/file.txt",
            name="file.txt",
            extension=".txt",
            size=100,
            modified_time=1_700_000_000.0,
            semantic_score=0.9,
            time_score=0.8,
            combined_score=0.85,
        )
        response = SearchResponse(
            query="test",
            results=[result],
            count=1,
            timestamp=1_700_000_000.0,
        )
        assert response.count == 1
        assert response.results[0].name == "file.txt"

    def test_health_response_model(self):
        from api.schemas.response import HealthResponse
        resp = HealthResponse(status="healthy", index_stats={"total_files": 10})
        assert resp.status == "healthy"

    def test_index_response_model(self):
        from api.schemas.response import IndexResponse
        resp = IndexResponse(success=True, message="Indexed", indexed_count=1)
        assert resp.success is True


# ── HTTP endpoint tests ───────────────────────────────────────────────────
class TestRootEndpoint:
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_json_has_message(self, client):
        response = client.get("/")
        data = response.json()
        assert "message" in data

    def test_root_json_has_docs_key(self, client):
        response = client.get("/")
        data = response.json()
        assert "docs" in data


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_json_has_status(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data

    def test_health_status_is_string(self, client):
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["status"], str)

    def test_health_json_has_index_stats(self, client):
        response = client.get("/health")
        data = response.json()
        assert "index_stats" in data


class TestSearchEndpoint:
    def test_search_empty_index_returns_200(self, client):
        payload = {"query": "python files", "top_k": 5}
        response = client.post("/search/", json=payload)
        assert response.status_code == 200

    def test_search_response_has_required_fields(self, client):
        payload = {"query": "test query"}
        response = client.post("/search/", json=payload)
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "count" in data
        assert "timestamp" in data

    def test_search_results_is_list(self, client):
        payload = {"query": "any query"}
        response = client.post("/search/", json=payload)
        data = response.json()
        assert isinstance(data["results"], list)

    def test_search_count_matches_results_length(self, client):
        payload = {"query": "any query"}
        response = client.post("/search/", json=payload)
        data = response.json()
        assert data["count"] == len(data["results"])

    def test_search_empty_query_returns_422(self, client):
        payload = {"query": ""}
        response = client.post("/search/", json=payload)
        assert response.status_code == 422

    def test_search_missing_query_returns_422(self, client):
        response = client.post("/search/", json={})
        assert response.status_code == 422

    def test_search_top_k_too_large_returns_422(self, client):
        payload = {"query": "test", "top_k": 999}
        response = client.post("/search/", json=payload)
        assert response.status_code == 422

    def test_search_query_echoed_in_response(self, client):
        payload = {"query": "machine learning"}
        response = client.post("/search/", json=payload)
        data = response.json()
        assert data["query"] == "machine learning"

    def test_search_use_time_ranking_false(self, client):
        payload = {"query": "test", "use_time_ranking": False}
        response = client.post("/search/", json=payload)
        assert response.status_code == 200

    def test_search_timestamp_is_float(self, client):
        payload = {"query": "test"}
        response = client.post("/search/", json=payload)
        data = response.json()
        assert isinstance(data["timestamp"], float)


class TestIndexEndpoints:
    def test_index_file_nonexistent_path(self, client):
        """Indexing a nonexistent file: endpoint should handle gracefully."""
        mock_idx = _make_mock_index()
        mock_idx.add_file.return_value = False
        mock_idx.save.return_value = None

        with patch("api.routes.index.get_index", return_value=mock_idx):
            payload = {"file_path": "/nonexistent/file.txt"}
            response = client.post("/index/file", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "indexed_count" in data

    def test_index_file_empty_path_returns_422(self, client):
        payload = {"file_path": ""}
        response = client.post("/index/file", json=payload)
        assert response.status_code == 422

    def test_index_directory_response_shape(self, client):
        mock_idx = _make_mock_index()
        mock_idx.index_directory.return_value = 0
        mock_idx.save.return_value = None

        with patch("api.routes.index.get_index", return_value=mock_idx):
            payload = {"directory_path": "/tmp", "recursive": False}
            response = client.post("/index/directory", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "indexed_count" in data

    def test_index_directory_empty_path_returns_422(self, client):
        payload = {"directory_path": ""}
        response = client.post("/index/directory", json=payload)
        assert response.status_code == 422


class TestOpenEndpoint:
    def test_open_returns_json(self, client):
        from unittest.mock import patch
        with patch("subprocess.Popen"):
            response = client.get("/open", params={"path": "/tmp/test.txt"})
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

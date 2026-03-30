import unittest
import types
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

if "sentence_transformers" not in sys.modules:
    fake_st = types.ModuleType("sentence_transformers")

    class _DummySentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def get_sentence_embedding_dimension(self):
            return 384

        def encode(self, texts, **kwargs):
            return [[0.0] * 384 for _ in texts]

    fake_st.SentenceTransformer = _DummySentenceTransformer
    sys.modules["sentence_transformers"] = fake_st

if "faiss" not in sys.modules:
    fake_faiss = types.ModuleType("faiss")

    class _DummyIndexFlatL2:
        def __init__(self, dim):
            self.dim = dim
            self.ntotal = 0

        def add(self, embedding):
            self.ntotal += len(embedding)

        def search(self, query_embedding, k):
            return [[0.0] * k], [[-1] * k]

    fake_faiss.IndexFlatL2 = _DummyIndexFlatL2
    fake_faiss.read_index = lambda path: _DummyIndexFlatL2(384)
    fake_faiss.write_index = lambda index, path: None
    sys.modules["faiss"] = fake_faiss

from api.routes import health, index, search


class _FakeSearchEngine:
    def __init__(self, results):
        self._results = results

    def search(self, query, top_k, use_time_ranking):
        return self._results


class _FakeIndex:
    def __init__(self, add_file_result=True, index_directory_count=2):
        self.add_file_result = add_file_result
        self.index_directory_count = index_directory_count
        self.saved = 0

    def add_file(self, path):
        return self.add_file_result

    def index_directory(self, path, recursive):
        return self.index_directory_count

    def save(self):
        self.saved += 1

    def get_index_stats(self):
        return {"total_documents": 3, "index_size": 3, "embedding_dim": 384, "watch_paths": []}


class TestApiRoutes(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(search.router)
        app.include_router(index.router)
        app.include_router(health.router)
        self.client = TestClient(app)

    def test_search_endpoint_returns_results(self):
        sample_results = [{
            "path": "/tmp/file.txt",
            "name": "file.txt",
            "extension": ".txt",
            "size": 100,
            "modified_time": 1.0,
            "semantic_score": 0.9,
            "time_score": 0.8,
            "combined_score": 0.88,
        }]
        with patch("api.routes.search.get_search_engine", return_value=_FakeSearchEngine(sample_results)):
            response = self.client.post("/search/", json={"query": "file", "top_k": 5, "use_time_ranking": True})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["name"], "file.txt")

    def test_search_endpoint_invalid_payload_returns_422(self):
        response = self.client.post("/search/", json={"query": "", "top_k": 0})
        self.assertEqual(response.status_code, 422)

    def test_index_file_endpoint_success(self):
        fake_index = _FakeIndex(add_file_result=True)
        with patch("api.routes.index.get_index", return_value=fake_index):
            response = self.client.post("/index/file", json={"file_path": "/tmp/a.txt"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        self.assertEqual(fake_index.saved, 1)

    def test_index_file_endpoint_skipped(self):
        fake_index = _FakeIndex(add_file_result=False)
        with patch("api.routes.index.get_index", return_value=fake_index):
            response = self.client.post("/index/file", json={"file_path": "/tmp/a.txt"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["indexed_count"], 0)
        self.assertEqual(fake_index.saved, 1)

    def test_index_directory_endpoint_returns_count(self):
        fake_index = _FakeIndex(index_directory_count=7)
        with patch("api.routes.index.get_index", return_value=fake_index):
            response = self.client.post("/index/directory", json={"directory_path": "/tmp", "recursive": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["indexed_count"], 7)
        self.assertEqual(fake_index.saved, 1)

    def test_health_endpoint_healthy(self):
        fake_index = _FakeIndex()
        with patch("api.routes.health.get_index", return_value=fake_index):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertIn("index_stats", response.json())

    def test_health_endpoint_unhealthy_on_error(self):
        with patch("api.routes.health.get_index", side_effect=RuntimeError("fail")):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unhealthy")

    def test_open_endpoint_windows_uses_explorer(self):
        with patch("platform.system", return_value="Windows"), patch("subprocess.Popen") as popen:
            response = self.client.get("/open", params={"path": "/tmp/file.txt"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        popen.assert_called_once()

    def test_open_endpoint_linux_uses_xdg_open(self):
        with patch("platform.system", return_value="Linux"), patch("subprocess.Popen") as popen:
            response = self.client.get("/open", params={"path": "/tmp/file.txt"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        popen.assert_called_once_with(["xdg-open", "/tmp"])


if __name__ == "__main__":
    unittest.main()

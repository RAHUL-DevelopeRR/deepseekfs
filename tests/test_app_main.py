import unittest
import types
import sys
from unittest.mock import patch

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

if "watchdog" not in sys.modules:
    fake_watchdog = types.ModuleType("watchdog")
    fake_watchdog_observers = types.ModuleType("watchdog.observers")
    fake_watchdog_events = types.ModuleType("watchdog.events")

    class _DummyObserver:
        def schedule(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def join(self):
            pass

    class _DummyEventHandler:
        pass

    fake_watchdog_observers.Observer = _DummyObserver
    fake_watchdog_events.FileSystemEventHandler = _DummyEventHandler
    sys.modules["watchdog"] = fake_watchdog
    sys.modules["watchdog.observers"] = fake_watchdog_observers
    sys.modules["watchdog.events"] = fake_watchdog_events


class TestAppMain(unittest.TestCase):
    def test_root_endpoint_returns_expected_shape(self):
        with patch("core.embeddings.embedder.SentenceTransformer"), patch(
            "core.indexing.index_builder.IndexBuilder.load_or_create_index"
        ):
            from app.main import app

        client = TestClient(app)
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("message", payload)
        self.assertIn("watch_paths", payload)
        self.assertEqual(payload["docs"], "/docs")

    def test_shutdown_event_stops_file_watcher_when_present(self):
        with patch("core.embeddings.embedder.SentenceTransformer"), patch(
            "core.indexing.index_builder.IndexBuilder.load_or_create_index"
        ):
            import app.main as main_module

        class _Watcher:
            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        watcher = _Watcher()
        main_module._file_watcher = watcher

        import asyncio

        asyncio.run(main_module.shutdown_event())
        self.assertTrue(watcher.stopped)


if __name__ == "__main__":
    unittest.main()

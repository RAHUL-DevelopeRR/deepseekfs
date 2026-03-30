import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


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

"""Tests for the persistent ResponseCache."""
import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestResponseCache:
    """Test ResponseCache CRUD and eviction."""

    def _make_cache(self, max_size=10):
        from services.cache import ResponseCache
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        return ResponseCache(db_path=path, max_size=max_size), path

    def test_put_and_get(self):
        cache, _ = self._make_cache()
        cache.put("hello", "world")
        assert cache.get("hello") == "world"

    def test_miss_returns_none(self):
        cache, _ = self._make_cache()
        assert cache.get("nonexistent") is None

    def test_overwrite(self):
        cache, _ = self._make_cache()
        cache.put("key", "value1")
        cache.put("key", "value2")
        assert cache.get("key") == "value2"

    def test_eviction(self):
        cache, _ = self._make_cache(max_size=3)
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        cache.put("d", "4")  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == "4"

    def test_stats(self):
        cache, _ = self._make_cache()
        cache.put("x", "y")
        cache.get("x")       # hit
        cache.get("missing")  # miss
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_clear(self):
        cache, _ = self._make_cache()
        cache.put("a", "1")
        cache.put("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.stats()["entries"] == 0

    def test_persistence(self):
        """Cache survives across instances pointing at same DB."""
        from services.cache import ResponseCache
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        c1 = ResponseCache(db_path=path)
        c1.put("persistent", "data")
        c1.close()

        c2 = ResponseCache(db_path=path)
        assert c2.get("persistent") == "data"
        c2.close()

    def test_unicode(self):
        cache, _ = self._make_cache()
        cache.put("こんにちは", "Hello in Japanese")
        assert cache.get("こんにちは") == "Hello in Japanese"

    def test_long_response(self):
        cache, _ = self._make_cache()
        long_text = "x" * 10000
        cache.put("long", long_text)
        assert cache.get("long") == long_text

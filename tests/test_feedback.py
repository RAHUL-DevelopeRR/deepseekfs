"""Tests for the RLHF Feedback System."""
import sys
import os
import json
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestFeedbackTypes:
    """Test FeedbackEntry and Rating."""

    def test_rating_values(self):
        from services.feedback.types import Rating
        assert int(Rating.POSITIVE) == 1
        assert int(Rating.NEGATIVE) == -1

    def test_entry_creation(self):
        from services.feedback.types import FeedbackEntry, Rating
        entry = FeedbackEntry(
            query="hello",
            response="hi there",
            mode="chat",
            rating=Rating.POSITIVE,
        )
        assert entry.query == "hello"
        assert entry.rating == Rating.POSITIVE
        assert len(entry.id) == 12

    def test_entry_immutable(self):
        from services.feedback.types import FeedbackEntry, Rating
        entry = FeedbackEntry(
            query="test", response="resp", mode="chat", rating=Rating.POSITIVE
        )
        with pytest.raises(AttributeError):
            entry.query = "modified"

    def test_entry_to_dict(self):
        from services.feedback.types import FeedbackEntry, Rating
        entry = FeedbackEntry(
            query="hi", response="hello", mode="chat", rating=Rating.POSITIVE
        )
        d = entry.to_dict()
        assert d["query"] == "hi"
        assert d["rating"] == 1
        assert "id" in d

    def test_entry_from_row(self):
        from services.feedback.types import FeedbackEntry, Rating
        row = {
            "id": "abc123def456",
            "timestamp": 1234567890.0,
            "query": "test query",
            "response": "test response",
            "mode": "chat",
            "rating": -1,
            "intent": "chat",
            "confidence": 0.85,
            "correction": None,
            "model": "SmolLM3-3B",
        }
        entry = FeedbackEntry.from_row(row)
        assert entry.rating == Rating.NEGATIVE
        assert entry.intent == "chat"

    def test_training_pair(self):
        from services.feedback.types import FeedbackEntry, Rating
        entry = FeedbackEntry(
            query="hi", response="hello", mode="chat", rating=Rating.POSITIVE
        )
        pair = entry.to_training_pair()
        assert len(pair["messages"]) == 2
        assert pair["messages"][0]["role"] == "user"
        assert pair["messages"][1]["role"] == "assistant"

    def test_training_pair_with_correction(self):
        from services.feedback.types import FeedbackEntry, Rating
        entry = FeedbackEntry(
            query="hi",
            response="bad response",
            mode="chat",
            rating=Rating.NEGATIVE,
            correction="good response",
        )
        pair = entry.to_training_pair()
        assert pair["messages"][1]["content"] == "good response"


class TestFeedbackStore:
    """Test SQLite-backed FeedbackStore."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from services.feedback.store import FeedbackStore
        self.db_path = tmp_path / "test_feedback.db"
        self.store = FeedbackStore(db_path=self.db_path)

    def test_record_positive(self):
        from services.feedback.types import Rating
        entry = self.store.record(
            query="hello", response="hi", rating=Rating.POSITIVE, mode="chat"
        )
        assert entry.rating == Rating.POSITIVE

    def test_record_negative(self):
        from services.feedback.types import Rating
        entry = self.store.record(
            query="bad query", response="bad", rating=Rating.NEGATIVE, mode="action"
        )
        assert entry.rating == Rating.NEGATIVE

    def test_stats(self):
        from services.feedback.types import Rating
        self.store.record(query="q1", response="r1", rating=Rating.POSITIVE, mode="chat")
        self.store.record(query="q2", response="r2", rating=Rating.POSITIVE, mode="chat")
        self.store.record(query="q3", response="r3", rating=Rating.NEGATIVE, mode="chat")

        stats = self.store.get_stats()
        assert stats["total"] == 3
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert stats["positive_rate"] == 66.7

    def test_negative_queries(self):
        from services.feedback.types import Rating
        self.store.record(query="bad", response="r", rating=Rating.NEGATIVE, mode="chat")
        self.store.record(query="good", response="r", rating=Rating.POSITIVE, mode="chat")

        negatives = self.store.get_negative_queries()
        assert "bad" in negatives
        assert "good" not in negatives

    def test_export_jsonl(self, tmp_path):
        from services.feedback.types import Rating
        self.store.record(query="q1", response="r1", rating=Rating.POSITIVE, mode="chat")
        self.store.record(query="q2", response="r2", rating=Rating.NEGATIVE, mode="action")

        output = tmp_path / "export.jsonl"
        count = self.store.export_jsonl(output)
        assert count == 2

        with open(output) as f:
            lines = f.readlines()
        assert len(lines) == 2
        data = json.loads(lines[0])
        assert "messages" in data

    def test_export_positive_only(self, tmp_path):
        from services.feedback.types import Rating
        self.store.record(query="q1", response="r1", rating=Rating.POSITIVE, mode="chat")
        self.store.record(query="q2", response="r2", rating=Rating.NEGATIVE, mode="chat")

        output = tmp_path / "positive.jsonl"
        count = self.store.export_jsonl(output, positive_only=True)
        assert count == 1

    def test_get_entries(self):
        from services.feedback.types import Rating
        self.store.record(query="q1", response="r1", rating=Rating.POSITIVE, mode="chat")
        self.store.record(query="q2", response="r2", rating=Rating.NEGATIVE, mode="chat")

        all_entries = self.store.get_entries()
        assert len(all_entries) == 2

        positive = self.store.get_entries(rating=Rating.POSITIVE)
        assert len(positive) == 1
        assert positive[0].query == "q1"

    def test_db_persists(self, tmp_path):
        """Store survives restart."""
        from services.feedback.store import FeedbackStore
        from services.feedback.types import Rating

        db = tmp_path / "persist.db"
        store1 = FeedbackStore(db_path=db)
        store1.record(query="q", response="r", rating=Rating.POSITIVE, mode="chat")

        # New instance, same db
        store2 = FeedbackStore(db_path=db)
        stats = store2.get_stats()
        assert stats["total"] == 1

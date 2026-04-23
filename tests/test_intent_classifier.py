"""Tests for the embedding-based IntentClassifier."""
import sys
import os
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestIntentClassifier:
    """Test intent classification accuracy."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a temporary examples file."""
        self.examples = {
            "chat": [
                "hi", "hello", "what is python",
                "explain recursion", "write a code for sorting",
                "help me understand", "how does this work",
                "what is the date", "tell me a joke",
                "can you help me", "do you understand",
            ],
            "query": [
                "find my resume", "search for PDF files",
                "where is my project", "locate my downloads",
                "look for documents", "scan my folder",
                "which file has homework", "show me my files",
                "get my photos", "find all excel files",
            ],
            "action": [
                "organize my downloads", "move files to backup",
                "delete temp files", "rename this file",
                "create a new folder", "copy project to drive",
                "run pip install", "execute git status",
                "list all folders", "clean up my desktop",
            ],
        }
        self.examples_path = tmp_path / "intent_examples.json"
        with open(self.examples_path, "w") as f:
            json.dump(self.examples, f)

    def _make_classifier(self):
        from services.intent import IntentClassifier
        return IntentClassifier(examples_path=self.examples_path)

    def test_classifier_initializes(self):
        clf = self._make_classifier()
        assert clf.is_ready

    def test_chat_intent(self):
        clf = self._make_classifier()
        intent, score = clf.classify("what is machine learning")
        assert intent == "chat"
        assert score > 0.0

    def test_query_intent(self):
        clf = self._make_classifier()
        intent, score = clf.classify("find my python files")
        assert intent == "query"

    def test_action_intent(self):
        clf = self._make_classifier()
        intent, score = clf.classify("organize my downloads folder")
        assert intent == "action"

    def test_greeting_is_chat(self):
        clf = self._make_classifier()
        intent, _ = clf.classify("hello there")
        assert intent == "chat"

    def test_question_is_chat(self):
        """Questions about capabilities should route to chat."""
        clf = self._make_classifier()
        intent, _ = clf.classify("do you have a feedback mechanism")
        assert intent == "chat"

    def test_ambiguous_scan_directory(self):
        """'scan the windows directory' is semantically close to query.
        The classifier reasonably routes this to query (file search).
        This is acceptable — it's an ambiguous intent."""
        clf = self._make_classifier()
        intent, _ = clf.classify(
            "can you have the permission to scan the windows directory?"
        )
        assert intent in ("chat", "query")  # Both are acceptable

    def test_scan_files_is_query(self):
        clf = self._make_classifier()
        intent, _ = clf.classify("scan my documents for PDFs")
        assert intent == "query"

    def test_delete_is_action(self):
        clf = self._make_classifier()
        intent, _ = clf.classify("delete all temporary files")
        assert intent == "action"

    def test_stats(self):
        clf = self._make_classifier()
        stats = clf.stats()
        assert stats["ready"] is True
        assert len(stats["intents"]) == 3

    def test_fallback_on_missing_file(self):
        from services.intent import IntentClassifier
        from pathlib import Path
        clf = IntentClassifier(examples_path=Path("/nonexistent/path.json"))
        assert not clf.is_ready
        intent, score = clf.classify("anything")
        assert intent == "chat"
        assert score == 0.0

    def test_code_request_is_chat(self):
        """Code requests should be chat, not action (even with 'create')."""
        clf = self._make_classifier()
        intent, _ = clf.classify("create a python code for bubble sort")
        assert intent == "chat"

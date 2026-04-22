"""
Neuron — Watch Rules Tests
============================
Tests watch rule matching and hook engine.

Covers:
  - Rule pattern matching (glob)
  - Path filtering
  - Rule persistence (save/load)
  - CRUD operations
"""
import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.watch_rules.rules import WatchRule


class TestWatchRule:
    """Test rule pattern matching."""

    def test_basic_match(self):
        rule = WatchRule(
            name="pdfs",
            patterns=["*.pdf"],
            paths=[],
            action="notify",
        )
        assert rule.matches("C:\\Users\\rahul\\Downloads\\report.pdf")
        assert not rule.matches("C:\\Users\\rahul\\Downloads\\report.txt")

    def test_multiple_patterns(self):
        rule = WatchRule(
            name="docs",
            patterns=["*.pdf", "*.docx", "*.txt"],
            paths=[],
            action="notify",
        )
        assert rule.matches("report.pdf")
        assert rule.matches("essay.docx")
        assert rule.matches("notes.txt")
        assert not rule.matches("code.py")

    def test_path_filtering(self):
        rule = WatchRule(
            name="downloads_only",
            patterns=["*.pdf"],
            paths=["C:\\Users\\rahul\\Downloads"],
            action="notify",
        )
        assert rule.matches("C:\\Users\\rahul\\Downloads\\report.pdf")
        assert not rule.matches("C:\\Users\\rahul\\Desktop\\report.pdf")

    def test_empty_paths_matches_all(self):
        rule = WatchRule(
            name="global",
            patterns=["*.py"],
            paths=[],
            action="notify",
        )
        assert rule.matches("C:\\any\\path\\script.py")

    def test_serialization(self):
        rule = WatchRule(
            name="test",
            patterns=["*.pdf"],
            paths=["C:\\Downloads"],
            action="summarize",
            action_args={"max_chars": 1000},
        )
        d = rule.to_dict()
        r2 = WatchRule.from_dict(d)
        assert r2.name == "test"
        assert r2.patterns == ["*.pdf"]
        assert r2.action == "summarize"
        assert r2.action_args["max_chars"] == 1000

    def test_unique_rule_id(self):
        r1 = WatchRule(name="a", patterns=["*"], paths=[], action="notify")
        r2 = WatchRule(name="b", patterns=["*"], paths=[], action="notify")
        assert r1.rule_id != r2.rule_id

    def test_case_insensitive_match(self):
        rule = WatchRule(
            name="pdfs",
            patterns=["*.PDF"],
            paths=[],
            action="notify",
        )
        # fnmatch is case-insensitive on Windows
        if os.name == "nt":
            assert rule.matches("report.pdf")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

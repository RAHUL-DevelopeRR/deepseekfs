import json
import subprocess
import sys

import pytest

from neufs import _parse_tool_args


def test_parse_tool_args_accepts_repeatable_pairs():
    parsed = _parse_tool_args("{}", ["path=.", "max_items=5", "recursive=false"])

    assert parsed == {"path": ".", "max_items": 5, "recursive": False}


def test_parse_tool_args_merges_json_and_pairs(tmp_path):
    args_file = tmp_path / "args.json"
    args_file.write_text(json.dumps({"path": "old", "max_depth": 1}), encoding="utf-8")

    parsed = _parse_tool_args(f"@{args_file}", ["path=C:/tmp"])

    assert parsed == {"path": "C:/tmp", "max_depth": 1}


def test_parse_tool_args_rejects_bad_pair():
    with pytest.raises(ValueError, match="key=value"):
        _parse_tool_args("{}", ["path"])


def test_neufs_chat_smoke():
    result = subprocess.run(
        [sys.executable, "neufs.py", "chat", "hello", "--mode", "chat"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )

    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["ok"] is True
    assert payload["mode"] == "chat"
    assert payload["response"]


def test_neufs_chat_accepts_internet_flag():
    result = subprocess.run(
        [sys.executable, "neufs.py", "chat", "hello", "--mode", "chat", "--internet"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )

    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["ok"] is True
    assert payload["response"]


def test_neufs_summarize_folder(tmp_path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.md").write_text("bravo", encoding="utf-8")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "skip.js").write_text("skip", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "neufs.py", "summarize", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )

    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["ok"] is True
    assert "Folder summary" in payload["summary"]
    assert payload["data"]["files"] == 2
    assert payload["data"]["top_extensions"][".txt"] == 1


def test_neufs_doctor_reports_model_without_loading():
    result = subprocess.run(
        [sys.executable, "neufs.py", "doctor"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )

    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["ok"] is True
    assert "runtime" in payload
    assert "model_search_dirs" in payload
    assert payload["load_attempted"] is False

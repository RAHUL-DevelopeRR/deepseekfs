"""Real CLI smoke: chunk retrieval, grounded answer, update, and tool handoff."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pymupdf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", default="neufs.py", help="Source CLI or packaged neufs executable")
    args = parser.parse_args()
    cli = Path(args.cli).resolve()
    command = [sys.executable, str(cli)] if cli.suffix == ".py" else [str(cli)]

    with tempfile.TemporaryDirectory(prefix="neufs-usability-") as temporary:
        root = Path(temporary)
        documents = root / "documents"
        documents.mkdir()
        env = os.environ.copy()
        env.update(NEURON_STORAGE_DIR=str(root / "state"), HF_HUB_OFFLINE="1")
        report = documents / "quarterly_report.pdf"
        pdf = pymupdf.open()
        for page in range(1, 9):
            content = ("Q3 revenue was 987654 dollars, as approved by Finance."
                       if page == 8 else f"Operations and staffing notes for page {page}.")
            pdf.new_page().insert_text((72, 72), content)
        pdf.save(report)
        pdf.close()
        note = documents / "project_status.txt"
        note.write_text("The project status code is oldstatus73.", encoding="utf-8")

        timings = {}

        def run(name: str, *parts: str) -> dict:
            started = time.perf_counter()
            completed = subprocess.run(command + list(parts), env=env, text=True,
                                       capture_output=True, timeout=240, check=False)
            timings[name] = round(time.perf_counter() - started, 2)
            if completed.returncode:
                raise RuntimeError(f"{name} failed ({completed.returncode}): "
                                   f"{completed.stdout[-900:]} {completed.stderr[-900:]}")
            # The app logger can precede the CLI's JSON on stdout.
            output = completed.stdout
            start = output.rfind("\n{")
            return json.loads(output[start + 1:] if start >= 0 else output)

        status = run("status", "status")
        assert status["ok"] and status["model_path"], "Qwen model was not found"
        indexed = run("index", "index", str(documents))
        assert indexed["index_count"] >= 2
        found = run("search", "search", "Q3 revenue", "--limit", "5")
        assert any(item["path"] == str(report) and item.get("page") == 8
                   for item in found["results"]), "Page 8 was not retrieved"
        answered = run("query", "chat", "What was Q3 revenue?", "--mode", "query",
                       "--worker", "--offline")
        assert "987654" in answered["response"] and "Page 8" in answered["response"]
        tool = run("tool", "action", "--tool", "semantic_search", "--arg",
                   "query=Q3 revenue")
        observation = json.loads(tool["output"].split("Search results (untrusted data):\n", 1)[1])
        assert any(item["path"] == str(report) for item in observation), "Agent search lost the exact path"

        note.write_text("The project status code is newstatus84.", encoding="utf-8")
        run("reindex", "index", str(documents))
        updated = run("updated_search", "search", "newstatus84", "--limit", "5")
        note_hits = [item for item in updated["results"] if item["path"] == str(note)]
        assert note_hits and "newstatus84" in note_hits[0].get("text", "")
        assert "oldstatus73" not in note_hits[0].get("text", ""), "Old vector remains"

        print(json.dumps({"ok": True, "platform": platform.platform(),
                          "cli": str(cli), "indexed_files": indexed["index_count"],
                          "retrieved_pdf_page": 8, "answer": answered["response"],
                          "modified_file_refreshed": True, "agent_path_handoff": True,
                          "seconds": timings}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify that a packaged NeuCockpit can load and answer with local AI."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run(cli: Path, *args: str, storage: Path) -> dict:
    env = os.environ.copy()
    env.update(
        NEURON_STORAGE_DIR=str(storage),
        HF_HUB_OFFLINE="1",
        NEURON_LLM_THREADS="4",
        NEURON_LLM_BATCH="128",
    )
    result = subprocess.run(
        [str(cli), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=240,
        check=False,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        raise RuntimeError(
            f"{' '.join(args)} exited {result.returncode}: "
            f"{result.stdout[-1000:]} {result.stderr[-1000:]}"
        )
    start = result.stdout.rfind("\n{")
    payload = json.loads(result.stdout[start + 1 :] if start >= 0 else result.stdout)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    args = parser.parse_args()
    cli = args.cli.resolve()
    if not cli.is_file():
        raise FileNotFoundError(cli)

    # Windows can retain the worker's log handle briefly after the CLI exits.
    with tempfile.TemporaryDirectory(prefix="neucockpit-release-ai-", ignore_cleanup_errors=True) as tmp:
        storage = Path(tmp)
        started = time.perf_counter()
        status = _run(cli, "status", "--load-embeddings", storage=storage)
        embedding_seconds = round(time.perf_counter() - started, 3)
        if not (status.get("ok") and ':onnx-cls:' in str(status.get('embedding_backend'))):
            raise RuntimeError(f"Packaged BGE embeddings failed: {status}")
        if embedding_seconds > 30:
            raise RuntimeError(f"Packaged embedding startup too slow: {embedding_seconds}s")
        started = time.perf_counter()
        doctor = _run(cli, "doctor", "--load", storage=storage)
        qwen_seconds = round(time.perf_counter() - started, 3)
        if not (doctor.get("ok") and doctor.get("model_available") and doctor.get("loaded")):
            raise RuntimeError(f"Packaged model load failed: {doctor.get('load_error')}")
        startup_limit = 45 if platform.system() == "Darwin" else 30
        if qwen_seconds > startup_limit:
            raise RuntimeError(f"Packaged Qwen startup too slow: {qwen_seconds}s (limit {startup_limit}s)")

        answer = _run(
            cli,
            "chat",
            "--offline",
            "--worker",
            "--stream",
            "Reply with exactly: AI MODE OK",
            storage=storage,
        )
        response = str(answer.get("response", "")).strip()
        if not answer.get("ok") or "AI MODE OK" not in response.upper():
            raise RuntimeError(f"Packaged AI answer failed: {response!r}")
        if answer.get('first_token_seconds') is None or answer.get('token_events', 0) < 1:
            raise RuntimeError('Packaged streaming emitted no tokens')

        documents = storage / "documents"
        documents.mkdir()
        (documents / "release-proof.txt").write_text("Synthetic release test", encoding="utf-8")
        action = _run(cli, "chat", "--offline", "--worker", "--mode", "action",
                      f"List the files in this folder: {documents}", storage=storage)
        with sqlite3.connect(storage / "events.db") as conn:
            tool_used = conn.execute(
                "SELECT 1 FROM events WHERE event_type='tool_result' "
                "AND tool_name='folder_list' AND status='success' LIMIT 1"
            ).fetchone()
            completed = conn.execute(
                "SELECT 1 FROM events WHERE event_type='task_completed' LIMIT 1"
            ).fetchone()
        if not tool_used or not completed or str(action.get("response", "")).startswith("Task failed:"):
            raise RuntimeError(f"Packaged model-driven Action failed: {action}")

    print(json.dumps({"ok": True, "cli": str(cli), "model_loaded": True, "embedding_backend": status['embedding_backend'], "embedding_seconds": embedding_seconds, "qwen_seconds": qwen_seconds, "qwen_startup_limit_seconds": startup_limit, "streaming": True, "first_token_seconds": answer['first_token_seconds'], "response": response, "action_tool": "folder_list"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

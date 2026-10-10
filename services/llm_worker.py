"""Isolated local LLM worker.

The desktop process talks to this module over a tiny JSON-lines protocol.
That keeps llama.cpp native crashes, RAM spikes, and long generations outside
the Qt process. Source runs execute it with ``python -m services.llm_worker``;
frozen builds execute ``Neuron.exe --llm-worker``.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def _handle(engine, command: str, payload: dict[str, Any]) -> Any:
    if command == "status":
        return {
            "loaded": bool(engine.is_loaded),
            "load_error": engine.load_error,
            "model_path": getattr(engine, "_model_path", None),
        }
    if command == "load":
        return {
            "loaded": bool(engine.load_model(allow_download=bool(payload.get("allow_download", False)))),
            "load_error": engine.load_error,
            "model_path": getattr(engine, "_model_path", None),
        }
    if command == "unload":
        engine.unload()
        return {"loaded": False}
    if command == "generate":
        return engine.generate(**payload)
    if command == "chat":
        return engine.chat(**payload)
    if command == "chat_with_tools":
        return engine.chat_with_tools(**payload)
    if command == "summarize_file":
        return engine.summarize_file(**payload)
    if command == "ask_about_files":
        return engine.ask_about_files(**payload)
    if command == "suggest_tags":
        return engine.suggest_tags(**payload)
    raise ValueError(f"Unknown worker command: {command}")


def main() -> int:
    os.environ["NEURON_LLM_WORKER_PROCESS"] = "1"
    os.environ.setdefault("NEURON_LOG_STDERR", "1")
    os.environ.setdefault("NEURON_LLM_VERBOSE", "0")

    from app.logger import logger
    from services.llm_engine import LLMEngine

    logger.info("LLMWorker: process started")
    engine = LLMEngine()
    _write({"event": "ready", "ok": True})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            request_id = request.get("id")
            if str(request.get("command", "")) == "exit":
                engine.unload()
                _write({"id": request_id, "ok": True, "result": {"loaded": False}})
                return 0
            if str(request.get("command", "")) == "chat_stream":
                for token in engine.chat_stream(**(request.get("payload") or {})):
                    _write({"id": request_id, "ok": True, "event": "token", "token": token})
                _write({"id": request_id, "ok": True, "event": "done", "result": ""})
                continue
            if str(request.get("command", "")) == "generate_stream":
                for token in engine.generate_stream(**(request.get("payload") or {})):
                    _write({"id": request_id, "ok": True, "event": "token", "token": token})
                _write({"id": request_id, "ok": True, "event": "done", "result": ""})
                continue
            result = _handle(
                engine,
                str(request.get("command", "")),
                request.get("payload") or {},
            )
            _write({"id": request_id, "ok": True, "result": result})
        except SystemExit:
            raise
        except Exception as exc:
            logger.error(f"LLMWorker: request failed: {exc}")
            _write(
                {
                    "id": request.get("id") if isinstance(request, dict) else None,
                    "ok": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=6),
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

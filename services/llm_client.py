"""Client for the isolated local LLM worker."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from itertools import count
from pathlib import Path
from typing import Any, Iterator, Optional

from app.logger import logger
from services.llm_engine import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from services.model_health import format_ai_unavailable, normalize_model_error


class LLMWorkerClient:
    """Drop-in LLMEngine facade backed by a supervised subprocess.

    The API intentionally mirrors ``LLMEngine`` for callers that already use
    ``generate``, ``chat``, ``chat_with_tools`` and summarization helpers.
    Calls are serialized through a lock because the worker owns one model.
    """

    def __init__(self, command: Optional[list[str]] = None, cwd: Optional[str] = None):
        self._command = command
        self._cwd = cwd or str(Path(__file__).resolve().parent.parent)
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._ids = count(1)
        self._loaded = False
        self._load_error: str | None = None
        self._stderr_thread: threading.Thread | None = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def cache_size(self) -> int:
        return 0

    def _build_command(self) -> list[str]:
        if self._command:
            return list(self._command)
        if getattr(sys, "frozen", False):
            worker_name = "NeuronLLMWorker.exe" if os.name == "nt" else "NeuronLLMWorker"
            sibling = Path(sys.executable).with_name(worker_name)
            if sibling.exists():
                return [str(sibling)]
            return [sys.executable, "--llm-worker"]
        return [sys.executable, "-m", "services.llm_worker"]

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return

        env = os.environ.copy()
        env["NEURON_LLM_WORKER_PROCESS"] = "1"
        env.setdefault("NEURON_LOG_STDERR", "1")
        env.setdefault("NEURON_LLM_VERBOSE", "0")
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        cmd = self._build_command()
        logger.info(f"LLMWorkerClient: starting worker: {cmd}")
        self._process = subprocess.Popen(
            cmd,
            cwd=self._cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name="llm-worker-stderr",
            daemon=True,
        )
        self._stderr_thread.start()

        try:
            ready = self._read_response(expect_event=True, timeout_s=20)
            if not ready.get("ok"):
                raise RuntimeError(f"LLM worker did not start: {ready}")
        except Exception:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass
            raise

    def _drain_stderr(self) -> None:
        proc = self._process
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                logger.info(f"LLMWorker: {line}")

    def _read_response(self, expect_event: bool = False, timeout_s: float = 120) -> dict[str, Any]:
        proc = self._process
        if proc is None or proc.stdout is None:
            raise RuntimeError("LLM worker is not running")

        # ``readline`` is blocking; the worker is only used from background
        # inference paths, and the timeout is enforced by the worker lifetime
        # checks around EOF/crash.
        while True:
            if proc.poll() is not None:
                raise RuntimeError(
                    normalize_model_error(f"LLM worker exited with code {proc.returncode}")
                )
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("LLM worker closed stdout")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.info(f"LLMWorker stdout: {line.rstrip()}")
                continue
            if expect_event and payload.get("event") != "ready":
                continue
            return payload

    def _request(self, command: str, payload: dict[str, Any] | None = None) -> Any:
        with self._lock:
            try:
                self._start()
                proc = self._process
                if proc is None or proc.stdin is None:
                    raise RuntimeError("LLM worker stdin unavailable")
                request_id = next(self._ids)
                proc.stdin.write(
                    json.dumps(
                        {"id": request_id, "command": command, "payload": payload or {}},
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
                proc.stdin.flush()

                while True:
                    response = self._read_response()
                    if response.get("id") != request_id:
                        continue
                    if not response.get("ok"):
                        raise RuntimeError(response.get("error", "worker request failed"))
                    return response.get("result")
            except Exception as exc:
                self._loaded = False
                self._load_error = normalize_model_error(exc)
                logger.error(f"LLMWorkerClient: {command} failed: {self._load_error}")
                return None

    def _stream_request(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        with self._lock:
            try:
                self._start()
                proc = self._process
                if proc is None or proc.stdin is None:
                    raise RuntimeError("LLM worker stdin unavailable")
                request_id = next(self._ids)
                proc.stdin.write(
                    json.dumps(
                        {"id": request_id, "command": command, "payload": payload or {}},
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
                proc.stdin.flush()

                while True:
                    response = self._read_response()
                    if response.get("id") != request_id:
                        continue
                    if not response.get("ok"):
                        raise RuntimeError(response.get("error", "worker stream failed"))
                    event = response.get("event")
                    if event == "token":
                        yield str(response.get("token", ""))
                    elif event == "done":
                        return
                    else:
                        result = response.get("result")
                        if isinstance(result, str):
                            yield result
                        return
            except Exception as exc:
                self._loaded = False
                self._load_error = normalize_model_error(exc)
                logger.error(f"LLMWorkerClient: {command} failed: {self._load_error}")
                yield format_ai_unavailable(self._load_error)

    def load_model(self, progress_cb=None, allow_download: bool = False) -> bool:
        result = self._request("load", {"allow_download": allow_download})
        if isinstance(result, dict):
            self._loaded = bool(result.get("loaded"))
            self._load_error = normalize_model_error(result.get("load_error")) if result.get("load_error") else None
        else:
            self._loaded = False
        if progress_cb and self._loaded:
            progress_cb(1.0, "Model ready")
        return self._loaded

    def unload(self) -> None:
        proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                self._request("exit")
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._loaded = False

    def cancel(self) -> None:
        """Terminate an in-flight worker request without waiting on the client lock."""
        proc = self._process
        if proc is not None and proc.poll() is None:
            logger.warning("LLMWorkerClient: cancelling worker process")
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._process = None
        self._loaded = False

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        stop: Optional[list[str]] = None,
    ) -> str:
        result = self._request(
            "generate",
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stop": stop,
            },
        )
        return result if isinstance(result, str) else format_ai_unavailable(self._load_error)

    def generate_stream(self, *args, **kwargs) -> Iterator[str]:
        prompt = args[0] if args else kwargs.get("prompt", "")
        system = kwargs.get("system", args[1] if len(args) > 1 else "")
        max_tokens = kwargs.get("max_tokens", DEFAULT_MAX_TOKENS)
        temperature = kwargs.get("temperature", DEFAULT_TEMPERATURE)
        yield from self._stream_request(
            "generate_stream",
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        tools_description: str = "",
    ) -> str:
        result = self._request(
            "chat",
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "tools_description": tools_description,
            },
        )
        return result if isinstance(result, str) else format_ai_unavailable(self._load_error)

    def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> Iterator[str]:
        yield from self._stream_request(
            "chat_stream",
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> dict:
        result = self._request(
            "chat_with_tools",
            {
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        return result if isinstance(result, dict) else {"content": format_ai_unavailable(self._load_error)}

    def summarize_file(self, path: str) -> str:
        result = self._request("summarize_file", {"path": path})
        return result if isinstance(result, str) else "AI summary unavailable."

    def ask_about_files(self, question: str, file_contexts: list[dict]) -> str:
        result = self._request(
            "ask_about_files",
            {"question": question, "file_contexts": file_contexts},
        )
        return result if isinstance(result, str) else "AI could not generate a response."

    def suggest_tags(self, path: str) -> list[str]:
        result = self._request("suggest_tags", {"path": path})
        return result if isinstance(result, list) else []

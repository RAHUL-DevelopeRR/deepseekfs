"""Persistent hidden PowerShell session for supervised local actions."""
from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from app.logger import logger


_MAX_OUTPUT_CHARS = 16_000


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


class PowerShellSession:
    """One long-lived PowerShell process with command/response markers."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc and self._proc.poll() is None else None

    def start(self) -> None:
        if self._proc and self._proc.poll() is None:
            return

        exe = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
        if not exe:
            raise RuntimeError("PowerShell executable was not found on PATH")

        self._proc = subprocess.Popen(
            [
                exe,
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=_creation_flags(),
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True, name="neuron-powershell-reader")
        self._reader.start()
        logger.info(f"PowerShellSession: started pid={self._proc.pid}")
        self._wait_until_ready()

    def _wait_until_ready(self) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return
        marker = f"__NEURON_PS_READY_{uuid.uuid4().hex}__"
        try:
            proc.stdin.write(f"Write-Output '{marker}'\n")
            proc.stdin.flush()
        except Exception as exc:
            logger.warning(f"PowerShellSession: ready probe failed: {exc}")
            return

        deadline = time.time() + 8
        while time.time() < deadline:
            if proc.poll() is not None:
                logger.warning("PowerShellSession: process exited during ready probe")
                return
            try:
                line = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if marker in line:
                return
        logger.warning("PowerShellSession: ready probe timed out; continuing")

    def reset(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=2)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
            self._proc = None
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                self._queue.put(line)
        except Exception as exc:
            logger.warning(f"PowerShellSession: reader stopped: {exc}")

    def run(self, command: str, cwd: str = "", timeout: int = 30) -> tuple[bool, str]:
        command = (command or "").strip()
        if not command:
            return True, f"PowerShell session ready. pid={self.pid or 'not started'}"

        with self._lock:
            self.start()
            assert self._proc is not None and self._proc.stdin is not None

            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

            marker = f"__NEURON_PS_DONE_{uuid.uuid4().hex}__"
            cwd_script = ""
            if cwd and Path(cwd).exists():
                cwd_script = f"Set-Location -LiteralPath {_ps_quote(str(Path(cwd).resolve()))}\n"

            script = (
                "$ErrorActionPreference = 'Continue'\n"
                f"{cwd_script}"
                "$neuronExitCode = 0\n"
                "$global:LASTEXITCODE = $null\n"
                "try {\n"
                "  $neuronOutput = & {\n"
                f"{command}\n"
                "  } 2>&1 | Out-String -Width 240\n"
                "  if ($LASTEXITCODE -ne $null) { $neuronExitCode = $LASTEXITCODE }\n"
                "  Write-Output $neuronOutput\n"
                "} catch {\n"
                "  $neuronExitCode = 1\n"
                "  Write-Output ('[PowerShell error] ' + ($_ | Out-String))\n"
                "}\n"
                f"Write-Output ('{marker}:' + $neuronExitCode)\n"
            )

            self._proc.stdin.write(script + "\n")
            self._proc.stdin.flush()

            output: list[str] = []
            deadline = time.time() + max(1, int(timeout or 30))
            code = 0
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    return False, "PowerShell session exited unexpectedly."
                try:
                    line = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if marker in line:
                    tail = line.split(marker + ":", 1)[-1].strip()
                    try:
                        code = int(tail)
                    except ValueError:
                        code = 0
                    text = "".join(output).strip()[:_MAX_OUTPUT_CHARS]
                    return code == 0, text or "(command completed with no output)"
                output.append(line)

            return False, f"PowerShell command timed out after {timeout}s:\n{command}"


_session: PowerShellSession | None = None
_session_lock = threading.Lock()


def get_powershell_session() -> PowerShellSession:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = PowerShellSession()
    return _session

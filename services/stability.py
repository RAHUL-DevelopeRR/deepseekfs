"""Runtime stability diagnostics for the desktop app."""
from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
from pathlib import Path

from app.config import STORAGE_DIR
from app.logger import logger


class UiHangWatchdog:
    """Dump thread stacks when the Qt event loop stops ticking.

    This does not fix hangs by itself. It turns "the app froze" into a concrete
    stack trace in storage/logs/ui_hang_dump.log so the blocking subsystem can
    be isolated.
    """

    def __init__(self, interval_ms: int = 1000, threshold_s: float = 8.0):
        self.interval_ms = interval_ms
        self.threshold_s = threshold_s
        self._last_beat = time.monotonic()
        self._last_dump = 0.0
        self._stop = threading.Event()
        self._timer = None

    def start(self) -> None:
        from PyQt6.QtCore import QTimer

        self._timer = QTimer()
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self.beat)
        self._timer.start()

        thread = threading.Thread(
            target=self._watch,
            name="Neuron-UiHangWatchdog",
            daemon=True,
        )
        thread.start()
        logger.info(
            f"Stability: UI hang watchdog started "
            f"(threshold={self.threshold_s:.1f}s)"
        )

    def stop(self) -> None:
        self._stop.set()
        if self._timer is not None:
            self._timer.stop()

    def beat(self) -> None:
        self._last_beat = time.monotonic()

    def _watch(self) -> None:
        while not self._stop.wait(1.0):
            now = time.monotonic()
            stalled_for = now - self._last_beat
            if stalled_for < self.threshold_s:
                continue
            if now - self._last_dump < self.threshold_s:
                continue
            self._last_dump = now
            self._dump(stalled_for)

    def _dump(self, stalled_for: float) -> None:
        log_dir = STORAGE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        dump_path = log_dir / "ui_hang_dump.log"
        try:
            with dump_path.open("a", encoding="utf-8") as fh:
                fh.write("\n" + "=" * 72 + "\n")
                fh.write(
                    f"UI heartbeat stalled for {stalled_for:.1f}s "
                    f"at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                faulthandler.dump_traceback(file=fh, all_threads=True)
            logger.warning(f"Stability: UI hang dump written to {dump_path}")
        except Exception as exc:
            logger.warning(f"Stability: failed to write UI hang dump: {exc}")


def install_crash_diagnostics() -> Path:
    """Enable faulthandler output for native crashes and fatal errors."""
    log_dir = STORAGE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    crash_path = log_dir / "native_crash_dump.log"

    try:
        handle = crash_path.open("a", encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)
        # Keep the handle reachable so faulthandler can write later.
        sys._neuron_fault_log_handle = handle  # type: ignore[attr-defined]
        logger.info(f"Stability: native crash diagnostics enabled at {crash_path}")
    except Exception as exc:
        logger.warning(f"Stability: faulthandler enable failed: {exc}")

    try:
        os.environ.setdefault("PYTHONFAULTHANDLER", "1")
    except Exception:
        pass
    return crash_path

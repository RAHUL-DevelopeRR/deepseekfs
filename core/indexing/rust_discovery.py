"""Optional adapter for the Rust file-discovery core.

Architecture
------------
The Rust binary ``neuron-index-core`` performs high-speed recursive file
discovery and emits one JSON object per line on stdout.  This Python module
invokes it via ``subprocess``, parses the output, and returns a list of dicts.

If the Rust binary is not built, callers should fall back to the pure-Python
discovery path in ``core.indexing.index_builder``.

Hardening (v5.2)
-----------------
* **Timeout** — 120 s default; prevents indefinite hangs on network drives or
  permission dialogs.
* **stderr logging** — warnings from the Rust side are forwarded to the Python
  logger instead of being silently swallowed.
* **Per-line JSON resilience** — one malformed line no longer kills the batch.
* **CalledProcessError** — exit-code failures surface with stderr context.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable, List

import app.config as config
from app.logger import logger

# Maximum seconds to wait for the Rust discovery binary.  Large repos on
# spinning disks can be slow, so 120 s is generous but not infinite.
_DEFAULT_TIMEOUT_SECONDS = 120


def _binary_path() -> Path:
    exe = "neuron-index-core.exe" if os.name == "nt" else "neuron-index-core"
    return config.BASE_DIR / "rust" / "index-core" / "target" / "release" / exe


def is_available() -> bool:
    """Return True when the compiled Rust helper exists on disk."""
    return _binary_path().is_file()


def discover_files(
    root: str,
    supported_extensions: Iterable[str] | None = None,
    *,
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
) -> List[dict]:
    """Discover indexable files with the Rust helper when it has been built.

    Parameters
    ----------
    root:
        Absolute path to the directory tree to scan.
    supported_extensions:
        File extensions to include (e.g. ``{".py", ".md"}``).  Defaults to
        ``config.SUPPORTED_EXTENSIONS``.
    timeout:
        Maximum wall-clock seconds before the subprocess is killed.

    Returns
    -------
    list[dict]
        Each dict has ``path``, ``size``, and ``extension`` keys.

    Raises
    ------
    FileNotFoundError
        If the Rust binary has not been compiled.
    TimeoutError
        If the binary does not finish within *timeout* seconds.
    RuntimeError
        If the binary exits with a non-zero status.
    """
    binary = _binary_path()
    if not binary.is_file():
        raise FileNotFoundError(f"Rust index helper not built: {binary}")

    extensions = supported_extensions or config.SUPPORTED_EXTENSIONS
    cmd = [
        str(binary),
        "discover",
        root,
        str(config.MAX_FILE_SIZE_BYTES),
        ",".join(sorted(extensions)),
        ",".join(sorted(config.SKIP_DIRS)),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Rust discovery timed out after {timeout}s on root: {root}"
        )

    # Forward any stderr as warnings — the Rust binary may log permission
    # errors or skipped paths there.
    if proc.stderr and proc.stderr.strip():
        for line in proc.stderr.strip().splitlines():
            logger.warning(f"rust_discovery stderr: {line}")

    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or "").strip()[:500]
        raise RuntimeError(
            f"Rust discovery exited with code {proc.returncode}: {stderr_snippet}"
        )

    # Parse each line individually — one bad line must not discard the batch.
    results: List[dict] = []
    for line_no, raw in enumerate(proc.stdout.splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            results.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            logger.warning(
                f"rust_discovery: skipping malformed JSON at line {line_no}: "
                f"{exc} — raw={raw[:120]!r}"
            )
    return results

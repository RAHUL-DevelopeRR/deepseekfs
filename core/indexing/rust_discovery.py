"""Optional adapter for the Rust file-discovery core."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

import app.config as config


def _binary_path() -> Path:
    exe = "neuron-index-core.exe" if os.name == "nt" else "neuron-index-core"
    return config.BASE_DIR / "rust" / "index-core" / "target" / "release" / exe


def is_available() -> bool:
    return _binary_path().is_file()


def discover_files(root: str, supported_extensions: Iterable[str] | None = None) -> list[dict]:
    """Discover indexable files with the Rust helper when it has been built."""
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
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

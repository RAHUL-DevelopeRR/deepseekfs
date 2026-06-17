"""Small cross-OS support layer for tools and packaging decisions."""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class PlatformProfile:
    system: str
    machine: str
    python: str
    home: str
    config_dir: str
    data_dir: str
    cache_dir: str
    hotkeys: str
    desktop_bundle: str
    mobile_bundle: str

    def to_dict(self) -> dict:
        return asdict(self)


def _windows_local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))


def get_platform_profile() -> PlatformProfile:
    system = platform.system() or sys.platform
    low = system.lower()
    home = Path.home()

    if low.startswith("win"):
        root = _windows_local_appdata() / "Neuron"
        hotkeys = "RegisterHotKey"
        desktop_bundle = "PyInstaller onedir or Tauri MSI/NSIS for Windows 10+"
    elif low == "darwin":
        root = home / "Library" / "Application Support" / "Neuron"
        hotkeys = "macOS event tap with Accessibility permission"
        desktop_bundle = "Tauri .app/.dmg with notarization"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "neuron"
        hotkeys = "X11/Wayland portal backend with user permission"
        desktop_bundle = "Tauri AppImage/deb/rpm"

    return PlatformProfile(
        system=system,
        machine=platform.machine(),
        python=platform.python_version(),
        home=str(home),
        config_dir=str(root / "config"),
        data_dir=str(root / "data"),
        cache_dir=str(root / "cache"),
        hotkeys=hotkeys,
        desktop_bundle=desktop_bundle,
        mobile_bundle="Android build should use a native mobile shell and on-device LLM provider",
    )


def is_windows_10_or_newer() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return sys.getwindowsversion().major >= 10
    except Exception:
        return False

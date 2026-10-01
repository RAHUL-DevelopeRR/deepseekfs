"""Cross-platform global hotkey management for the desktop shell.

Windows has first-class support through RegisterHotKey. Other desktop OSes
need platform-specific backends or accessibility permissions, so this module
fails closed there and lets the tray/menu remain the activation path.
"""
from __future__ import annotations

import ctypes
import platform
import time
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer

from app.logger import logger

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_SHIFT = 0x10
VK_CTRL = 0x11
VK_ALT = 0x12
VK_SPACE = 0x20
VK_N = 0x4E
VK_R = 0x52

PANEL_HOTKEY_ID = 0xBFFF
PANEL_FALLBACK_HOTKEY_ID = 0xBFFD
PANEL_SAFE_FALLBACK_HOTKEY_ID = 0xBFFC
PANEL_OS_SAFE_HOTKEY_ID = 0xBFFB
OVERLAY_HOTKEY_ID = 0xBFFE


@dataclass(frozen=True)
class HotkeySpec:
    """A single global hotkey registration."""

    hotkey_id: int
    name: str
    modifiers: int
    virtual_key: int
    modifier_keys: tuple[int, ...]
    label: str


PANEL_PRIMARY = HotkeySpec(
    hotkey_id=PANEL_HOTKEY_ID,
    name="panel.primary",
    modifiers=MOD_SHIFT | MOD_NOREPEAT,
    virtual_key=VK_SPACE,
    modifier_keys=(VK_SHIFT,),
    label="Shift+Space",
)

PANEL_FALLBACK = HotkeySpec(
    hotkey_id=PANEL_FALLBACK_HOTKEY_ID,
    name="panel.fallback",
    modifiers=MOD_CTRL | MOD_NOREPEAT,
    virtual_key=VK_SPACE,
    modifier_keys=(VK_CTRL,),
    label="Ctrl+Space",
)

PANEL_SAFE_FALLBACK = HotkeySpec(
    hotkey_id=PANEL_SAFE_FALLBACK_HOTKEY_ID,
    name="panel.safe_fallback",
    modifiers=MOD_CTRL | MOD_ALT | MOD_NOREPEAT,
    virtual_key=VK_SPACE,
    modifier_keys=(VK_CTRL, VK_ALT),
    label="Ctrl+Alt+Space",
)

PANEL_OS_SAFE_FALLBACK = HotkeySpec(
    hotkey_id=PANEL_OS_SAFE_HOTKEY_ID,
    name="panel.os_safe_fallback",
    modifiers=MOD_CTRL | MOD_ALT | MOD_NOREPEAT,
    virtual_key=VK_N,
    modifier_keys=(VK_CTRL, VK_ALT),
    label="Ctrl+Alt+N",
)

OVERLAY_PRIMARY = HotkeySpec(
    hotkey_id=OVERLAY_HOTKEY_ID,
    name="overlay.primary",
    modifiers=MOD_CTRL | MOD_SHIFT | MOD_NOREPEAT,
    virtual_key=VK_R,
    modifier_keys=(VK_CTRL, VK_SHIFT),
    label="Ctrl+Shift+R",
)

PANEL_HOTKEYS = (
    PANEL_PRIMARY,
    PANEL_FALLBACK,
    PANEL_SAFE_FALLBACK,
    PANEL_OS_SAFE_FALLBACK,
)

_HOTKEY_ALIASES = {
    "shift+space": PANEL_PRIMARY,
    "ctrl+space": PANEL_FALLBACK,
    "control+space": PANEL_FALLBACK,
    "ctrl+alt+space": PANEL_SAFE_FALLBACK,
    "control+alt+space": PANEL_SAFE_FALLBACK,
    "ctrl+alt+n": PANEL_OS_SAFE_FALLBACK,
    "control+alt+n": PANEL_OS_SAFE_FALLBACK,
}


def normalize_hotkey(value: str | None) -> str:
    """Normalize user-configured hotkey text to a stable config key."""
    if not value:
        return "shift+space"
    parts = (
        value.lower()
        .replace("control", "ctrl")
        .replace("-", "+")
        .replace(" ", "+")
        .split("+")
    )
    cleaned = [part for part in (p.strip() for p in parts) if part]
    order = {"ctrl": 0, "alt": 1, "shift": 2}
    modifiers = sorted([p for p in cleaned if p in order], key=lambda p: order[p])
    keys = [p for p in cleaned if p not in order]
    key = keys[-1] if keys else "space"
    normalized = "+".join([*modifiers, key])
    return normalized if normalized in _HOTKEY_ALIASES else "shift+space"


def get_hotkey_label(value: str | None) -> str:
    """Return a display label for a normalized or user-entered hotkey."""
    return _HOTKEY_ALIASES[normalize_hotkey(value)].label


def get_panel_hotkey_specs(value: str | None = None) -> tuple[HotkeySpec, ...]:
    """Return the selected panel hotkey plus the OS-safe fallback."""
    selected = _HOTKEY_ALIASES[normalize_hotkey(value)]
    if selected == PANEL_OS_SAFE_FALLBACK:
        return (PANEL_OS_SAFE_FALLBACK,)
    return (selected, PANEL_OS_SAFE_FALLBACK)


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_ulonglong),
        ("lParam", ctypes.c_longlong),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class _WindowsHotkeyFilter(QAbstractNativeEventFilter):
    """Debounced WM_HOTKEY bridge.

    RegisterHotKey can repeat while the key chord is held. A raw toggle on each
    event makes the panel show and immediately hide. This filter fires once per
    press and rearms only after the involved keys are released.
    """

    def __init__(
        self,
        spec: HotkeySpec,
        callback: Callable[[], None],
        debounce_ms: int = 350,
        release_guard_ms: int = 450,
    ):
        super().__init__()
        self._spec = spec
        self._callback = callback
        self._debounce_s = max(0.05, debounce_ms / 1000.0)
        self._release_guard_s = max(0.05, release_guard_ms / 1000.0)
        self._last_fire = 0.0
        self._blocked_until = 0.0
        self._armed = True
        self._rearm_scheduled = False
        self._received = 0
        self._ignored = 0

    def nativeEventFilter(self, event_type, message):
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
            if msg.message != WM_HOTKEY or msg.wParam != self._spec.hotkey_id:
                return False, 0

            now = time.monotonic()
            self._received += 1
            if (
                not self._armed
                or now < self._blocked_until
                or now - self._last_fire < self._debounce_s
            ):
                self._log_ignored(now)
                self._schedule_rearm()
                return True, 0

            self._armed = False
            self._last_fire = now
            logger.info(f"Hotkey: received {self._spec.label} (event #{self._received})")
            self._callback()
            self._schedule_rearm()
            return True, 0
        except Exception as exc:
            logger.warning(f"Hotkey: event filter failed for {self._spec.label}: {exc}")
            return False, 0

    def _schedule_rearm(self) -> None:
        if self._rearm_scheduled:
            return
        self._rearm_scheduled = True
        QTimer.singleShot(80, self._maybe_rearm)

    def _maybe_rearm(self) -> None:
        self._rearm_scheduled = False
        if self._keys_still_down():
            self._schedule_rearm()
            return
        self._armed = True
        self._blocked_until = max(
            self._blocked_until,
            time.monotonic() + self._release_guard_s,
        )

    def _log_ignored(self, now: float) -> None:
        self._ignored += 1
        if self._ignored <= 3 or self._ignored % 20 == 0:
            reason = "latched"
            if now < self._blocked_until:
                reason = "release guard"
            elif now - self._last_fire < self._debounce_s:
                reason = "debounce"
            logger.info(
                f"Hotkey: ignored repeat {self._spec.label} "
                f"({reason}, ignored #{self._ignored})"
            )

    def _keys_still_down(self) -> bool:
        try:
            user32 = ctypes.windll.user32
            keys = (self._spec.virtual_key, *self._spec.modifier_keys)
            return any(user32.GetAsyncKeyState(key) & 0x8000 for key in keys)
        except Exception:
            return False


class GlobalHotkeyManager:
    """Owns global hotkey lifetime for the Qt application."""

    def __init__(self, app):
        self._app = app
        self._filters: list[_WindowsHotkeyFilter] = []
        self._registered: list[HotkeySpec] = []
        self._system = platform.system()

    @property
    def supported(self) -> bool:
        return self._system == "Windows"

    @property
    def registered_labels(self) -> list[str]:
        return [spec.label for spec in self._registered]

    def register(self, spec: HotkeySpec, callback: Callable[[], None]) -> bool:
        if not self.supported:
            logger.warning(
                f"Hotkey: global shortcut {spec.label} unsupported on {self._system}; "
                "use tray/menu activation."
            )
            return False

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.UnregisterHotKey(None, spec.hotkey_id)
        ok = bool(user32.RegisterHotKey(None, spec.hotkey_id, spec.modifiers, spec.virtual_key))
        if not ok:
            error_code = ctypes.get_last_error()
            logger.warning(
                f"Hotkey: failed to register {spec.label} "
                f"(id={spec.hotkey_id}, error={error_code})"
            )
            return False

        event_filter = _WindowsHotkeyFilter(spec, callback)
        self._app.installNativeEventFilter(event_filter)
        self._filters.append(event_filter)
        self._registered.append(spec)
        logger.info(f"Hotkey: registered {spec.label}")
        return True

    def unregister_all(self) -> None:
        if self.supported:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            for spec, event_filter in zip(self._registered, self._filters):
                try:
                    user32.UnregisterHotKey(None, spec.hotkey_id)
                    self._app.removeNativeEventFilter(event_filter)
                    logger.info(f"Hotkey: unregistered {spec.label}")
                except Exception as exc:
                    logger.warning(f"Hotkey: unregister failed for {spec.label}: {exc}")
        self._registered.clear()
        self._filters.clear()

"""Tests for global hotkey registration policy."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class DummyApp:
    def installNativeEventFilter(self, _event_filter):
        raise AssertionError("unsupported platforms should not install filters")


def test_hotkey_specs_have_distinct_ids():
    from ui.hotkeys import (
        MOD_NOREPEAT,
        OVERLAY_PRIMARY,
        PANEL_FALLBACK,
        PANEL_HOTKEYS,
        PANEL_OS_SAFE_FALLBACK,
        PANEL_PRIMARY,
        PANEL_SAFE_FALLBACK,
    )

    ids = {
        PANEL_PRIMARY.hotkey_id,
        PANEL_FALLBACK.hotkey_id,
        PANEL_SAFE_FALLBACK.hotkey_id,
        PANEL_OS_SAFE_FALLBACK.hotkey_id,
        OVERLAY_PRIMARY.hotkey_id,
    }

    assert len(ids) == 5
    assert PANEL_PRIMARY.label == "Shift+Space"
    assert PANEL_FALLBACK.label == "Ctrl+Space"
    assert PANEL_SAFE_FALLBACK.label == "Ctrl+Alt+Space"
    assert PANEL_OS_SAFE_FALLBACK.label == "Ctrl+Alt+N"
    assert PANEL_HOTKEYS == (
        PANEL_PRIMARY,
        PANEL_FALLBACK,
        PANEL_SAFE_FALLBACK,
        PANEL_OS_SAFE_FALLBACK,
    )
    assert all(spec.modifiers & MOD_NOREPEAT for spec in [*PANEL_HOTKEYS, OVERLAY_PRIMARY])


def test_global_hotkey_manager_fails_closed_on_unsupported_os(monkeypatch):
    import ui.hotkeys as hotkeys

    monkeypatch.setattr(hotkeys.platform, "system", lambda: "Linux")

    manager = hotkeys.GlobalHotkeyManager(DummyApp())
    assert manager.supported is False
    assert manager.register(hotkeys.PANEL_PRIMARY, lambda: None) is False
    assert manager.registered_labels == []


def test_hotkey_config_defaults_to_shift_space_with_safe_fallback():
    from ui.hotkeys import (
        PANEL_OS_SAFE_FALLBACK,
        PANEL_PRIMARY,
        get_hotkey_label,
        get_panel_hotkey_specs,
        normalize_hotkey,
    )

    assert normalize_hotkey("") == "shift+space"
    assert normalize_hotkey("Shift Space") == "shift+space"
    assert normalize_hotkey("control+alt+n") == "ctrl+alt+n"
    assert get_hotkey_label("shift+space") == "Shift+Space"
    assert get_panel_hotkey_specs("shift+space") == (
        PANEL_PRIMARY,
        PANEL_OS_SAFE_FALLBACK,
    )


def test_hotkey_config_uses_selected_shortcut_first():
    from ui.hotkeys import PANEL_FALLBACK, PANEL_OS_SAFE_FALLBACK, get_panel_hotkey_specs

    assert get_panel_hotkey_specs("ctrl+space") == (
        PANEL_FALLBACK,
        PANEL_OS_SAFE_FALLBACK,
    )
    assert get_panel_hotkey_specs("ctrl+alt+n") == (PANEL_OS_SAFE_FALLBACK,)


def test_local_shift_space_is_reserved_for_panel_toggle():
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent
    from ui.spotlight_panel import SpotlightPanel

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ShiftModifier,
    )

    assert SpotlightPanel._is_shift_space_event(event)

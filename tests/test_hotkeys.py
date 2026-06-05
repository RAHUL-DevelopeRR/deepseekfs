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

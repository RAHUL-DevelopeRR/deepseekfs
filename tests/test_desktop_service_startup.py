import sys
from types import ModuleType


def _install_fake_watcher(monkeypatch, events):
    fake_mod = ModuleType("core.watcher.file_watcher")

    class FakeFileWatcher:
        def __init__(self, index):
            self.index = index

        def start(self):
            events.append("watch")

    fake_mod.FileWatcher = FakeFileWatcher
    monkeypatch.setitem(sys.modules, "core.watcher.file_watcher", fake_mod)


def test_empty_index_starts_maintenance_scan_even_when_config_disabled(monkeypatch):
    import services.desktop_service as desktop_service
    from services.desktop_service import DesktopService

    events = []
    _install_fake_watcher(monkeypatch, events)
    monkeypatch.setenv("NEURON_STARTUP_INDEX_DELAY", "0")
    monkeypatch.setattr(
        desktop_service.UserConfig,
        "load",
        lambda: {"auto_index_on_launch": False},
    )

    class FakeStartupIndexer:
        def run_synchronously(self):
            events.append("index")

    monkeypatch.setattr(desktop_service, "StartupIndexer", FakeStartupIndexer)

    svc = DesktopService.__new__(DesktopService)
    svc._idx = object()
    svc.watcher = None
    svc.total_indexed = lambda: 0

    svc._maintenance_init()

    assert events == ["index", "watch"]


def test_nonempty_index_respects_disabled_maintenance_scan(monkeypatch):
    import services.desktop_service as desktop_service
    from services.desktop_service import DesktopService

    events = []
    _install_fake_watcher(monkeypatch, events)
    monkeypatch.setenv("NEURON_STARTUP_INDEX_DELAY", "0")
    monkeypatch.setattr(
        desktop_service.UserConfig,
        "load",
        lambda: {"auto_index_on_launch": False},
    )

    class FakeStartupIndexer:
        def run_synchronously(self):
            events.append("index")

    monkeypatch.setattr(desktop_service, "StartupIndexer", FakeStartupIndexer)

    svc = DesktopService.__new__(DesktopService)
    svc._idx = object()
    svc.watcher = None
    svc.total_indexed = lambda: 7

    svc._maintenance_init()

    assert events == ["watch"]

import json
from pathlib import Path


def test_watch_path_change_does_not_wipe_existing_index(monkeypatch, tmp_path):
    import app.config as config
    import services.startup_indexer as startup_indexer
    from services.startup_indexer import StartupIndexer

    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()

    roots_file = tmp_path / "indexed_roots.json"
    first_run_flag = tmp_path / ".first_run_complete"
    roots_file.write_text(json.dumps([str(old_root)]), encoding="utf-8")
    first_run_flag.touch()

    class FakeIndex:
        def __init__(self):
            self.metadata = [{"path": str(old_root / "existing.txt")}]
            self.scanned = []
            self.saved = 0

        def index_directory(self, path, recursive=True):
            self.scanned.append((path, recursive))
            return 0

        def save(self):
            self.saved += 1

    fake_index = FakeIndex()

    monkeypatch.setattr(config, "WATCH_PATHS", [str(old_root), str(new_root)])
    monkeypatch.setattr(config, "INDEXED_ROOTS_FILE", roots_file)
    monkeypatch.setattr(config, "FIRST_RUN_FLAG", first_run_flag)
    monkeypatch.setattr(startup_indexer, "get_index", lambda: fake_index)

    si = StartupIndexer()

    def fail_wipe(reason):
        raise AssertionError(f"index should not be wiped for: {reason}")

    monkeypatch.setattr(si, "_wipe_index", fail_wipe)

    si._run()

    assert fake_index.scanned == [(str(old_root), True), (str(new_root), True)]
    assert set(json.loads(roots_file.read_text(encoding="utf-8"))) == {
        str(old_root),
        str(new_root),
    }

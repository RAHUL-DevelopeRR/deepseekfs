from core.indexing.index_builder import _is_skipped_dir, _is_skipped_file


def test_indexer_skips_cache_and_build_directories():
    assert _is_skipped_dir("node_modules")
    assert _is_skipped_dir("webcache_6613")
    assert _is_skipped_dir("Intermediate")
    assert _is_skipped_dir(".git")


def test_indexer_skips_transient_files():
    assert _is_skipped_file("~$draft.docx")
    assert _is_skipped_file("download.part")
    assert _is_skipped_file("setup.crdownload")
    assert _is_skipped_file("desktop.ini")
    assert _is_skipped_file("Thumbs.db")


def test_indexer_keeps_regular_supported_names():
    assert not _is_skipped_dir("Documents")
    assert not _is_skipped_file("notes.docx")


def test_watcher_skips_full_drive_noise():
    import app.config as config
    from core.watcher.file_watcher import _is_skipped_path

    assert _is_skipped_path(r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\Temp\x.ps1")
    assert _is_skipped_path(r"C:\Users\rahul\AppData\Local\Temp\x.ps1")
    assert _is_skipped_path(r"C:\\")
    assert _is_skipped_path(str(config.STORAGE_DIR / "neuron.log"))
    assert not _is_skipped_path(r"C:\Users\rahul\Downloads\ptytest3.exe")


def test_live_watcher_filters_drive_roots():
    import app.config as config

    paths = [r"C:\\", r"C:\Users\rahul\Downloads"]
    assert config.filter_live_watch_paths(paths) == [r"C:\Users\rahul\Downloads"]

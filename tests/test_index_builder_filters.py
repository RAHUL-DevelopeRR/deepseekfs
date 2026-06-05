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


def test_indexer_keeps_regular_supported_names():
    assert not _is_skipped_dir("Documents")
    assert not _is_skipped_file("notes.docx")

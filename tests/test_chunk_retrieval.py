"""Offline regression tests with real SQLite/FAISS and deterministic embeddings."""

import os
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


class TestEmbedder:
    __test__ = False
    identity = "test-lexical-v1"

    def encode(self, texts, batch_size=8):
        from core.embeddings.embedder import _FallbackEmbedder

        return _FallbackEmbedder(384).encode(texts)

    def encode_single(self, text):
        return self.encode([text])[0]


@pytest.fixture
def index(monkeypatch, tmp_path):
    import app.config as config
    import core.indexing.index_builder as module

    monkeypatch.setattr(config, "SQLITE_DB_PATH", str(tmp_path / "index.db"))
    monkeypatch.setattr(config, "FAISS_INDEX_PATH", str(tmp_path / "index.faiss"))
    monkeypatch.setattr(config, "BASE_DIR", tmp_path / "application")
    monkeypatch.setattr(module, "get_embedder", TestEmbedder)
    instance = module.IndexBuilder()
    yield instance
    instance._db.close()


def test_late_content_is_indexed_and_file_results_are_unique(index, tmp_path):
    file = tmp_path / "report.txt"
    file.write_text(
        "unrelated introduction\n" * 900 + "\nQ3 revenue reached 987654 dollars.",
        encoding="utf-8",
    )
    assert index.add_file(str(file))
    embedding = np.array([index.embedder.encode_single("Q3 revenue 987654")])
    results = index.search_chunks(embedding)
    assert any("987654" in result["text"] for result in results)
    assert results[0]["chunk_id"]
    assert len(index.search_raw(embedding, 10)[1]) == 1
    assert index._db.count() == 1
    assert index.index.ntotal > 1


def test_modified_file_replaces_evidence_preserves_identity_and_access(index, tmp_path):
    file = tmp_path / "report.txt"
    file.write_text("Revenue Q3 was 111 dollars.")
    assert index.add_file(str(file))
    index.record_open(str(file))
    previous = index.metadata[0]
    file.write_text("Revenue Q3 was 999 dollars.")
    assert index.add_file(str(file))
    assert index.metadata[0]["id"] == previous["id"]
    assert index.metadata[0]["open_count"] == 1
    results = index.search_chunks(np.array([index.embedder.encode_single("revenue")]))
    assert all("111" not in result["text"] for result in results)
    assert "999" in results[0]["text"]
    assert not index.add_file(str(file))


def test_force_detects_same_stat_content_change(index, tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("old content text")
    assert index.add_file(str(file))
    stat = file.stat()
    file.write_text("new content text")
    os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert index.add_file(str(file), force=True)


def test_empty_file_removes_stale_chunks(index, tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("secret old contents")
    assert index.add_file(str(file))
    file.write_text("")
    assert index.add_file(str(file))
    assert not index.search_chunks(np.array([index.embedder.encode_single("secret")]))


def test_restart_recovers_without_faiss_snapshot(index, tmp_path):
    from core.indexing.index_builder import IndexBuilder

    file = tmp_path / "notes.txt"
    file.write_text("Durable evidence survived a crash.")
    assert index.add_file(str(file))
    # No save() call: SQLite must still recover all committed vectors.
    recovered = IndexBuilder()
    try:
        assert recovered.index.ntotal == 1
        assert recovered.search_chunks(
            np.array([index.embedder.encode_single("durable")])
        )
    finally:
        recovered._db.close()


def test_directory_removal_cascades_without_removing_sibling(index, tmp_path):
    folder, sibling = tmp_path / "docs", tmp_path / "docs-other"
    folder.mkdir()
    sibling.mkdir()
    for root in (folder, sibling):
        file = root / "notes.txt"
        file.write_text("Document evidence.")
        index.add_file(str(file))
    assert index.remove_file(str(folder))
    assert index._db.count() == 1
    assert index.index.ntotal == 1
    assert index.metadata[0]["path"].startswith(str(sibling))


def test_pdf_all_pages_have_locations(tmp_path):
    import fitz
    from core.ingestion.chunks import parse_chunks

    file = tmp_path / "pages.pdf"
    with fitz.open() as document:
        for number in range(8):
            page = document.new_page()
            page.insert_text((72, 72), f"Revenue evidence on page {number + 1}")
        document.save(file)
    chunks, truncated = parse_chunks(str(file))
    assert not truncated
    assert {chunk["page"] for chunk in chunks} == set(range(1, 9))


def test_xlsx_preserves_sheet_row_and_headers(tmp_path):
    from openpyxl import Workbook
    from core.ingestion.chunks import parse_chunks

    book = Workbook()
    sheet = book.active
    sheet.title = "Revenue"
    sheet.append(["Quarter", "Amount"])
    for i in range(150):
        sheet.append(["Q3", i])
    file = tmp_path / "revenue.xlsx"
    book.save(file)
    chunks, _ = parse_chunks(str(file))
    assert "Revenue, row 151" in chunks[-1]["section"]
    assert "Amount" in chunks[-1]["text"]
    assert "149" in chunks[-1]["text"]


def test_image_is_explicit_metadata_without_ocr(tmp_path, monkeypatch):
    from PIL import Image
    from core.ingestion.chunks import parse_chunks

    monkeypatch.delenv("NEURON_INDEX_IMAGE_OCR", raising=False)
    file = tmp_path / "cat.png"
    Image.new("RGB", (20, 30)).save(file)
    chunks, _ = parse_chunks(str(file))
    assert chunks[0]["evidence_kind"] == "metadata"
    assert "width=20" in chunks[0]["text"]


def test_subtitle_evidence_has_timestamps_and_updates(index, tmp_path):
    video = tmp_path / "meeting.mp4"
    video.write_bytes(b"fake video; no decoder needed")
    subtitle = video.with_suffix(".srt")
    subtitle.write_text("1\n00:00:10,000 --> 00:00:12,000\nRevenue was 123 dollars.\n")
    assert index.add_file(str(video))
    rows = (
        index._db._conn()
        .execute("SELECT * FROM chunks WHERE evidence_kind='subtitle'")
        .fetchall()
    )
    assert "00:00:10" in rows[0]["timestamp"]
    subtitle.write_text("1\n00:00:10,000 --> 00:00:12,000\nRevenue was 789 dollars.\n")
    assert index.add_file(str(video))
    rows = (
        index._db._conn()
        .execute("SELECT text FROM chunks WHERE evidence_kind='subtitle'")
        .fetchall()
    )
    assert "789" in rows[0][0]


def test_parse_does_not_hold_search_lock(index, tmp_path, monkeypatch):
    import core.indexing.index_builder as module

    file = tmp_path / "notes.txt"
    file.write_text("Some content.")
    entered, release = threading.Event(), threading.Event()
    original = module.parse_chunks

    def slow_parse(path):
        entered.set()
        assert release.wait(5)
        return original(path)

    monkeypatch.setattr(module, "parse_chunks", slow_parse)
    worker = threading.Thread(target=lambda: index.add_file(str(file)))
    worker.start()
    try:
        assert entered.wait(3)
        assert index.lock.acquire(timeout=0.2)
        index.lock.release()
    finally:
        release.set()
        worker.join(5)


def test_query_mode_receives_content_and_source_locations(monkeypatch):
    import services.memory_os as module

    received = {}

    class Engine:
        def chat(self, **kwargs):
            received.update(kwargs)
            return "Q3 revenue was 987654 dollars [S1]."

    agent = module.MemoryOSAgent.__new__(module.MemoryOSAgent)
    agent._get_engine = lambda: Engine()
    agent._remember = lambda *args: None
    agent._recent_messages = lambda **kwargs: []
    agent._run_search = lambda query: [
        {
            "path": "C:/report.pdf",
            "name": "report.pdf",
            "text": "Q3 revenue was 987654 dollars.",
            "section": "Revenue",
            "page": 8,
            "evidence_kind": "content",
        }
    ]
    monkeypatch.setattr(
        module, "get_event_store", lambda: SimpleNamespace(insert=lambda *args: None)
    )
    monkeypatch.setattr(
        module, "_live_context_for_prompt", lambda query: ("", 0, False)
    )
    answer = agent._query_mode("What was Q3 revenue?")
    assert "987654" in received["messages"][1]["content"]
    assert "untrusted" in received["messages"][0]["content"]
    assert "web evidence" not in received["messages"][1]["content"].lower()
    assert "C:/report.pdf" in answer
    assert "page 8" in answer


def test_query_mode_streams_evidence_answer(monkeypatch):
    import services.memory_os as module

    emitted = []

    class Engine:
        def chat_stream(self, **kwargs):
            assert "987654" in kwargs["messages"][1]["content"]
            yield "Q3 revenue "
            yield "was 987654 [S1]."

    agent = module.MemoryOSAgent.__new__(module.MemoryOSAgent)
    agent._get_engine = lambda: Engine()
    agent._remember = lambda *args: None
    agent._recent_messages = lambda **kwargs: []
    agent._run_search = lambda query: [{
        "path": "C:/report.pdf", "name": "report.pdf",
        "text": "Q3 revenue was 987654 dollars.",
        "section": "Revenue", "page": 8, "evidence_kind": "content",
    }]
    agent.on_token = emitted.append
    monkeypatch.setattr(module, "get_event_store", lambda: SimpleNamespace(insert=lambda *args: None))
    monkeypatch.setattr(module, "_live_context_for_prompt", lambda query: ("", 0, False))
    answer = agent._query_mode("What was Q3 revenue?")
    assert "".join(emitted) == "Q3 revenue was 987654 [S1]."
    assert "Retrieved sources" in answer


def test_search_tool_observation_contains_full_path(monkeypatch):
    import core.search.semantic_search as module
    from services.tools.search_tools import SemanticSearchTool

    monkeypatch.setattr(
        module,
        "SemanticSearch",
        lambda: SimpleNamespace(
            search=lambda *a, **k: [
                {
                    "name": "report.pdf",
                    "path": "C:/Users/example/report.pdf",
                    "combined_score": 0.9,
                }
            ]
        ),
    )
    result = SemanticSearchTool().execute("report")
    assert result.success
    assert "C:/Users/example/report.pdf" in result.output


def test_evidence_budget_and_metadata_exclusion():
    from services.retrieval_context import build_evidence

    rows = [
        {"name": "image.png", "text": "image metadata", "evidence_kind": "metadata"}
    ]
    rows += [{"name": "notes.txt", "path": "notes.txt", "text": "evidence " * 500}] * 20
    evidence, sources = build_evidence(rows, max_chars=1500)
    assert len(evidence) <= 1500
    assert "image metadata" not in evidence
    assert "[S1]" in sources


def test_filename_query_retrieves_content(index, tmp_path, monkeypatch):
    import core.search.semantic_search as module

    monkeypatch.setattr(module, "get_embedder", TestEmbedder)
    file = tmp_path / "report.txt"
    file.write_text("Q3 revenue was 456 dollars.")
    index.add_file(str(file))
    results = module.SemanticSearch(index=index).search_evidence("report.txt")
    assert "456" in results[0]["text"]


def test_stale_evidence_is_withheld_until_reindexed(index, tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("Old confidential data.")
    index.add_file(str(file))
    file.write_text("Entirely new text with a different length.")
    query = index.embedder.encode_single("data")
    assert index.evidence_for_paths(query, [str(file)]) == []
    assert index.search_chunks(query.reshape(1, -1)) == []


def test_embedding_backend_change_invalidates_vectors_but_keeps_paths(
    index, tmp_path, monkeypatch
):
    import core.indexing.index_builder as module

    file = tmp_path / "notes.txt"
    file.write_text("Embedding identity matters.")
    index.add_file(str(file))
    index.save()
    replacement = TestEmbedder()
    replacement.identity = "different-test-backend"
    monkeypatch.setattr(module, "get_embedder", lambda: replacement)
    changed = module.IndexBuilder()
    try:
        assert changed.index.ntotal == 0
        assert changed._db.count() == 1
        assert changed.get_index_stats()["pending_chunk_migration"] == 1
        assert changed.add_file(str(file))
    finally:
        changed._db.close()


def test_snapshot_is_not_reused_after_unsaved_modification(index, tmp_path):
    from core.indexing.index_builder import IndexBuilder

    file = tmp_path / "notes.txt"
    file.write_text("The old evidence.")
    index.add_file(str(file))
    index.save()
    file.write_text("The newly changed evidence.")
    index.add_file(str(file))
    recovered = IndexBuilder()
    try:
        result = recovered.search_chunks(
            index.embedder.encode_single("evidence").reshape(1, -1)
        )
        assert "newly" in result[0]["text"]
    finally:
        recovered._db.close()


def test_corrupt_snapshot_recovers(index, tmp_path):
    from core.indexing.index_builder import IndexBuilder

    file = tmp_path / "notes.txt"
    file.write_text("Evidence preserved in SQLite.")
    index.add_file(str(file))
    index.save()
    (tmp_path / "index.faiss").write_bytes(b"broken")
    recovered = IndexBuilder()
    try:
        assert recovered.index.ntotal == 1
    finally:
        recovered._db.close()


def test_parser_failure_does_not_replace_committed_chunks(index, tmp_path, monkeypatch):
    import core.indexing.index_builder as module

    file = tmp_path / "notes.txt"
    file.write_text("Existing indexed contents.")
    index.add_file(str(file))
    old_id = index.metadata[0]["faiss_id"]
    file.write_text("A new document with a simulated parsing failure.")
    monkeypatch.setattr(
        module,
        "parse_chunks",
        lambda *args: (_ for _ in ()).throw(ValueError("parse failed")),
    )
    assert not index.add_file(str(file))
    assert index.metadata[0]["faiss_id"] == old_id
    assert (
        index.evidence_for_paths(index.embedder.encode_single("contents"), [str(file)])
        == []
    )


def test_agent_observation_keeps_complete_json_paths():
    import json
    from services.retrieval_context import search_observation

    results = [
        {
            "path": "C:/Users/" + "long directory/" * 12 + f"file-{i}.pdf",
            "name": f"file-{i}.pdf",
            "text": "evidence " * 100,
        }
        for i in range(20)
    ]
    text = search_observation(results)
    records = json.loads(text.split("\n", 1)[1])
    assert records
    assert all(row["path"] == results[i]["path"] for i, row in enumerate(records))
    assert len(text) < 2000


def test_legacy_database_migrates_without_losing_files(tmp_path, monkeypatch):
    import app.config as config
    import core.indexing.index_builder as module

    database = tmp_path / "old.db"
    file = tmp_path / "legacy.txt"
    file.write_text("Legacy content now becomes chunks.")
    with sqlite3.connect(database) as conn:
        conn.execute(module._MetadataDB._CREATE_TABLE)
        conn.execute(
            "INSERT INTO files (faiss_id,path,name) VALUES (0,?,?)",
            (str(file), file.name),
        )
    monkeypatch.setattr(config, "SQLITE_DB_PATH", str(database))
    monkeypatch.setattr(config, "BASE_DIR", tmp_path / "app")
    monkeypatch.setattr(module, "get_embedder", TestEmbedder)
    migrated = module.IndexBuilder()
    try:
        assert migrated._db.count() == 1
        assert migrated.get_index_stats()["pending_chunk_migration"] == 1
        assert migrated.add_file(str(file))
        assert migrated.index.ntotal == 1
    finally:
        migrated._db.close()


def test_primary_model_is_1_5b_and_does_not_select_3b(tmp_path, monkeypatch):
    from services import model_manager

    assert "1.5B" in model_manager.LLM_MODEL_REPO
    assert "1.5b" in model_manager.LLM_MODEL_FILE
    assert "q4_k_m" in model_manager.LLM_MODEL_FILE
    larger = tmp_path / "qwen2.5-coder-3b-instruct-q5_k_m.gguf"
    with larger.open("wb") as stream:
        stream.truncate(model_manager._MIN_GGUF_SIZE_BYTES + 1)
    monkeypatch.setenv("NEURON_MODEL_DIRS", str(tmp_path))
    monkeypatch.setenv("NEURON_MODEL_DIRS_ONLY", "1")
    monkeypatch.delenv(model_manager.ALLOW_SMALL_MODEL_FALLBACK_ENV, raising=False)
    assert model_manager.get_llm_model_path() is None


def test_query_without_evidence_does_not_load_model(monkeypatch):
    import services.memory_os as module

    agent = module.MemoryOSAgent.__new__(module.MemoryOSAgent)
    agent._get_engine = lambda: pytest.fail("No evidence should not load Qwen")
    agent._remember = lambda *args: None
    agent._run_search = lambda query: [
        {"path": "C:/cat.png", "name": "cat.png", "evidence_kind": "metadata"}
    ]
    monkeypatch.setattr(
        module, "get_event_store", lambda: SimpleNamespace(insert=lambda *args: None)
    )
    monkeypatch.setattr(
        module, "_live_context_for_prompt", lambda query: ("", 0, False)
    )
    result = agent._query_mode("What is in the picture?")
    assert "metadata only" in result


def test_watcher_modification_forces_content_check(monkeypatch, tmp_path):
    import core.watcher.file_watcher as module

    called = []
    fake = SimpleNamespace(
        add_file=lambda path, **kwargs: called.append((path, kwargs)) or True,
        save=lambda: None,
    )
    monkeypatch.setattr(module, "_is_skipped_path", lambda path: False)
    handler = module.FileEventHandler(fake)
    handler.on_modified(
        SimpleNamespace(src_path=str(tmp_path / "notes.txt"), is_directory=False)
    )
    assert called[0][1]["force"] is True


def test_moving_into_excluded_folder_removes_old_entry(monkeypatch, tmp_path):
    import core.watcher.file_watcher as module

    removed = []
    fake = SimpleNamespace(remove_file=lambda path: removed.append(path))
    monkeypatch.setattr(module, "_is_skipped_path", lambda path: "excluded" in Path(path).parts)
    handler = module.FileEventHandler(fake)
    handler.on_moved(
        SimpleNamespace(
            src_path=str(tmp_path / "notes.txt"),
            dest_path=str(tmp_path / "excluded" / "notes.txt"),
            is_directory=False,
        )
    )
    assert removed == [str(tmp_path / "notes.txt")]


def test_missing_neural_runtime_preserves_existing_vectors(index, tmp_path):
    from types import SimpleNamespace
    document = tmp_path / 'notes.txt'
    document.write_text('important existing document evidence')
    assert index.add_file(str(document))
    count = index._db._conn().execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
    index.embedder = SimpleNamespace(identity='lexical-blake2b-v1:384')
    with pytest.raises(RuntimeError, match='preserved'):
        index._load_or_create_index()
    assert index._db._conn().execute('SELECT COUNT(*) FROM chunks').fetchone()[0] == count

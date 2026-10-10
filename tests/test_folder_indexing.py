from pathlib import Path


def test_folder_index_text_captures_folder_shape(tmp_path):
    from core.indexing.index_builder import FOLDER_EXTENSION, _folder_index_text
    from core.search.nlp_parser import parse_query

    (tmp_path / "reports").mkdir()
    (tmp_path / "notes.md").write_text("release notes", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b\n1,2", encoding="utf-8")

    text = _folder_index_text(tmp_path)

    assert "reports" in text
    assert "notes.md" in text
    assert ".md files" in text
    parsed = parse_query("project folders")
    assert FOLDER_EXTENSION in parsed.target_exts


def test_executable_metadata_is_searchable_without_binary_parse(tmp_path):
    from core.ingestion.file_parser import FileParser

    exe = tmp_path / "ptytest3.exe"
    exe.write_bytes(b"MZ\x00\x00")

    text = FileParser.parse(str(exe))

    assert "ptytest3.exe" in text
    assert "metadata only" in text


def test_specific_filename_query_detects_exe():
    from core.search.semantic_search import SemanticSearch

    assert SemanticSearch._looks_like_specific_file_query("ptytest3.exe")
    assert SemanticSearch._looks_like_specific_file_query(r"C:\Tools\ptytest3.exe")
    assert not SemanticSearch._looks_like_specific_file_query("hospital management system")


def test_folder_summary_includes_subfolders_and_largest_files(tmp_path):
    from services.tools.search_tools import SummarizeTool

    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "big.txt").write_text("x" * 2000, encoding="utf-8")
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "small.md").write_text("tiny", encoding="utf-8")

    result = SummarizeTool().execute(str(tmp_path))

    assert result.success
    assert "Top subfolders by file count" in result.output
    assert "Largest files" in result.output
    assert "big.txt" in result.output

"""
Unit tests for core/search/query_parser.py
Covers: extract_intent — extension detection, path filtering,
        size filtering, negation, fuzzy groups, noise removal.
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.search.query_parser import extract_intent


# ── Helper ────────────────────────────────────────────────────────────────
def intent(query):
    """Shorthand: return (cleaned, exts, path, size, excluded) tuple."""
    return extract_intent(query)


class TestReturnShape:
    """extract_intent always returns the correct 5-tuple."""

    def test_returns_five_tuple(self):
        result = intent("find python files")
        assert isinstance(result, tuple)
        assert len(result) == 5

    def test_cleaned_is_str(self):
        cleaned, *_ = intent("search for reports")
        assert isinstance(cleaned, str)

    def test_exts_is_list(self):
        _, exts, *_ = intent("pdf files")
        assert isinstance(exts, list)

    def test_path_is_none_or_str(self):
        _, _, path, *_ = intent("any query")
        assert path is None or isinstance(path, str)

    def test_size_is_none_or_str(self):
        _, _, _, size, _ = intent("any query")
        assert size is None or isinstance(size, str)

    def test_excluded_is_list(self):
        *_, excluded = intent("any query")
        assert isinstance(excluded, list)


class TestExtensionDetection:
    """Verify that extension aliases map correctly."""

    def test_python_files(self):
        _, exts, *_ = intent("python files about ML")
        assert ".py" in exts

    def test_pdf(self):
        _, exts, *_ = intent("pdf documents")
        assert ".pdf" in exts

    def test_pdfs_plural(self):
        _, exts, *_ = intent("show me pdfs")
        assert ".pdf" in exts

    def test_docx(self):
        _, exts, *_ = intent("docx files")
        assert ".docx" in exts

    def test_word(self):
        _, exts, *_ = intent("word documents")
        assert ".docx" in exts or ".doc" in exts

    def test_excel(self):
        _, exts, *_ = intent("excel spreadsheet")
        assert ".xlsx" in exts or ".xls" in exts

    def test_pptx(self):
        _, exts, *_ = intent("pptx files about budget")
        assert ".pptx" in exts

    def test_powerpoint(self):
        _, exts, *_ = intent("powerpoint presentations")
        assert ".pptx" in exts or ".ppt" in exts

    def test_jupyter_notebook(self):
        _, exts, *_ = intent("jupyter notebooks")
        assert ".ipynb" in exts

    def test_csv(self):
        _, exts, *_ = intent("csv spreadsheets")
        assert ".csv" in exts

    def test_yaml(self):
        _, exts, *_ = intent("yaml config files")
        assert ".yaml" in exts or ".yml" in exts

    def test_no_type_keyword_empty_exts(self):
        _, exts, *_ = intent("machine learning project")
        assert exts == []

    def test_markdown(self):
        _, exts, *_ = intent("markdown docs")
        assert ".md" in exts

    def test_javascript(self):
        _, exts, *_ = intent("javascript files")
        assert ".js" in exts

    def test_typescript(self):
        _, exts, *_ = intent("typescript files")
        assert ".ts" in exts

    def test_log_files(self):
        _, exts, *_ = intent("log files")
        assert ".log" in exts


class TestFuzzyGroups:
    """Fuzzy group keywords map to multiple extensions."""

    def test_code_group(self):
        _, exts, *_ = intent("code files about API")
        assert ".py" in exts
        assert ".js" in exts

    def test_docs_group(self):
        _, exts, *_ = intent("docs about SWOT analysis")
        assert ".pdf" in exts or ".docx" in exts or ".md" in exts

    def test_images_group(self):
        _, exts, *_ = intent("images from last month")
        assert ".png" in exts or ".jpg" in exts

    def test_videos_group(self):
        _, exts, *_ = intent("videos files")
        assert ".mp4" in exts

    def test_configs_group(self):
        _, exts, *_ = intent("configs files")
        assert ".yaml" in exts or ".toml" in exts or ".ini" in exts


class TestPathFiltering:
    """Path filters extracted from 'in <location>' pattern."""

    def test_in_downloads(self):
        _, _, path, *_ = intent("pdfs in downloads")
        assert path == "Downloads"

    def test_in_desktop(self):
        _, _, path, *_ = intent("files in desktop")
        assert path == "Desktop"

    def test_in_documents(self):
        _, _, path, *_ = intent("reports in documents")
        assert path == "Documents"

    def test_in_pictures(self):
        _, _, path, *_ = intent("images in pictures")
        assert path == "Pictures"

    def test_no_path_filter_returns_none(self):
        _, _, path, *_ = intent("python files about ML")
        assert path is None

    def test_in_unknown_location_no_path_filter(self):
        _, _, path, *_ = intent("files in someunknownplace")
        assert path is None

    def test_case_insensitive_location(self):
        _, _, path, *_ = intent("files in Downloads")
        # 'downloads' lowercased before lookup
        assert path == "Downloads"


class TestSizeFiltering:
    """Size filters extracted from size adjectives."""

    def test_large(self):
        _, _, _, size, _ = intent("large pdf files")
        assert size == "large"

    def test_big(self):
        _, _, _, size, _ = intent("big videos")
        assert size == "large"

    def test_huge(self):
        _, _, _, size, _ = intent("huge files in downloads")
        assert size == "large"

    def test_small(self):
        _, _, _, size, _ = intent("small text files")
        assert size == "small"

    def test_tiny(self):
        _, _, _, size, _ = intent("tiny config files")
        assert size == "small"

    def test_no_size_filter_returns_none(self):
        _, _, _, size, _ = intent("python scripts")
        assert size is None


class TestNegation:
    """Excluded paths via 'not in <location>'."""

    def test_not_in_downloads(self):
        *_, excluded = intent("python files not in downloads")
        assert "Downloads" in excluded

    def test_not_in_desktop(self):
        *_, excluded = intent("code files not in desktop")
        assert "Desktop" in excluded

    def test_multiple_locations_no_negation_not_excluded(self):
        *_, excluded = intent("files in documents")
        assert "Documents" not in excluded

    def test_no_negation_returns_empty_list(self):
        *_, excluded = intent("pdf files in downloads")
        assert excluded == []


class TestCleanedQuery:
    """Semantic query is stripped of noise and type keywords."""

    def test_noise_words_removed(self):
        cleaned, *_ = intent("show me python files about ML")
        assert "show" not in cleaned
        assert "me" not in cleaned
        assert "files" not in cleaned

    def test_semantic_content_preserved(self):
        cleaned, *_ = intent("python files about machine learning")
        assert "machine" in cleaned or "learning" in cleaned

    def test_fallback_to_original_if_too_short(self):
        # If all words are noise/type words, fallback to original
        cleaned, *_ = intent("pdf")
        # "pdf" is a strong keyword so exts=[".pdf"], cleaned might be empty → fallback
        assert isinstance(cleaned, str)
        assert len(cleaned) >= 1

    def test_empty_query_handled(self):
        cleaned, exts, path, size, excluded = intent("")
        assert isinstance(cleaned, str)
        assert exts == []
        assert path is None
        assert size is None
        assert excluded == []

    def test_complex_query(self):
        cleaned, exts, path, size, excluded = intent(
            "large pdf files in downloads not in desktop"
        )
        assert ".pdf" in exts
        assert path == "Downloads"
        assert size == "large"
        assert "Desktop" in excluded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

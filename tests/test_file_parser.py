import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ingestion.file_parser import FileParser


class TestFileParser(unittest.TestCase):
    def test_parse_text_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "notes.txt"
            file_path.write_text("hello world", encoding="utf-8")

            content = FileParser.parse(str(file_path))

            self.assertEqual(content, "hello world")

    def test_parse_unsupported_extension_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "image.bmp"
            file_path.write_bytes(b"BM")

            content = FileParser.parse(str(file_path))

            self.assertIsNone(content)

    def test_parse_handles_parser_exceptions(self):
        with patch.object(FileParser, "_parse_text", side_effect=RuntimeError("boom")):
            result = FileParser.parse("/tmp/file.txt")
        self.assertIsNone(result)

    def test_get_file_metadata_contains_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "example.md"
            file_path.write_text("# title", encoding="utf-8")

            metadata = FileParser.get_file_metadata(str(file_path))

            self.assertEqual(metadata["name"], "example.md")
            self.assertEqual(metadata["extension"], ".md")
            self.assertEqual(metadata["path"], str(file_path))
            self.assertGreaterEqual(metadata["size"], 1)
            self.assertIn("modified_time", metadata)
            self.assertIn("created_time", metadata)


if __name__ == "__main__":
    unittest.main()

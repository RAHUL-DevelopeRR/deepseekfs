"""Search and summarization tools."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import app.config as config

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult
from .common import format_size

_MAX_FOLDER_SUMMARY_ITEMS = int(os.getenv("NEURON_FOLDER_SUMMARY_MAX_ITEMS", "5000"))


def _skip_dir_name(name: str) -> bool:
    low = name.lower()
    for pattern in config.SKIP_DIRS:
        pattern_low = pattern.lower()
        if fnmatch.fnmatch(low, pattern_low):
            return True
    return False


class SemanticSearchTool(BaseTool):
    name = "semantic_search"
    description = "Search for files using natural language queries. Uses FAISS vector similarity search."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("query", "string", "Natural language search query"),
        ToolParam("max_results", "integer", "Maximum results", required=False, default=10),
    ]

    def execute(self, query: str, max_results: int = 10, **kwargs) -> ToolResult:
        try:
            from core.search.semantic_search import SemanticSearch

            searcher = SemanticSearch()
            results = searcher.search(query, top_k=max_results)
            if not results:
                return ToolResult(True, f"No results found for: {query}")

            output_lines = [f"Search results for '{query}':"]
            for index, result in enumerate(results, 1):
                name = result.get("name", Path(result.get("path", "")).name)
                score = result.get("combined_score", result.get("semantic_score", 0))
                output_lines.append(f"  {index}. {name} (score: {score:.2f})")
            return ToolResult(True, "\n".join(output_lines), results)
        except Exception as exc:
            return ToolResult(False, f"Search error: {exc}")


class SummarizeTool(BaseTool):
    name = "summarize"
    description = "Summarize a file or folder contents using AI."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("path", "path", "File or folder path to summarize"),
    ]

    def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            target = Path(path)
            if target.is_file():
                from services.llm_engine import get_llm_engine

                summary = get_llm_engine().summarize_file(path)
                return ToolResult(True, f"Summary of {target.name}:\n{summary}")

            if target.is_dir():
                file_count = 0
                dir_count = 0
                total_size = 0
                ext_counts: dict[str, int] = {}
                scanned_items = 0
                truncated = False

                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in dirs if not _skip_dir_name(d)]
                    dir_count += len(dirs)

                    for fname in files:
                        scanned_items += 1
                        if scanned_items > _MAX_FOLDER_SUMMARY_ITEMS:
                            truncated = True
                            break
                        item = Path(root) / fname
                        file_count += 1
                        try:
                            total_size += item.stat().st_size
                        except OSError:
                            pass
                        ext = item.suffix.lower() or "(no ext)"
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1

                    if truncated:
                        break

                top_exts = sorted(ext_counts.items(), key=lambda pair: -pair[1])[:10]
                top_text = ", ".join(f"{ext} ({count})" for ext, count in top_exts) or "none"
                output = (
                    f"Folder summary: {path}\n"
                    f"  Files: {file_count}\n"
                    f"  Folders: {dir_count}\n"
                    f"  Total size: {format_size(total_size)}\n"
                    f"  Top file types: {top_text}"
                )
                if truncated:
                    output += f"\n  Note: stopped after {_MAX_FOLDER_SUMMARY_ITEMS:,} files"
                return ToolResult(True, output, {
                    "files": file_count,
                    "folders": dir_count,
                    "total_size": total_size,
                    "top_extensions": dict(top_exts),
                    "truncated": truncated,
                })

            return ToolResult(False, f"Path not found: {path}")
        except Exception as exc:
            return ToolResult(False, f"Summarize error: {exc}")


class OCRTool(BaseTool):
    name = "ocr"
    description = "Extract text from scanned PDFs and images using OCR. Uses PyMuPDF for digital PDFs."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("path", "path", "Path to PDF or image file"),
    ]

    def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            ext = Path(path).suffix.lower()
            if ext == ".pdf":
                import fitz

                doc = fitz.open(path)
                text = ""
                for page in doc:
                    text += page.get_text() + "\n"
                doc.close()
                if text.strip():
                    return ToolResult(True, f"Extracted text from {Path(path).name}:\n{text[:4000]}")
                return ToolResult(True, "PDF appears to be scanned (no extractable text). OCR not available.")

            if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}:
                return ToolResult(True, f"Image OCR for {Path(path).name} requires pytesseract (not installed).")

            return ToolResult(False, f"Unsupported file type for OCR: {ext}")
        except Exception as exc:
            return ToolResult(False, f"OCR error: {exc}")

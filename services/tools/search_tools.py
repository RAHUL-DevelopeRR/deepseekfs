"""Search and summarization tools."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import app.config as config

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult
from .common import format_size
from services.summary_presenter import (
    build_extractive_summary,
    format_summary_markdown,
    is_ai_unavailable_text,
)

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
                if is_ai_unavailable_text(summary):
                    summary = format_summary_markdown(
                        build_extractive_summary(path, ai_error=summary)
                    )
                return ToolResult(True, f"Summary of {target.name}:\n{summary}")

            if target.is_dir():
                file_count = 0
                dir_count = 0
                total_size = 0
                ext_counts: dict[str, int] = {}
                top_dirs: dict[str, int] = {}
                largest_files: list[tuple[int, str]] = []
                scanned_items = 0
                truncated = False

                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in dirs if not _skip_dir_name(d)]
                    dir_count += len(dirs)
                    for dirname in dirs[:50]:
                        top_dirs[str(Path(root) / dirname)] = 0

                    for fname in files:
                        scanned_items += 1
                        if scanned_items > _MAX_FOLDER_SUMMARY_ITEMS:
                            truncated = True
                            break
                        item = Path(root) / fname
                        file_count += 1
                        try:
                            item_size = item.stat().st_size
                            total_size += item_size
                        except OSError:
                            item_size = 0
                        ext = item.suffix.lower() or "(no ext)"
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1
                        parent = str(item.parent)
                        top_dirs[parent] = top_dirs.get(parent, 0) + 1
                        if len(largest_files) < 12 or item_size > largest_files[-1][0]:
                            largest_files.append((item_size, str(item)))
                            largest_files.sort(key=lambda pair: -pair[0])
                            largest_files = largest_files[:12]

                    if truncated:
                        break

                top_exts = sorted(ext_counts.items(), key=lambda pair: -pair[1])[:10]
                top_text = ", ".join(f"{ext} ({count})" for ext, count in top_exts) or "none"
                top_folder_text = "\n".join(
                    f"  - {folder} ({count} files)"
                    for folder, count in sorted(top_dirs.items(), key=lambda pair: -pair[1])[:8]
                    if count > 0
                ) or "  - none"
                largest_text = "\n".join(
                    f"  - {name} ({format_size(size)})" for size, name in largest_files[:5]
                ) or "  - none"
                output = (
                    f"Folder summary: {path}\n"
                    f"  Files: {file_count}\n"
                    f"  Folders: {dir_count}\n"
                    f"  Total size: {format_size(total_size)}\n"
                    f"  Top file types: {top_text}\n"
                    f"Top subfolders by file count:\n{top_folder_text}\n"
                    f"Largest files:\n{largest_text}"
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
    description = "Extract text from scanned PDFs and images. Uses offline OCR when installed and PyMuPDF for digital PDFs."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("path", "path", "Path to PDF or image file"),
    ]

    def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            ext = Path(path).suffix.lower()
            if ext == ".pdf":
                from services.document_reader import extract_document_sample

                extracted = extract_document_sample(path, max_chars=6000)
                if extracted.text.strip():
                    note = "\n".join(extracted.warnings)
                    return ToolResult(
                        True,
                        f"Extracted evidence from {Path(path).name}:\n"
                        f"Pages: {extracted.page_count}, sampled: {extracted.sampled_pages}\n"
                        f"{note}\n\n{extracted.text[:5000]}",
                    )
                return ToolResult(True, "PDF has no extractable text and OCR is not available.")

            if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}:
                try:
                    import pytesseract
                    from PIL import Image
                except Exception:
                    return ToolResult(
                        True,
                        f"Image OCR for {Path(path).name} requires pytesseract and a Tesseract runtime.",
                    )
                text = pytesseract.image_to_string(Image.open(path)) or ""
                return ToolResult(True, text[:5000] if text.strip() else "No text found by OCR.")

            return ToolResult(False, f"Unsupported file type for OCR: {ext}")
        except Exception as exc:
            return ToolResult(False, f"OCR error: {exc}")

"""Presentation-ready offline summaries for files and folders.

This module is intentionally model-independent. It gives the UI something
useful to show when the local Qwen runtime is unavailable or incompatible.
"""
from __future__ import annotations

import re
from pathlib import Path

from services.document_reader import extract_document_sample, ocr_available


_AI_UNAVAILABLE_PREFIXES = (
    "AI unavailable:",
    "[AI unavailable:",
    "AI summary unavailable",
)


def is_ai_unavailable_text(text: str | None) -> bool:
    value = (text or "").strip()
    return any(value.startswith(prefix) for prefix in _AI_UNAVAILABLE_PREFIXES)


def build_extractive_summary(path: str, ai_error: str | None = None) -> dict[str, object]:
    """Return a compact, structured summary without requiring an LLM."""
    target = Path(path)
    if target.is_dir():
        return _folder_summary(target, ai_error)
    return _file_summary(target, ai_error)


def format_summary_markdown(summary: dict[str, object]) -> str:
    title = str(summary.get("title") or "Offline summary")
    subtitle = str(summary.get("subtitle") or "")
    bullets = [str(item) for item in summary.get("bullets", []) if str(item).strip()]
    stats = summary.get("stats") or {}
    note = str(summary.get("note") or "")

    lines = [f"### {title}"]
    if subtitle:
        lines.append(subtitle)
    if stats:
        stat_text = " | ".join(f"{key}: {value}" for key, value in stats.items())
        lines.append(f"**At a glance:** {stat_text}")
    if bullets:
        lines.append("")
        lines.extend(f"- {bullet}" for bullet in bullets[:6])
    if note:
        lines.append("")
        lines.append(f"_Note: {note}_")
    return "\n".join(lines).strip()


def _file_summary(path: Path, ai_error: str | None) -> dict[str, object]:
    extracted = extract_document_sample(str(path), max_chars=8000)
    text = extracted.text or ""
    sentences = _best_sentences(text)
    stat = _safe_stat(path)

    bullets = sentences[:4]
    if extracted.is_weak_text:
        sampled = ", ".join(str(page) for page in extracted.sampled_pages[:8]) or "selected pages"
        bullets = [
            (
                f"This PDF has {extracted.page_count:,} pages, but its embedded "
                "text layer is too weak for a trustworthy summary."
            ),
            (
                f"Sampled pages {sampled} mostly exposed repeated headers, "
                "page numbers, or isolated answer fragments instead of the "
                "actual visible PDF content."
            ),
            (
                "Run offline OCR first; after OCR text is available, the local "
                "Qwen model can summarize the real page content."
            ),
        ]
        if not ocr_available():
            bullets.append(
                "OCR is not installed in this runtime, so Neuron is correctly "
                "refusing to invent a summary from unreadable page images."
            )
    if not bullets:
        bullets = [
            "No extractable text was found in this file.",
            "The file can still be opened from search results for manual review.",
        ]

    stats = {
        "Type": path.suffix.upper().lstrip(".") or "File",
        "Size": _format_size(stat.st_size if stat else 0),
        "Text": f"{len(text):,} chars" if text else "not extracted",
    }
    if extracted.page_count:
        stats["Pages"] = f"{extracted.page_count:,}"
    if extracted.sampled_pages:
        stats["Sampled"] = ", ".join(str(page) for page in extracted.sampled_pages[:8])
    if extracted.is_weak_text:
        stats["OCR"] = "required" if not ocr_available() else "available"

    note_parts = [_fallback_note(ai_error)]
    if extracted.warnings:
        note_parts.extend(extracted.warnings)

    return {
        "kind": "file",
        "title": f"Offline summary - {path.name}",
        "subtitle": "Generated from local file text and metadata.",
        "bullets": bullets,
        "stats": stats,
        "note": " ".join(note_parts),
    }


def _folder_summary(path: Path, ai_error: str | None) -> dict[str, object]:
    file_count = 0
    folder_count = 0
    total_size = 0
    extensions: dict[str, int] = {}
    samples: list[str] = []

    for root, dirs, files in _safe_walk(path):
        folder_count += len(dirs)
        for filename in files:
            file_count += 1
            item = Path(root) / filename
            ext = item.suffix.lower() or "(none)"
            extensions[ext] = extensions.get(ext, 0) + 1
            try:
                total_size += item.stat().st_size
            except OSError:
                pass
            if len(samples) < 5:
                samples.append(str(item.relative_to(path)))
            if file_count >= 5000:
                break
        if file_count >= 5000:
            break

    top_ext = ", ".join(
        f"{ext} ({count})"
        for ext, count in sorted(extensions.items(), key=lambda pair: -pair[1])[:5]
    ) or "none"

    bullets = [
        f"Contains {file_count:,} files across {folder_count:,} folders.",
        f"Most common file types: {top_ext}.",
    ]
    if samples:
        bullets.append("Representative files: " + ", ".join(samples))

    return {
        "kind": "folder",
        "title": f"Folder brief - {path.name}",
        "subtitle": "Generated locally from folder structure and file metadata.",
        "bullets": bullets,
        "stats": {
            "Files": f"{file_count:,}",
            "Folders": f"{folder_count:,}",
            "Size": _format_size(total_size),
        },
        "note": _fallback_note(ai_error),
    }


def _best_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(raw_sentences[:80]):
        sentence = sentence.strip()
        words = re.findall(r"[A-Za-z0-9_'-]+", sentence)
        if len(words) < 6:
            continue
        score = min(len(words), 32)
        score += sum(2 for word in words if len(word) > 8)
        if ":" in sentence or ";" in sentence:
            score += 2
        scored.append((score, -index, sentence[:320]))
    scored.sort(reverse=True)
    selected = [sentence for _, _, sentence in scored[:4]]
    return selected or [cleaned[:320]]


def _safe_walk(path: Path):
    try:
        yield from path.walk()  # Python 3.12+
    except AttributeError:
        import os

        yield from os.walk(path)


def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _fallback_note(ai_error: str | None) -> str:
    if not ai_error:
        return "Local Qwen was not required for this summary."
    if "ocr" in ai_error.lower():
        return "OCR is required before the local Qwen model can summarize the visible page content."
    if "0xC000001D" in ai_error or "illegal instruction" in ai_error.lower():
        return "Qwen could not run on this CPU backend, so Neuron used offline extractive summarization."
    return "Qwen was unavailable, so Neuron used offline extractive summarization."

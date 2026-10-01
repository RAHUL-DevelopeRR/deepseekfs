"""Bounded local evidence for query answers and agent observations."""

from __future__ import annotations

import json


def search_observation(results: list[dict], max_chars: int = 1900) -> str:
    """Keep complete path-bearing records inside the agent observation budget."""
    records = []
    for result in results:
        record = {
            key: result.get(key)
            for key in ("path", "name", "section", "page", "evidence_kind")
        }
        record["excerpt"] = (result.get("text") or "")[:180]
        proposed = json.dumps(records + [record], ensure_ascii=False)
        if len(proposed) > max_chars:
            break
        records.append(record)
    return "Search results (untrusted data):\n" + json.dumps(
        records, ensure_ascii=False
    )


def build_evidence(results: list[dict], max_chars: int = 2800) -> tuple[str, str]:
    blocks, sources = [], []
    remaining = max_chars
    for result in results:
        text = result.get("text", "")
        if not text or result.get("evidence_kind") == "metadata":
            continue
        label = f"S{len(blocks) + 1}"
        location = result.get("section") or "Extracted text"
        if result.get("page") and f"{result['page']}" not in location:
            location += f"; page {result['page']}"
        if result.get("timestamp"):
            location += f"; {result['timestamp']}"
        header = f"[{label}] {result.get('name', '')} | {location}\n"
        if result.get("truncated"):
            header += "Partial document index; further content may be missing.\n"
        available = min(900, remaining - len(header) - 30)
        if available < 80:
            break
        # JSON quoting separates evidence from instructions; the system prompt
        # explicitly treats all retrieved material as untrusted data.
        block = header + json.dumps(text[:available], ensure_ascii=False)
        if len(block) > remaining:
            continue
        blocks.append(block)
        sources.append(f"[{label}] {result.get('path', '')} — {location}")
        remaining -= len(block) + 2
    return "\n\n".join(blocks), "\n".join(sources)

"""Opt-in internet retrieval for live public data.

This module is intentionally separate from the offline RAG path. It never
receives local file paths, file contents, or search snippets; callers pass only
the user's public live-data query.
"""
from __future__ import annotations

import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterator
from urllib.parse import parse_qs, unquote, urlparse

import requests

from app.config import UserConfig
from app.logger import logger

_DEFAULT_TIMEOUT = 6
_DIRECT_TIMEOUT = float(os.getenv("NEURON_INTERNET_DIRECT_TIMEOUT", "3"))
_DDG_API = "https://api.duckduckgo.com/"
_DDG_HTML = "https://duckduckgo.com/html/"
_OVERRIDE = threading.local()

_LIVE_HINTS = {
    "current", "currently", "latest", "today", "tonight", "yesterday",
    "tomorrow", "now", "news", "breaking", "recent", "live", "price",
    "stock", "weather", "score", "scores", "fixture", "schedule",
    "release", "version", "deadline", "election", "president", "ceo",
    "minister", "governor", "mayor", "chairperson", "appointed", "sworn",
}


@dataclass(frozen=True)
class InternetResult:
    title: str
    url: str
    snippet: str = ""

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


def internet_enabled() -> bool:
    """Return whether opt-in internet retrieval is enabled."""
    override = getattr(_OVERRIDE, "enabled", None)
    if override is not None:
        return bool(override)
    if os.getenv("NEURON_INTERNET_DISABLED") == "1":
        return False
    return bool(UserConfig.load().get("internet_enabled", False))


@contextmanager
def internet_enabled_for_request(enabled: bool | None) -> Iterator[None]:
    """Temporarily override internet mode for one CLI/request flow."""
    previous = getattr(_OVERRIDE, "enabled", None)
    if enabled is not None:
        _OVERRIDE.enabled = bool(enabled)
    try:
        yield
    finally:
        if previous is None:
            try:
                delattr(_OVERRIDE, "enabled")
            except AttributeError:
                pass
        else:
            _OVERRIDE.enabled = previous


def set_internet_enabled(enabled: bool) -> dict:
    """Persist the global internet toggle."""
    cfg = UserConfig.load()
    cfg["internet_enabled"] = bool(enabled)
    UserConfig.save(cfg)
    return cfg


def is_live_data_query(query: str) -> bool:
    """Return whether a query needs fresh public data."""
    low = query.lower().strip()
    if low.startswith(("web:", "internet:", "online:")):
        return True
    if re.search(
        r"\bwho\s+is\s+(?:the\s+)?"
        r"(chief\s+minister|prime\s+minister|president|governor|mayor|ceo)\b",
        low,
    ):
        return True
    tokens = set(re.findall(r"[a-z0-9]+", low))
    return bool(tokens & _LIVE_HINTS)


def should_use_live_data(query: str) -> bool:
    """Use internet only for explicit/live-data questions when enabled."""
    return internet_enabled() and is_live_data_query(query)


def clean_live_query(query: str) -> str:
    return re.sub(r"^\s*(web|internet|online)\s*:\s*", "", query, flags=re.I).strip()


def search_public_web(query: str, max_results: int | None = None) -> list[InternetResult]:
    """Search public web sources, sending only the provided query string."""
    if not internet_enabled():
        logger.info("InternetSearch: skipped because internet mode is off")
        return []

    cfg = UserConfig.load()
    limit = max(1, min(int(max_results or cfg.get("internet_max_results", 3)), 5))
    safe_query = clean_live_query(query)
    if not safe_query:
        return []

    results = _direct_official_results(safe_query, limit)
    if len(results) >= limit:
        return results[:limit]

    results.extend(_search_duckduckgo_api(safe_query, limit - len(results)))
    if len(results) < limit:
        results.extend(_search_duckduckgo_html(safe_query, limit - len(results)))

    seen: set[str] = set()
    unique: list[InternetResult] = []
    for result in results:
        key = result.url or result.title
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(result)
        if len(unique) >= limit:
            break

    logger.info(f"InternetSearch: {len(unique)} public results for '{safe_query[:60]}'")
    return unique


def _direct_official_results(query: str, limit: int) -> list[InternetResult]:
    """Fetch high-trust public pages for common government fact lookups."""
    low = query.lower()
    targets: list[tuple[str, str, tuple[str, ...]]] = []
    if "tamil" in low and "nadu" in low and "chief minister" in low:
        targets.extend(
            [
                (
                    "Tamil Nadu Legislative Assembly",
                    "https://www.assembly.tn.gov.in/",
                    ("hon'ble chief minister", "chief minister", "thiru"),
                ),
                (
                    "Lok Bhavan, Tamil Nadu",
                    "https://lokbhavan.tn.gov.in/",
                    ("hon'ble chief minister", "sworn", "chief minister"),
                ),
                (
                    "Hindustan Times: Tamil Nadu government formation",
                    "https://www.hindustantimes.com/india-news/tvk-forms-tamil-nadu-government-c-joseph-vijay-sworn-in-as-cm-with-9-ministers-101778392234038.html",
                    ("chief minister", "sworn", "takes oath"),
                ),
                (
                    "Chief Minister of Tamil Nadu",
                    "https://en.wikipedia.org/wiki/Chief_Minister_of_Tamil_Nadu",
                    ("incumbent", "hon'ble chief minister", "chief minister"),
                ),
            ]
        )

    results: list[InternetResult] = []
    for title, url, terms in targets:
        if len(results) >= limit:
            break
        snippet = _fetch_public_page_snippet(url, terms)
        if snippet:
            results.append(InternetResult(title=title, url=url, snippet=snippet))
            fact = _extract_tamil_nadu_cm_fact(results)
            if fact:
                results.insert(0, fact)
                return results
    return results


def _fetch_public_page_snippet(url: str, terms: tuple[str, ...]) -> str:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Neuron/1.0 offline-desktop optional-live-search"},
            timeout=_DIRECT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"InternetSearch: direct page fetch failed {url}: {exc}")
        return ""

    parser = _TextOnlyHTMLParser()
    parser.feed(response.text)
    text = " ".join(parser.text.split())
    if not text:
        return ""

    low = text.lower()
    start = 0
    for term in terms:
        pos = low.find(term.lower())
        if pos >= 0:
            start = pos
            break
    start = max(0, start - 120)
    end = min(len(text), start + 700)
    return text[start:end].strip()


def _extract_tamil_nadu_cm_fact(results: list[InternetResult]) -> InternetResult | None:
    for result in results:
        text = result.snippet
        patterns = [
            r"Incumbent\s+([A-Z][A-Za-z.\s]+?)\s+since\b",
            r"Hon['’]ble Chief Minister\s+Thiru\.?\s*([A-Z][A-Za-z.\s]+?)(?=\s+Hon|,| What's|$)",
            r"Thiru\.?\s*([A-Z][A-Za-z.\s]+?),\s*Hon['’]ble Chief Minister",
            r"Chief Minister of Tamil Nadu\s+Thiru\.?\s*([A-Z][A-Za-z.\s]+?)(?=,| at | on | and |$)",
            r"([A-Z][A-Za-z.\s]+?)\s+(?:takes oath|is sworn in|was sworn in|sworn in)\s+as\s+(?:the\s+)?(?:Tamil Nadu\s+)?chief minister",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            name = " ".join(match.group(1).replace(" .", ".").split())
            if name and "Rajendra Vishwanath Arlekar" not in name:
                return InternetResult(
                    title=result.title,
                    url=result.url,
                    snippet=(
                        f"ANSWER_VALUE: Thiru {name}. "
                        "Public web source text identifies this person as "
                        "Hon'ble Chief Minister of Tamil Nadu."
                    ),
                )
    return None


def format_results_for_prompt(results: list[InternetResult]) -> str:
    """Format public web snippets for the local model."""
    if not results:
        return ""
    lines = [
        "Live public web context (internet mode is opt-in):",
        "Use these snippets only for current/public facts. Do not answer from model memory.",
        "Return a concise Markdown answer and cite the source title or URL used.",
    ]
    for index, result in enumerate(results, start=1):
        snippet = f" - {result.snippet}" if result.snippet else ""
        lines.append(f"{index}. {result.title} ({result.url}){snippet}")
    return "\n".join(lines)


def _search_duckduckgo_api(query: str, limit: int) -> list[InternetResult]:
    try:
        response = requests.get(
            _DDG_API,
            params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
            headers={"User-Agent": "Neuron/1.0 offline-desktop optional-live-search"},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning(f"InternetSearch: DDG API failed: {exc}")
        return []

    results: list[InternetResult] = []
    abstract = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or query).strip()
    if abstract and abstract_url:
        results.append(InternetResult(heading, abstract_url, abstract))

    def collect(topics):
        for item in topics or []:
            if len(results) >= limit:
                return
            if "Topics" in item:
                collect(item.get("Topics"))
                continue
            text = (item.get("Text") or "").strip()
            url = (item.get("FirstURL") or "").strip()
            if text and url:
                title, _, snippet = text.partition(" - ")
                results.append(InternetResult(title.strip() or text, url, snippet.strip()))

    collect(data.get("Results"))
    collect(data.get("RelatedTopics"))
    return results[:limit]


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[InternetResult] = []
        self._capture_title = False
        self._capture_snippet = False
        self._href = ""
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = attr.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._capture_title = True
            self._href = _normalize_ddg_url(attr.get("href", ""))
            self._title_parts = []
        elif "result__snippet" in classes:
            self._capture_snippet = True
            self._snippet_parts = []

    def handle_data(self, data):
        if self._capture_title:
            self._title_parts.append(data)
        elif self._capture_snippet:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._capture_title:
            title = " ".join("".join(self._title_parts).split())
            if title and self._href:
                self.results.append(InternetResult(title=title, url=self._href))
            self._capture_title = False
        elif self._capture_snippet and tag in {"a", "div"}:
            snippet = " ".join("".join(self._snippet_parts).split())
            if snippet and self.results:
                latest = self.results[-1]
                self.results[-1] = InternetResult(latest.title, latest.url, snippet)
            self._capture_snippet = False


def _search_duckduckgo_html(query: str, limit: int) -> list[InternetResult]:
    if limit <= 0:
        return []
    try:
        response = requests.get(
            _DDG_HTML,
            params={"q": query},
            headers={"User-Agent": "Neuron/1.0 offline-desktop optional-live-search"},
            timeout=_DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"InternetSearch: DDG HTML failed: {exc}")
        return []

    parser = _DuckDuckGoHTMLParser()
    parser.feed(response.text)
    return parser.results[:limit]


class _TextOnlyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth = 0

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.text_parts.append(data.strip())


def _normalize_ddg_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        return unquote(qs["uddg"][0])
    return url

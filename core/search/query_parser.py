"""
Query Intent Parser for DeepSeekFS (v2.0)
==========================================
Extracts file type, path filters, size filters, and negations
from natural language queries.

Examples:
  "python files about ML"            -> ("ML", [".py"], None, None, [])
  "large pdfs in downloads"          -> ("", [".pdf"], "downloads", ">50MB", [])
  "code files not in downloads"      -> ("", [code exts], None, None, ["downloads"])
  "docs about SWOT"                  -> ("SWOT", [".pdf",".docx",...], None, None, [])
"""
import re
import os
from pathlib import Path
from typing import Tuple, List, Optional

# ── Extension aliases ─────────────────────────────────────────────────────
EXT_MAP = {
    # Programming languages
    "python":       [".py", ".ipynb"],
    "py":           [".py"],
    "javascript":   [".js", ".ts", ".jsx", ".tsx"],
    "js":           [".js"],
    "typescript":   [".ts", ".tsx"],
    "ts":           [".ts"],
    "java":         [".java"],
    "c++":          [".cpp", ".hpp", ".cc"],
    "cpp":          [".cpp", ".hpp"],
    "c#":           [".cs"],
    "cs":           [".cs"],
    "rust":         [".rs"],
    "rs":           [".rs"],
    "go":           [".go"],
    "golang":       [".go"],
    "html":         [".html", ".htm"],
    "css":          [".css"],
    "json":         [".json"],
    "csv":          [".csv"],

    # Documents
    "excel":        [".xlsx", ".xls"],
    "spreadsheet":  [".xlsx", ".xls", ".csv"],
    "word":         [".docx", ".doc"],
    "doc":          [".docx", ".doc"],
    "docx":         [".docx"],
    "document":     [".docx", ".doc", ".pdf", ".txt"],

    # PDF
    "pdf":          [".pdf"],
    "pdfs":         [".pdf"],

    # Presentations
    "powerpoint":   [".pptx", ".ppt"],
    "ppt":          [".pptx", ".ppt"],
    "pptx":         [".pptx"],
    "presentation": [".pptx", ".ppt"],
    "presentations":[".pptx", ".ppt"],
    "slide":        [".pptx", ".ppt"],
    "slides":       [".pptx", ".ppt"],

    # Text
    "text":         [".txt", ".md"],
    "txt":          [".txt"],
    "markdown":     [".md"],
    "md":           [".md"],

    # Media
    "video":        [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "movie":        [".mp4", ".mkv", ".avi", ".mov"],
    "image":        [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
    "photo":        [".png", ".jpg", ".jpeg"],
    "picture":      [".png", ".jpg", ".jpeg", ".gif", ".webp"],

    # Notebooks
    "notebook":     [".ipynb"],
    "ipynb":        [".ipynb"],
    "jupyter":      [".ipynb"],

    # Config
    "config":       [".env", ".ini", ".toml", ".cfg", ".yaml", ".yml"],
    "yaml":         [".yaml", ".yml"],
    "toml":         [".toml"],

    # Logs
    "log":          [".log"],
    "logs":         [".log"],
}

# ── Fuzzy groups ──────────────────────────────────────────────────────────
FUZZY_GROUPS = {
    "code": [".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
             ".java", ".cpp", ".c", ".h", ".cs", ".rb", ".php",
             ".swift", ".kt"],
    "docs": [".pdf", ".docx", ".doc", ".md", ".txt", ".pptx"],
    "documents": [".pdf", ".docx", ".doc", ".md", ".txt", ".pptx"],
    "images": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "media": [".mp4", ".mkv", ".avi", ".mov", ".png", ".jpg", ".jpeg",
              ".gif", ".webp"],
    "spreadsheets": [".xlsx", ".xls", ".csv"],
    "configs": [".env", ".ini", ".toml", ".cfg", ".yaml", ".yml"],
}

# Context words that confirm file-type intent
_FILE_CONTEXT_WORDS = {
    "file", "files", "document", "documents", "docs", "doc",
    "presentation", "presentations", "spreadsheet", "spreadsheets",
    "code", "script", "scripts", "program", "programs",
    "report", "reports", "sheet", "sheets",
}

# Strong keywords that always trigger extension filtering
_STRONG_KEYWORDS = {
    "pdf", "pdfs", "ppt", "pptx", "docx", "csv", "excel",
    "powerpoint", "spreadsheet", "spreadsheets",
    "presentation", "presentations", "slide", "slides",
    "notebook", "jupyter", "ipynb",
}

# Noise words to strip for cleaner semantic query
_NOISE_WORDS = {
    "file", "files", "document", "documents", "docs",
    "show", "find", "search", "get", "give", "list",
    "me", "my", "the", "all", "for", "about", "with",
    "related", "regarding", "on", "of", "in", "from",
    "large", "small", "big", "tiny", "not",
}

# ── Path keywords ────────────────────────────────────────────────────────
_PATH_KEYWORDS = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
    "pictures": "Pictures",
    "videos": "Videos",
    "music": "Music",
    "onedrive": "OneDrive",
}


def extract_intent(query: str) -> Tuple[str, List[str], Optional[str], Optional[str], List[str]]:
    """
    Parse a natural-language query to extract:
      1. cleaned_query   – the semantic part to embed
      2. target_exts     – file extensions to filter by (may be empty)
      3. path_filter     – directory name to restrict to (e.g. "Downloads")
      4. size_filter     – "large" or "small" or None
      5. excluded_paths  – list of directory names to exclude

    Returns (cleaned_query, target_extensions, path_filter, size_filter, excluded_paths).
    """
    query_lower = query.lower().strip()
    words = query_lower.split()
    found_exts: set = set()
    keep_words: list = []
    skip_next = False
    path_filter: Optional[str] = None
    size_filter: Optional[str] = None
    excluded_paths: List[str] = []
    negate_next = False

    for i, w in enumerate(words):
        if skip_next:
            skip_next = False
            continue

        w_clean = re.sub(r'[^\w#+.]', '', w)

        # ── Negation detection ──────────────────────
        if w_clean == "not":
            negate_next = True
            continue

        # ── Path filter: "in downloads" / "not in downloads" ──
        if w_clean == "in" and i + 1 < len(words):
            next_w = re.sub(r'[^\w]', '', words[i + 1]).lower()
            if next_w in _PATH_KEYWORDS:
                if negate_next:
                    excluded_paths.append(_PATH_KEYWORDS[next_w])
                    negate_next = False
                else:
                    path_filter = _PATH_KEYWORDS[next_w]
                skip_next = True
                continue

        # ── Size filter ─────────────────────────────
        if w_clean in ("large", "big", "huge"):
            size_filter = "large"
            negate_next = False
            continue
        if w_clean in ("small", "tiny", "little"):
            size_filter = "small"
            negate_next = False
            continue

        negate_next = False

        # ── Fuzzy group match: "code files", "docs" ──
        if w_clean in FUZZY_GROUPS:
            found_exts.update(FUZZY_GROUPS[w_clean])
            next_word = ""
            if i + 1 < len(words):
                next_word = re.sub(r'[^\w]', '', words[i + 1])
            if next_word in _FILE_CONTEXT_WORDS:
                skip_next = True
            continue

        # ── Exact extension alias match ──────────────
        if w_clean in EXT_MAP:
            next_word = ""
            if i + 1 < len(words):
                next_word = re.sub(r'[^\w]', '', words[i + 1])

            if w_clean in _STRONG_KEYWORDS:
                found_exts.update(EXT_MAP[w_clean])
                if next_word in _FILE_CONTEXT_WORDS:
                    skip_next = True
                continue

            if next_word in _FILE_CONTEXT_WORDS:
                found_exts.update(EXT_MAP[w_clean])
                skip_next = True
                continue

            keep_words.append(w)
        elif w.startswith(".") and w[1:] in EXT_MAP:
            found_exts.update(EXT_MAP[w[1:]])
        else:
            keep_words.append(w)

    # Clean noise words from semantic query
    semantic_words = [w for w in keep_words if w not in _NOISE_WORDS]

    cleaned_query = " ".join(semantic_words).strip()

    # Fallback: if query is too short, use original
    if not cleaned_query or len(cleaned_query) < 2:
        cleaned_query = query

    return cleaned_query, list(found_exts), path_filter, size_filter, excluded_paths

"""
Query Intent Parser for DeepSeekFS
===================================
Extracts file type intentions and semantic context from natural language queries.
Examples:
  "python files about machine learning" -> (["machine learning"], [".py", ".ipynb"])
  "show me pdfs"                        -> ([""], [".pdf"])
  "fibonacci code"                      -> (["fibonacci code"], [])
"""
import re
from typing import Tuple, List

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
}

# Words that, when following a type keyword, confirm it's a file-type intent
_FILE_CONTEXT_WORDS = {
    "file", "files", "document", "documents", "docs", "doc",
    "presentation", "presentations", "spreadsheet", "spreadsheets",
    "code", "script", "scripts", "program", "programs",
    "report", "reports", "sheet", "sheets",
}

# Strong keywords that always trigger extension filtering (no context word needed)
_STRONG_KEYWORDS = {
    "pdf", "pdfs", "ppt", "pptx", "docx", "csv", "excel",
    "powerpoint", "spreadsheet", "spreadsheets",
    "presentation", "presentations", "slide", "slides",
}

# Words to strip when they appear on their own (noise for semantic search)
_NOISE_WORDS = {
    "file", "files", "document", "documents", "docs",
    "show", "find", "search", "get", "give", "list",
    "me", "my", "the", "all", "for", "about", "with",
    "related", "regarding", "on", "of", "in", "from",
}


def extract_intent(query: str) -> Tuple[str, List[str]]:
    """
    Parse a natural-language search query to extract:
      1. cleaned_query  – the semantic part to embed
      2. target_exts    – list of file extensions to filter by (may be empty)

    Returns (cleaned_query, target_extensions).
    """
    query_lower = query.lower().strip()
    words = query_lower.split()
    found_exts: set = set()
    keep_words: list = []
    skip_next = False

    for i, w in enumerate(words):
        if skip_next:
            skip_next = False
            continue

        # Strip punctuation for matching
        w_clean = re.sub(r'[^\w#+.]', '', w)

        # Check if this word is a known file-type alias
        if w_clean in EXT_MAP:
            next_word = ""
            if i + 1 < len(words):
                next_word = re.sub(r'[^\w]', '', words[i + 1])

            # Case 1: strong keyword → always filter
            if w_clean in _STRONG_KEYWORDS:
                found_exts.update(EXT_MAP[w_clean])
                # If next word is a context word, skip it too
                if next_word in _FILE_CONTEXT_WORDS:
                    skip_next = True
                continue

            # Case 2: followed by a file-context word ("python files")
            if next_word in _FILE_CONTEXT_WORDS:
                found_exts.update(EXT_MAP[w_clean])
                skip_next = True
                continue

            # Case 3: preceded by a dot (".py")
            # Not a type match, just a regular word
            keep_words.append(w)
        elif w.startswith(".") and w[1:] in EXT_MAP:
            # Explicit extension like ".py"
            found_exts.update(EXT_MAP[w[1:]])
        else:
            keep_words.append(w)

    # Clean noise words from the semantic query
    semantic_words = [w for w in keep_words if w not in _NOISE_WORDS]

    # If we stripped too much, fall back to original minus type keywords
    if not semantic_words:
        semantic_words = [w for w in keep_words if w not in _NOISE_WORDS]

    cleaned_query = " ".join(semantic_words).strip()

    # Final fallback: if query is completely empty, use original
    if not cleaned_query or len(cleaned_query) < 2:
        cleaned_query = query

    return cleaned_query, list(found_exts)

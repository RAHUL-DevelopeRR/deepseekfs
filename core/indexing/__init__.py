"""Indexing sub-package — public API."""

from core.indexing import index_builder  # noqa: F401 — expose for patch targets
from core.indexing.index_builder import IndexBuilder, get_index

__all__ = ["IndexBuilder", "get_index"]

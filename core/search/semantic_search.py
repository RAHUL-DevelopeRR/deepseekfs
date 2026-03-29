"""Semantic search — uses the shared global index (v2.0)

Upgraded hybrid scoring:
  combined = 0.55×semantic + 0.20×time + 0.10×size + 0.10×depth + 0.05×access
Plus keyword bonuses and path/size/negation pre-filters.
"""
import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.time.scoring import (
    calculate_time_score, get_time_multiplier,
    extract_time_target, calculate_target_time_score,
)
from core.indexing.index_builder import get_index
from core.search.query_parser import extract_intent


# ── Size thresholds for filters ──────────────────────────────
_LARGE_FILE_THRESHOLD = 50 * 1024 * 1024   # 50 MB
_SMALL_FILE_THRESHOLD = 1 * 1024 * 1024    # 1 MB


class SemanticSearch:
    """Search engine that always reads from the shared singleton index."""

    def __init__(self):
        self.embedder = get_embedder()

    def search(
        self,
        query: str,
        top_k: int = config.TOP_K,
        use_time_ranking: bool = True,
    ) -> List[Dict]:
        index_builder = get_index()

        if index_builder.index is None or index_builder.index.ntotal == 0:
            logger.warning("Index is empty. Indexing may still be running.")
            return []

        try:
            # ── Parse query for date targets ──────────────────
            target_time, cleaned_query = extract_time_target(query)

            # ── Parse query for intent (exts, path, size, negation) ──
            cleaned_query, target_exts, path_filter, size_filter, excluded_paths = \
                extract_intent(cleaned_query)

            # Use cleaned query for embedding
            search_text = cleaned_query if len(cleaned_query) >= 3 else query
            query_embedding = self.embedder.encode_single(search_text)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            # Search wider when filtering
            search_limit = top_k * 10 if (target_exts or path_filter or size_filter) else top_k * 3
            distances, indices = index_builder.search_raw(query_embedding, search_limit)

            results = []
            time_multiplier = get_time_multiplier(query) if use_time_ranking else 1.0
            home_str = str(Path.home()).lower()

            for i, idx in enumerate(indices):
                if idx < 0:
                    continue

                meta = index_builder.get_metadata_by_faiss_id(int(idx))
                if meta is None:
                    continue

                file_path = meta.get("path", "")
                ext = meta.get("extension", "").lower()
                file_size = meta.get("size", 0)
                file_path_lower = file_path.lower()

                # ── Extension filter ──────────────────────────
                if target_exts and ext not in target_exts:
                    continue

                # ── Path filter ───────────────────────────────
                if path_filter:
                    if path_filter.lower() not in file_path_lower:
                        continue

                # ── Excluded paths ────────────────────────────
                if excluded_paths:
                    skip = False
                    for exc in excluded_paths:
                        if exc.lower() in file_path_lower:
                            skip = True
                            break
                    if skip:
                        continue

                # ── Size filter ───────────────────────────────
                if size_filter == "large" and file_size < _LARGE_FILE_THRESHOLD:
                    continue
                if size_filter == "small" and file_size > _SMALL_FILE_THRESHOLD:
                    continue

                # ── Base similarity ───────────────────────────
                distance = float(distances[i])
                base_similarity = 1 / (1 + distance)

                # ── Keyword / filename bonus ──────────────────
                name_lower = meta.get("name", "").lower()
                query_lower = search_text.lower().strip()
                query_words = [w for w in query_lower.split() if len(w) >= 2]

                keyword_bonus = 0.0
                # Exact filename match (strongest signal)
                if query_lower and (query_lower == name_lower or
                                     query_lower == name_lower.rsplit('.', 1)[0]):
                    keyword_bonus = 0.85
                # Filename contains query
                elif query_lower and query_lower in name_lower:
                    keyword_bonus = 0.55
                # All query words in filename
                elif query_words and all(w in name_lower for w in query_words):
                    keyword_bonus = 0.35
                # Any query word in filename
                elif query_words and any(w in name_lower for w in query_words):
                    keyword_bonus = 0.15
                # Any query word in file path
                elif query_words and any(w in file_path_lower for w in query_words):
                    keyword_bonus = 0.08

                similarity = min(1.0, base_similarity + keyword_bonus)

                # ── Depth score (shallower = more important) ──
                sep_count = file_path.count(os.sep)
                depth_score = 1.0 / (1.0 + sep_count * 0.05)

                # ── Access frequency score ────────────────────
                open_count = index_builder.get_open_count(int(idx))
                access_score = min(1.0, open_count / 10.0)

                # ── Size signal ───────────────────────────────
                size_signal = 1.0 if file_size > 1000 else 0.5

                # ── Combined score ────────────────────────────
                if target_time is not None:
                    time_score = calculate_target_time_score(
                        meta.get("modified_time", 0), target_time
                    )
                    time_penalty = 1.0 if time_score > 0.5 else 0.1
                    combined_score = (
                        0.65 * similarity * time_penalty
                        + 0.25 * time_score
                        + 0.05 * depth_score
                        + 0.05 * access_score
                    )
                else:
                    time_score = calculate_time_score(meta.get("modified_time", 0))
                    combined_score = (
                        0.55 * similarity
                        + 0.20 * time_score * time_multiplier
                        + 0.10 * size_signal
                        + 0.10 * depth_score
                        + 0.05 * access_score
                    )

                results.append({
                    "path": file_path,
                    "name": meta["name"],
                    "extension": meta["extension"],
                    "size": file_size,
                    "modified_time": meta["modified_time"],
                    "semantic_score": round(similarity, 4),
                    "time_score": round(time_score, 4),
                    "combined_score": round(combined_score, 4),
                    "open_count": open_count,
                })

            results.sort(key=lambda x: x["combined_score"], reverse=True)

            # ── Direct filename search (catches what FAISS misses) ──
            result_paths = {r["path"] for r in results}
            query_lower = search_text.lower().strip()
            if query_lower and len(query_lower) >= 2:
                try:
                    db = index_builder._db
                    conn = db._conn()
                    # Search by filename LIKE pattern
                    pattern = f"%{query_lower}%"
                    rows = conn.execute(
                        "SELECT * FROM files WHERE LOWER(name) LIKE ? LIMIT ?",
                        (pattern, top_k)
                    ).fetchall()
                    for row in rows:
                        row_dict = dict(row)
                        fpath = row_dict["path"]
                        if fpath in result_paths:
                            continue
                        if not Path(fpath).exists():
                            continue
                        name = row_dict.get("name", "")
                        name_l = name.lower()
                        # Score: exact match > contains > partial
                        if query_lower == name_l or query_lower == name_l.rsplit('.', 1)[0]:
                            fn_score = 0.95
                        elif query_lower in name_l:
                            fn_score = 0.75
                        else:
                            fn_score = 0.60
                        results.append({
                            "path": fpath,
                            "name": name,
                            "extension": row_dict.get("extension", ""),
                            "size": row_dict.get("size", 0),
                            "modified_time": row_dict.get("modified_time", 0),
                            "semantic_score": round(fn_score, 4),
                            "time_score": 0.5,
                            "combined_score": round(fn_score, 4),
                            "open_count": row_dict.get("open_count", 0),
                        })
                        result_paths.add(fpath)
                except Exception as e:
                    logger.warning(f"Filename search fallback error: {e}")

                # Re-sort after merging filename matches
                results.sort(key=lambda x: x["combined_score"], reverse=True)

            results = results[:top_k]

            logger.info(f"Query: '{query}' -> {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

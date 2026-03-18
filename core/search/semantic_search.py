"""Semantic search - uses the shared global index"""
import numpy as np
from typing import List, Dict
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.time.scoring import calculate_time_score, get_time_multiplier, extract_time_target, calculate_target_time_score
from core.indexing.index_builder import get_index


class SemanticSearch:
    """Search engine that always reads from the shared singleton index"""

    def __init__(self):
        self.embedder = get_embedder()

    def search(
        self,
        query: str,
        top_k: int = config.TOP_K,
        use_time_ranking: bool = True
    ) -> List[Dict]:
        # Always fetch the live singleton index
        index_builder = get_index()

        if index_builder.index is None or len(index_builder.metadata) == 0:
            logger.warning("Index is empty. Indexing may still be running.")
            return []

        try:
            # Intercept date queries
            target_time, cleaned_query = extract_time_target(query)
            
            # Use cleaned query for embedding, if it became empty just use original
            search_text = cleaned_query if len(cleaned_query) >= 3 else query
            query_embedding = self.embedder.encode_single(search_text)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            distances, indices = index_builder.search_raw(query_embedding, top_k * 2)

            results = []
            time_multiplier = get_time_multiplier(query) if use_time_ranking else 1.0

            for i, idx in enumerate(indices):
                if idx < 0 or idx >= len(index_builder.metadata):
                    continue

                meta = index_builder.metadata[idx]
                distance = float(distances[i])
                similarity = 1 / (1 + distance)
                if target_time is not None:
                    # Strict target-based time scoring
                    time_score = calculate_target_time_score(meta.get("modified_time", 0), target_time)
                    # If it heavily mismatches the date, penalize the combined score significantly
                    time_penalty = 1.0 if time_score > 0.5 else 0.1
                    combined_score = (0.7 * similarity * time_penalty) + (0.3 * time_score)
                else:
                    time_score = calculate_time_score(meta.get("modified_time", 0))
                    combined_score = (
                        0.6 * similarity
                        + 0.25 * time_score * time_multiplier
                        + 0.15 * (1.0 if meta.get("size", 0) > 1000 else 0.5)
                    )

                results.append({
                    "path": meta["path"],
                    "name": meta["name"],
                    "extension": meta["extension"],
                    "size": meta["size"],
                    "modified_time": meta["modified_time"],
                    "semantic_score": round(similarity, 4),
                    "time_score": round(time_score, 4),
                    "combined_score": round(combined_score, 4),
                })

            results.sort(key=lambda x: x["combined_score"], reverse=True)
            logger.info(f"Query: '{query}' → {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

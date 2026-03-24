"""Semantic search - uses the shared global index"""
import numpy as np
from typing import List, Dict
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.time.scoring import calculate_time_score, get_time_multiplier, extract_time_target, calculate_target_time_score
from core.indexing.index_builder import get_index
from core.search.query_parser import extract_intent


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

        if index_builder.index is None or index_builder.index.ntotal == 0:
            logger.warning("Index is empty. Indexing may still be running.")
            return []

        try:
            # Intercept date queries
            target_time, cleaned_query = extract_time_target(query)
            
            # Intercept file type intents
            cleaned_query, target_exts = extract_intent(cleaned_query)
            
            # Use cleaned query for embedding, if it became empty just use original
            search_text = cleaned_query if len(cleaned_query) >= 3 else query
            query_embedding = self.embedder.encode_single(search_text)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            search_limit = top_k * 10 if target_exts else top_k * 2
            distances, indices = index_builder.search_raw(query_embedding, search_limit)

            results = []
            time_multiplier = get_time_multiplier(query) if use_time_ranking else 1.0

            for i, idx in enumerate(indices):
                if idx < 0:
                    continue

                meta = index_builder.get_metadata_by_faiss_id(int(idx))
                if meta is None:
                    continue
                    
                # Apply intent filtering
                ext = meta.get("extension", "").lower()
                if target_exts and ext not in target_exts:
                    continue

                distance = float(distances[i])
                base_similarity = 1 / (1 + distance)
                
                # --- HYBRID SEARCH: Keyword Bonus ---
                name_lower = meta.get("name", "").lower()
                query_lower = search_text.lower().strip()
                query_words = [w for w in query_lower.split() if len(w) > 2]
                
                keyword_bonus = 0.0
                if query_lower and query_lower in name_lower:
                    keyword_bonus = 0.40  # Massive boost for exact phrase match
                elif query_words and all(w in name_lower for w in query_words):
                    keyword_bonus = 0.25  # All words present in filename
                elif query_words and any(w in name_lower for w in query_words):
                    keyword_bonus = 0.10  # At least one word present
                    
                similarity = min(1.0, base_similarity + keyword_bonus)

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
            # Trim to top_k after all filtering
            results = results[:top_k]
            
            logger.info(f"Query: '{query}' -> {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

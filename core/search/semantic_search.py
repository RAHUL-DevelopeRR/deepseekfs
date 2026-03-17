"""Semantic search using FAISS"""
import faiss
import numpy as np
import pickle
from typing import List, Dict, Tuple
from pathlib import Path
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.time.scoring import calculate_time_score, get_time_multiplier

class SemanticSearch:
    """Semantic search engine"""
    
    def __init__(self):
        self.embedder = get_embedder()
        self.index = None
        self.metadata = []
        self.load_index()
    
    def load_index(self):
        """Load FAISS index and metadata"""
        index_path = config.FAISS_INDEX_PATH
        metadata_path = config.METADATA_PATH
        
        if Path(index_path).exists() and Path(metadata_path).exists():
            self.index = faiss.read_index(index_path)
            with open(metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
            logger.info(f"Search index loaded. Documents: {len(self.metadata)}")
        else:
            logger.warning("No index found. Please run initial_index.py first.")
    
    def search(
        self,
        query: str,
        top_k: int = config.TOP_K,
        use_time_ranking: bool = True
    ) -> List[Dict]:
        """Search for files"""
        if self.index is None or len(self.metadata) == 0:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode_single(query)
            query_embedding = np.array([query_embedding], dtype=np.float32)
            
            # FAISS search
            distances, indices = self.index.search(query_embedding, min(top_k, len(self.metadata)))
            
            results = []
            time_multiplier = get_time_multiplier(query) if use_time_ranking else 1.0
            
            for i, idx in enumerate(indices[0]):
                if idx >= len(self.metadata):
                    continue
                
                metadata = self.metadata[idx]
                distance = float(distances[0][i])
                
                # Convert L2 distance to similarity score (0-1)
                similarity = 1 / (1 + distance)
                
                # Calculate time score
                modified_time = metadata.get('modified_time', 0)
                time_score = calculate_time_score(modified_time)
                
                # Combined score
                combined_score = (
                    0.6 * similarity +
                    0.25 * time_score * time_multiplier +
                    0.15 * (1.0 if metadata.get('size', 0) > 1000 else 0.5)  # Frequency proxy
                )
                
                results.append({
                    "path": metadata["path"],
                    "name": metadata["name"],
                    "extension": metadata["extension"],
                    "size": metadata["size"],
                    "modified_time": metadata["modified_time"],
                    "semantic_score": round(similarity, 4),
                    "time_score": round(time_score, 4),
                    "combined_score": round(combined_score, 4),
                })
            
            # Sort by combined score
            results.sort(key=lambda x: x["combined_score"], reverse=True)
            
            logger.info(f"Search query: '{query}' - Found {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

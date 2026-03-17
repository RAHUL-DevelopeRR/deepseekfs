"""Sentence Transformer Wrapper for Embeddings"""
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union
import app.config as config
from app.logger import logger

class Embedder:
    """Generate embeddings using sentence-transformers"""
    
    def __init__(self, model_name: str = config.MODEL_NAME):
        logger.info(f"Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        logger.info(f"Model loaded. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        batch_size: int = 32,
        show_progress_bar: bool = False
    ) -> np.ndarray:
        """Generate embeddings for texts"""
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=True
        )
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.encode([text])[0]

# Global embedder instance
_embedder_instance = None

def get_embedder() -> Embedder:
    """Get or create embedder singleton"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance

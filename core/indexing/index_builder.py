"""Build FAISS index from documents"""
import faiss
import numpy as np
import pickle
from typing import List, Dict
from pathlib import Path
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.ingestion.file_parser import FileParser

class IndexBuilder:
    """Build and manage FAISS index"""
    
    def __init__(self):
        self.embedder = get_embedder()
        self.index = None
        self.metadata = []
        self.load_or_create_index()
    
    def load_or_create_index(self):
        """Load existing index or create new"""
        index_path = config.FAISS_INDEX_PATH
        metadata_path = config.METADATA_PATH
        
        if Path(index_path).exists() and Path(metadata_path).exists():
            logger.info("Loading existing FAISS index...")
            self.index = faiss.read_index(index_path)
            with open(metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
            logger.info(f"Index loaded. Documents: {len(self.metadata)}")
        else:
            logger.info("Creating new FAISS index...")
            self.index = faiss.IndexFlatL2(config.EMBEDDING_DIM)
            self.metadata = []
    
    def add_file(self, file_path: str) -> bool:
        """Index a single file"""
        try:
            # Parse file
            text = FileParser.parse(file_path)
            if not text or len(text.strip()) < 10:
                logger.debug(f"Skipping empty file: {file_path}")
                return False
            
            # Generate embedding
            embedding = self.embedder.encode_single(text)
            embedding = np.array([embedding], dtype=np.float32)
            
            # Get metadata
            metadata = FileParser.get_file_metadata(file_path)
            
            # Add to FAISS
            self.index.add(embedding)
            self.metadata.append(metadata)
            
            logger.debug(f"Indexed: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")
            return False
    
    def index_directory(self, directory: str, recursive: bool = True) -> int:
        """Index all files in directory"""
        path = Path(directory)
        count = 0
        
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0
        
        pattern = "**/*" if recursive else "*"
        
        for file_path in path.glob(pattern):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in config.SUPPORTED_EXTENSIONS:
                    if self.add_file(str(file_path)):
                        count += 1
        
        logger.info(f"Indexed {count} files from {directory}")
        return count
    
    def save(self):
        """Save index to disk"""
        faiss.write_index(self.index, config.FAISS_INDEX_PATH)
        with open(config.METADATA_PATH, 'wb') as f:
            pickle.dump(self.metadata, f)
        logger.info(f"Index saved. Total documents: {len(self.metadata)}")
    
    def get_index_stats(self) -> Dict:
        """Get index statistics"""
        return {
            "total_documents": len(self.metadata),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": config.EMBEDDING_DIM,
        }

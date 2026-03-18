"""FAISS Index Builder - Singleton pattern so ALL modules share ONE index"""
import faiss
import numpy as np
import pickle
from typing import List, Dict, Set
from pathlib import Path
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.ingestion.file_parser import FileParser


class IndexBuilder:
    """Shared FAISS index with duplicate protection"""

    def __init__(self):
        self.embedder = get_embedder()
        self.index = None
        self.metadata: List[Dict] = []
        self.indexed_paths: Set[str] = set()
        self.load_or_create_index()

    def load_or_create_index(self):
        index_path = Path(config.FAISS_INDEX_PATH)
        metadata_path = Path(config.METADATA_PATH)
        indexed_paths_db = Path(config.INDEXED_PATHS_DB)

        if index_path.exists() and metadata_path.exists():
            try:
                self.index = faiss.read_index(str(index_path))
                with open(metadata_path, "rb") as f:
                    self.metadata = pickle.load(f)

                # Load or rebuild path set
                if indexed_paths_db.exists():
                    with open(indexed_paths_db, "rb") as f:
                        self.indexed_paths = pickle.load(f)
                else:
                    self.indexed_paths = {m["path"] for m in self.metadata}

                logger.info(f"Index loaded: {len(self.metadata)} documents")
            except Exception as e:
                logger.warning(f"Corrupt index, rebuilding: {e}")
                self._create_fresh_index()
        else:
            logger.info("No index found. Creating fresh index.")
            self._create_fresh_index()

    def _create_fresh_index(self):
        self.index = faiss.IndexFlatL2(config.EMBEDDING_DIM)
        self.metadata = []
        self.indexed_paths = set()

    def add_file(self, file_path: str) -> bool:
        norm_path = str(Path(file_path).resolve())

        if norm_path in self.indexed_paths:
            return False

        try:
            p = Path(norm_path)
            if not p.exists():
                return False
            if p.stat().st_size > config.MAX_FILE_SIZE_BYTES:
                return False

            text = FileParser.parse(norm_path)
            if not text or len(text.strip()) < 10:
                return False

            embedding = self.embedder.encode_single(text)
            embedding = np.array([embedding], dtype=np.float32)
            meta = FileParser.get_file_metadata(norm_path)

            self.index.add(embedding)
            self.metadata.append(meta)
            self.indexed_paths.add(norm_path)
            return True
        except Exception as e:
            logger.error(f"Error indexing {norm_path}: {e}")
            return False

    def index_directory(self, directory: str, recursive: bool = True) -> int:
        path = Path(directory)
        count = 0
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0

        pattern = "**/*" if recursive else "*"
        files = [
            f for f in path.glob(pattern)
            if f.is_file() and f.suffix.lower() in config.SUPPORTED_EXTENSIONS
        ]
        logger.info(f"Found {len(files)} candidate files in {directory}")
        for f in files:
            if self.add_file(str(f)):
                count += 1
        logger.info(f"Indexed {count} NEW files from {directory}")
        return count

    def save(self):
        faiss.write_index(self.index, config.FAISS_INDEX_PATH)
        with open(config.METADATA_PATH, "wb") as f:
            pickle.dump(self.metadata, f)
        with open(config.INDEXED_PATHS_DB, "wb") as f:
            pickle.dump(self.indexed_paths, f)
        logger.info(f"Index saved: {len(self.metadata)} total documents")

    def get_index_stats(self) -> Dict:
        return {
            "total_documents": len(self.metadata),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": config.EMBEDDING_DIM,
            "watch_paths": config.WATCH_PATHS,
        }

    def search_raw(self, query_embedding: np.ndarray, top_k: int):
        """Direct FAISS search on this index"""
        if self.index is None or len(self.metadata) == 0:
            return [], []
        k = min(top_k, len(self.metadata))
        distances, indices = self.index.search(query_embedding, k)
        return distances[0], indices[0]


# ─────────────────────────────────────────────────────────────
# GLOBAL SINGLETON  — import this everywhere
# ─────────────────────────────────────────────────────────────
_global_index: IndexBuilder = None

def get_index() -> IndexBuilder:
    global _global_index
    if _global_index is None:
        _global_index = IndexBuilder()
    return _global_index

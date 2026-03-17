"""Build FAISS index from documents"""
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
    """Build and manage FAISS index with duplicate protection"""

    def __init__(self):
        self.embedder = get_embedder()
        self.index = None
        self.metadata: List[Dict] = []
        self.indexed_paths: Set[str] = set()  # ← duplicate guard
        self.load_or_create_index()

    # ──────────────────────────────────────────────
    # Load / Create
    # ──────────────────────────────────────────────
    def load_or_create_index(self):
        index_path = config.FAISS_INDEX_PATH
        metadata_path = config.METADATA_PATH
        indexed_paths_db = config.INDEXED_PATHS_DB

        if Path(index_path).exists() and Path(metadata_path).exists():
            logger.info("Loading existing FAISS index...")
            self.index = faiss.read_index(index_path)
            with open(metadata_path, "rb") as f:
                self.metadata = pickle.load(f)

            # Load indexed paths set (or rebuild from metadata)
            if Path(indexed_paths_db).exists():
                with open(indexed_paths_db, "rb") as f:
                    self.indexed_paths = pickle.load(f)
            else:
                self.indexed_paths = {m["path"] for m in self.metadata}

            logger.info(f"Index loaded. Documents: {len(self.metadata)}")
        else:
            logger.info("Creating new FAISS index...")
            self.index = faiss.IndexFlatL2(config.EMBEDDING_DIM)
            self.metadata = []
            self.indexed_paths = set()

    # ──────────────────────────────────────────────
    # Add single file
    # ──────────────────────────────────────────────
    def add_file(self, file_path: str) -> bool:
        """Index a single file. Skips duplicates automatically."""
        norm_path = str(Path(file_path).resolve())

        # ── Duplicate guard ──
        if norm_path in self.indexed_paths:
            logger.debug(f"Already indexed, skipping: {norm_path}")
            return False

        try:
            # Size guard
            size = Path(norm_path).stat().st_size
            if size > config.MAX_FILE_SIZE_BYTES:
                logger.debug(f"File too large, skipping: {norm_path}")
                return False

            text = FileParser.parse(norm_path)
            if not text or len(text.strip()) < 10:
                logger.debug(f"Empty/unsupported file: {norm_path}")
                return False

            embedding = self.embedder.encode_single(text)
            embedding = np.array([embedding], dtype=np.float32)

            meta = FileParser.get_file_metadata(norm_path)

            self.index.add(embedding)
            self.metadata.append(meta)
            self.indexed_paths.add(norm_path)

            logger.debug(f"Indexed: {norm_path}")
            return True
        except Exception as e:
            logger.error(f"Error indexing {norm_path}: {e}")
            return False

    # ──────────────────────────────────────────────
    # Index entire directory
    # ──────────────────────────────────────────────
    def index_directory(self, directory: str, recursive: bool = True) -> int:
        path = Path(directory)
        count = 0

        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0

        pattern = "**/*" if recursive else "*"
        files = [f for f in path.glob(pattern)
                 if f.is_file() and f.suffix.lower() in config.SUPPORTED_EXTENSIONS]

        logger.info(f"Found {len(files)} candidate files in {directory}")

        for file_path in files:
            if self.add_file(str(file_path)):
                count += 1

        logger.info(f"Indexed {count} NEW files from {directory}")
        return count

    # ──────────────────────────────────────────────
    # Save
    # ──────────────────────────────────────────────
    def save(self):
        faiss.write_index(self.index, config.FAISS_INDEX_PATH)
        with open(config.METADATA_PATH, "wb") as f:
            pickle.dump(self.metadata, f)
        with open(config.INDEXED_PATHS_DB, "wb") as f:
            pickle.dump(self.indexed_paths, f)
        logger.info(f"Index saved. Total documents: {len(self.metadata)}")

    # ──────────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────────
    def get_index_stats(self) -> Dict:
        return {
            "total_documents": len(self.metadata),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": config.EMBEDDING_DIM,
            "watch_paths": config.WATCH_PATHS,
        }

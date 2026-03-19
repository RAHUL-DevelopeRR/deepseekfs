"""FAISS Index Builder — HNSW + SQLite backed (v2.0)

Singleton pattern so ALL modules share ONE index.
- IndexHNSWFlat for O(log n) approximate nearest-neighbour search
- SQLite for metadata (row-level updates, no full-RAM pickle load)
"""
import faiss
import numpy as np
import sqlite3
import threading
import os
from typing import List, Dict, Set
from pathlib import Path
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.ingestion.file_parser import FileParser


# ─────────────────────────────────────────────────────────────
# SQLite helper: one connection per thread
# ─────────────────────────────────────────────────────────────
class _MetadataDB:
    """Thread-safe SQLite wrapper for file metadata."""

    _CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS files (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        faiss_id     INTEGER NOT NULL,
        path         TEXT    NOT NULL UNIQUE,
        name         TEXT,
        size         INTEGER,
        modified_time REAL,
        created_time  REAL,
        extension    TEXT
    );
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        # Initialise the table on the creating thread
        self._conn().execute("PRAGMA journal_mode=WAL;")

    # ── connection per thread ──────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute(self._CREATE_TABLE)
            conn.commit()
            self._local.conn = conn
        return conn

    # ── public API ─────────────────────────────────────────────
    def contains(self, path: str) -> bool:
        row = self._conn().execute(
            "SELECT 1 FROM files WHERE path=? LIMIT 1", (path,)
        ).fetchone()
        return row is not None

    def insert(self, faiss_id: int, meta: Dict):
        self._conn().execute(
            """INSERT INTO files (faiss_id, path, name, size, modified_time, created_time, extension)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                faiss_id,
                meta["path"],
                meta["name"],
                meta["size"],
                meta["modified_time"],
                meta["created_time"],
                meta["extension"],
            ),
        )
        self._conn().commit()

    def get_by_faiss_id(self, fid: int) -> dict | None:
        row = self._conn().execute(
            "SELECT * FROM files WHERE faiss_id=? LIMIT 1", (fid,)
        ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def all_rows(self) -> List[Dict]:
        """Return all rows as list of dicts — backward compat with old .metadata list."""
        rows = self._conn().execute(
            "SELECT * FROM files ORDER BY faiss_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def all_paths(self) -> Set[str]:
        rows = self._conn().execute("SELECT path FROM files").fetchall()
        return {r[0] for r in rows}

    def drop_all(self):
        self._conn().execute("DELETE FROM files")
        self._conn().commit()

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None


# ─────────────────────────────────────────────────────────────
# IndexBuilder  (HNSW + SQLite)
# ─────────────────────────────────────────────────────────────
class IndexBuilder:
    """Shared FAISS HNSW index with SQLite metadata store"""

    HNSW_M = 32   # neighbours per graph node
    HNSW_EF_CONSTRUCTION = 40   # build-time search depth (higher = better recall)
    HNSW_EF_SEARCH = 64         # query-time search depth

    def __init__(self):
        self.embedder = get_embedder()
        self.index: faiss.Index | None = None
        self._db = _MetadataDB(config.SQLITE_DB_PATH)
        self.lock = threading.RLock()
        self._load_or_create_index()

    # ── backward compatibility ─────────────────────────────────
    @property
    def metadata(self) -> List[Dict]:
        """Backward-compatible property: returns all metadata rows as a list.
        Indexed by position so that metadata[faiss_id] works."""
        return self._db.all_rows()

    @property
    def indexed_paths(self) -> Set[str]:
        """Backward-compatible property."""
        return self._db.all_paths()

    # ── index lifecycle ────────────────────────────────────────
    def _load_or_create_index(self):
        index_path = Path(config.FAISS_INDEX_PATH)

        if index_path.exists() and self._db.count() > 0:
            try:
                self.index = faiss.read_index(str(index_path))
                logger.info(
                    f"HNSW index loaded: {self._db.count()} documents, "
                    f"FAISS vectors: {self.index.ntotal}"
                )
            except Exception as e:
                logger.warning(f"Corrupt index, rebuilding: {e}")
                self._create_fresh_index()
        else:
            logger.info("No index found. Creating fresh HNSW index.")
            self._create_fresh_index()

    def _create_fresh_index(self):
        self.index = faiss.IndexHNSWFlat(config.EMBEDDING_DIM, self.HNSW_M)
        self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        self.index.hnsw.efSearch = self.HNSW_EF_SEARCH
        self._db.drop_all()

    # ── add files ──────────────────────────────────────────────
    def add_file(self, file_path: str) -> bool:
        with self.lock:
            norm_path = str(Path(file_path).resolve())

            if self._db.contains(norm_path):
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

                faiss_id = self.index.ntotal  # next slot
                self.index.add(embedding)
                self._db.insert(faiss_id, meta)
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

        files = []
        if recursive:
            for root, dirs, fnames in os.walk(directory):
                for fname in fnames:
                    ext = Path(fname).suffix.lower()
                    if ext in config.SUPPORTED_EXTENSIONS:
                        fpath = os.path.join(root, fname)
                        try:
                            if os.path.getsize(fpath) <= config.MAX_FILE_SIZE_BYTES:
                                files.append(fpath)
                        except Exception:
                            pass
        else:
            for p in path.glob("*"):
                if p.is_file() and p.suffix.lower() in config.SUPPORTED_EXTENSIONS:
                    files.append(str(p))

        logger.info(f"Found {len(files)} candidate files in {directory}")
        for f in files:
            if self.add_file(str(f)):
                count += 1
        logger.info(f"Indexed {count} NEW files from {directory}")
        return count

    # ── persist / save ─────────────────────────────────────────
    def save(self):
        """Save FAISS index to disk.  SQLite is already committed per-insert."""
        faiss.write_index(self.index, config.FAISS_INDEX_PATH)
        logger.info(f"HNSW index saved: {self._db.count()} total documents")

    # ── stats ──────────────────────────────────────────────────
    def get_index_stats(self) -> Dict:
        return {
            "total_documents": self._db.count(),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": config.EMBEDDING_DIM,
            "watch_paths": config.WATCH_PATHS,
        }

    # ── raw search ─────────────────────────────────────────────
    def search_raw(self, query_embedding: np.ndarray, top_k: int):
        """Direct FAISS search on this index"""
        n_docs = self._db.count()
        if self.index is None or n_docs == 0:
            return [], []
        k = min(top_k, n_docs)
        distances, indices = self.index.search(query_embedding, k)
        return distances[0], indices[0]

    def get_metadata_by_faiss_id(self, fid: int) -> dict | None:
        """Efficient single-row lookup by FAISS vector index."""
        return self._db.get_by_faiss_id(fid)


# ─────────────────────────────────────────────────────────────
# GLOBAL SINGLETON  — import this everywhere
# ─────────────────────────────────────────────────────────────
_global_index: IndexBuilder = None

def get_index() -> IndexBuilder:
    global _global_index
    if _global_index is None:
        _global_index = IndexBuilder()
    return _global_index

"""FAISS Index Builder — HNSW + SQLite backed (v3.0)

Singleton pattern so ALL modules share ONE index.
- IndexHNSWFlat for O(log n) approximate nearest-neighbour search
- SQLite for metadata (row-level updates, no full-RAM pickle load)
- open_count / last_opened tracking for access-frequency scoring
"""
import faiss
import numpy as np
import sqlite3
import threading
import time
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
        extension    TEXT,
        open_count   INTEGER DEFAULT 0,
        last_opened  REAL
    );
    """

    _MIGRATIONS = [
        "ALTER TABLE files ADD COLUMN open_count INTEGER DEFAULT 0",
        "ALTER TABLE files ADD COLUMN last_opened REAL",
    ]

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        self._conn().execute("PRAGMA journal_mode=WAL;")
        self._run_migrations()

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

    def _run_migrations(self):
        """Add columns if they don't exist (safe for existing DBs)."""
        for sql in self._MIGRATIONS:
            try:
                self._conn().execute(sql)
                self._conn().commit()
            except sqlite3.OperationalError:
                pass  # column already exists

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
        rows = self._conn().execute(
            "SELECT * FROM files ORDER BY faiss_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def all_paths(self) -> Set[str]:
        rows = self._conn().execute("SELECT path FROM files").fetchall()
        return {r[0] for r in rows}

    def record_open(self, path: str):
        """Increment open_count and set last_opened timestamp."""
        import time
        self._conn().execute(
            "UPDATE files SET open_count = open_count + 1, last_opened = ? WHERE path = ?",
            (time.time(), path),
        )
        self._conn().commit()

    def get_open_count(self, faiss_id: int) -> int:
        row = self._conn().execute(
            "SELECT open_count FROM files WHERE faiss_id=? LIMIT 1", (faiss_id,)
        ).fetchone()
        return row[0] if row and row[0] else 0

    def drop_all(self):
        self._conn().execute("DELETE FROM files")
        self._conn().commit()

    def remove_by_path(self, path: str) -> bool:
        """Remove a file entry by path. Returns True if it existed."""
        cur = self._conn().execute("DELETE FROM files WHERE path=?", (path,))
        self._conn().commit()
        return cur.rowcount > 0

    def get_faiss_id_by_path(self, path: str) -> int | None:
        """Get the FAISS vector ID for a given path."""
        row = self._conn().execute(
            "SELECT faiss_id FROM files WHERE path=? LIMIT 1", (path,)
        ).fetchone()
        return row[0] if row else None

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

    HNSW_M = 32
    HNSW_EF_CONSTRUCTION = 40
    HNSW_EF_SEARCH = 64

    def __init__(self):
        self.embedder = get_embedder()
        self.index: faiss.Index | None = None
        self._db = _MetadataDB(config.SQLITE_DB_PATH)
        self.lock = threading.RLock()
        self._load_or_create_index()

    # ── backward compatibility ─────────────────────────────────
    @property
    def metadata(self) -> List[Dict]:
        return self._db.all_rows()

    @property
    def indexed_paths(self) -> Set[str]:
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

            # Skip project's own directory (resolve both sides)
            try:
                p = Path(norm_path).resolve()
                base_dir = config.BASE_DIR.resolve()
                if p == base_dir or base_dir in p.parents:
                    return False
            except Exception:
                pass

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
                    logger.debug(f"Skipping {norm_path}: Extracted text < 10 characters")
                    return False

                embedding = self.embedder.encode_single(text)
                embedding = np.array([embedding], dtype=np.float32)
                meta = FileParser.get_file_metadata(norm_path)

                faiss_id = self.index.ntotal
                self.index.add(embedding)
                self._db.insert(faiss_id, meta)
                return True
            except Exception as e:
                logger.error(f"Error indexing {norm_path}: {e}")
                return False

    def remove_file(self, file_path: str) -> bool:
        """Remove a file from the index (soft delete — marks in SQLite, FAISS vector stays but unused)."""
        with self.lock:
            norm_path = str(Path(file_path).resolve())
            removed = self._db.remove_by_path(norm_path)
            if removed:
                self.save()
                logger.info(f"Removed from index: {norm_path}")
            return removed

    def index_directory(self, directory: str, recursive: bool = True) -> int:
        path = Path(directory)
        count = 0
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0

        files = []
        if recursive:
            for root, dirs, fnames in os.walk(directory):
                try:
                    target_dir = Path(root).resolve()
                    base_dir = config.BASE_DIR.resolve()
                    if target_dir == base_dir or base_dir in target_dir.parents:
                        dirs.clear()
                        continue
                except Exception:
                    pass

                for skip in list(config.SKIP_DIRS):
                    if skip in dirs:
                        dirs.remove(skip)

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
        for i, f in enumerate(files):
            try:
                if self.add_file(str(f)):
                    count += 1
                    # Save in batches of 50 to avoid data loss on crash
                    if count % 50 == 0:
                        self.save()
                        logger.info(f"  Progress: {i+1}/{len(files)} scanned, {count} indexed")
            except Exception as e:
                logger.warning(f"Error processing {f}: {e}")
            # ── CPU throttle: yield 50ms between files to prevent system freeze ──
            time.sleep(0.05)
        logger.info(f"Indexed {count} NEW files from {directory}")
        return count

    # ── access frequency ──────────────────────────────────────
    def record_open(self, path: str):
        """Record that a user opened a file."""
        norm = str(Path(path).resolve())
        self._db.record_open(norm)

    def get_open_count(self, faiss_id: int) -> int:
        return self._db.get_open_count(faiss_id)

    # ── persist / save ─────────────────────────────────────────
    def save(self):
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
        n_docs = self._db.count()
        if self.index is None or n_docs == 0:
            return [], []
        # Search more than needed to compensate for deleted files
        k = min(top_k * 2, self.index.ntotal)
        if k == 0:
            return [], []
        distances, indices = self.index.search(query_embedding, k)
        # Filter out FAISS IDs that no longer exist in metadata (deleted files)
        valid_d, valid_i = [], []
        for d, i in zip(distances[0], indices[0]):
            if i < 0:
                continue
            meta = self._db.get_by_faiss_id(int(i))
            if meta and Path(meta["path"]).exists():
                valid_d.append(d)
                valid_i.append(i)
                if len(valid_d) >= top_k:
                    break
        return valid_d, valid_i

    def get_metadata_by_faiss_id(self, fid: int) -> dict | None:
        return self._db.get_by_faiss_id(fid)


# ─────────────────────────────────────────────────────────────
# GLOBAL SINGLETON
# ─────────────────────────────────────────────────────────────
_global_index: IndexBuilder | None = None
_global_index_lock = threading.Lock()

def get_index() -> IndexBuilder:
    global _global_index
    if _global_index is None:
        with _global_index_lock:
            if _global_index is None:
                _global_index = IndexBuilder()
    return _global_index

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
import fnmatch
import hashlib
from itertools import islice
from typing import List, Dict, Set
from pathlib import Path
import app.config as config
from app.logger import logger
from core.embeddings.embedder import get_embedder
from core.ingestion.file_parser import FileParser
from core.ingestion.chunks import (
    parse_chunks,
    PARSER_VERSION,
    VIDEO_EXTENSIONS,
    MAX_CONTENT_BYTES,
)

FOLDER_EXTENSION = "[folder]"


def _is_skipped_dir(name: str) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatch(low, pattern.lower()) for pattern in config.SKIP_DIRS)


def _is_skipped_file(name: str) -> bool:
    low = name.lower()
    return (
        low.startswith("~$")
        or low in {"desktop.ini", "thumbs.db", ".ds_store"}
        or low.endswith(".tmp")
        or low.endswith(".temp")
        or low.endswith(".part")
        or low.endswith(".crdownload")
    )


def _folder_index_text(folder: Path, max_items: int = 80) -> str:
    """Build a compact searchable description for a folder node."""
    child_dirs: list[str] = []
    child_files: list[str] = []
    ext_counts: dict[str, int] = {}
    total_size = 0

    try:
        entries = sorted(
            islice(folder.iterdir(), max_items),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )
    except (OSError, PermissionError):
        entries = []

    for entry in entries[:max_items]:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            if _is_skipped_dir(entry.name):
                continue
            child_dirs.append(entry.name)
            continue
        if _is_skipped_file(entry.name):
            continue
        child_files.append(entry.name)
        ext = entry.suffix.lower() or "(no extension)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        try:
            total_size += entry.stat().st_size
        except OSError:
            pass

    top_types = ", ".join(
        f"{ext} files ({count})"
        for ext, count in sorted(ext_counts.items(), key=lambda item: -item[1])[:8]
    )
    return (
        f"Folder: {folder.name}\n"
        f"Path: {folder}\n"
        f"Subfolders: {', '.join(child_dirs[:30]) or 'none'}\n"
        f"Files: {', '.join(child_files[:50]) or 'none'}\n"
        f"File types: {top_types or 'none'}\n"
        f"Approx child file bytes: {total_size}"
    )


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
        "ALTER TABLE files ADD COLUMN content_hash TEXT",
        "ALTER TABLE files ADD COLUMN modified_ns INTEGER",
        "ALTER TABLE files ADD COLUMN parser_version TEXT",
        "ALTER TABLE files ADD COLUMN truncated INTEGER DEFAULT 0",
    ]

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        self._conn().execute("PRAGMA journal_mode=WAL;")
        self._run_migrations()
        self._conn().executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                text TEXT NOT NULL, section TEXT, page INTEGER,
                offset_start INTEGER, offset_end INTEGER, evidence_kind TEXT,
                timestamp TEXT, vector BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chunks_file_id ON chunks(file_id);
            CREATE INDEX IF NOT EXISTS files_faiss_id ON files(faiss_id);
            CREATE TABLE IF NOT EXISTS index_settings (key TEXT PRIMARY KEY, value TEXT);
        """)

    # ── connection per thread ──────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
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
        row = (
            self._conn()
            .execute("SELECT 1 FROM files WHERE path=? LIMIT 1", (path,))
            .fetchone()
        )
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
        row = (
            self._conn()
            .execute(
                """SELECT files.*, chunks.id AS chunk_id, chunks.text, chunks.section,
                      chunks.page, chunks.offset_start, chunks.offset_end,
                      chunks.evidence_kind, chunks.timestamp
               FROM chunks JOIN files ON files.id=chunks.file_id WHERE chunks.id=?""",
                (fid,),
            )
            .fetchone()
        )
        return dict(row) if row else None

    def count(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def all_rows(self) -> List[Dict]:
        rows = self._conn().execute("SELECT * FROM files ORDER BY faiss_id").fetchall()
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
        row = (
            self._conn()
            .execute(
                "SELECT open_count FROM files JOIN chunks ON chunks.file_id=files.id WHERE chunks.id=?",
                (faiss_id,),
            )
            .fetchone()
        )
        return row[0] if row and row[0] else 0

    def drop_all(self):
        self._conn().execute("DELETE FROM chunks")
        self._conn().execute("DELETE FROM files")
        self._conn().commit()

    def remove_by_path(self, path: str) -> bool:
        """Remove a file entry by path. Returns True if it existed."""
        cur = self._conn().execute("DELETE FROM files WHERE path=?", (path,))
        self._conn().commit()
        return cur.rowcount > 0

    def get_faiss_id_by_path(self, path: str) -> int | None:
        """Get the FAISS vector ID for a given path."""
        row = (
            self._conn()
            .execute("SELECT faiss_id FROM files WHERE path=? LIMIT 1", (path,))
            .fetchone()
        )
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
        self._write_lock = threading.RLock()
        self._load_or_create_index()

    # ── backward compatibility ─────────────────────────────────
    @property
    def metadata(self) -> List[Dict]:
        return self._db.all_rows()

    @property
    def indexed_paths(self) -> Set[str]:
        return self._db.all_paths()

    # ── index lifecycle ────────────────────────────────────────
    def _empty_index(self):
        base = faiss.IndexHNSWFlat(config.EMBEDDING_DIM, self.HNSW_M)
        base.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        base.hnsw.efSearch = self.HNSW_EF_SEARCH
        return faiss.IndexIDMap2(base)

    def _rebuild_vectors(self):
        # SQLite is authoritative: an interrupted FAISS save cannot lose documents.
        rebuilt = self._empty_index()
        cursor = self._db._conn().execute("SELECT id, vector FROM chunks ORDER BY id")
        while rows := cursor.fetchmany(256):
            vectors = np.vstack(
                [np.frombuffer(row["vector"], dtype=np.float32) for row in rows]
            )
            rebuilt.add_with_ids(
                vectors, np.array([row["id"] for row in rows], dtype=np.int64)
            )
        self.index = rebuilt

    def _load_or_create_index(self):
        conn = self._db._conn()
        identity = getattr(self.embedder, "identity", config.MODEL_NAME)
        old = conn.execute(
            "SELECT value FROM index_settings WHERE key='embedding'"
        ).fetchone()
        if old and old[0] != identity:
            # Same dimension does NOT mean the same embedding space.
            logger.warning(
                "Embedding backend changed; old vectors invalidated for background reindex"
            )
            with conn:
                conn.execute("DELETE FROM chunks")
                conn.execute("UPDATE files SET parser_version=NULL, faiss_id=-1")
                self._mark_dirty(conn)
        if not old and self._db.count():
            # Keep legacy file records for filename lookup. Background indexing will
            # upgrade them because parser_version is unset; never label old vectors
            # as belonging to a potentially different embedding backend.
            logger.info(
                "Legacy file index retained; chunk embeddings will be populated by the next scan"
            )
        conn.execute(
            "INSERT OR REPLACE INTO index_settings VALUES ('embedding', ?)", (identity,)
        )
        conn.commit()
        revision = conn.execute(
            "SELECT value FROM index_settings WHERE key='revision'"
        ).fetchone()
        saved = conn.execute(
            "SELECT value FROM index_settings WHERE key='saved_revision'"
        ).fetchone()
        if revision and saved and revision[0] == saved[0]:
            try:
                self.index = faiss.read_index(str(config.FAISS_INDEX_PATH))
                if self.index.d == config.EMBEDDING_DIM:
                    return
            except Exception as exc:
                logger.warning("Rebuilding FAISS cache from SQLite: %s", exc)
        self._rebuild_vectors()

    @staticmethod
    def _mark_dirty(conn):
        conn.execute("""INSERT INTO index_settings VALUES ('revision', '1')
                        ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1""")

    def _create_fresh_index(self):
        with self._write_lock, self.lock:
            self._db.drop_all()
            with self._db._conn() as conn:
                self._mark_dirty(conn)
            self.index = self._empty_index()

    @staticmethod
    def _fingerprint(path: Path) -> str:
        digest = hashlib.sha256()
        if path.is_dir():
            digest.update(_folder_index_text(path).encode("utf-8"))
        elif (
            path.suffix.lower() not in VIDEO_EXTENSIONS
            and path.stat().st_size > MAX_CONTENT_BYTES
        ):
            stat = path.stat()
            digest.update(
                f"metadata-only:{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode()
            )
        elif path.suffix.lower() not in VIDEO_EXTENSIONS:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        else:
            # No frame extraction: hash the indexed inputs, not gigabytes of video.
            stat = path.stat()
            digest.update(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
            for suffix in (".srt", ".vtt"):
                sidecar = path.with_suffix(suffix)
                digest.update(suffix.encode())
                if sidecar.is_file():
                    if sidecar.stat().st_size > MAX_CONTENT_BYTES:
                        digest.update(
                            f"oversized:{sidecar.stat().st_size}:{sidecar.stat().st_mtime_ns}".encode()
                        )
                        continue
                    with sidecar.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
        return digest.hexdigest()

    def add_file(self, file_path: str, force: bool = False) -> bool:
        path = Path(file_path).resolve()
        if (
            path == config.BASE_DIR.resolve()
            or config.BASE_DIR.resolve() in path.parents
        ):
            return False
        if not path.is_file() or path.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
            return False
        return self._upsert(path, folder=False, force=force)

    def add_folder(self, folder_path: str) -> bool:
        path = Path(folder_path).resolve()
        if (
            path == config.BASE_DIR.resolve()
            or config.BASE_DIR.resolve() in path.parents
        ):
            return False
        if not path.is_dir() or _is_skipped_dir(path.name):
            return False
        return self._upsert(path, folder=True, force=False)

    def _upsert(self, path: Path, folder: bool, force: bool) -> bool:
        # Serialize writers, but keep parsing and inference outside the search lock.
        with self._write_lock:
            try:
                stat = path.stat()
                if not folder and stat.st_size > config.MAX_FILE_SIZE_BYTES:
                    self.remove_file(str(path))
                    return False
                conn = self._db._conn()
                old = conn.execute(
                    "SELECT * FROM files WHERE path=?", (str(path),)
                ).fetchone()
                version = (
                    PARSER_VERSION + ":ocr=" + os.getenv("NEURON_INDEX_IMAGE_OCR", "0")
                )
                is_video = path.suffix.lower() in VIDEO_EXTENSIONS
                if (
                    old
                    and not force
                    and not folder
                    and not is_video
                    and old["parser_version"] == version
                    and old["modified_ns"] == stat.st_mtime_ns
                    and old["size"] == stat.st_size
                ):
                    return False
                fingerprint = self._fingerprint(path)
                if (
                    old
                    and old["content_hash"] == fingerprint
                    and old["parser_version"] == version
                ):
                    with conn:
                        conn.execute(
                            "UPDATE files SET modified_ns=?, modified_time=?, size=? WHERE id=?",
                            (stat.st_mtime_ns, stat.st_mtime, stat.st_size, old["id"]),
                        )
                    return False
                if folder:
                    chunks = [
                        {
                            "text": _folder_index_text(path),
                            "section": "Folder listing",
                            "evidence_kind": "metadata",
                            "offset_start": 0,
                            "offset_end": 0,
                        }
                    ]
                    truncated = False
                else:
                    chunks, truncated = parse_chunks(str(path))
                vectors = []
                for start in range(0, len(chunks), 8):
                    vectors.extend(
                        self.embedder.encode(
                            [c["text"] for c in chunks[start : start + 8]], batch_size=8
                        )
                    )
                    time.sleep(0)  # yield to foreground requests between small batches
                after = path.stat()
                if (
                    after.st_mtime_ns != stat.st_mtime_ns
                    or after.st_size != stat.st_size
                ):
                    logger.info("File changed during extraction; deferred: %s", path)
                    return False
                if is_video and self._fingerprint(path) != fingerprint:
                    return False
                with self.lock:
                    with conn:
                        conn.execute(
                            """INSERT INTO files
                            (faiss_id,path,name,size,modified_time,created_time,extension,content_hash,modified_ns,parser_version,truncated)
                            VALUES (-1,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                            name=excluded.name,size=excluded.size,modified_time=excluded.modified_time,
                            extension=excluded.extension,content_hash=excluded.content_hash,
                            modified_ns=excluded.modified_ns,parser_version=excluded.parser_version,truncated=excluded.truncated""",
                            (
                                str(path),
                                path.name,
                                0 if folder else stat.st_size,
                                stat.st_mtime,
                                stat.st_ctime,
                                FOLDER_EXTENSION if folder else path.suffix.lower(),
                                fingerprint,
                                stat.st_mtime_ns,
                                version,
                                int(truncated),
                            ),
                        )
                        file_id = conn.execute(
                            "SELECT id FROM files WHERE path=?", (str(path),)
                        ).fetchone()[0]
                        conn.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
                        ids = []
                        for chunk, vector in zip(chunks, vectors):
                            array = np.asarray(vector, dtype=np.float32)
                            if (
                                array.shape != (config.EMBEDDING_DIM,)
                                or not np.isfinite(array).all()
                            ):
                                raise ValueError(
                                    "Invalid embedding shape or non-finite values"
                                )
                            cursor = conn.execute(
                                """INSERT INTO chunks
                                (file_id,text,section,page,offset_start,offset_end,evidence_kind,timestamp,vector)
                                VALUES (?,?,?,?,?,?,?,?,?)""",
                                (
                                    file_id,
                                    chunk["text"],
                                    chunk.get("section"),
                                    chunk.get("page"),
                                    chunk.get("offset_start"),
                                    chunk.get("offset_end"),
                                    chunk.get("evidence_kind", "content"),
                                    chunk.get("timestamp"),
                                    array.tobytes(),
                                ),
                            )
                            ids.append(cursor.lastrowid)
                        conn.execute(
                            "UPDATE files SET faiss_id=? WHERE id=?",
                            (ids[0] if ids else -1, file_id),
                        )
                        self._mark_dirty(conn)
                    try:
                        if ids:
                            self.index.add_with_ids(
                                np.asarray(vectors, dtype=np.float32),
                                np.array(ids, dtype=np.int64),
                            )
                        active = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[
                            0
                        ]
                        if self.index.ntotal > max(active * 1.5, active + 256):
                            self._rebuild_vectors()
                    except Exception:
                        self._rebuild_vectors()
                return True
            except Exception as exc:
                logger.error("Error indexing %s: %s", path, exc)
                return False

    def remove_file(self, file_path: str) -> bool:
        with self._write_lock, self.lock:
            norm_path = str(Path(file_path).resolve())
            # Include directory descendants on move/delete, with a separator boundary.
            paths = [
                row[0]
                for row in self._db._conn().execute("SELECT path FROM files")
                if row[0] == norm_path or row[0].startswith(norm_path + os.sep)
            ]
            with self._db._conn() as conn:
                conn.executemany(
                    "DELETE FROM files WHERE path=?", [(p,) for p in paths]
                )
                if paths:
                    self._mark_dirty(conn)
            if paths:
                self._rebuild_vectors()
            return bool(paths)

    def index_directory(self, directory: str, recursive: bool = True) -> int:
        path = Path(directory)
        count = 0
        if not path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0

        files = []
        folders = []
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

                dirs[:] = [d for d in dirs if not _is_skipped_dir(d)]
                folders.append(root)

                for fname in fnames:
                    if _is_skipped_file(fname):
                        continue
                    ext = Path(fname).suffix.lower()
                    if ext in config.SUPPORTED_EXTENSIONS:
                        fpath = os.path.join(root, fname)
                        try:
                            if os.path.getsize(fpath) <= config.MAX_FILE_SIZE_BYTES:
                                files.append(fpath)
                        except Exception:
                            pass
        else:
            folders.append(str(path))
            for p in path.glob("*"):
                if p.is_dir() and not _is_skipped_dir(p.name):
                    folders.append(str(p))
                elif p.is_file() and p.suffix.lower() in config.SUPPORTED_EXTENSIONS:
                    files.append(str(p))

        logger.info(
            f"Found {len(folders)} candidate folders and {len(files)} candidate files in {directory}"
        )
        for folder in folders:
            try:
                if self.add_folder(str(folder)):
                    count += 1
            except Exception as e:
                logger.warning(f"Error processing folder {folder}: {e}")

        for i, f in enumerate(files):
            try:
                if self.add_file(str(f)):
                    count += 1
                    # Save in batches of 50 to avoid data loss on crash
                    if count % 50 == 0:
                        self.save()
                        logger.info(
                            f"  Progress: {i + 1}/{len(files)} scanned, {count} indexed"
                        )
            except Exception as e:
                logger.warning(f"Error processing {f}: {e}")
            # CPU throttle: yield 10ms every 10 files to prevent freeze without crawling
            if i % 10 == 9:
                time.sleep(0.01)
        logger.info(f"Indexed {count} NEW file/folder records from {directory}")
        self.save()
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
        with self.lock:
            target = Path(config.FAISS_INDEX_PATH)
            temporary = target.with_suffix(target.suffix + ".tmp")
            faiss.write_index(self.index, str(temporary))
            os.replace(temporary, target)
            with self._db._conn() as conn:
                conn.execute("""INSERT OR REPLACE INTO index_settings
                    SELECT 'saved_revision', value FROM index_settings WHERE key='revision'""")

    # ── stats ──────────────────────────────────────────────────
    def get_index_stats(self) -> Dict:
        return {
            "total_documents": self._db.count(),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": config.EMBEDDING_DIM,
            "total_chunks": self._db._conn()
            .execute("SELECT COUNT(*) FROM chunks")
            .fetchone()[0],
            "pending_chunk_migration": self._db._conn()
            .execute("SELECT COUNT(*) FROM files WHERE parser_version IS NULL")
            .fetchone()[0],
            "embedding_backend": getattr(self.embedder, "identity", config.MODEL_NAME),
            "watch_paths": config.WATCH_PATHS,
        }

    # ── raw search ─────────────────────────────────────────────
    def _nearest(self, query_embedding: np.ndarray, top_k: int, unique_files: bool):
        with self.lock:
            if self.index is None or not self.index.ntotal or top_k <= 0:
                return [], []
            k = min(max(top_k * 3, 16), self.index.ntotal)
            while True:
                distances, indices = self.index.search(query_embedding, k)
                valid_d, valid_i, seen = [], [], set()
                for distance, idx in zip(distances[0], indices[0]):
                    meta = self._db.get_by_faiss_id(int(idx)) if idx >= 0 else None
                    if not meta:
                        continue
                    try:
                        stat = Path(meta["path"]).stat()
                        if (
                            meta.get("extension") != FOLDER_EXTENSION
                            and meta.get("modified_ns") != stat.st_mtime_ns
                        ):
                            continue
                    except OSError:
                        continue
                    if unique_files and meta["path"] in seen:
                        continue
                    seen.add(meta["path"])
                    valid_d.append(distance)
                    valid_i.append(idx)
                    if len(valid_i) >= top_k:
                        return valid_d, valid_i
                if k == self.index.ntotal:
                    return valid_d, valid_i
                k = min(k * 2, self.index.ntotal)

    def search_raw(self, query_embedding: np.ndarray, top_k: int):
        return self._nearest(query_embedding, top_k, unique_files=True)

    def search_chunks(self, query_embedding: np.ndarray, top_k: int = 12) -> list[dict]:
        distances, ids = self._nearest(query_embedding, top_k, unique_files=False)
        results = []
        for distance, idx in zip(distances, ids):
            meta = self._db.get_by_faiss_id(int(idx))
            if meta:
                meta["semantic_score"] = 1 / (1 + float(distance))
                results.append(meta)
        return results

    def evidence_for_paths(
        self, query_embedding: np.ndarray, paths: list[str], per_file: int = 2
    ) -> list[dict]:
        """Rank passages inside the files selected by the existing query filters."""
        best = {}
        query = query_embedding.reshape(-1)
        for path in dict.fromkeys(paths):
            row = (
                self._db._conn()
                .execute("SELECT id,modified_ns,size FROM files WHERE path=?", (path,))
                .fetchone()
            )
            try:
                stat = Path(path).stat()
                if (
                    not row
                    or row["modified_ns"] != stat.st_mtime_ns
                    or row["size"] != stat.st_size
                ):
                    continue  # never feed evidence from a known stale file to Qwen
            except OSError:
                continue
            selected = []
            cursor = self._db._conn().execute(
                "SELECT id,vector FROM chunks WHERE file_id=? AND evidence_kind!='metadata'",
                (row["id"],),
            )
            while batch := cursor.fetchmany(64):
                vectors = np.vstack(
                    [np.frombuffer(item["vector"], dtype=np.float32) for item in batch]
                )
                distances = np.sum((vectors - query) ** 2, axis=1)
                selected.extend(
                    (float(distance), item["id"])
                    for item, distance in zip(batch, distances)
                )
                selected = sorted(selected)[:per_file]
            best[path] = selected
        results = []
        for distance, chunk_id in sorted(
            item for selected in best.values() for item in selected
        ):
            meta = self._db.get_by_faiss_id(chunk_id)
            if meta:
                meta["semantic_score"] = 1 / (1 + distance)
                results.append(meta)
        return results

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

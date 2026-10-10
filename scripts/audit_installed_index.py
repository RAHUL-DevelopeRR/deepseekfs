"""Read-only aggregate checks; never print document paths or content."""
import json
from pathlib import Path
import sqlite3
import numpy as np

database = Path.home() / "AppData/Local/Neuron/storage/cache/metadata_baai_bge_small_en_v1_5.db"
with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
    report = {
        "database": str(database),
        "integrity": connection.execute("PRAGMA quick_check").fetchone()[0],
        "backend": connection.execute("SELECT value FROM index_settings WHERE key='embedding'").fetchone()[0],
        "files": connection.execute("SELECT COUNT(*) FROM files").fetchone()[0],
        "chunks": connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
        "pending_migration": connection.execute("SELECT COUNT(*) FROM files WHERE parser_version IS NULL").fetchone()[0],
        "evidence_kinds": dict(connection.execute("SELECT evidence_kind,COUNT(*) FROM chunks GROUP BY evidence_kind")),
    }
    invalid = 0
    for vector, in connection.execute("SELECT vector FROM chunks"):
        array = np.frombuffer(vector, dtype=np.float32)
        if array.shape != (384,) or not np.isfinite(array).all() or not np.isclose(np.linalg.norm(array), 1, atol=1e-4):
            invalid += 1
    report["invalid_vectors"] = invalid
print(json.dumps(report, indent=2))

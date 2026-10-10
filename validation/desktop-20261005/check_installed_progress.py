from pathlib import Path
import tempfile
import sqlite3

for root in sorted(Path(tempfile.gettempdir()).glob('neucockpit-release-ai-*'), key=lambda p: p.stat().st_mtime)[-1:]:
    for log in root.rglob('*.log'):
        print(log.name)
        print('\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-6:]))
    database = root / 'events.db'
    if database.exists():
        with sqlite3.connect(database) as connection:
            print('Tool events:', connection.execute("SELECT event_type,tool_name,status FROM events WHERE event_type IN ('tool_result','task_completed','task_failed')").fetchall())

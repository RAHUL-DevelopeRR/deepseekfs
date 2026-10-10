from pathlib import Path
import tempfile
roots = sorted(Path(tempfile.gettempdir()).glob('neucockpit-release-ai-*'), key=lambda p: p.stat().st_mtime, reverse=True)
for root in roots[:1]:
    print(root)
    for p in root.rglob('*.log'):
        print(p.name, p.read_text(encoding='utf-8', errors='replace')[-2500:])

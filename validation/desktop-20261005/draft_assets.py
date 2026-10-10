from pathlib import Path
import json
d = json.loads(Path(__file__).with_name('draft-release.json').read_text())
print(d['targetCommitish'])
print('\n'.join(a['name'] for a in d['assets']))

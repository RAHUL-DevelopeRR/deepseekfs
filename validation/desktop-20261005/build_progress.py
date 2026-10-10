import json
from pathlib import Path
d = json.loads(Path(__file__).with_name('upgrade-build-status.json').read_text())
print(d['status'], d['conclusion'])
for job in d.get('jobs', []):
    print(job['name'], job['status'], job['conclusion'], next((s['name'] for s in job.get('steps', []) if s['status'] == 'in_progress'), ''))

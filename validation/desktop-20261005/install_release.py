import hashlib
import json
import pathlib
import subprocess
import urllib.request

root = pathlib.Path('D:/NeuCockpit-build-archive/2026-10-05/accelerated-release')
root.mkdir(parents=True, exist_ok=True)
with urllib.request.urlopen('https://api.github.com/repos/RAHUL-DevelopeRR/deepseekfs/releases/latest', timeout=30) as response:
    release = json.load(response)
assert release['target_commitish'].startswith('4e3d5a6'), release['target_commitish']
(root / 'release.json').write_text(json.dumps(release, indent=2), encoding='utf-8')
name = 'NeuCockpitSetup_v1.0_windows_x64.exe'
for filename in [name + '.sha256', name]:
    asset = next(a for a in release['assets'] if a['name'] == filename)
    dest = root / filename
    subprocess.run(['curl.exe', '-sfL', '--retry', '3', '--output', str(dest), asset['browser_download_url']], check=True)
expected = (root / (name + '.sha256')).read_text().split()[0].lower()
with (root / name).open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
assert actual == expected, (actual, expected)
print(json.dumps({'release': release['tag_name'], 'installer': str(root / name), 'sha256': actual, 'verified': True}), flush=True)

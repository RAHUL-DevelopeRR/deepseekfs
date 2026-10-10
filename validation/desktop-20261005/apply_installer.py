import hashlib
import pathlib
import subprocess

root = pathlib.Path('D:/NeuCockpit-build-archive/2026-10-05/accelerated-release')
installer = root / 'NeuCockpitSetup_v1.0_windows_x64.exe'
assert installer.stat().st_size > 1000000000
with installer.open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
assert actual == pathlib.Path(str(installer) + '.sha256').read_text().split()[0].lower()
print('Checksum verified. Installing.', flush=True)
result = subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(root / 'install.log')], timeout=900)
print('Installer exit:', result.returncode, flush=True)
assert result.returncode == 0

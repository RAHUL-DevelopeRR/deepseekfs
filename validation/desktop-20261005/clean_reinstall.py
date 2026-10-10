import os
from pathlib import Path
import shutil
import subprocess

app = (Path(os.environ['LOCALAPPDATA']) / 'Programs/NeuCockpit').resolve()
expected = Path('C:/Users/DELL/AppData/Local/Programs/NeuCockpit').resolve()
archive = Path('D:/NeuCockpit-build-archive/2026-10-05/previous-installed-layout').resolve()
assert app == expected and app.is_dir()
assert not archive.exists()
assert (Path(os.environ['LOCALAPPDATA']) / 'Neuron/storage').resolve() not in app.parents
shutil.move(str(app), str(archive))
print('Archived previous installed layout:', archive, flush=True)
result = subprocess.run([str(Path('.venv/Scripts/python.exe').resolve()), str(Path(__file__).with_name('apply_installer.py'))], timeout=1000)
assert result.returncode == 0

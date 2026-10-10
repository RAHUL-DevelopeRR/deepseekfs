import json
import os
import pathlib
import subprocess
import sys
import tempfile

app = pathlib.Path(os.environ['LOCALAPPDATA']) / 'Programs/NeuCockpit'
out = pathlib.Path(__file__).parent
if os.environ.get('NEURON_VERIFY_DESKTOP_ONLY') != '1' and '--desktop-only' not in sys.argv:
    result = subprocess.run([str(pathlib.Path('.venv/Scripts/python.exe').resolve()), 'scripts/verify_release_ai.py', '--cli', str(app / 'neufs.exe')], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    (out / 'installed-ai.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout, flush=True)
    assert result.returncode == 0, result.stderr[-2000:]
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    (out / 'installed-ai-final.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
with tempfile.TemporaryDirectory(prefix='neucockpit-installed-desktop-') as storage:
    env = os.environ.copy()
    env.update(NEURON_STORAGE_DIR=storage, NEURON_DESKTOP_SMOKE='1', NEURON_STARTUP_INDEX_ON_LAUNCH='0', HF_HUB_OFFLINE='1')
    desktop = subprocess.run([str(app / 'NeuCockpit.exe')], env=env, capture_output=True, timeout=120)
    logs = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in pathlib.Path(storage).rglob('*.log'))
    (out / 'installed-desktop.log').write_text(logs, encoding='utf-8')
    assert desktop.returncode == 0, desktop.returncode
    assert 'smoke mode ready; quitting' in logs, logs[-2000:]
    print(json.dumps({'desktop_startup': True, 'exit_code': desktop.returncode}), flush=True)

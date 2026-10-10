import faulthandler
import os
import runpy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

faulthandler.enable()
faulthandler.dump_traceback_later(10, repeat=True)
with tempfile.TemporaryDirectory(prefix='neucockpit-cli-probe-', ignore_cleanup_errors=True) as storage:
    os.environ['NEURON_STORAGE_DIR'] = storage
    sys.argv = ['neufs.py', 'chat', 'hello', '--mode', 'chat']
    runpy.run_path('neufs.py', run_name='__main__')

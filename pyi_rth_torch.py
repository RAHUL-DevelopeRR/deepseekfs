"""
PyInstaller runtime hook for PyTorch.
Adds torch/lib to DLL search path before any torch imports.
"""
import os
import sys

# Get the base directory (where Neuron.exe lives)
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
else:
    base = os.path.dirname(os.path.abspath(__file__))

# Add torch lib directories to DLL search path
torch_lib = os.path.join(base, 'torch', 'lib')
torch_internal = os.path.join(base, '_internal', 'torch', 'lib')

for p in [torch_lib, torch_internal, base]:
    if os.path.isdir(p):
        os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')
        try:
            os.add_dll_directory(p)
        except (OSError, AttributeError):
            pass

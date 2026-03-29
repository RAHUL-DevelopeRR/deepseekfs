# -*- mode: python ; coding: utf-8 -*-
"""
Neuron — PyInstaller Build Spec (Fixed DLL resolution)
=======================================================
"""
import sys
import os
from pathlib import Path

block_cipher = None

hidden_imports = [
    'PyQt6.sip', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'numpy', 'sqlite3',
    'sentence_transformers',
    'sentence_transformers.models',
    'sentence_transformers.models.Transformer',
    'sentence_transformers.models.Pooling',
    'transformers',
    'transformers.models.bert',
    'transformers.models.bert.modeling_bert',
    'transformers.models.bert.tokenization_bert',
    'transformers.models.bert.tokenization_bert_fast',
    'huggingface_hub', 'tokenizers', 'safetensors',
    'torch', 'torch.nn', 'torch.nn.functional', 'torch._C',
    'fitz', 'docx', 'pptx',
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'ctypes', 'ctypes.wintypes', 'platform', 'subprocess',
]

datas = [('assets', 'assets')]

from PyInstaller.utils.hooks import collect_data_files
try:
    datas += collect_data_files('sentence_transformers')
except Exception:
    pass
try:
    datas += collect_data_files('transformers')
except Exception:
    pass
try:
    datas += collect_data_files('tokenizers')
except Exception:
    pass

# ── Explicitly add torch DLLs as binaries ──
import torch
torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
torch_binaries = []
if os.path.isdir(torch_lib):
    for f in os.listdir(torch_lib):
        if f.endswith('.dll'):
            torch_binaries.append((os.path.join(torch_lib, f), '.'))

a = Analysis(
    ['run_desktop.py'],
    pathex=['.'],
    binaries=torch_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_torch.py'],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'sklearn', 'tensorflow',
        'keras', 'PIL.ImageTk', 'tkinter', 'unittest',
        'notebook', 'jupyter', 'IPython',
        'tensorboard', 'tensorboardX',
        'torch.distributed', 'torch.testing',
        'torch.utils.tensorboard', 'torch.utils.benchmark',
        'torch._inductor', 'torch.onnx', 'caffe2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Neuron',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/neuron_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Neuron',
)

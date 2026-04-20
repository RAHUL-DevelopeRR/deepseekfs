# -*- mode: python ; coding: utf-8 -*-
"""
Neuron v5.0 - PyInstaller --onedir spec (ONNX)
===============================================
Bundles the desktop app with ONNX Runtime for neural embeddings.
No PyTorch/torch dependency — uses the same MiniLM model exported
to ONNX format for identical search quality without DLL conflicts.

Build:
    pyinstaller neuron_onedir.spec --noconfirm

Output:
    dist/Neuron/Neuron.exe   (+ all DLLs, packages, assets, model)
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("QT_API", "pyqt6")

block_cipher = None

# ── Paths ──────────────────────────────────────────────────────
PROJECT = os.path.abspath('.')

# ── Data files to bundle ──────────────────────────────────────
datas = [
    # App source packages (imported at runtime)
    ('app', 'app'),
    ('core', 'core'),
    ('services', 'services'),
    ('ui', 'ui'),
    # Assets (icons, images)
    ('assets', 'assets'),
    # ONNX model (neural search without torch)
    ('storage/models/onnx', 'storage/models/onnx'),
    # Docs
    ('docs', 'docs'),
]

# Explicitly copy metadata PyInstaller misses for runtime dependencies.
datas += copy_metadata('tqdm')
datas += copy_metadata('regex')

# Only include datas that exist
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# ── Hidden imports ────────────────────────────────────────────
# PyInstaller can't always find these through static analysis
hiddenimports = [
    # Our packages
    'app', 'app.config', 'app.logger',
    'core', 'core.indexing', 'core.indexing.index_builder',
    'core.embeddings', 'core.embeddings.embedder',
    'core.search', 'core.search.semantic_search',
    'core.search.query_parser', 'core.search.query_corrector',
    'core.search.llm_reranker',
    'core.ingestion', 'core.ingestion.file_parser',
    'core.time', 'core.time.scoring',
    'core.watcher', 'core.watcher.file_watcher',
    'core.activity', 'core.activity.activity_logger',
    'services.desktop_service', 'services.startup_indexer',
    'services.ollama_service',
    'ui.spotlight_panel', 'ui.memory_lane_panel', 'ui.icons',
    # faiss
    'faiss',
    # file parsers
    'fitz',            # PyMuPDF
    'docx',            # python-docx
    'pptx',            # python-pptx
    'openpyxl',
    'lxml', 'lxml.etree',
    'pdfminer', 'pdfminer.high_level',
    # ONNX Runtime (replaces torch for neural embeddings)
    'onnxruntime',
    'tokenizers',
    # other deps
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'dateparser',
    'numpy',
    'tqdm',
    'regex',
    'certifi',
    'yaml',
    'sqlite3',
    'json',
    'ctypes', 'ctypes.wintypes',
    'PyQt6',
    'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'PyQt6.sip',
]

# ── Excludes (things we definitely don't need) ────────────────
excludes = [
    'tkinter', 'unittest', 'test', 'tests',
    'matplotlib', 'IPython', 'notebook', 'jupyter',
    'pytest', 'py', 'sphinx', 'docutils',
    'pandas', 'pyarrow', 'numba', 'llvmlite', 'sqlalchemy',
    'sklearn', 'scipy',
    'onnxruntime',
    'qtpy', 'PyQt5', 'PySide6', 'PySide2',
    'tensorflow', 'tensorflow_hub', 'tf_keras', 'keras', 'jax', 'flax',
    'tensorboard', 'torch.cuda', 'torch.distributed',
    'torch.testing', 'torch.utils.tensorboard',
    'torch', 'torchvision', 'torchaudio',
    'transformers', 'sentence_transformers', 'tokenizers',
    'huggingface_hub', 'safetensors',
    'torch._dynamo', 'torch._inductor', 'torch._export',
    'torch._functorch', 'torch._higher_order_ops', 'torch._subclasses',
    'functorch', 'torch.func', 'torch.compiler', 'torch.onnx',
    'torch.ao', 'torch.quantization', 'torch.export', 'torch.masked',
    'torch.profiler', 'torch.utils', 'torch.utils.data',
    'torch.utils.benchmark', 'torch.utils.tensorboard',
    'torch.distributions', 'torch.special', 'torch.sparse', 'torch.optim',
    'torch.signal', 'torch.mps', 'torch.cpu', 'torch.amp',
    'torch.nn.intrinsic', 'torch.nn.qat', 'torch.nn.quantized',
    'torch.nn.quantizable',
    'scipy._lib.array_api_compat.torch',
    'sympy', 'mpmath', 'IPython', 'ipykernel', 'ipywidgets', 'jupyter',
    'debugpy', 'traitlets', 'pydantic', 'httpx', 'aiohttp',
    'PIL',  # We don't need Pillow for the Qt app
]

# ── Analysis ──────────────────────────────────────────────────
a = Analysis(
    ['run_desktop.py'],
    pathex=[PROJECT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                     # --onedir: don't pack binaries into exe
    exclude_binaries=True,  # --onedir mode
    name='Neuron',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # No console window (pythonw-equivalent)
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

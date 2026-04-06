# -*- mode: python ; coding: utf-8 -*-
"""
Neuron v4.7 — Full PyInstaller --onedir spec
=============================================
Bundles the ENTIRE app (Python + all packages + model) into a
self-contained folder. No venv needed on the target machine.

Build:
    pyinstaller neuron_onedir.spec --noconfirm

Output:
    dist/Neuron/Neuron.exe   (+ all DLLs, packages, assets, model)
"""
import os
import sys
from pathlib import Path

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
    # Pre-cached AI model (so first run doesn't need internet)
    ('storage/models', 'storage/models'),
    # Docs
    ('docs', 'docs'),
]

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
    # sentence-transformers and its deps
    'sentence_transformers',
    'sentence_transformers.models',
    'sentence_transformers.models.Transformer',
    'sentence_transformers.models.Pooling',
    'sentence_transformers.models.Normalize',
    'transformers',
    'transformers.models',
    'transformers.models.bert',
    'transformers.models.bert.modeling_bert',
    'transformers.models.bert.tokenization_bert',
    'transformers.models.bert.tokenization_bert_fast',
    'tokenizers',
    # torch (CPU)
    'torch',
    'torch.nn',
    'torch.nn.functional',
    # faiss
    'faiss',
    # file parsers
    'fitz',            # PyMuPDF
    'docx',            # python-docx
    'pptx',            # python-pptx
    'openpyxl',
    'lxml', 'lxml.etree',
    'pdfminer', 'pdfminer.high_level',
    # other deps
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'dateparser',
    'sklearn', 'sklearn.utils',
    'numpy',
    'scipy',
    'huggingface_hub',
    'safetensors',
    'tqdm',
    'regex',
    'requests',
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
    'tensorboard', 'torch.cuda', 'torch.distributed',
    'torch.testing', 'torch.utils.tensorboard',
    'torchvision', 'torchaudio',
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

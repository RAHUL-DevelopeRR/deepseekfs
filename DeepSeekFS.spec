# -*- mode: python ; coding: utf-8 -*-
# DeepSeekFS v3.0 — Minimal PyInstaller spec
# Avoids collect_data_files which pulls too much data

a = Analysis(
    ['run_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('core', 'core'),
        ('services', 'services'),
        ('app', 'app'),
    ],
    hiddenimports=[
        # ML core
        'sentence_transformers',
        'sentence_transformers.models',
        'sentence_transformers.util',
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'transformers',
        'tokenizers',
        'faiss',
        'tqdm',
        'huggingface_hub',
        'sklearn.utils',
        'sklearn.metrics.pairwise',
        # UI
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
        # Utilities
        'watchdog',
        'watchdog.observers',
        'watchdog.events',
        'dateparser',
        'orjson',
        'joblib',
        # File ingestion
        'docx',
        'fitz',
        'pdfminer',
        'pdfminer.high_level',
        'openpyxl',
        'pptx',
        # stdlib that pyinstaller sometimes misses
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PySide6', 'PySide2',
        'tensorflow', 'keras', 'tensorboard', 'tb_nightly',
        'matplotlib', 'mpl_toolkits',
        'sphinx', 'docutils', 'alabaster',
        'IPython', 'ipykernel', 'ipywidgets',
        'pytest', '_pytest',
        'av', 'grpc', 'grpcio',
        'google.cloud', 'google.auth', 'googleapiclient',
        'lxml', 'llvmlite', 'numba',
        'cv2', 'PIL', 'scipy', 'sympy',
        'notebook', 'jupyter', 'jupyterlab',
        'dns', 'flask', 'django', 'psutil', 'h5py',
        'pandas', 'win32com', 'win32api',
        'tkinter', '_tkinter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DeepSeekFS',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DeepSeekFS',
)

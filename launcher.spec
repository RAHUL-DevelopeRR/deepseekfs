# -*- mode: python ; coding: utf-8 -*-
"""
Neuron Launcher — TINY PyInstaller build.
Only bundles the launcher stub (~5MB), NOT torch/transformers.
Builds in under 30 seconds.
"""

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'transformers', 'sentence_transformers',
        'numpy', 'PIL', 'matplotlib', 'scipy',
        'PyQt6', 'watchdog', 'fitz', 'docx', 'pptx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
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
    onefile=True,
)

# -*- mode: python ; coding: utf-8 -*-
"""
NeuCockpit v1.0 - PyInstaller --onedir spec (BGE ONNX)
===============================================
Bundles the desktop app with ONNX Runtime for neural embeddings.
No PyTorch/torch dependency — uses the same MiniLM model exported
to ONNX format for identical search quality without DLL conflicts.

Build:
    pyinstaller neuron_onedir.spec --noconfirm

Output:
    dist/Neuron/NeuCockpit.exe   (+ all DLLs, packages, assets, models)
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("QT_API", "pyqt6")

block_cipher = None

# ── Paths ──────────────────────────────────────────────────────
PROJECT = os.path.abspath('.')
APP_ICON = 'assets/neuron_icon.ico' if sys.platform.startswith('win') else None

# ── Data files to bundle ──────────────────────────────────────
datas = [
    # App source packages (imported at runtime)
    ('app', 'app'),
    ('core', 'core'),
    ('services', 'services'),
    ('ui', 'ui'),
    # Assets (icons, images)
    ('assets', 'assets'),
    # Primary bundled embedding model: BGE Small ONNX.
    ('storage/models/BAAI/bge-small-en-v1.5', 'storage/models/BAAI/bge-small-en-v1.5'),
    # Docs
    ('docs', 'docs'),
    # Headless command surface
    ('neufs.py', '.'),
    ('neufs.cmd', '.'),
]

# Product builds bundle the primary Qwen 2.5 Coder 3B GGUF so MemoryOS works
# from dist/Neuron without a separate model setup step.
if os.environ.get('NEURON_SKIP_QWEN_GGUF') != '1':
    primary_gguf = Path('storage/models/qwen2.5-coder-3b-instruct-q5_k_m.gguf')
    if primary_gguf.exists():
        datas.append((str(primary_gguf), 'storage/models'))

# llama-cpp-python loads DLLs from llama_cpp/lib at runtime.
binaries = collect_dynamic_libs('llama_cpp')

# Explicitly copy metadata PyInstaller misses for runtime dependencies.
datas += copy_metadata('tqdm')
datas += copy_metadata('regex')
datas += copy_metadata('huggingface_hub')

# Only include datas that exist
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# ── Hidden imports ────────────────────────────────────────────
# PyInstaller can't always find these through static analysis.
# Every module under app/, core/, services/, ui/ that is imported
# at runtime MUST be listed here — especially those loaded via
# lazy imports (llama_cpp, plugins) or dynamic registry patterns
# (services.tools submodules).
hiddenimports = [
    # ── app ──
    'app', 'app.config', 'app.logger',

    # ── core.indexing ──
    'core', 'core.indexing', 'core.indexing.index_builder',
    'core.indexing.rust_discovery',

    # ── core.embeddings ──
    'core.embeddings', 'core.embeddings.embedder',

    # ── core.search ──
    'core.search', 'core.search.semantic_search',
    'core.search.query_parser', 'core.search.query_corrector',
    'core.search.llm_reranker', 'core.search.nlp_parser',

    # ── core misc ──
    'core.ingestion', 'core.ingestion.file_parser',
    'core.time', 'core.time.scoring',
    'core.watcher', 'core.watcher.file_watcher',
    'core.activity', 'core.activity.activity_logger',

    # ── services (top-level modules) ──
    'services',
    'services.desktop_service', 'services.startup_indexer',
    'services.ollama_service', 'services.llm_engine',
    'services.memory_os', 'services.speech_service',
    'services.model_manager', 'services.coder_engine',
    'services.internet_search', 'services.stability',
    'services.jinja2_patches', 'services.agent_context',
    'services.llm_client', 'services.llm_worker',
    'services.model_health',
    'services.platform_support',

    # ── services.agent ──
    'services.agent', 'services.agent.executor',
    'services.agent.queue', 'services.agent.task',

    # ── services.tools (split from monolith in v5.2) ──
    'services.tools', 'services.tools.base', 'services.tools.common',
    'services.tools.file_tools', 'services.tools.folder_tools',
    'services.tools.execution_tools', 'services.tools.search_tools',
    'services.tools.system_tools', 'services.tools.registry',

    # ── services sub-packages ──
    'services.cache',
    'services.events', 'services.events.store', 'services.events.types',
    'services.feedback', 'services.feedback.store', 'services.feedback.types',
    'services.intent',
    'services.plugins', 'services.plugins.loader', 'services.plugins.protocol',
    'services.profiles', 'services.profiles.manager', 'services.profiles.models',
    'services.validation', 'services.validation.schema',
    'services.watch_rules', 'services.watch_rules.hooks', 'services.watch_rules.rules',

    # ── ui ──
    'ui', 'ui.spotlight_panel', 'ui.spotlight_components',
    'ui.memory_lane_panel', 'ui.memoryos_panel',
    'ui.activity_panel', 'ui.research_overlay',
    'ui.main_window', 'ui.icons', 'ui.icon_helpers',
    'ui.hotkeys',

    # ── llama.cpp (lazy-loaded by CoderEngine + LLMEngine) ──
    'llama_cpp',

    # ── faiss ──
    'faiss',

    # ── file parsers ──
    'fitz',            # PyMuPDF
    'docx',            # python-docx
    'pptx',            # python-pptx
    'openpyxl',
    'lxml', 'lxml.etree',
    'pdfminer', 'pdfminer.high_level',

    # ── ONNX Runtime (neural embeddings) ──
    'onnxruntime',
    'tokenizers',

    # ── other deps ──
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'dateparser',
    'markdown_it',
    'mdurl',
    'numpy',
    'tqdm',
    'huggingface_hub',
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
    'django', 'asgiref', 'channels', 'daphne',
    'websockets', 'uvicorn', 'starlette', 'fastapi',
    'anyio', 'trio', 'sniffio', 'httpcore', 'h11',
    'psutil', 'clr', 'pythonnet', 'clr_loader',
    'cryptography', 'cffi', 'pycparser',
    'pandas', 'pyarrow', 'numba', 'llvmlite', 'sqlalchemy',
    'sklearn', 'scipy',
    'qtpy', 'PyQt5', 'PySide6', 'PySide2',
    'tensorflow', 'tensorflow_hub', 'tf_keras', 'keras', 'jax', 'flax',
    'tensorboard', 'torch.cuda', 'torch.distributed',
    'torch.testing', 'torch.utils.tensorboard',
    'torch', 'torchvision', 'torchaudio',
    'transformers', 'sentence_transformers',
    'safetensors',
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

worker_hiddenimports = [
    'app', 'app.config', 'app.logger',
    'services', 'services.llm_worker', 'services.llm_engine',
    'services.model_manager', 'services.ollama_service',
    'services.jinja2_patches', 'services.model_health',
    'llama_cpp',
    'jinja2', 'numpy', 'tqdm', 'huggingface_hub', 'regex', 'certifi',
    'fitz', 'docx', 'pptx', 'openpyxl',
]

worker_excludes = excludes + [
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'onnxruntime', 'faiss', 'watchdog', 'markdown_it',
]

# ── Analysis ──────────────────────────────────────────────────
a = Analysis(
    ['run_desktop.py'],
    pathex=[PROJECT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

worker_a = Analysis(
    ['run_llm_worker.py'],
    pathex=[PROJECT],
    binaries=binaries,
    datas=datas,
    hiddenimports=worker_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=worker_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

cli_a = Analysis(
    ['neufs.py'],
    pathex=[PROJECT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
worker_pyz = PYZ(worker_a.pure, worker_a.zipped_data, cipher=block_cipher)
cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                     # --onedir: don't pack binaries into exe
    exclude_binaries=True,  # --onedir mode
    name='NeuCockpit',
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
    icon=APP_ICON,
)

worker_exe = EXE(
    worker_pyz,
    worker_a.scripts,
    [],
    exclude_binaries=True,
    name='NeuronLLMWorker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name='neufs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

coll = COLLECT(
    exe,
    worker_exe,
    cli_exe,
    a.binaries,
    worker_a.binaries,
    cli_a.binaries,
    a.zipfiles,
    worker_a.zipfiles,
    cli_a.zipfiles,
    a.datas,
    worker_a.datas,
    cli_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Neuron',
)

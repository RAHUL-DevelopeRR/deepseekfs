# Verification report

Generated during the cleanup, Rust migration, Qwen Coder integration, and
tool-safety repair pass.

## Passing checks

- Python compile check: `python -m compileall -q app core services ui run_desktop.py`
- Python tests: `python -m pytest tests -q`
- Rust tests: `cargo test` in `rust/index-core`
- Rust release build: `cargo build --release` in `rust/index-core`
- Rust discovery adapter smoke: discovered Python files under `tests/`
- PyQt import smoke: imported `SpotlightPanel` and created a `QApplication`
- Qwen Coder smoke: loaded GGUF through `llama-cpp-python` and returned JSON

## Known issues

- Some comments still contain mojibake from earlier encoding damage, but the
  repaired runtime modules compile.
- The application now targets Qwen 2.5 Coder as the unified local chat,
  summarization, and tool-planning model.

## 2026-06-05 bundle verification

### Passing

- README was replaced with an ASCII-only zero-x.live-aligned version using
  local Lucide SVG assets under `assets/readme/`.
- Source compile smoke passed for desktop, CLI, model, internet, stability,
  hotkey, and MemoryOS modules.
- Full Python test suite passed: `169 passed, 2 skipped`.
- Headless status found the bundled Qwen GGUF model and ONNX embedding model.
- Headless search returned indexed local results.
- Headless offline chat loaded Qwen from source and returned a model response.
- Headless summarization loaded Qwen from source and summarized `README.md`.
- Headless internet mode returned a live, source-formatted Tamil Nadu chief
  minister answer through Internet -> Model -> User.
- Source desktop smoke mode preloaded Qwen before PyQt, registered hotkeys,
  initialized search/index services, and exited with code 0.
- PyInstaller one-dir bundle was produced at `dist/Neuron/Neuron.exe`.
- Packaged smoke mode starts, initializes ONNX/search/hotkeys, writes logs, and
  exits with code 0.
- Bundle contains:
  - `dist/Neuron/Neuron.exe`
  - `dist/Neuron/_internal/storage/models/qwen2.5-coder-0.5b-instruct-q4_0.gguf`
  - `dist/Neuron/_internal/storage/models/onnx/model.onnx`
  - `dist/Neuron/_internal/llama_cpp/lib/*.dll`
  - `dist/Neuron/_internal/neufs.py`
  - `dist/Neuron/_internal/assets/readme/lucide-*.svg`

### Release blocker

- Packaged Qwen preload still fails inside `Neuron.exe` with:
  `exception: access violation reading 0x0000000000000000` from
  `llama_cpp.llama_backend_init()`.
- The same model loads from source Python, so the failure is currently isolated
  to the PyInstaller + llama-cpp-python native runtime combination.
- This means the produced bundle is a diagnostic artifact, not a production
  shippable build for offline Qwen generation yet.

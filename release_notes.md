<p align="center">
  <img src="https://raw.githubusercontent.com/RAHUL-DevelopeRR/deepseekfs/main/assets/neuron_circular.png" alt="Neuron" width="120"/>
</p>

<h2 align="center">Neuron v5.0</h2>
<p align="center"><b>Crash-safe indexing and Windows packaging release</b></p>

---

## What's New in v5.0

### Fixed
- Resolved the startup crash caused by unresolved merge-conflict markers in the embedding module.
- Watch-path changes no longer wipe the working SQLite/FAISS index before scanning.
- Startup indexing now keeps existing results available while new roots are scanned.
- Windows watch-path detection now includes redirected profile folders and OneDrive roots.
- Added a deterministic fallback embedder so indexing/search still run if MiniLM cannot load.
- Forced the embedding stack into PyTorch-only mode to avoid TensorFlow/protobuf import crashes.
- Updated `sentence-transformers` to 5.3.0 to match the bundled MiniLM cache metadata.
- Restored the `extract_text()` file-parser API expected by existing tests.

### Verified
- Local runtime index rebuilt successfully: 800 files indexed, SQLite and FAISS counts match.
- Desktop service starts without initialization errors and returns search results.
- Regression test added for the watch-path-change no-wipe behavior.
- Test suite: 13 passed.

---

## Installation

1. Download `NeuronSetup_v5.0.exe` from the release assets.
2. Run the installer.
3. Press `Shift + Space` to open Neuron.

Optional Encyl AI summaries require Ollama and the `llama3.2:1b` model.

---

## System Requirements

- Windows 10/11 64-bit
- 4 GB RAM minimum, 8 GB recommended
- No Python installation required for the bundled installer

---

100% local. No telemetry. Privacy first.

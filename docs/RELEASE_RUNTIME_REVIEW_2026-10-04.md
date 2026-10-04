# Bundled runtime review — 4 October 2026

## Confirmed defects and fixes

- Windows x64 installed the training requirements, which omit ONNX Runtime. Windows now uses the same packaging requirements as Linux and macOS. The spec aborts when ONNX, tokenizers, FAISS or llama.cpp is missing.
- Release checks previously tested only Qwen. They now require the BGE ONNX backend, offline generation, streamed tokens, and model loads below 30 seconds on the release runner.
- `neufs status` loaded the entire embedding/index stack, could invalidate vectors after fallback, and reported success despite missing ONNX. Status now reads existing SQLite metadata in read-only mode. `--load-embeddings` explicitly tests runtime health and reports degradation as failure.
- A missing neural runtime could invalidate existing neural vectors when switching to lexical fallback. This transition now fails while preserving the vectors.
- Headless chat used in-process native generation; the CLI now defaults to the same isolated worker as the desktop.
- Stream completion read a Qt-owned flag from a worker before queued token events necessarily ran. Completion now follows actual callback emission, with a regression test.
- Python modules were stored as many separate files, plus duplicate source files. The package now archives Python modules and collects local modules for dynamic imports.

## Initial measurements on this PC

Installed 1 October build, isolated temporary storage, offline mode:
- status: 1.805 seconds, confirmed missing ONNX and lexical fallback.
- desktop startup smoke: 8.724 seconds; search degraded.
- Qwen load through worker: 6.404 seconds.
- Source BGE model initialization: 3.218 seconds; first embedding: 0.394 seconds.

These checks did not reproduce a 30-second model load. Cold disk cache, antivirus, memory pressure and generation latency may change observed time. Final packaged measurements and deployment evidence will be appended after verification.

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

## Verified fresh Windows package

Source: cf17a08, `dist/fresh-20261004/Neuron`.

- Full suite: 250 passed, 2 skipped. CLI tests use temporary state outside the document folder.
- GitHub code and retrieval checks passed.
- Offline packaged release check: BGE ONNX CLS backend confirmed; embedding check (including process startup) 5.501 s; Qwen check 6.310 s; first streamed token 6.850 s; response `AI MODE OK`.
- Packaged desktop smoke: clean exit, 8.484 s to ready; isolated state, maintenance scan disabled.
- Packaged retrieval smoke: found PDF page 8 and Q3 amount 987654, refreshed modified text, and retained exact paths in agent observations. Status 0.770 s, initial index 3.220 s, search 2.120 s, grounded answer 21.070 s, reindex 2.010 s.
- Headless workers now stop and close their reader threads before CLI exit. This removes worker handles surviving interpreter shutdown; logs go to stderr while stdout contains the JSON response.
- Future release workflows upload all assets as a draft before publishing, so latest download links cannot expose partially uploaded releases.

Generation latency is distinct from loading: the grounded answer took 21 seconds including retrieval and inference. These are measurements on this PC, not a promise for every CPU or storage device.

## Installed upgrade and disk space

- The first silent upgrade ran out of space on C: and rolled back. The stale build outputs were transferred to `D:/NeuCockpit-build-archive/2026-10-04`, freeing approximately 9 GB on C:.
- The retry completed with installer exit code 0; no Windows restart was required.
- All three installed executables match the fresh package by SHA-256. Read-only status succeeds, reports ONNX available, and retains the existing index with 263 records.
- The installed-layout offline check passes BGE ONNX, Qwen generation, and streaming. During post-install system activity, BGE took 11.896 s, Qwen 24.809 s, and the first streamed token 17.297 s. This variation reinforces that the earlier isolated timings are not universal latency guarantees.
- Intel macOS cold-start checks measured 32.712 s and 38.131 s. The Intel CPU package now excludes the unused Metal backend; the 30-second release gate remains in place. Native verification of that change is required before publishing the complete release.

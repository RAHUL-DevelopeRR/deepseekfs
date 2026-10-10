# NeuCockpit architecture and retrieval review

Reviewed branch: `codex/ui-ux-unique-icons` (starting at `b0bd74a`). This document describes the local changes in this branch. The existing `main` checkout was `f186884` before switching. No release artifact or four-gigabyte target device was certified in this review.

## Product boundaries

NeuCockpit is a local filesystem agent with a PyQt desktop surface and `neufs` headless CLI. `DesktopService` initializes the BGE embedder and FAISS index in the background, then performs an incremental scan and starts the watcher. `MemoryOSAgent` routes chat, query, and action requests. Query mode now uses extracted local evidence; action mode passes tool observations to the agent executor. The GGUF model runs through `llama-cpp-python` in a supervised subprocess in desktop builds. `Qwen2.5-Coder-1.5B-Instruct-GGUF` at Q4_K_M is the configured primary model. Internet retrieval is an explicit opt-in and receives only the typed public query.

```
PyQt / neufs
  -> DesktopService / MemoryOSAgent / TaskExecutor
  -> SemanticSearch -> BGE Small ONNX -> FAISS HNSW
  -> chunk SQLite store (file, page/slide/row/section, offset, text, hash)
  -> bounded evidence prompt -> isolated Qwen llama.cpp worker
```

## Findings and repairs

1. **One truncated passage per file.** `FileParser.parse()` remains available for legacy file-reading callers, but `IndexBuilder` now indexes bounded passages from all PDF pages, Markdown sections, DOCX paragraphs/tables, PPTX slides, spreadsheet rows, and supported text/code files. Each passage has a vector and location. Extraction is capped at 4,096 passages or 64 MiB of source material; a limit is marked as partial rather than represented as a complete document. Scanned PDFs still need OCR, and older binary Office formats are metadata only.
2. **Search hits without text in Qwen prompts.** `SemanticSearch.search_evidence()` selects passages inside the matching files. Query mode sends bounded excerpts with source IDs and appends the exact file and location list to the answer. When only metadata is available, it returns a file list without asking Qwen to guess document contents. The prompt states that local document text is untrusted input. Search results retain their existing file-level shape for the desktop UI.
3. **Edited files kept old vectors.** Indexing now compares size, nanosecond modification time, parser version, and content hash. Watcher modifications force a content check. Replacement passes through a SQLite transaction while preserving file identity and access counts. Retrieval rejects chunks when a file has changed since it was indexed. Deleted files and moved directory descendants are removed. SQLite stores passage vectors as the durable source; FAISS snapshots are rebuilt after an interrupted save or corruption. A saved revision permits fast normal startup. When the embedding backend changes, old vectors are invalidated for reindexing.
4. **Agent lost paths after search.** The `semantic_search` tool and its compact executor observation now include full paths and short excerpts. The JSON observation stays within the agent's character budget without cutting a path in half.
5. **Stalled worker and model sizing.** The worker client now enforces response deadlines and terminates a hung subprocess, including during app shutdown. The default model is 1.5B Q4_K_M. The desktop uses a balanced CPU profile, up to four inference threads, and 128-token batch. Context is 2,048 tokens by default and is preserved on model-load fallback. Chat prompts are measured with the actual llama.cpp tokenizer before inference; long user material is explicitly marked as truncated. Query answers stream into the desktop panel. `NEURON_LLM_KV_TYPE=q8_0` is an optional lower-memory setting; FP16 KV remains the default because a single Q8 comparison was inconclusive for speed.
6. **Release packaging could silently omit Qwen.** A requested bundled release now fails the PyInstaller spec if the configured 1.5B GGUF is absent. Explicit unbundled builds remain possible. Cross-platform source regressions run in a separate Windows/Linux/macOS workflow. The multi-platform release job now requires all six platform builds to pass, and Linux/macOS dependency installation failures stop the build.

## Image and video scope

Images (`png`, `jpg`, `jpeg`, `gif`, `webp`, `bmp`, `tif`, `tiff`) are indexed by filename and dimensions. Setting `NEURON_INDEX_IMAGE_OCR=1` also extracts text when a local Tesseract installation is available. This supports searches for image filenames and visible text; it does **not** understand objects or scenes. The OCR setting does not send images to a cloud service.

Videos (`mp4`, `mkv`, `avi`, `mov`, `wmv`, `flv`, `webm`) are indexed by filename. A same-name `.srt` or `.vtt` sidecar contributes timestamped transcript passages. No audio transcription or frame embedding is performed. Visual questions such as “find the clip with a red car” require a separate offline vision encoder and sampled frame index; the current text-only BGE encoder cannot answer them. Transcript passages are labeled so Qwen cannot present them as verified visual events.

## Validation and limits

The Python suite passed with 241 tests and 2 skips. Focused tests cover late-page retrieval, spreadsheet rows, modifications, same-stat watcher changes, stale evidence exclusion, corrupt-snapshot recovery, backend migration, tool paths, worker timeout, context budgeting, and query streaming. A real BGE ONNX + Qwen 1.5B Q4_K_M isolated-worker test retrieved revenue from page 8 of an eight-page PDF and answered `987654` with a source. On this 11.9 GiB Windows laptop (two physical/four logical CPU cores), the final four-thread streaming run took 12.1 seconds including a 5.2-second model load; first visible text appeared at 10.9 seconds; warm search median was 45 ms; the worker used roughly 1.7 GiB RSS. Warm model generation took 5.6 seconds with first text after 4.3 seconds. A short synthetic warm prompt took about 2 seconds while a longer one took about 19 seconds. These are single-run measurements, not comparative quality or 4 GiB compatibility evidence. Q8 KV saved about 27 MiB in one run, but subsequent FP16 timing varied similarly, so its speed effect is unresolved.

Remaining release work includes packaged inference tests for each OS/architecture, a physically constrained 4 GiB memory test, UI responsiveness during a long index and generation, and a representative answer-quality comparison of the former 3B model against 1.5B. A green installer job still does not certify end-user AI mode. The existing GitHub Actions release matrix already covers six OS/architecture targets; AWS CodeBuild could run a parallel matrix, but would add infrastructure and macOS reserved capacity cost without fixing inference latency. Visual media search and OCR for scanned PDFs need separate model/runtime work and data-grounded evaluation before being advertised as available.

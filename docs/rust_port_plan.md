# Rust port plan

This codebase should not be rewritten in Rust all at once. The right move is to
stabilize boundaries in Python first, then port the parts that benefit from
native performance, stronger concurrency, and tighter memory behavior.

## Keep in Python for now

- PyQt UI (`ui/`)
- document parsing breadth (`core/ingestion/file_parser.py`)
- local LLM orchestration (`services/llm_engine.py`, `services/memory_os.py`)
- plugin loading and high-level task orchestration

These areas depend heavily on mature Python libraries and would be expensive to
rebuild before the interfaces are cleaner.

## Best first Rust targets

### 1. Indexing core

Port the file crawl, change detection, and index update coordinator first.

Why:
- file watching and directory walking are throughput-sensitive
- current Python path handling and update flow are correctness-sensitive
- this is the part closest to OS events and long-running state

Suggested Rust crate responsibilities:
- recursive file discovery
- watch event normalization
- content hash / modified-time based upsert decisions
- batching work for embeddings and persistence

### 2. Watcher and native Windows integration

Move filesystem watching, debouncing, and hotkey/window-adjacent native hooks to
Rust if the Python watcher remains brittle under load.

Why:
- easier to build a robust event loop
- cleaner bridge to Windows-specific APIs
- lower overhead for high event volume

### 3. Metadata and search repository

Move the metadata store and query filter pipeline into Rust once indexing is
stable.

Why:
- strong typing around path normalization and metadata schemas
- easier to guarantee upsert/delete semantics
- faster pre-filtering before semantic ranking

## Search stack split

Recommended split:

- Rust:
  - watcher
  - index coordinator
  - metadata store
  - filter/query executor
  - ranking pre- and post-processing
- Python:
  - embedding model invocation
  - FAISS integration initially
  - LLM summarization and agent orchestration

Later, if the interfaces settle, you can replace FAISS/Python glue with a Rust
vector layer or a service boundary.

## Tool calling and offline coding model

For robust offline file operations and tool calling, the cleanest architecture is:

- Python orchestrator owns UI state, plugin discovery, and human-facing flows.
- A local coding/model service owns offline tool-calling.
- Rust owns sensitive execution rails and filesystem/index operations.

### Qwen 2.5 Coder placement

Use Qwen 2.5 Coder as a local tool-calling and file-ops planner, not as the
only authority over execution.

Recommended flow:

1. User request enters Python orchestrator.
2. Python builds a compact tool schema and repo context.
3. Qwen 2.5 Coder produces:
   - tool selection
   - structured arguments
   - optional patch plan
4. Python validates the request.
5. Rust services execute:
   - file indexing ops
   - watcher control
   - metadata queries
   - guarded filesystem mutations where native speed matters
6. Python returns results to the UI and keeps conversation state.

### Why this split works

- Qwen stays offline and useful for repo-aware tool calling.
- Rust becomes the reliable execution substrate instead of the planner.
- Python remains the fastest layer for product iteration.

## Proposed workspace shape after Rust starts

- `python-app/` or existing root:
  - UI
  - agent orchestration
  - LLM adapters
  - plugin system
- `rust/index-core/`:
  - watcher
  - path normalization
  - index coordinator
  - metadata repository
- `rust/native-bridge/`:
  - Python bindings or local IPC bridge

## Port order

1. Fix Python boundaries and remove god files.
2. Define a stable indexing API: `discover`, `upsert`, `remove`, `query`, `watch`.
3. Implement watcher + index coordinator in Rust.
4. Move metadata repository and query filters into Rust.
5. Add a guarded tool-execution bridge for file operations.
6. Re-evaluate whether vector search also belongs in Rust.

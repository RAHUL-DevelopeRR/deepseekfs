# Rust Backend + React Frontend Port Draft

Context: Neuron is a desktop-first, offline file intelligence application. The
port should preserve local-only operation, fast launcher behavior, global
shortcuts, tray presence, local model execution, and guarded file operations.

## Recommended target

Use Tauri with:

- Rust backend for native services, indexing, metadata, IPC, filesystem guards,
  model process supervision, tray, hotkeys, and packaging.
- React frontend for the desktop shell, command palette, MemoryOS chat,
  settings, activity views, and research overlays.
- Local IPC only. No cloud dependency for core search, chat history, indexing,
  or settings.

This keeps the app offline and small while giving the UI a cleaner component
model than the current PyQt surface.

## Product principles

- The first screen is the working app, not a landing page.
- Startup should show a lightweight shell quickly, then stream service readiness
  states from Rust.
- All user data stays on device unless the user explicitly exports it.
- Destructive operations require explicit confirmation with a clear path preview.
- The UI should be quiet, dense, and fast to scan, since this is a repeated-use
  desktop productivity tool.

## Proposed workspace

```text
app/
  desktop/
    src/
      components/
      features/
      routes/
      styles/
      icons/
      fonts/
    package.json
    vite.config.ts
src-tauri/
  src/
    commands/
    indexing/
    metadata/
    models/
    search/
    tools/
    tray/
    hotkeys/
    main.rs
  tauri.conf.json
rust/
  crates/
    neuron-index/
    neuron-metadata/
    neuron-tools/
    neuron-model-host/
```

Keep Python temporarily as a compatibility service only where it still owns a
mature dependency, such as document parsing, embeddings, or current LLM glue.
Each Python dependency should sit behind a Rust command boundary so it can be
removed later without changing the React app.

## Rust backend responsibilities

### Native shell

- Tauri window lifecycle.
- Tray icon and menu.
- Global shortcuts.
- File open, reveal in explorer, and path selection.
- Settings storage and migration.
- App update and diagnostics screens.

### Indexing and metadata

- Recursive discovery.
- Watch event normalization.
- Path canonicalization.
- Skip rules.
- Content hashing.
- File metadata upsert/delete.
- SQLite persistence.
- Query prefiltering before semantic ranking.

### Tool execution

- Typed command registry.
- Risk classification: safe, confirm, blocked.
- Confirmation payload generation.
- Filesystem mutation guardrails.
- Audit trail for each executed tool.
- No shell execution without a risk result.

### Model host

- Local GGUF model discovery.
- Model download/import status.
- Disk space checks.
- Process supervision for LLM and embedding workers.
- Streaming token bridge to the frontend.
- Structured tool-call validation before execution.

## React frontend responsibilities

### Main surfaces

- Command palette and file results.
- MemoryOS chat with streaming responses.
- Activity and recent-work timeline.
- Research overlay.
- Settings.
- Model manager.
- Tool confirmation modal.
- Diagnostics and verification panel.

### State model

- Use a small client store for UI state.
- Treat Rust as the source of truth for filesystem, index, model, and tool state.
- Subscribe to Tauri events for long-running work: indexing progress, model
  loading, search updates, and token streams.
- Use optimistic UI only for reversible local interactions, not filesystem
  mutations.

## IPC contract

Prefer stable typed commands instead of ad hoc JSON strings.

Example command groups:

```text
index.discover(path)
index.start_watch(path)
index.stop_watch(path)
search.query(text, filters)
files.read(path, max_chars)
files.reveal(path)
tools.plan(user_request)
tools.execute(approved_request_id)
models.status()
models.load(model_id)
models.chat_stream(session_id, messages)
settings.get()
settings.set(patch)
```

Each command should return a typed result:

```text
ok: boolean
data: object | null
error: string | null
trace_id: string
```

## UI system

### Icons

Use `lucide-react` for the primary icon set.

Recommended icon mapping:

- Search: `Search`
- Files: `File`, `FileText`, `Folder`, `FolderOpen`
- Actions: `Play`, `Pause`, `Square`, `Check`, `X`
- Tool safety: `ShieldCheck`, `ShieldAlert`, `TriangleAlert`
- Models: `Cpu`, `HardDrive`, `Download`, `RefreshCw`
- Navigation: `Home`, `History`, `Settings`, `Activity`
- Chat: `MessageSquare`, `Send`, `Sparkles`
- Window/tray actions: `Minimize2`, `Maximize2`, `PanelRight`, `Command`

Icon buttons need accessible names, fixed dimensions, hover states, disabled
states, and tooltips for any icon that is not obvious.

### Fonts

Bundle fonts locally so the app remains offline.

Recommended stack:

- UI text: Inter, bundled as local `woff2`.
- Code and paths: JetBrains Mono, bundled as local `woff2`.
- Optional compact fallback: system UI fonts.

CSS:

```css
@font-face {
  font-family: "Inter";
  src: url("../fonts/inter-var.woff2") format("woff2");
  font-weight: 100 900;
}

@font-face {
  font-family: "JetBrains Mono";
  src: url("../fonts/jetbrains-mono-var.woff2") format("woff2");
  font-weight: 100 800;
}

:root {
  font-family: "Inter", "Segoe UI", system-ui, sans-serif;
}

code,
.path,
.mono {
  font-family: "JetBrains Mono", "Cascadia Mono", monospace;
}
```

## Visual direction

- Use neutral dark and light themes with restrained accent colors.
- Avoid one-hue blue or purple dominance.
- Use compact panels, tables, split panes, and list rows.
- Keep cards only for repeated items, modals, and framed tools.
- Keep command surfaces keyboard-first.
- Use stable row heights and fixed icon button sizes.
- Prefer icons for common actions and short labels only where clarity needs it.

## Offline data layout

```text
%LOCALAPPDATA%/Neuron/
  config/
  indexes/
  models/
  logs/
  cache/
  exports/
```

The portable build can redirect this to an app-local `data/` directory. The
frontend should never hardcode paths; it should ask Rust for the active data
root.

## Port phases

### Phase 1: Shell and bridge

- Scaffold Tauri + React app.
- Add local fonts and Lucide icon system.
- Implement basic tray, window, shortcuts, settings, and diagnostics.
- Create typed IPC command wrappers in React.
- Keep current Python services running behind Rust commands.

### Phase 2: Rust indexing core

- Move discovery, skip rules, path normalization, and metadata writes to Rust.
- Add watcher service.
- Add progress events.
- Validate parity against current Python index results.

### Phase 3: Search and activity

- Move metadata filtering and activity timeline queries to Rust.
- Keep embeddings behind a worker boundary.
- Add React search result views with stable keyboard navigation.

### Phase 4: Tools and safety

- Implement Rust tool registry.
- Add dynamic risk classification.
- Add confirmation modal flow.
- Add audit log viewer.
- Remove direct shell/file mutation paths from the UI.

### Phase 5: Model host

- Move model status, load, unload, and streaming supervision to Rust.
- Keep model execution local.
- Support import of existing GGUF files.
- Show disk, RAM, and readiness status in the React model manager.

### Phase 6: Remove Python surface area

- Replace remaining Python services one boundary at a time.
- Keep Python only where it is still the best dependency host.
- Delete compatibility bridges after parity tests pass.

## Verification gates

- Python and Rust parity tests for indexing output.
- IPC schema tests.
- Tool risk classification tests.
- Offline startup test with network disabled.
- Fresh machine install test.
- Portable build test.
- UI screenshot checks for compact, expanded, and narrow desktop windows.
- Manual smoke for tray, shortcut, search, chat streaming, and tool confirmation.

## First implementation slice

Build the smallest real desktop shell:

1. Tauri app starts offline.
2. React shell displays command palette, status bar, and settings button.
3. Lucide icons and local fonts render from bundled assets.
4. Rust exposes `settings.get`, `models.status`, and `index.status`.
5. React subscribes to a mock `index.progress` event.
6. Existing Python app remains untouched while the new shell proves packaging,
   IPC, theme, fonts, and native integration.


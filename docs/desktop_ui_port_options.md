# Desktop UI port options

## Best fit for this app

If Neuron stays Windows-first, the best UI target is C# WinUI 3 with Windows App
SDK, backed by a Rust core for indexing, filesystem watching, and native file
operations.

Why:
- native Windows shell integration
- reliable tray, notifications, hotkeys, acrylic/Mica, file dialogs
- good installer/MSIX story
- easier accessibility and DPI behavior than a custom Python shell
- Rust can still own the performance-sensitive backend

## Other options

- PyQt/PySide: fastest to continue from the current code, but packaging and
  native Windows polish remain harder.
- Tauri + React/Svelte + Rust: good if the UI becomes web-like and cross-platform,
  but Windows shell UX takes more custom work.
- Qt C++: strong native desktop option, but slower product iteration and more C++
  surface area.
- Slint/Iced: interesting Rust-native UIs, but not the safest choice for a
  complex Windows productivity app yet.

## Recommended port shape

- WinUI 3: panels, settings, tray, notification UX, keyboard navigation
- Rust: watcher, file discovery, path normalization, metadata store, guarded file
  operations
- Python or local service: LLM adapters during transition
- Qwen Coder: offline planning for code/file operations, behind validated tools

## UI/UX flaws found in the current PyQt surface

- `ui/spotlight_panel.py` still contains mojibake in visible text and comments,
  so some icons/labels can render as corrupted characters.
- The panel coordinator is still large after the first split and should be
  decomposed further into navigation, activity, AI answer, tray, and search
  controller modules.
- The UI uses text glyph buttons for navigation/actions. A port should use real
  icons with accessible names and stable button dimensions.
- The palette is heavily dark/blue. It works for a launcher, but the activity and
  settings surfaces need more neutral contrast and clearer state hierarchy.
- Several user-facing strings explain features rather than directly supporting
  the workflow. A production polish pass should reduce instructional copy.

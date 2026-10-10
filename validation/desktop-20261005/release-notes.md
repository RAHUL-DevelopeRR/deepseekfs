## NeuCockpit desktop fixes

- Rearm global shortcuts when the trigger key is released, and apply shortcut settings immediately.
- Keep one desktop instance per user. Additional launches activate the existing app.
- Retain recent conversation turns across Chat, Query and Action; package the Auto intent examples.
- Expose function schemas to Qwen through its tool protocol, execute returned calls, and report failures instead of falling back to chat.
- Scope Action instructions to the requested operation and stop after success. Confirmation and dangerous-operation denial remain enforced.
- Bound document and folder chunks using the actual BGE tokenizer before producing normalized 384-dimensional vectors.
- Clean up the entire Windows model-worker process tree on cancellation.

All six native packages passed offline BGE, Qwen load, streaming and model-selected folder-listing checks. Source tests: 259 passed, 2 skipped. Real local and clean-runner checks also verified persistent Chat recall and model-selected file writing against synthetic data.

These packages include BGE Small and Qwen 2.5 Coder 1.5B for offline use. Action generation can still be slow on CPU. Conversation context is bounded; this release does not add MCP connectivity. Image/video understanding remains limited to supported metadata, optional OCR and available subtitles.

### Downloads

- Windows x64: `NeuCockpitSetup_v1.0_windows_x64.exe`
- Windows ARM64: `NeuCockpitSetup_v1.0_windows_arm64.exe`
- macOS ARM64: `NeuCockpit-v1.0-macos-arm64.dmg`
- macOS Intel: `NeuCockpit-v1.0-macos-intel.dmg`
- Linux x64: `NeuCockpit-v1.0-linux-x64.run`
- Linux ARM64: `NeuCockpit-v1.0-linux-arm64.run`

SHA256 files and native AI verification reports accompany the installers.

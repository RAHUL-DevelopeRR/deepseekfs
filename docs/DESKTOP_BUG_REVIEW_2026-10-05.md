# NeuCockpit desktop review, 5 October 2026

## Failures traced and corrected

| Area | Cause | Change |
| --- | --- | --- |
| Hotkeys | Rearming waited for every modifier to be released, then blocked presses for another 450 ms. Settings only applied after restarting. | Rearm when the trigger key is released; keep a short repeat debounce. Apply changed shortcuts immediately and display actual registered shortcuts. |
| Instances | No desktop ownership guard. Competing desktops can claim different global shortcuts and start duplicate model workers. | Per-user QLockFile ownership with Windows event activation and Qt local IPC elsewhere. Secondary launches activate the owner and exit before loading the desktop service. The separate model worker remains intentional. |
| Conversation | The default history limit was one message, which was the current input. Previous Query/Action turns were filtered out. Action context budgets favored the oldest messages. | Send bounded recent turns across modes, preserve the full current input, prioritize newest persistent context, and resolve code follow-ups in Auto. |
| Auto | Intent examples were neither bundled nor found under the install directory when user storage lacked them. | Package the example data and fall back to the bundled copy. |
| Action | Plain ChatML discarded schemas passed in `tools`; errors fell back to chat. Context instructions contaminated tool selection, and each successful one-tool request paid for a second model inference just to restate the tool result. | Serialize schemas using Qwen's Hermes tool protocol, parse calls into the existing tool API, return observations, execute every returned call, enforce the exposed tool allowlist and report failures. Score whole keywords against the latest request, omit unrelated history, and return the verified result immediately when a single exposed tool succeeds. Multi-tool tasks retain the model loop. |
| Code actions | A denied/failed write could still run code and report it saved. Failed revisions could run the old program. | Stop on denied writes and failed revisions; record correct task outcomes. |
| Worker cleanup | Windows venv launchers can leave their child interpreter and pipes alive when terminated alone. | Stop the worker process tree on Windows cancellation and clean up startup failures. |
| Embeddings | Character-bounded chunks can exceed BGE's token window; folder listings bypassed chunk splitting. | Split with the actual BGE tokenizer, preserving offsets and overlap, before embedding. Update parser version so existing files refresh. |
| Startup | Python 3.13 and FAISS's ARM probe invoke Windows WMI even for simple platform checks. Resource failures appeared in local validation. | Use `sys.platform` for Windows checks; use NumPy's detected AVX2 support to choose the Windows FAISS library without WMI. |

## Tool and MCP scope

The application exposes 17 built-in Python tools plus locally installed Python plugins. There is no MCP client, transport, server discovery or remote MCP authentication in this repository. Codex's own connectors are not exposed to NeuCockpit's model. This change fixes the local tool path; it does not claim MCP connectivity.

Tool argument validation, moderate-operation confirmation and dangerous-operation denial remain enforced. Tool generation failure cannot be reported as successful plain chat.

## Retrieval pipeline and limits

Supported documents are parsed into page, slide, paragraph, table-row or section chunks. SQLite holds source references, content hashes, modification timestamps and float32 vectors; FAISS HNSW retrieves chunks. BGE Small ONNX uses CLS pooling and unit-length 384-dimensional vectors. Its input window is 512 tokens. Token splitting now prevents silent omission within that window.

Folders contain listing metadata, not every descendant's document contents. Descendant files are indexed independently. Images provide metadata unless local OCR is enabled. Videos provide metadata and available subtitle sidecars; visual frames and audio are not understood. Scanned-PDF OCR is not implemented. Extraction remains capped at 64 MiB / 4,096 chunks and records truncation. Conversation history is also bounded by the model's 2,048-token context; stored history is not unlimited model memory.

## Verification and release status

- Latest focused run: **29 tests passed**, including native Windows event ownership/activation, modifier-held shortcut rearming, persistent history, single-tool completion, multi-call execution, denial handling, permissions and retrieval.
- Source compilation and whitespace checks passed.
- Full local suite after the prompt and action-loop fixes: **264 passed, 2 skipped in 35.75 seconds**. Earlier load-related timeout results are retained in the task history; the final full suite passed.
- Windows, Linux and macOS each passed the 68-test CI regression set on the preceding source revision; CI is rerunning it against the current prompt-selection change.
- A read-only installed-index audit found BGE ONNX active, SQLite integrity `ok`, 297 file/folder records, 538 valid normalized vectors and 256 records still pending chunk migration. No document contents were printed or uploaded. These counts are a point-in-time snapshot.
- The actual local BGE/Qwen flow check passed: normalized token-bounded embeddings, synthetic document retrieval, persisted `Atlas` recall, model-selected `folder_list` and model-selected `file_write` with the written file verified. The latest evidence is [desktop-flows-single-turn.json](../validation/desktop-20261005/latest/desktop-flows-single-turn.json).
- The first Action probe exposed unrelated follow-up calls caused by unconditional code-writing instructions. Scoping those instructions to coding requests and asking the model to stop after success corrected that run; permission checks blocked the unrelated write during the failed probe.
- The Windows x64 release smoke then found a second Action issue: a 6,500-character history block filled the 2,048-token window, and prefix truncation dropped the current request at the end. Action history is now capped at 1,200 characters, and overflow keeps the newest suffix containing the actual request.
- In the latest local run, Qwen loaded in 5.6 seconds and the model-driven folder listing took 47.6 seconds on this CPU. Returning the verified single-tool result removes its second inference; multi-tool flows still need further model turns. This improves the avoidable part of latency but does not make CPU inference instant or guarantee the same timing on other hardware.
- A manual CI job runs the actual bundled BGE/Qwen models against synthetic chat, listing and file-writing tasks. Publication of replacement binaries remains gated on that check.
- Each release package must also complete a model-driven folder listing with successful tool and task events in its isolated SQLite log, in addition to the existing offline BGE, Qwen and streaming checks.
- Native UI automation initialization failed with `failed to write kernel assets: The system cannot find the path specified (os error 3)`. No physical shortcut or complete desktop click-through is claimed.

Anti-slop after-development audit: changes preserve the existing desktop design. The new shortcut status uses the existing pale blue accent to make successful registration and failure legible. Functional regression evidence is recorded above; full visual acceptance remains unverified.

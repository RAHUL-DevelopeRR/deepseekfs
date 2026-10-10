# Release verification in progress

The installed baseline package passed desktop startup and BGE ONNX loading after the previous mixed installation was archived. The baseline Qwen runtime loaded but generated too slowly: first streamed token took 42.85 seconds and folder-list Action timed out.

The replacement build at commit `4e3d5a6` enables dynamically selected CPU variants on Windows x64 and includes the missing variant DLLs in the Python runtime directory. It also preserves multiple sequential Action steps and allows final answers using successful tool observations.

Focused tests: 22 passed. The broader local suite recorded 260 passed, 2 skipped, 3 environment/CLI timeouts and one outdated assertion. The assertion was corrected; the focused suite passed. A separate recheck passed PowerShell but two CLI greetings exceeded 20 seconds. A later synthetic source-model Action probe also timed out. No new installed performance result is claimed yet.

Build: https://github.com/RAHUL-DevelopeRR/deepseekfs/actions/runs/37337296495

Required before completion: all six packaged gates, replacement release publication, Windows x64 checksum validation and installation, installed offline BGE/Qwen/stream/Action check, and all website downloads resolving to the replacement release.

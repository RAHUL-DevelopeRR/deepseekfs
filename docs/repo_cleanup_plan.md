# Repo cleanup plan

This repo mixes source code, generated build outputs, local runtime state, and
manual smoke scripts in the top-level tree. The cleanup goal is to keep source
and release inputs in the repo, while making generated artifacts disposable.

## Keep in the repo

- `app/`, `core/`, `services/`, `ui/`: application source
- `tests/`: automated tests only
- `docs/`: operator and architecture documentation
- `scripts/`: repeatable maintenance and release scripts
- `assets/`: bundled app assets
- `.github/`: CI and release automation
- `README.md`, `requirements.txt`, `neuron_onedir.spec`, `neuron_installer.iss`, `version.py`

## Keep locally, but treat as runtime state

- `storage/`: local index DBs, downloaded models, runtime app state
- `venv/`: workstation-specific Python environment

These should stay out of version control and should not be deleted by default in
cleanup scripts because they can contain expensive-to-rebuild or user-specific data.

## Clean as generated artifacts

- `build/`
- `dist/`
- `installer_output/`
- `.pytest_cache/`
- all `__pycache__/` directories
- all `*.pyc` files

## Extract or isolate

- `aifs/`: vendored upstream subproject. It is not referenced by the main app
  code today, so it should either remain clearly isolated as a separate package
  or be moved to its own repository/submodule later.
- `scripts/manual_smoke/`: manual operator smoke checks that should not sit in
  `tests/` because they depend on optional local models and workstation setup.

## Refactor focus

The biggest god-file boundary cleaned in this pass is `services/tools/`.
It is now split into:

- `services/tools/base.py`
- `services/tools/file_tools.py`
- `services/tools/folder_tools.py`
- `services/tools/search_tools.py`
- `services/tools/execution_tools.py`
- `services/tools/registry.py`

The next large monolith worth splitting is `ui/spotlight_panel.py`.

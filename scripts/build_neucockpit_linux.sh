#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export NEURON_SKIP_QWEN_GGUF="${NEURON_SKIP_QWEN_GGUF:-0}"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller
python3 -c "from services.model_manager import download_llm_model; download_llm_model()"
python3 -m PyInstaller neuron_onedir.spec --noconfirm

mkdir -p dist/release
tar -C dist -czf dist/release/NeuCockpit-v1.0-linux-x64.tar.gz Neuron

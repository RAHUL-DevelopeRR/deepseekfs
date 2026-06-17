#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export NEURON_SKIP_QWEN_GGUF="${NEURON_SKIP_QWEN_GGUF:-0}"

echo "=== NeuCockpit Linux Build ==="
echo "Platform: $(uname -m)"
ARCH=$(uname -m)

python3 -m pip install --upgrade pip

# Filter out Windows-only packages from requirements.txt
grep -viE '(pywin32|pyaudiowpatch|pefile|ctypes\.wintypes)' requirements.txt > /tmp/requirements-linux.txt

# Also filter torch+cpu Windows wheel URL if present
sed -i 's/torch==.*+cpu/torch/g' /tmp/requirements-linux.txt

# Ubuntu ARM64 runners do not have PyQt6 wheels for this pinned version.
# The workflow installs python3-pyqt6 from apt, so do not let pip try to
# build Qt bindings from source.
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    grep -viE '^(PyQt6|PyQt6-Qt6|PyQt6_sip)==|^(PyQt6|PyQt6-Qt6|PyQt6_sip)>=' /tmp/requirements-linux.txt > /tmp/requirements-linux-arm.txt
    mv /tmp/requirements-linux-arm.txt /tmp/requirements-linux.txt
fi

python3 -m pip install pyinstaller huggingface_hub
python3 -m pip install -r /tmp/requirements-linux.txt pyinstaller || {
    echo "Some packages failed, trying with --ignore-installed..."
    python3 -m pip install -r /tmp/requirements-linux.txt pyinstaller --ignore-installed 2>&1 || true
}
python3 -m pip install pyinstaller huggingface_hub

# Download models if not skipping
if [ "${NEURON_SKIP_QWEN_GGUF}" != "1" ]; then
    python3 -c "from services.model_manager import download_llm_model; download_llm_model()" || echo "Model download skipped"
fi

python3 -m PyInstaller neuron_onedir.spec --noconfirm

mkdir -p dist/release
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    OUT="dist/release/NeuCockpit-v1.0-linux-arm64.tar.gz"
else
    OUT="dist/release/NeuCockpit-v1.0-linux-x64.tar.gz"
fi
tar -C dist -czf "$OUT" Neuron

rm -rf dist/release/upload
bash scripts/prepare_release_upload.sh "$OUT" dist/release/upload

echo "=== Build complete ==="
ls -lh dist/release/

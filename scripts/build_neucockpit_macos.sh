#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export NEURON_SKIP_QWEN_GGUF="${NEURON_SKIP_QWEN_GGUF:-0}"

echo "=== NeuCockpit macOS Build ==="
echo "Platform: $(uname -m)"

python3 -m pip install --upgrade pip

# Filter out Windows-only and Linux-specific packages
grep -viE '(pywin32|pyaudiowpatch|pefile|ctypes\.wintypes|vosk)' requirements.txt > /tmp/requirements-macos.txt

# Replace torch+cpu with plain torch (macOS uses MPS or CPU)
sed -i '' 's/torch==.*+cpu/torch/g' /tmp/requirements-macos.txt 2>/dev/null || \
sed 's/torch==.*+cpu/torch/g' requirements.txt > /tmp/requirements-macos.txt

python3 -m pip install -r /tmp/requirements-macos.txt pyinstaller || {
    echo "Some packages failed, retrying..."
    python3 -m pip install -r /tmp/requirements-macos.txt pyinstaller --ignore-installed 2>&1 || true
}

# Download models if not skipping
if [ "${NEURON_SKIP_QWEN_GGUF}" != "1" ]; then
    python3 -c "from services.model_manager import download_llm_model; download_llm_model()" || echo "Model download skipped"
fi

python3 -m PyInstaller neuron_onedir.spec --noconfirm

mkdir -p dist/release
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    VOLNAME="NeuCockpit v1.0 (Apple Silicon)"
    OUTNAME="NeuCockpit-v1.0-macos-arm64.dmg"
else
    VOLNAME="NeuCockpit v1.0 (Intel)"
    OUTNAME="NeuCockpit-v1.0-macos-intel.dmg"
fi

hdiutil create \
  -volname "$VOLNAME" \
  -srcfolder dist/Neuron \
  -ov \
  -format UDZO \
  "dist/release/$OUTNAME"

rm -rf dist/release/upload
bash scripts/prepare_release_upload.sh "dist/release/$OUTNAME" dist/release/upload

echo "=== Build complete ==="
ls -lh dist/release/

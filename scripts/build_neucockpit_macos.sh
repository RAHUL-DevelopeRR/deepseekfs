#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export NEURON_SKIP_QWEN_GGUF="${NEURON_SKIP_QWEN_GGUF:-0}"

echo "=== NeuCockpit macOS Build ==="
echo "Platform: $(uname -m)"

python3 -m pip install --upgrade pip

python3 -m pip install -r requirements-package.txt

# Build llama.cpp as a portable CPU backend. Prebuilt/native wheels can emit
# illegal-instruction crashes on older Intel CPUs.
export CMAKE_ARGS="${CMAKE_ARGS:-} -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_AVX512=OFF"
export FORCE_CMAKE=1
python3 -m pip install --no-cache-dir --force-reinstall --no-binary=llama-cpp-python "llama-cpp-python>=0.3.0"

# Download release models into app-local storage so PyInstaller bundles them.
python3 scripts/prepare_release_models.py

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

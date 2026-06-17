#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export NEURON_SKIP_QWEN_GGUF="${NEURON_SKIP_QWEN_GGUF:-0}"

echo "=== NeuCockpit Linux Build ==="
echo "Platform: $(uname -m)"
ARCH=$(uname -m)

if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    python3 -m venv --system-site-packages .venv-build
    # shellcheck disable=SC1091
    source .venv-build/bin/activate
fi

python -m pip install --upgrade pip

# Filter out Windows-only packages from requirements.txt
grep -viE '(pywin32|pyaudiowpatch|pefile|ctypes\.wintypes|^llama-cpp-python)' requirements.txt > /tmp/requirements-linux.txt

# Also filter torch+cpu Windows wheel URL if present
sed -i 's/torch==.*+cpu/torch/g' /tmp/requirements-linux.txt

# Ubuntu ARM64 runners do not have PyQt6 wheels for this pinned version.
# The workflow installs python3-pyqt6 from apt, so do not let pip try to
# build Qt bindings from source.
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    grep -viE '^(PyQt6|PyQt6-Qt6|PyQt6_sip)==|^(PyQt6|PyQt6-Qt6|PyQt6_sip)>=' /tmp/requirements-linux.txt > /tmp/requirements-linux-arm.txt
    mv /tmp/requirements-linux-arm.txt /tmp/requirements-linux.txt
fi

python -m pip install pyinstaller huggingface_hub cmake ninja
python -m pip install -r /tmp/requirements-linux.txt pyinstaller || {
    echo "Some packages failed, trying with --ignore-installed..."
    python -m pip install -r /tmp/requirements-linux.txt pyinstaller --ignore-installed 2>&1 || true
}
python -m pip install pyinstaller huggingface_hub cmake ninja

# Build llama.cpp as a portable CPU backend. Prebuilt/native wheels can emit
# illegal-instruction crashes on older x64 CPUs.
export CMAKE_ARGS="${CMAKE_ARGS:-} -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_AVX512=OFF"
export FORCE_CMAKE=1
python -m pip install --no-cache-dir --force-reinstall --no-binary=llama-cpp-python "llama-cpp-python>=0.3.0"

# Download release models into app-local storage so PyInstaller bundles them.
python scripts/prepare_release_models.py

python -m PyInstaller neuron_onedir.spec --noconfirm

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

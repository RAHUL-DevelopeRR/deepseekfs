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
    ARCH_LABEL="arm64"
else
    ARCH_LABEL="x64"
fi

PAYLOAD="dist/release/NeuCockpit-v1.0-linux-${ARCH_LABEL}.payload.tar.gz"
OUT="dist/release/NeuCockpit-v1.0-linux-${ARCH_LABEL}.run"
tar -C dist -czf "$PAYLOAD" Neuron

cat > "$OUT" <<'INSTALLER'
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="NeuCockpit"
INSTALL_DIR="${NEUCOCKPIT_INSTALL_DIR:-$HOME/.local/share/NeuCockpit}"
BIN_DIR="${NEUCOCKPIT_BIN_DIR:-$HOME/.local/bin}"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

echo "Installing $APP_NAME to $INSTALL_DIR"
tmp="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

payload_line="$(awk '/^__NEUCOCKPIT_PAYLOAD_BELOW__$/ { print NR + 1; exit }' "$0")"
if [ -z "$payload_line" ]; then
  echo "Installer payload marker not found." >&2
  exit 1
fi

tail -n +"$payload_line" "$0" > "$tmp/payload.tar.gz"
tar -xzf "$tmp/payload.tar.gz" -C "$tmp"

mkdir -p "$(dirname "$INSTALL_DIR")" "$BIN_DIR" "$DESKTOP_DIR"
rm -rf "$INSTALL_DIR"
mv "$tmp/Neuron" "$INSTALL_DIR"

chmod +x "$INSTALL_DIR/NeuCockpit" "$INSTALL_DIR/neufs" "$INSTALL_DIR/NeuronLLMWorker" 2>/dev/null || true
ln -sf "$INSTALL_DIR/NeuCockpit" "$BIN_DIR/neucockpit"
ln -sf "$INSTALL_DIR/neufs" "$BIN_DIR/neufs"

icon_path="$INSTALL_DIR/assets/neuron_icon.png"
if [ ! -f "$icon_path" ]; then
  icon_path="$INSTALL_DIR/assets/neuron_icon.ico"
fi

cat > "$DESKTOP_DIR/neucockpit.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=NeuCockpit
Comment=Semantic search and offline chat workspace
Exec=$INSTALL_DIR/NeuCockpit
Icon=$icon_path
Terminal=false
Categories=Utility;Office;
DESKTOP

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "$APP_NAME installed."
echo "Run it from your app launcher, or start it with: $BIN_DIR/neucockpit"
exit 0

__NEUCOCKPIT_PAYLOAD_BELOW__
INSTALLER
cat "$PAYLOAD" >> "$OUT"
chmod +x "$OUT"
rm -f "$PAYLOAD"

rm -rf dist/release/upload
bash scripts/prepare_release_upload.sh "$OUT" dist/release/upload

echo "=== Build complete ==="
ls -lh dist/release/

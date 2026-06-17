#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: prepare_release_upload.sh <asset-file> <upload-dir>" >&2
  exit 2
fi

ASSET="$1"
UPLOAD_DIR="$2"
CHUNK_BYTES="${NEUCOCKPIT_RELEASE_CHUNK_BYTES:-1900000000}"

if [ ! -f "$ASSET" ]; then
  echo "Asset not found: $ASSET" >&2
  exit 1
fi

mkdir -p "$UPLOAD_DIR"

BASENAME="$(basename "$ASSET")"
SIZE="$(wc -c < "$ASSET" | tr -d ' ')"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ASSET" > "$UPLOAD_DIR/$BASENAME.sha256"
else
  shasum -a 256 "$ASSET" > "$UPLOAD_DIR/$BASENAME.sha256"
fi

if [ "$SIZE" -gt "$CHUNK_BYTES" ]; then
  split -b "$CHUNK_BYTES" -d -a 3 "$ASSET" "$UPLOAD_DIR/$BASENAME.part-"
  cat > "$UPLOAD_DIR/$BASENAME.REASSEMBLE.txt" <<EOF
NeuCockpit v1.0 asset is split because GitHub Release assets must be under 2 GiB.

Original file:
$BASENAME

Reassemble on Linux/macOS:
cat $BASENAME.part-* > $BASENAME
shasum -a 256 -c $BASENAME.sha256

Reassemble on Windows PowerShell:
Get-Content -Encoding Byte -ReadCount 0 $BASENAME.part-* | Set-Content -Encoding Byte $BASENAME
Get-FileHash $BASENAME -Algorithm SHA256

Expected SHA256 is in:
$BASENAME.sha256
EOF
else
  cp "$ASSET" "$UPLOAD_DIR/$BASENAME"
fi

find "$UPLOAD_DIR" -maxdepth 1 -type f | sort | while IFS= read -r f; do
  printf '%s %s bytes\n' "$(basename "$f")" "$(wc -c < "$f" | tr -d ' ')"
done

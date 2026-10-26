#!/bin/sh
# Build the hand-off folder: build/{plainletter.zip, screenshots/, samples/, outputs/, hf-post.md, README.md}
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build"
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$ROOT/screenshots" "$ROOT/samples" "$ROOT/outputs" "$OUT/"
cp "$ROOT/hf-post.md" "$ROOT/README.md" "$OUT/"
cd "$(dirname "$ROOT")"
zip -qr "$OUT/plainletter.zip" "$(basename "$ROOT")" \
  -x "*/build/*" "*/__pycache__/*" "*.pyc" "*/.DS_Store"
echo "$OUT"
ls -la "$OUT"

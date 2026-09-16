#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "usage: $0 EMA_ROOT PATCHED_SOURCE_DIR EXTENSION_DIR [BUILD_DIR]" >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
EMA_ROOT=$(realpath "$1")
PATCHED_SOURCE_DIR=$2
EXTENSION_DIR=$3
BUILD_DIR=${4:-"${PATCHED_SOURCE_DIR}.build"}
PYTHON=${PYTHON:-python3}

for path in "$PATCHED_SOURCE_DIR" "$EXTENSION_DIR" "$BUILD_DIR"; do
  if [[ -e "$path" ]]; then
    echo "refusing to overwrite existing path: $path" >&2
    exit 1
  fi
done

test -f "$EMA_ROOT/hnswlib/hnswlib/hnswalg.h"
test -f "$EMA_ROOT/hnswlib/setup.py"

cp -a "$EMA_ROOT/hnswlib" "$PATCHED_SOURCE_DIR"
for patch_file in \
  ema_closed_range.patch \
  ema_ft_initialization.patch \
  ema_bucket_coverage.patch; do
  patch --fuzz=0 -d "$PATCHED_SOURCE_DIR" -p1 \
    < "$SCRIPT_DIR/$patch_file"
done

"$PYTHON" "$PATCHED_SOURCE_DIR/setup.py" build_ext \
  --build-lib "$EXTENSION_DIR" \
  --build-temp "$BUILD_DIR"

echo "EMA-FTFix-V2 extension written to $EXTENSION_DIR"
sha256sum "$EXTENSION_DIR"/hashannlib*.so

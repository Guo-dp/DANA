#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 6 ]]; then
  echo "Usage: $0 SNAPSHOT_DIR QUERY_PATH INDEX_DIR LOG_DIR ATTR_COUNT N"
  exit 1
fi

SNAPSHOT_DIR="$1"
QUERY_PATH="$2"
INDEX_DIR="$3"
LOG_DIR="$4"
ATTR_COUNT="$5"
N="$6"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

mkdir -p "$INDEX_DIR"
mkdir -p "$LOG_DIR"

echo "[1/3] Preparing attribute-ordered vectors"

python3 scripts/prepare_multi_dsg_data.py \
  --base "$SNAPSHOT_DIR/base.snapshot.fbin" \
  --attrs "$SNAPSHOT_DIR/attrs.snapshot.csv" \
  --attr-count "$ATTR_COUNT" \
  --output "$SNAPSHOT_DIR/multi_dsg"

echo "[2/3] Building per-attribute DSG indexes"

for ((attr=0; attr<ATTR_COUNT; ++attr)); do
  echo "Building attr=$attr"

  ./build/apps/build_static_index \
    -dataset "rebuilt_attr${attr}" \
    -N "$N" \
    -dataset_path \
      "$SNAPSHOT_DIR/multi_dsg/base.attr${attr}.fbin" \
    -query_path "$QUERY_PATH" \
    -index_path "$INDEX_DIR/attr${attr}.dsg" \
    -k 16 \
    -ef_construction 100 \
    -ef_max 200 \
    -alpha 1.0 \
    | tee "$LOG_DIR/build_attr${attr}.log"

  cp \
    "$SNAPSHOT_DIR/multi_dsg/rank_to_original.attr${attr}.ibin" \
    "$INDEX_DIR/rank_to_snapshot.attr${attr}.ibin"
done

echo "[3/3] Installing stable ID mapping"

cp \
  "$SNAPSHOT_DIR/snapshot_to_original.ibin" \
  "$INDEX_DIR/snapshot_to_original.ibin"

echo "Rebuild completed"
echo "Snapshot: $SNAPSHOT_DIR"
echo "Index:    $INDEX_DIR"

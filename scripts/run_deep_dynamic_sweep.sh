#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="${ROOT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT_DIR"
stage="${1:-verify}"
case "$stage" in verify|growth|breakdown|threshold|rebuild) ;; *) echo 'Usage: run_deep_dynamic_sweep.sh verify|growth|breakdown|threshold|rebuild' >&2; exit 2;; esac
BASE="${BASE:-data/deep/base.10M.fbin}"
QUERY="${QUERY:-data/deep/query.public.10K.fbin}"
WORKLOAD_ROOT="${WORKLOAD_ROOT:-data/deep_10m_96d/multiattr_independent}"
INDEX_ROOT="${INDEX_ROOT:-index/static/deep_10m_96d/dana}"
REORDER_ROOT="${REORDER_ROOT:-$WORKLOAD_ROOT/dana}"
LOG_ROOT="${LOG_ROOT:-logs/deep_10m_96d/dynamic_current}"
SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-data/deep_10m_96d/rebuild_current_5pct}"
REBUILT_INDEX_ROOT="${REBUILT_INDEX_ROOT:-index/static/deep_10m_96d/rebuilt_current_5pct}"
default_queries=100
if [[ "$stage" == rebuild ]]; then default_queries=1000; fi
EVAL_QUERIES="${EVAL_QUERIES:-$default_queries}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 - "$BASE" "$QUERY" <<'PY'
import struct, sys
from pathlib import Path
for name, expected_n in zip(sys.argv[1:], (10000000, 10000)):
    path = Path(name)
    with path.open('rb') as stream:
        n, dim = struct.unpack('<II', stream.read(8))
    if n != expected_n or dim != 96 or path.stat().st_size != 8 + n * dim * 4:
        raise SystemExit(f'Invalid DEEP-96D file: {path}: n={n}, dim={dim}')
print('PASS dimension-matched DEEP-10M/public-10K inputs')
PY
[[ "$stage" != verify ]] || exit 0
[[ -x ./build/apps/update_and_query_dana ]] || { echo 'Build update_and_query_dana first' >&2; exit 1; }
mkdir -p "$LOG_ROOT"
common=(-dataset deep_10m_96d -N 10000000 -dataset_path "$BASE" -query_path "$QUERY"
  -attr_path "$WORKLOAD_ROOT/attrs.csv" -filter_path "$WORKLOAD_ROOT/filters.multi_only.csv"
  -index_root "$INDEX_ROOT" -reordered_data_root "$REORDER_ROOT"
  -attr_count 3 -query_num 1000 -query_k 10 -search_ef 1024 -seed 2031
  -eval_queries "$EVAL_QUERIES")
run() {
  local name="$1"; shift
  [[ ! -e "$LOG_ROOT/$name.log" ]] || { echo "Refusing to overwrite $name.log" >&2; exit 1; }
  /usr/bin/time -v ./build/apps/update_and_query_dana "${common[@]}" "$@" > "$LOG_ROOT/$name.log" 2>&1
  grep -E '^base|^after_|^snapshot_exported' "$LOG_ROOT/$name.log"
}
case "$stage" in
growth)
  for count in 1000 5000 10000 25000 50000 100000; do
    run "growth_$count" -insert_count "$count" -update_count "$count" -delete_count "$count" -rebuild_fraction 0.05
  done ;;
breakdown)
  for count in 0 50000 100000; do
    run "insert_only_$count" -insert_count "$count" -update_count 0 -delete_count 0 -rebuild_fraction 0.05
  done ;;
threshold)
  for tau in 0.005 0.01 0.02 0.05 0.10; do
    run "threshold_$tau" -insert_count 100000 -update_count 100000 -delete_count 100000 -rebuild_fraction "$tau"
  done ;;
rebuild)
  run cycle_5pct -insert_count 166667 -update_count 166667 -delete_count 166667 -rebuild_fraction 0.05 -snapshot_dir "$SNAPSHOT_ROOT"
  REORDER_SCRIPT=scripts/prepare_dana_data_memmap.py DSG_EF_MAX=400 \
    bash scripts/dynamic/rebuild_dana_snapshot.sh "$SNAPSHOT_ROOT" "$QUERY" "$REBUILT_INDEX_ROOT" "$LOG_ROOT/build" 3 10000000
  for repeat in 1 2 3; do
    ./build/apps/query_rebuilt_dana -dataset deep_10m_96d_rebuilt -N 10000000 \
      -dataset_path "$SNAPSHOT_ROOT/base.snapshot.fbin" -query_path "$QUERY" \
      -attr_path "$SNAPSHOT_ROOT/attrs.snapshot.csv" -filter_path "$WORKLOAD_ROOT/filters.multi_only.csv" \
      -index_root "$REBUILT_INDEX_ROOT" -reordered_data_root "$SNAPSHOT_ROOT/dana" \
      -stable_mapping_path "$SNAPSHOT_ROOT/snapshot_to_original.ibin" \
      -attr_count 3 -query_num 1000 -query_k 10 -search_ef 1024 -eval_queries "$EVAL_QUERIES" \
      > "$LOG_ROOT/rebuilt_run$repeat.log" 2>&1
  done ;;
esac

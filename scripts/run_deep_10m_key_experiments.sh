#!/usr/bin/env bash
set -Eeuo pipefail

# Run the final DEEP-10M-96D key comparison in resumable stages.
# This script targets the server branch containing the DANA and HNSW
# benchmark executables added during the multi-attribute experiments.

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
DATA_ROOT="${DATA_ROOT:-data/deep_10m_96d}"
WORKLOAD_ROOT="${WORKLOAD_ROOT:-${DATA_ROOT}/multiattr_independent}"
REORDER_ROOT="${REORDER_ROOT:-${WORKLOAD_ROOT}/multi_dsg}"
INDEX_ROOT="${INDEX_ROOT:-index/static/deep_10m_96d}"
DSG_INDEX_ROOT="${DSG_INDEX_ROOT:-${INDEX_ROOT}/multi_dsg}"
HNSW_INDEX="${HNSW_INDEX:-${INDEX_ROOT}/hnsw/M16.hnsw}"
LOG_ROOT="${LOG_ROOT:-logs/deep_10m_96d}"

BASE="${BASE:-data/deep/base.10M.fbin}"
QUERY="${QUERY:-data/deep/query.public.10K.fbin}"
PUBLIC_GT="${PUBLIC_GT:-data/deep/groundtruth.public.10K.ibin}"
ATTRS="${ATTRS:-${WORKLOAD_ROOT}/attrs.csv}"
FILTERS="${FILTERS:-${WORKLOAD_ROOT}/filters.multi_only.csv}"

N="${N:-10000000}"
QUERY_NUM="${QUERY_NUM:-1000}"
QUERY_K="${QUERY_K:-10}"
ATTR_COUNT="${ATTR_COUNT:-3}"
SEED="${SEED:-2031}"
CHUNK_ROWS="${CHUNK_ROWS:-16384}"

DSG_K="${DSG_K:-16}"
DSG_EF_CONSTRUCTION="${DSG_EF_CONSTRUCTION:-100}"
DSG_EF_MAX="${DSG_EF_MAX:-400}"
DSG_ALPHA="${DSG_ALPHA:-1.0}"
HNSW_M="${HNSW_M:-16}"
HNSW_EF_CONSTRUCTION="${HNSW_EF_CONSTRUCTION:-100}"

stage="${1:-all}"

cd "$ROOT_DIR"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_file() {
  [[ -s "$1" ]] || die "required file is missing or empty: $1"
}

need_executable() {
  [[ -x "$1" ]] || die "required executable is missing: $1"
}

run_stage() {
  local wanted="$1"
  [[ "$stage" == "all" || "$stage" == "$wanted" ]]
}

verify_fbin() {
  python3 - "$@" <<'PY'
import struct
import sys
from pathlib import Path

for raw in sys.argv[1:]:
    path = Path(raw)
    with path.open("rb") as stream:
        count, dim = struct.unpack("<II", stream.read(8))
    expected = 8 + count * dim * 4
    actual = path.stat().st_size
    if actual != expected:
        raise SystemExit(
            f"invalid fbin size: {path}, header=({count}, {dim}), "
            f"expected={expected}, actual={actual}"
        )
    print(f"verified {path}: count={count} dim={dim} bytes={actual}")
PY
}

mkdir -p "$LOG_ROOT" "$DSG_INDEX_ROOT" "$(dirname "$HNSW_INDEX")"

if run_stage verify; then
  need_file "$BASE"
  need_file "$QUERY"
  need_file "$PUBLIC_GT"
  verify_fbin "$BASE" "$QUERY"
fi

if run_stage prepare; then
  mkdir -p "$LOG_ROOT/prepare"
  if [[ -s "$ATTRS" && -s "$FILTERS" ]]; then
    echo "[skip] workload already exists: $WORKLOAD_ROOT"
  else
    /usr/bin/time -v python3 scripts/prepare_deep_multiattr_workloads.py \
      --base "$BASE" \
      --query "$QUERY" \
      --groundtruth "$PUBLIC_GT" \
      --output "$WORKLOAD_ROOT" \
      --size "$N" \
      --queries "$QUERY_NUM" \
      --attributes "$ATTR_COUNT" \
      --seed "$SEED" \
      --attribute-mode independent \
      2>&1 | tee "$LOG_ROOT/prepare/workload.log"
  fi
  need_file "$ATTRS"
  need_file "$FILTERS"
fi

if run_stage reorder; then
  need_file "$ATTRS"
  mkdir -p "$LOG_ROOT/prepare"
  complete=yes
  for attr in $(seq 0 $((ATTR_COUNT - 1))); do
    [[ -s "$REORDER_ROOT/base.attr${attr}.fbin" ]] || complete=no
    [[ -s "$REORDER_ROOT/rank_to_original.attr${attr}.ibin" ]] || complete=no
  done
  if [[ "$complete" == yes ]]; then
    echo "[skip] all reordered vectors and mappings already exist"
  else
    /usr/bin/time -v python3 scripts/prepare_multi_dsg_data_memmap.py \
      --base "$BASE" \
      --attrs "$ATTRS" \
      --attr-count "$ATTR_COUNT" \
      --output "$REORDER_ROOT" \
      --chunk-rows "$CHUNK_ROWS" \
      2>&1 | tee "$LOG_ROOT/prepare/reorder.log"
  fi
fi

if run_stage build_dsg; then
  need_executable ./build/apps/build_static_index
  mkdir -p "$LOG_ROOT/build_dsg"
  for attr in $(seq 0 $((ATTR_COUNT - 1))); do
    data_path="$REORDER_ROOT/base.attr${attr}.fbin"
    index_path="$DSG_INDEX_ROOT/attr${attr}.dsg"
    need_file "$data_path"
    if [[ -s "$index_path" ]]; then
      echo "[skip] DSG attr${attr} already exists: $index_path"
      continue
    fi
    echo "===== building DSG attr${attr} ====="
    /usr/bin/time -v ./build/apps/build_static_index \
      -dataset "deep_10m_96d_attr${attr}" \
      -N "$N" \
      -dataset_path "$data_path" \
      -query_path "$QUERY" \
      -index_path "$index_path" \
      -k "$DSG_K" \
      -ef_construction "$DSG_EF_CONSTRUCTION" \
      -ef_max "$DSG_EF_MAX" \
      -alpha "$DSG_ALPHA" \
      -seed "$SEED" \
      2>&1 | tee "$LOG_ROOT/build_dsg/attr${attr}.log"
    need_file "$index_path"
  done
fi

if run_stage build_hnsw; then
  need_executable ./build/apps/build_hnsw_index
  mkdir -p "$LOG_ROOT/build_hnsw"
  if [[ -s "$HNSW_INDEX" ]]; then
    echo "[skip] HNSW already exists: $HNSW_INDEX"
  else
    /usr/bin/time -v ./build/apps/build_hnsw_index \
      -dataset deep_10m_96d \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_path "$HNSW_INDEX" \
      -M "$HNSW_M" \
      -ef_construction "$HNSW_EF_CONSTRUCTION" \
      2>&1 | tee "$LOG_ROOT/build_hnsw/M16.log"
    need_file "$HNSW_INDEX"
  fi
fi

if run_stage query_dsg; then
  need_executable ./build/apps/query_multi_dsg_benchmark
  need_file "$ATTRS"
  need_file "$FILTERS"
  for attr in $(seq 0 $((ATTR_COUNT - 1))); do
    need_file "$DSG_INDEX_ROOT/attr${attr}.dsg"
  done
  mkdir -p "$LOG_ROOT/query/multi_dsg"
  for ef in 768 1024 1536; do
    log="$LOG_ROOT/query/multi_dsg/ef${ef}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] completed DANA ef=$ef"
      continue
    fi
    echo "===== DANA ef=$ef ====="
    ./build/apps/query_multi_dsg_benchmark \
      -dataset deep_10m_96d \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_root "$DSG_INDEX_ROOT" \
      -reordered_data_root "$REORDER_ROOT" \
      -attr_path "$ATTRS" \
      -attr_count "$ATTR_COUNT" \
      -filter_path "$FILTERS" \
      -query_num "$QUERY_NUM" \
      -query_k "$QUERY_K" \
      -search_ef "$ef" \
      -nav_mode adaptive \
      2>&1 | tee "$log"
  done
fi

if run_stage query_post; then
  need_executable ./build/apps/query_hnsw_postfilter_benchmark
  need_file "$HNSW_INDEX"
  mkdir -p "$LOG_ROOT/query/hnsw_postfilter"
  for candidate in 4096 8192 16384; do
    log="$LOG_ROOT/query/hnsw_postfilter/c${candidate}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] completed HNSW post-filter candidate=$candidate"
      continue
    fi
    echo "===== HNSW post-filter candidate=$candidate ====="
    ./build/apps/query_hnsw_postfilter_benchmark \
      -dataset deep_10m_96d \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_path "$HNSW_INDEX" \
      -attr_path "$ATTRS" \
      -attr_count "$ATTR_COUNT" \
      -filter_path "$FILTERS" \
      -query_num "$QUERY_NUM" \
      -query_k "$QUERY_K" \
      -candidate_k "$candidate" \
      -search_ef "$candidate" \
      2>&1 | tee "$log"
  done
fi

if run_stage query_insearch; then
  need_executable ./build/apps/query_hnsw_insearch_benchmark
  need_file "$HNSW_INDEX"
  mkdir -p "$LOG_ROOT/query/hnsw_insearch"
  for ef in 64 128 256; do
    log="$LOG_ROOT/query/hnsw_insearch/ef${ef}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] completed HNSW in-search ef=$ef"
      continue
    fi
    echo "===== HNSW in-search ef=$ef ====="
    ./build/apps/query_hnsw_insearch_benchmark \
      -dataset deep_10m_96d \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_path "$HNSW_INDEX" \
      -attr_path "$ATTRS" \
      -attr_count "$ATTR_COUNT" \
      -filter_path "$FILTERS" \
      -query_num "$QUERY_NUM" \
      -query_k "$QUERY_K" \
      -search_ef "$ef" \
      2>&1 | tee "$log"
  done
fi

if run_stage summarize; then
  python3 scripts/summarize_deep_10m_results.py --log-root "$LOG_ROOT/query"
fi

if [[ "$stage" == all ]]; then
  python3 scripts/summarize_deep_10m_results.py --log-root "$LOG_ROOT/query"
fi


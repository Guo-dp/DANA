#!/usr/bin/env bash
set -Eeuo pipefail

# Follow-up experiments for BigVectorBench app_reviews.
#
# Stages:
#   build_hnsw       build HNSW M16 if missing
#   dsg_high_ef      run Multi-DSG high-ef extension
#   hnsw_post        run HNSW post-filter high candidate curve
#   hnsw_insearch    run HNSW in-search high-ef curve
#   indexed_attrs    run Multi-DSG indexed-attribute ablation
#   summarize        summarize completed logs
#   all              run all stages

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
DATA_ROOT="${DATA_ROOT:-data/bigvectorbench/app_reviews_384_converted}"
INDEX_ROOT="${INDEX_ROOT:-index/static/bigvectorbench_app_reviews}"
DSG_INDEX_ROOT="${DSG_INDEX_ROOT:-${INDEX_ROOT}/multi_dsg}"
HNSW_INDEX="${HNSW_INDEX:-${INDEX_ROOT}/hnsw/M16.hnsw}"
LOG_ROOT="${LOG_ROOT:-logs/bigvectorbench_app_reviews}"

BASE="${BASE:-${DATA_ROOT}/base.277936.fbin}"
QUERY="${QUERY:-${DATA_ROOT}/query.10000.fbin}"
ATTRS="${ATTRS:-${DATA_ROOT}/attrs.csv}"
FILTERS="${FILTERS:-${DATA_ROOT}/filters.csv}"
REORDER_ROOT="${REORDER_ROOT:-${DATA_ROOT}/multi_dsg}"

N="${N:-277936}"
QUERY_NUM="${QUERY_NUM:-10000}"
QUERY_K="${QUERY_K:-10}"
ATTR_COUNT="${ATTR_COUNT:-3}"
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

mkdir -p "$LOG_ROOT/query" "$LOG_ROOT/build_hnsw" "$INDEX_ROOT/hnsw"

if run_stage build_hnsw; then
  need_executable ./build/apps/build_hnsw_index
  need_file "$BASE"
  need_file "$QUERY"
  if [[ -s "$HNSW_INDEX" ]]; then
    echo "[skip] HNSW exists: $HNSW_INDEX"
  else
    /usr/bin/time -v ./build/apps/build_hnsw_index \
      -dataset bigvectorbench_app_reviews \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_path "$HNSW_INDEX" \
      -M "$HNSW_M" \
      -ef_construction "$HNSW_EF_CONSTRUCTION" \
      2>&1 | tee "$LOG_ROOT/build_hnsw/M16.log"
  fi
fi

if run_stage dsg_high_ef; then
  need_executable ./build/apps/query_multi_dsg_benchmark
  for ef in 6144 8192; do
    log="$LOG_ROOT/query/dsg_ef${ef}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] Multi-DSG ef=$ef"
      continue
    fi
    echo "===== BigVectorBench Multi-DSG ef=$ef ====="
    ./build/apps/query_multi_dsg_benchmark \
      -dataset bigvectorbench_app_reviews \
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

if run_stage hnsw_post; then
  need_executable ./build/apps/query_hnsw_postfilter_benchmark
  need_file "$HNSW_INDEX"
  for candidate in 16384 32768 65536; do
    log="$LOG_ROOT/query/hnsw_post_c${candidate}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] HNSW post-filter candidate=$candidate"
      continue
    fi
    echo "===== HNSW post-filter candidate=$candidate ====="
    ./build/apps/query_hnsw_postfilter_benchmark \
      -dataset bigvectorbench_app_reviews \
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

if run_stage hnsw_insearch; then
  need_executable ./build/apps/query_hnsw_insearch_benchmark
  need_file "$HNSW_INDEX"
  for ef in 4096 8192; do
    log="$LOG_ROOT/query/hnsw_insearch_ef${ef}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] HNSW in-search ef=$ef"
      continue
    fi
    echo "===== HNSW in-search ef=$ef ====="
    ./build/apps/query_hnsw_insearch_benchmark \
      -dataset bigvectorbench_app_reviews \
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

if run_stage indexed_attrs; then
  need_executable ./build/apps/query_multi_dsg_benchmark
  mkdir -p "$LOG_ROOT/query/indexed_attrs_ablation"
  for attrs in "0" "1" "0,1" "0,1,2"; do
    safe="${attrs//,/}"
    log="$LOG_ROOT/query/indexed_attrs_ablation/attrs${safe}_ef4096.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] indexed attrs=$attrs"
      continue
    fi
    echo "===== indexed attrs=$attrs ef=4096 ====="
    ./build/apps/query_multi_dsg_benchmark \
      -dataset bigvectorbench_app_reviews \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_root "$DSG_INDEX_ROOT" \
      -reordered_data_root "$REORDER_ROOT" \
      -attr_path "$ATTRS" \
      -attr_count "$ATTR_COUNT" \
      -indexed_attrs "$attrs" \
      -filter_path "$FILTERS" \
      -query_num "$QUERY_NUM" \
      -query_k "$QUERY_K" \
      -search_ef 4096 \
      -nav_mode adaptive \
      2>&1 | tee "$log"
  done
fi

if run_stage summarize; then
  echo "===== Multi-DSG ====="
  for ef in 128 256 512 768 1024 1536 2048 3072 4096 6144 8192; do
    log="$LOG_ROOT/query/dsg_ef${ef}.log"
    [[ -s "$log" ]] || continue
    echo -n "ef=$ef "
    grep '^all' "$log"
  done

  echo "===== HNSW post-filter ====="
  for candidate in 512 1024 2048 4096 8192 16384 32768 65536; do
    log="$LOG_ROOT/query/hnsw_post_c${candidate}.log"
    [[ -s "$log" ]] || continue
    echo -n "candidate=$candidate "
    grep '^all' "$log"
  done

  echo "===== HNSW in-search ====="
  for ef in 128 256 512 1024 2048 4096 8192; do
    log="$LOG_ROOT/query/hnsw_insearch_ef${ef}.log"
    [[ -s "$log" ]] || continue
    echo -n "ef=$ef "
    grep '^all' "$log"
  done

  echo "===== indexed attrs ====="
  for safe in 0 1 01 012; do
    log="$LOG_ROOT/query/indexed_attrs_ablation/attrs${safe}_ef4096.log"
    [[ -s "$log" ]] || continue
    echo -n "attrs=$safe "
    grep '^all' "$log"
  done
fi

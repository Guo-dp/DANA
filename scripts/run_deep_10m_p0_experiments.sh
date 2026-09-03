#!/usr/bin/env bash
set -Eeuo pipefail

# Run the P0 follow-up experiments for DEEP-10M-96D.
#
# Stages:
#   repeat_summary      summarize completed low-load repeat logs with std/p95
#   indexed_attrs       run DANA with 1/2/3 indexed attributes
#   selectivity_filters generate tiny/small/medium/narrow/broad filters
#   prefilter           run Prefiltering on selectivity filters
#   dsg_selectivity     run DANA on selectivity filters
#   hybrid_summary      estimate Hybrid thresholds from completed logs
#   all                 run all stages in the order above

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
DATA_ROOT="${DATA_ROOT:-data/deep_10m_96d}"
WORKLOAD_ROOT="${WORKLOAD_ROOT:-${DATA_ROOT}/multiattr_independent}"
REORDER_ROOT="${REORDER_ROOT:-${WORKLOAD_ROOT}/multi_dsg}"
INDEX_ROOT="${INDEX_ROOT:-index/static/deep_10m_96d}"
DSG_INDEX_ROOT="${DSG_INDEX_ROOT:-${INDEX_ROOT}/multi_dsg}"
LOG_ROOT="${LOG_ROOT:-logs/deep_10m_96d}"

BASE="${BASE:-data/deep/base.10M.fbin}"
QUERY="${QUERY:-data/deep/query.public.10K.fbin}"
ATTRS="${ATTRS:-${WORKLOAD_ROOT}/attrs.csv}"
FILTERS="${FILTERS:-${WORKLOAD_ROOT}/filters.multi_only.csv}"
SELECTIVITY_FILTERS="${SELECTIVITY_FILTERS:-${WORKLOAD_ROOT}/filters.selectivity.csv}"

N="${N:-10000000}"
QUERY_NUM="${QUERY_NUM:-1000}"
QUERY_K="${QUERY_K:-10}"
ATTR_COUNT="${ATTR_COUNT:-3}"
SEARCH_EF="${SEARCH_EF:-1024}"
SEED="${SEED:-2033}"

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

need_script() {
  [[ -s "$1" ]] || die "required script is missing: $1"
}

run_stage() {
  local wanted="$1"
  [[ "$stage" == "all" || "$stage" == "$wanted" ]]
}

if run_stage repeat_summary; then
  mkdir -p "$LOG_ROOT/query/repeat_clean"
  python3 scripts/summarize_repeat_clean.py \
    --root "$LOG_ROOT/query/repeat_clean" \
    | tee "$LOG_ROOT/query/repeat_clean/summary_std_p95.txt"
fi

if run_stage indexed_attrs; then
  need_executable ./build/apps/query_multi_dsg_benchmark
  need_file "$BASE"
  need_file "$QUERY"
  need_file "$ATTRS"
  need_file "$FILTERS"
  mkdir -p "$LOG_ROOT/query/indexed_attrs_ablation"

  for attrs in "0" "0,1" "0,1,2"; do
    safe="${attrs//,/}"
    log="$LOG_ROOT/query/indexed_attrs_ablation/attrs${safe}_ef${SEARCH_EF}.log"
    if [[ -s "$log" ]] && grep -q '^all' "$log"; then
      echo "[skip] completed indexed attrs=$attrs"
      continue
    fi
    echo "===== indexed attrs=$attrs ef=$SEARCH_EF ====="
    ./build/apps/query_multi_dsg_benchmark \
      -dataset deep_10m_96d \
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
      -search_ef "$SEARCH_EF" \
      -nav_mode adaptive \
      2>&1 | tee "$log"
  done
fi

if run_stage selectivity_filters; then
  need_script scripts/generate_deep_selectivity_filters.py
  need_file "$ATTRS"
  mkdir -p "$LOG_ROOT/prefilter_hybrid"
  if [[ -s "$SELECTIVITY_FILTERS" ]]; then
    echo "[skip] selectivity filters already exist: $SELECTIVITY_FILTERS"
  else
    python3 scripts/generate_deep_selectivity_filters.py \
      --attrs "$ATTRS" \
      --output "$SELECTIVITY_FILTERS" \
      --attr-count "$ATTR_COUNT" \
      --queries "$QUERY_NUM" \
      --seed "$SEED" \
      2>&1 | tee "$LOG_ROOT/prefilter_hybrid/generate_filters.log"
  fi
fi

if run_stage prefilter; then
  need_script scripts/query_multi_prefilter_rank.py
  need_file "$BASE"
  need_file "$QUERY"
  need_file "$ATTRS"
  need_file "$SELECTIVITY_FILTERS"
  mkdir -p "$LOG_ROOT/prefilter_hybrid"
  log="$LOG_ROOT/prefilter_hybrid/prefilter_selectivity.log"
  if [[ -s "$log" ]] && grep -q '^all' "$log"; then
    echo "[skip] completed prefilter selectivity"
  else
    python3 scripts/query_multi_prefilter_rank.py \
      --base "$BASE" \
      --query "$QUERY" \
      --attrs "$ATTRS" \
      --rank-root "$REORDER_ROOT" \
      --filters "$SELECTIVITY_FILTERS" \
      --attr-count "$ATTR_COUNT" \
      --query-num "$QUERY_NUM" \
      --topk "$QUERY_K" \
      2>&1 | tee "$log"
  fi
fi

if run_stage dsg_selectivity; then
  need_executable ./build/apps/query_multi_dsg_benchmark
  need_file "$SELECTIVITY_FILTERS"
  mkdir -p "$LOG_ROOT/prefilter_hybrid"
  log="$LOG_ROOT/prefilter_hybrid/multi_dsg_selectivity_ef${SEARCH_EF}.log"
  if [[ -s "$log" ]] && grep -q '^all' "$log"; then
    echo "[skip] completed DANA selectivity"
  else
    ./build/apps/query_multi_dsg_benchmark \
      -dataset deep_10m_96d \
      -N "$N" \
      -dataset_path "$BASE" \
      -query_path "$QUERY" \
      -index_root "$DSG_INDEX_ROOT" \
      -reordered_data_root "$REORDER_ROOT" \
      -attr_path "$ATTRS" \
      -attr_count "$ATTR_COUNT" \
      -filter_path "$SELECTIVITY_FILTERS" \
      -query_num "$QUERY_NUM" \
      -query_k "$QUERY_K" \
      -search_ef "$SEARCH_EF" \
      -nav_mode adaptive \
      2>&1 | tee "$log"
  fi
fi

if run_stage hybrid_summary; then
  python3 scripts/summarize_hybrid_thresholds.py \
    --prefilter-log "$LOG_ROOT/prefilter_hybrid/prefilter_selectivity.log" \
    --dsg-log "$LOG_ROOT/prefilter_hybrid/multi_dsg_selectivity_ef${SEARCH_EF}.log" \
    --thresholds 1000,5000,10000,50000 \
    | tee "$LOG_ROOT/prefilter_hybrid/hybrid_thresholds_ef${SEARCH_EF}.txt"
fi

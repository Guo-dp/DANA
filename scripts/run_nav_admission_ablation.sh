#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$HOME/snap/VD/DRFA/Dynamic-Range-Filtering-ANNS-release_version}"
RUNS="${1:-3}"
EF="${EF:-1024}"
LOG_ROOT="${LOG_ROOT:-$ROOT_DIR/logs/deep_10m_96d/followup/nav_admission}"

cd "$ROOT_DIR"
mkdir -p "$LOG_ROOT"

run_one() {
  local run="$1"
  local mode="$2"
  local stem="$LOG_ROOT/${mode}_ef${EF}_run${run}"

  ./build/apps/query_dana_benchmark \
    -dataset deep_10m_96d \
    -N 10000000 \
    -dataset_path data/deep/base.10M.fbin \
    -query_path data/deep/query.public.10K.fbin \
    -index_root index/static/deep_10m_96d/dana \
    -reordered_data_root data/deep_10m_96d/multiattr_independent/dana \
    -attr_path data/deep_10m_96d/multiattr_independent/attrs.csv \
    -attr_count 3 \
    -filter_path data/deep_10m_96d/multiattr_independent/filters.multi_only.csv \
    -query_num 1000 \
    -query_k 10 \
    -search_ef "$EF" \
    -nav_mode adaptive \
    -admission_mode "$mode" \
    -per_query_path "${stem}.csv" \
    > "${stem}.log" 2>&1
}

for run in $(seq 1 "$RUNS"); do
  if (( run % 2 == 0 )); then
    modes=(hard_prune bridge)
  else
    modes=(bridge hard_prune)
  fi

  for mode in "${modes[@]}"; do
    echo "run=$run admission_mode=$mode ef=$EF"
    run_one "$run" "$mode"
    grep '^all' "$LOG_ROOT/${mode}_ef${EF}_run${run}.log"
  done
done

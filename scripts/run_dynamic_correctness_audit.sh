#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$HOME/snap/VD/DRFA/Dynamic-Range-Filtering-ANNS-release_version}"
LOG_ROOT="${LOG_ROOT:-$ROOT_DIR/logs/multiattr_100k_independent/dynamic_correctness}"

cd "$ROOT_DIR"
mkdir -p "$LOG_ROOT"

./build/apps/update_and_query_multi_dsg \
  -dataset multiattr_100k_independent \
  -N 100000 \
  -dataset_path data/multiattr_100k_independent/base.100000.fbin \
  -query_path data/multiattr_100k_independent/query.300.fbin \
  -attr_path data/multiattr_100k_independent/attrs.csv \
  -filter_path data/multiattr_100k_independent/filters.csv \
  -index_root index/static/multiattr_100k_independent/multi_dsg \
  -reordered_data_root data/multiattr_100k_independent/multi_dsg \
  -attr_count 3 \
  -query_num 300 \
  -query_k 10 \
  -search_ef 512 \
  -eval_queries 300 \
  -insert_count 1000 \
  -update_count 1000 \
  -delete_count 1000 \
  -seed 2030 \
  -rebuild_fraction 0.05 \
  -audit_correctness 1 \
  > "$LOG_ROOT/audit_count1000.log" 2>&1

grep -E '^base|^after_|^audit' \
  "$LOG_ROOT/audit_count1000.log"

test "$(grep -c '^audit phase=' "$LOG_ROOT/audit_count1000.log")" -eq 4

if grep -Eq '[a-z_]+_violations=[1-9][0-9]*' \
  "$LOG_ROOT/audit_count1000.log"; then
  echo "Correctness audit failed" >&2
  exit 1
fi

./build/apps/query_rebuilt_multi_dsg \
  -dataset multiattr_100k_independent_rebuilt \
  -N 100000 \
  -dataset_path data/multiattr_100k_independent/rebuild_snapshot/base.snapshot.fbin \
  -query_path data/multiattr_100k_independent/query.300.fbin \
  -attr_path data/multiattr_100k_independent/rebuild_snapshot/attrs.snapshot.csv \
  -filter_path data/multiattr_100k_independent/filters.csv \
  -index_root index/static/multiattr_100k_independent/rebuilt_multi_dsg \
  -reordered_data_root data/multiattr_100k_independent/rebuild_snapshot/multi_dsg \
  -stable_mapping_path data/multiattr_100k_independent/rebuild_snapshot/snapshot_to_original.ibin \
  -attr_count 3 \
  -query_num 300 \
  -query_k 10 \
  -search_ef 512 \
  -eval_queries 300 \
  -insert_count 100 \
  -update_count 100 \
  -delete_count 100 \
  -original_base_size 100000 \
  -audit_correctness 1 \
  > "$LOG_ROOT/audit_post_rebuild_count100.log" 2>&1

grep -E '^base|^audit' \
  "$LOG_ROOT/audit_post_rebuild_count100.log"

if grep -Eq '[a-z_]+_violations=[1-9][0-9]*' \
  "$LOG_ROOT/audit_post_rebuild_count100.log"; then
  echo "Post-rebuild correctness audit failed" >&2
  exit 1
fi

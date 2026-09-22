#!/usr/bin/env bash
set -uo pipefail

ROOT="$HOME/snap/VD/DRFA/Dynamic-Range-Filtering-ANNS-release_version"
cd "$ROOT" || exit 1

APP="./build/apps/update_and_query_dana"
LOG_ROOT="logs/deep_multi_independent/dynamic"

if [ ! -x "$APP" ]; then
    echo "ERROR: missing executable: $APP"
    exit 1
fi

mkdir -p "$LOG_ROOT"

export OMP_NUM_THREADS=32
export OMP_PROC_BIND=close
export OMP_PLACES=cores

# 0.1%, 0.5%, 1%, 2%, 5% of the 1M base.
COUNTS=(1000 5000 10000 20000 50000)

for count in "${COUNTS[@]}"; do
    log="$LOG_ROOT/count${count}.log"

    echo "===== DEEP dynamic count=$count ====="

    /usr/bin/time -v \
    "$APP" \
      -dataset deep_multi_independent \
      -N 1000000 \
      -dataset_path data/deep/base.1M.fbin \
      -query_path data/deep/query.derived.1K.200d.fbin \
      -attr_path data/deep/multiattr_independent/attrs.csv \
      -attr_count 3 \
      -filter_path data/deep/multiattr_independent/filters.multi_only.csv \
      -index_root index/static/deep_multi_independent/dana \
      -reordered_data_root data/deep/multiattr_independent/dana \
      -query_num 100 \
      -query_k 10 \
      -search_ef 1024 \
      -insert_count "$count" \
      -update_count "$count" \
      -delete_count "$count" \
      -rebuild_fraction 0.05 \
      > "$log" 2>&1

    status=$?

    echo "count=$count status=$status"

    if [ "$status" -ne 0 ]; then
        echo "ERROR: failed at count=$count"
        tail -50 "$log"
        exit "$status"
    fi

    grep -E \
      '^base|^after_insert|^after_update|^after_delete' \
      "$log"

    # Verify that command-line counts were actually accepted.
    expected_delta=$((count * 2))
    actual_delta=$(
        awk '
          /^after_delete/ {
            for (i = 1; i <= NF; ++i) {
              if ($i ~ /^delta_size=/) {
                split($i, value, "=")
                print value[2]
              }
            }
          }
        ' "$log"
    )

    if [ -z "$actual_delta" ]; then
        echo "ERROR: delta_size missing from $log"
        exit 1
    fi

    if [ "$actual_delta" -ne "$expected_delta" ]; then
        echo "ERROR: expected delta_size=$expected_delta, got $actual_delta"
        echo "Check dynamic benchmark argument names."
        exit 1
    fi
done

echo "DEEP dynamic sweep completed."

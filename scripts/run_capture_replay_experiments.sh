#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/build/capture_replay_experiment}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/results/capture_replay}"
BASELINE_REF="c10676c0056b5b9a2c35e15b8361422bc194332f"
mkdir -p "$WORK_DIR" "$OUT_DIR"
if [[ -e "$OUT_DIR/correctness.log" ]]; then
    echo "Refusing to overwrite an existing campaign; choose another OUT_DIR" >&2
    exit 1
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
BASELINE_SOURCE="${BASELINE_SOURCE:-$WORK_DIR/v3_source}"
if [[ ! -f "$BASELINE_SOURCE/CMakeLists.txt" ]]; then
    mkdir -p "$BASELINE_SOURCE"
    git -C "$ROOT_DIR" archive "$BASELINE_REF" | tar -x -C "$BASELINE_SOURCE"
    cp "$ROOT_DIR/apps/CMakeLists.txt" "$BASELINE_SOURCE/apps/CMakeLists.txt"
    cp "$ROOT_DIR/tests/test_dynamic_stable_ids.cpp" "$BASELINE_SOURCE/tests/"
    cp "$ROOT_DIR/tests/test_dynamic_capture_replay.cpp" "$BASELINE_SOURCE/tests/"
fi
{
    date -u --iso-8601=seconds
    hostname
    uname -a
    g++ --version
    cmake --version
    lscpu
    free -h
    echo "baseline_ref=$BASELINE_REF"
    echo "threads=1 repetitions=5 warmup_queries=40 measured_queries_per_phase=400 k=10 ef=128"
    sha256sum "$ROOT_DIR/include/dynamic_dana.h" "$ROOT_DIR/src/dynamic_dana.cc"
    sha256sum "$ROOT_DIR/tests/test_dynamic_stable_ids.cpp" "$ROOT_DIR/tests/test_dynamic_capture_replay.cpp"
    sha256sum "$BASELINE_SOURCE/include/dynamic_dana.h" "$BASELINE_SOURCE/src/dynamic_dana.cc"
} > "$OUT_DIR/environment.txt"
cmake -S "$ROOT_DIR" -B "$WORK_DIR/current" -DCMAKE_BUILD_TYPE=Release > "$OUT_DIR/configure_current.log" 2>&1
cmake --build "$WORK_DIR/current" -j 2 --target test_dynamic_capture_replay test_dynamic_stable_ids > "$OUT_DIR/build_current.log" 2>&1
cmake -S "$BASELINE_SOURCE" -B "$WORK_DIR/baseline" -DCMAKE_BUILD_TYPE=Release -DDANA_REPLAY_PERF_BASELINE=ON > "$OUT_DIR/configure_baseline.log" 2>&1
cmake --build "$WORK_DIR/baseline" -j 2 --target test_dynamic_capture_replay > "$OUT_DIR/build_baseline.log" 2>&1
"$WORK_DIR/current/apps/test_dynamic_stable_ids" "$WORK_DIR/stable_ids" > "$OUT_DIR/stable_ids.log" 2>&1
"$WORK_DIR/current/apps/test_dynamic_capture_replay" correctness "$WORK_DIR/correctness" > "$OUT_DIR/correctness.log" 2>&1
cp "$WORK_DIR/correctness/"*_operations.csv "$OUT_DIR/"
for run in 1 2 3 4 5; do
    case "$((run % 3))" in
        1) variants=(v3_baseline journal_off journal_on);;
        2) variants=(journal_on v3_baseline journal_off);;
        0) variants=(journal_off journal_on v3_baseline);;
    esac
    for variant in "${variants[@]}"; do
        echo "run=$run variant=$variant"
        uptime >> "$OUT_DIR/load.txt"
        binary="$WORK_DIR/current/apps/test_dynamic_capture_replay"
        args=()
        if [[ "$variant" == v3_baseline ]]; then binary="$WORK_DIR/baseline/apps/test_dynamic_capture_replay"; fi
        if [[ "$variant" == journal_on ]]; then args=(logging); fi
        /usr/bin/time -v -o "$OUT_DIR/${variant}_run${run}.time.txt" \
            "$binary" perf "$WORK_DIR/${variant}_run${run}" "$run" "${args[@]}" \
            > "$OUT_DIR/${variant}_run${run}.log" 2>&1
        cp "$WORK_DIR/${variant}_run${run}/performance.csv" "$OUT_DIR/${variant}_run${run}.csv"
    done
done
grep '^ALL PASS' "$OUT_DIR/correctness.log" "$OUT_DIR/stable_ids.log"
python3 "$ROOT_DIR/scripts/summarize_capture_replay.py" "$OUT_DIR" --pack
echo "DONE results=$OUT_DIR"

# Reproducibility Guide

## 1. Environment And Build

Recommended environment: Linux x86-64, CMake >= 3.16, GCC or Clang with C++17 and OpenMP, Python >= 3.10.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m compileall -q scripts analysis
python3 scripts/verify_bundled_data.py

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
ls build/apps
```

Important executables include:

```text
build_static_index
query_dana_benchmark
build_hnsw_index
query_hnsw_postfilter_benchmark
query_hnsw_insearch_benchmark
update_and_query_dana
query_rebuilt_dana
```

## 2. Small Deterministic Validation

Regenerate and validate the bundled workloads:

```bash
python3 scripts/generate_vector_calc_sanity_data.py
python3 scripts/generate_multiattr_smoke_data.py
python3 scripts/verify_bundled_data.py
```

Build one DSG per attribute and run the integrated query path:

```bash
python3 scripts/prepare_dana_data_memmap.py \
  --base data/vector_calc_sanity/base.8.fbin \
  --attrs data/vector_calc_sanity/attrs.csv \
  --attr-count 3 \
  --output data/vector_calc_sanity/dana \
  --chunk-rows 8

mkdir -p index/static/vector_calc_sanity/dana
for attr in 0 1 2; do
  ./build/apps/build_static_index \
    -dataset vector_calc_sanity_attr${attr} -N 8 \
    -dataset_path data/vector_calc_sanity/dana/base.attr${attr}.fbin \
    -query_path data/vector_calc_sanity/query.3.fbin \
    -index_path index/static/vector_calc_sanity/dana/attr${attr}.dsg \
    -k 4 -ef_construction 8 -ef_max 8 -alpha 1.0
done

./build/apps/query_dana_benchmark \
  -dataset vector_calc_sanity -N 8 \
  -dataset_path data/vector_calc_sanity/base.8.fbin \
  -query_path data/vector_calc_sanity/query.3.fbin \
  -index_root index/static/vector_calc_sanity/dana \
  -reordered_data_root data/vector_calc_sanity/dana \
  -attr_path data/vector_calc_sanity/attrs.csv \
  -attr_count 3 \
  -filter_path data/vector_calc_sanity/filters.csv \
  -query_num 3 -query_k 3 -search_ef 8 -nav_mode adaptive
```

Expected aggregate recall is `1.0000`.

The navigation--admission code path can be switched without rebuilding any
index. Add `-admission_mode bridge` (the default) to use bridge-preserving
traversal, or add `-admission_mode hard_prune` for the controlled
full-predicate hard-pruning ablation.

## 3. DEEP-10M Paper Workflow

Download dimension-matched DEEP files into `data/deep/`:

```bash
mkdir -p data/deep
wget -c https://storage.yandexcloud.net/yandex-research/ann-datasets/DEEP/base.10M.fbin \
  -O data/deep/base.10M.fbin
wget -c https://storage.yandexcloud.net/yandex-research/ann-datasets/DEEP/query.public.10K.fbin \
  -O data/deep/query.public.10K.fbin
wget -c https://storage.yandexcloud.net/yandex-research/ann-datasets/DEEP/groundtruth.public.10K.ibin \
  -O data/deep/groundtruth.public.10K.ibin
```

The base and query must both be 96-dimensional. Run the staged workflow:

```bash
bash scripts/run_deep_10m_key_experiments.sh verify
bash scripts/run_deep_10m_key_experiments.sh prepare
bash scripts/run_deep_10m_key_experiments.sh reorder
bash scripts/run_deep_10m_key_experiments.sh build_dsg
bash scripts/run_deep_10m_key_experiments.sh build_hnsw
bash scripts/run_deep_10m_key_experiments.sh query_dsg
bash scripts/run_deep_10m_key_experiments.sh query_post
bash scripts/run_deep_10m_key_experiments.sh query_insearch
bash scripts/run_deep_10m_key_experiments.sh summarize
```

The build requires substantial time and storage. The synchronized run produced three DSG indexes of roughly 34 GiB each and one HNSW index of roughly 5 GiB.

After those indexes exist, reproduce the paired DEEP-10M
navigation--admission ablation with:

```bash
bash scripts/run_nav_admission_ablation.sh 3
python3 scripts/summarize_nav_admission_ablation.py \
  logs/deep_10m_96d/followup/nav_admission \
  --output results/followup_experiments/nav_admission_deep10m/summary.csv
```

The runner alternates execution order across repetitions and changes only
`-admission_mode`; the DSGs, queries, routing, `k`, and `ef` are fixed.

## 4. BigVectorBench App-Reviews

Place `app_reviews-384-euclidean-filter.hdf5` in `data/bigvectorbench/`, then convert it:

```bash
python3 scripts/convert_bigvectorbench_hdf5.py --help
python3 scripts/convert_bigvectorbench_hdf5.py \
  --input data/bigvectorbench/app_reviews-384-euclidean-filter.hdf5 \
  --output data/bigvectorbench/app_reviews_384_converted
```

Prepare per-attribute rank order and build the three DSG indexes:

```bash
python3 scripts/prepare_dana_data_memmap.py \
  --base data/bigvectorbench/app_reviews_384_converted/base.277936.fbin \
  --attrs data/bigvectorbench/app_reviews_384_converted/attrs.csv \
  --attr-count 3 \
  --output data/bigvectorbench/app_reviews_384_converted/dana \
  --chunk-rows 16384

mkdir -p index/static/bigvectorbench_app_reviews/dana
for attr in 0 1 2; do
  ./build/apps/build_static_index \
    -dataset bigvectorbench_app_reviews_attr${attr} -N 277936 \
    -dataset_path data/bigvectorbench/app_reviews_384_converted/dana/base.attr${attr}.fbin \
    -query_path data/bigvectorbench/app_reviews_384_converted/query.10000.fbin \
    -index_path index/static/bigvectorbench_app_reviews/dana/attr${attr}.dsg \
    -k 16 -ef_construction 100 -ef_max 400 -alpha 1.0
done
```

Use the follow-up runner for HNSW construction, high-budget curves, routing, and indexed-attribute ablations:

```bash
bash scripts/run_bigvectorbench_followup.sh build_hnsw
bash scripts/run_bigvectorbench_followup.sh dsg_high_ef
bash scripts/run_bigvectorbench_followup.sh hnsw_post
bash scripts/run_bigvectorbench_followup.sh hnsw_insearch
bash scripts/run_bigvectorbench_followup.sh indexed_attrs
bash scripts/run_bigvectorbench_followup.sh summarize
```

The checked-in runner is the authoritative source for path overrides and sweep parameters.

## 5. Dynamic Evaluation

Run the growing-Delta sweep after preparing DEEP indexes:

```bash
bash scripts/run_deep_dynamic_sweep.sh
```

The runner evaluates update counts `1000 5000 10000 20000 50000`, records insert/update/delete stages, and checks the expected Delta size. For snapshot rebuilding:

```bash
bash scripts/dynamic/rebuild_dana_snapshot.sh \
  SNAPSHOT_DIR QUERY_PATH INDEX_DIR LOG_DIR ATTR_COUNT N
```

The dynamic design keeps stable original IDs, scans the Delta exactly, suppresses Base versions with tombstones, and rebuilds rank-based DSG indexes from a snapshot.

### Fresh-clone prerequisites for the dynamic correctness audit

After installing the Python dependencies and completing the Release build in
Section 1, run the following from the repository root. Generate the independent
100K workload (32 dimensions, three attributes, 300 queries), reorder it by each
attribute, and build the three initial DSG indexes used by DANA:

```bash
python3 scripts/generate_multiattr_independent_data.py \
  --output data/multiattr_100k_independent \
  --size 100000 --dim 32 --queries 300 --topk 10 --seed 2029

python3 scripts/prepare_dana_data.py \
  --base data/multiattr_100k_independent/base.100000.fbin \
  --attrs data/multiattr_100k_independent/attrs.csv \
  --attr-count 3 --output data/multiattr_100k_independent/dana

mkdir -p index/static/multiattr_100k_independent/dana
for attr in 0 1 2; do
  ./build/apps/build_static_index \
    -dataset "multiattr_100k_independent_attr${attr}" -N 100000 \
    -dataset_path "data/multiattr_100k_independent/dana/base.attr${attr}.fbin" \
    -query_path data/multiattr_100k_independent/query.300.fbin \
    -index_path "index/static/multiattr_100k_independent/dana/attr${attr}.dsg" \
    -k 16 -ef_construction 100 -ef_max 200 -alpha 1.0
done
```

Export a committed snapshot after 100 insertions, 100 attribute updates, and
100 deletions. These counts match the post-rebuild audit's expected stable IDs.
The snapshot still contains 100000 points because insertions and deletions
balance. The explicit `-rebuild_fraction 0.001` triggers export after the 300
changed IDs; the default 0.05 threshold would not export this small update batch.

```bash
./build/apps/update_and_query_dana \
  -dataset multiattr_100k_independent -N 100000 \
  -dataset_path data/multiattr_100k_independent/base.100000.fbin \
  -query_path data/multiattr_100k_independent/query.300.fbin \
  -attr_path data/multiattr_100k_independent/attrs.csv \
  -filter_path data/multiattr_100k_independent/filters.csv \
  -index_root index/static/multiattr_100k_independent/dana \
  -reordered_data_root data/multiattr_100k_independent/dana \
  -attr_count 3 -query_num 300 -query_k 10 -search_ef 512 \
  -eval_queries 300 -insert_count 100 -update_count 100 -delete_count 100 \
  -seed 2030 -rebuild_fraction 0.001 -audit_correctness 1 \
  -snapshot_dir data/multiattr_100k_independent/rebuild_snapshot

test -s data/multiattr_100k_independent/rebuild_snapshot/base.snapshot.fbin
test -s data/multiattr_100k_independent/rebuild_snapshot/snapshot_to_original.ibin

bash scripts/dynamic/rebuild_dana_snapshot.sh \
  data/multiattr_100k_independent/rebuild_snapshot \
  data/multiattr_100k_independent/query.300.fbin \
  index/static/multiattr_100k_independent/rebuilt_dana \
  logs/multiattr_100k_independent/rebuild 3 100000
```

The rebuild helper reorders `base.snapshot.fbin` and `attrs.snapshot.csv` into
`rebuild_snapshot/dana`, builds `attr0.dsg` through `attr2.dsg` under
`rebuilt_dana`, and installs the rank and stable-ID mappings. Its six positional
arguments are snapshot directory, query file, index directory, log directory,
attribute count, and snapshot point count.

Now run the sequential committed-state audit. Its first phase independently
applies 1000 insertions, updates, and deletions to the original indexes; its
second phase checks the 100-operation snapshot prepared above:

```bash
bash scripts/run_dynamic_correctness_audit.sh
```

The three experiment runners `run_nav_admission_ablation.sh`,
`run_dynamic_correctness_audit.sh`, and `run_deep_dynamic_sweep.sh` resolve the
repository root from their own script locations. Set `ROOT_DIR` to override it.

The script fails if any stale-version, deleted-ID, duplicate-ID, predicate,
invalid-ID, insertion-visibility, update-visibility, or deletion-visibility
counter is nonzero.

All `*_visibility_violations` values are violation counts rather than visible
object counts. A value of zero means that no violation was detected. The exact
control variables for the hard-pruning ablation and the audit-counter semantics
are documented in `docs/CONTROLLED_ABLATION_AND_DYNAMIC_AUDIT.md`.

## 6. Result Verification

Compact paper-point summaries, per-run statistics, audit outputs, and provenance manifests are retained under `results/` and `reproducibility/`. Large historical timing archives are intentionally excluded from the compact public artifact.

## 7. Timing Protocol

Run one benchmark process at a time. Record CPU, memory, compiler, thread count, and machine load. Repeat timing points at least three times. Use clean low-load runs for latency/QPS summaries; preserve but do not average known shared-server anomaly runs. Recall and deterministic work counters may still be compared when their output is identical.

## 8. DANA/EMA Static Comparison

The paper baseline package is documented separately in [DANA_EMA_REPRODUCIBILITY.md](DANA_EMA_REPRODUCIBILITY.md). It includes:

- the exact DANA JSONL adapter used by the formal measurements;
- a shared workload converter and exact evaluator;
- three isolated EMA-FTFix-V2 patch files and a zero-fuzz application script;
- frozen search grids, App validation/test split, and selected operating points;
- compact five-run results and a machine-readable audit.

The comparison uses exact boundary-tie Recall and does not claim a dynamic-maintenance comparison with EMA.

Regenerate the five-run variability table with:

```bash
python3 scripts/baselines/summarize_repetition_variability.py
```


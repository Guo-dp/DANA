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
query_multi_dsg_benchmark
build_hnsw_index
query_hnsw_postfilter_benchmark
query_hnsw_insearch_benchmark
update_and_query_multi_dsg
query_rebuilt_multi_dsg
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
python3 scripts/prepare_multi_dsg_data_memmap.py \
  --base data/vector_calc_sanity/base.8.fbin \
  --attrs data/vector_calc_sanity/attrs.csv \
  --attr-count 3 \
  --output data/vector_calc_sanity/multi_dsg \
  --chunk-rows 8

mkdir -p index/static/vector_calc_sanity/multi_dsg
for attr in 0 1 2; do
  ./build/apps/build_static_index \
    -dataset vector_calc_sanity_attr${attr} -N 8 \
    -dataset_path data/vector_calc_sanity/multi_dsg/base.attr${attr}.fbin \
    -query_path data/vector_calc_sanity/query.3.fbin \
    -index_path index/static/vector_calc_sanity/multi_dsg/attr${attr}.dsg \
    -k 4 -ef_construction 8 -ef_max 8 -alpha 1.0
done

./build/apps/query_multi_dsg_benchmark \
  -dataset vector_calc_sanity -N 8 \
  -dataset_path data/vector_calc_sanity/base.8.fbin \
  -query_path data/vector_calc_sanity/query.3.fbin \
  -index_root index/static/vector_calc_sanity/multi_dsg \
  -reordered_data_root data/vector_calc_sanity/multi_dsg \
  -attr_path data/vector_calc_sanity/attrs.csv \
  -attr_count 3 \
  -filter_path data/vector_calc_sanity/filters.csv \
  -query_num 3 -query_k 3 -search_ef 8 -nav_mode adaptive
```

Expected aggregate recall is `1.0000`.

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
python3 scripts/prepare_multi_dsg_data_memmap.py \
  --base data/bigvectorbench/app_reviews_384_converted/base.277936.fbin \
  --attrs data/bigvectorbench/app_reviews_384_converted/attrs.csv \
  --attr-count 3 \
  --output data/bigvectorbench/app_reviews_384_converted/multi_dsg \
  --chunk-rows 16384

mkdir -p index/static/bigvectorbench_app_reviews/multi_dsg
for attr in 0 1 2; do
  ./build/apps/build_static_index \
    -dataset bigvectorbench_app_reviews_attr${attr} -N 277936 \
    -dataset_path data/bigvectorbench/app_reviews_384_converted/multi_dsg/base.attr${attr}.fbin \
    -query_path data/bigvectorbench/app_reviews_384_converted/query.10000.fbin \
    -index_path index/static/bigvectorbench_app_reviews/multi_dsg/attr${attr}.dsg \
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
bash scripts/dynamic/rebuild_multi_dsg_snapshot.sh \
  SNAPSHOT_DIR QUERY_PATH INDEX_DIR LOG_DIR ATTR_COUNT N
```

The dynamic design keeps stable original IDs, scans the Delta exactly, suppresses Base versions with tombstones, and rebuilds rank-based DSG indexes from a snapshot.

## 6. Raw Logs And Verification

```bash
sha256sum -c results/raw_logs.tar.gz.sha256 --ignore-missing
mkdir -p reproduced_logs
tar -xzf results/raw_logs.tar.gz -C reproduced_logs
python3 scripts/summarize_deep_10m_results.py --help
```

`results/raw_logs_manifest.csv` lists every archived log and its SHA-256. It is the canonical inventory for the synchronized experiment evidence.

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


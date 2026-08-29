# Reproducibility Guide

This guide separates commands available in the partial snapshot from commands pending final server-side source synchronization.

## 1. Environment

Recommended: Linux x86-64, CMake >= 3.16, GCC/Clang with C++17 and OpenMP, Python >= 3.10.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 2. Validate Bundled Data

```bash
python3 -m compileall -q scripts
python3 scripts/verify_bundled_data.py
```

## 3. Generate And Reorder A Workload

```bash
python3 scripts/generate_multiattr_benchmark_data.py \
  --output data/example_10k --size 10000 --dim 32 \
  --queries 100 --topk 10 --seed 2027

python3 scripts/prepare_multi_dsg_data_memmap.py \
  --base data/example_10k/base.10000.fbin \
  --attrs data/example_10k/attrs.csv --attr-count 3 \
  --output data/example_10k/multi_dsg --chunk-rows 16384
```

## 4. Build The Partial Snapshot

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
```

Build a small one-dimensional DSG index:

```bash
mkdir -p index/static/multiattr_smoke
./build/apps/build_static_index \
  -dataset multiattr_smoke -N 32 \
  -dataset_path data/multiattr_smoke/base.32.fbin \
  -query_path data/multiattr_smoke/query.4.fbin \
  -index_path index/static/multiattr_smoke/multiattr_smoke.dsg \
  -k 8 -ef_construction 20 -ef_max 32 -alpha 1.0
```

The integrated multi-attribute query application is pending full-source sync.

## 5. Prepare A DEEP-Derived Workload

After placing dimension-matched public files under `data/deep`:

```bash
python3 scripts/prepare_deep_multiattr_workloads.py \
  --base data/deep/base.10M.fbin \
  --query data/deep/query.public.10K.fbin \
  --groundtruth data/deep/groundtruth.public.10K.ibin \
  --output data/deep_1m_96d/multiattr_independent \
  --size 1000000 --queries 1000 --attributes 3 \
  --seed 2031 --attribute-mode independent
```

## 6. Full Paper Workflow (Pending Full-Source Sync)

Missing applications include `query_multi_dsg_benchmark`, `build_hnsw_index`, both HNSW benchmark programs, `query_rebuilt_multi_dsg`, and `export_multi_dsg_snapshot`.

After restoration, the intended runner is:

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

These commands document the intended workflow; the partial snapshot does not yet reproduce every paper table.

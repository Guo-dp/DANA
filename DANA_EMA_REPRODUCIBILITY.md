# DANA/EMA Paper Comparison

This guide reproduces the static-query comparison between DANA and the explicitly labelled **EMA-FTFix-V2** variant. It does not compare dynamic maintenance.

## Version Boundary

This release normalizes DANA names and paths. Historical formal source hashes remain in provenance; current file hashes are in `reproducibility/SHA256SUMS` and differ after renaming. EMA is not vendored. Obtain it from [lmccccc/EMA](https://github.com/lmccccc/EMA), then apply the three patches under `scripts/baselines/`.

The retained EMA checkout did not contain Git metadata, so no upstream commit is claimed. The pre-patch `hnswlib/hnswlib/hnswalg.h` used by the experiments had SHA-256:

```text
eebd754577fe096c155479e738aa1601b6f1bd6a31ca4d7108cbbb6e87590242
```

The patches change only:

1. closed upper-bucket inclusion;
2. FT initialization after the level-0 memory clear;
3. final-bucket coverage of the largest stored value.

They are experimental corrections, not author-confirmed upstream fixes. The paper therefore reports `EMA-FTFix-V2`, never unmodified EMA.

## Build

Build DANA and its JSONL comparison adapter:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)" --target dana_external
```

Build EMA-FTFix-V2 in an isolated directory:

```bash
export PYTHON=/path/to/ema/python
bash scripts/baselines/apply_ema_ftfix_v2.sh \
  /path/to/EMA \
  /path/to/EMA-ftfix-v2-hnswlib \
  /path/to/ema_ftfix_v2_lib \
  /path/to/ema_ftfix_v2_build
```

Patch application uses `--fuzz=0` and refuses to overwrite existing paths. The formal server extension hash was:

```text
4abff11883bab17fcc6a69699dcdcaee48a0738d85bcaeb6a9a6d48254ad90a4
```

Compiler and dependency differences may produce a different binary hash; record the new hash in the artifact manifest.

## Shared Workload Preparation

`prepare_external.py` converts one vector/attribute/filter workload into a shared contract consumed by both methods. It preserves original row IDs, converts float attributes to dense ordinal integers for EMA, verifies predicate equivalence, and recomputes filtered exact float64 squared-L2 ground truth.

Example:

```bash
python scripts/baselines/prepare_external.py \
  --output /artifact/prepared/deep10m \
  --base data/deep/base.10M.fbin \
  --query data/deep/query.public.10K.fbin \
  --attrs data/deep_10m_96d/multiattr_independent/attrs.csv \
  --filters data/deep_10m_96d/multiattr_independent/filters.multi_only.csv \
  --attr-count 3 --query-count 1000 --topk 10
```

Use the analogous paths in `configs/dana_ema_paper.json` for both SIFT workloads and App-Reviews.

The App test workload uses the frozen seed-2041 split:

```bash
python scripts/baselines/prepare_prepared_subset.py \
  --source /artifact/prepared/app_reviews \
  --split configs/app_reviews_split.json \
  --key validation \
  --output /artifact/prepared/app_reviews_validation

python scripts/baselines/prepare_prepared_subset.py \
  --source /artifact/prepared/app_reviews \
  --split configs/app_reviews_split.json \
  --key test \
  --output /artifact/prepared/app_reviews_test
```

The split contains 3,000 fitting, 2,000 validation, and 5,000 evaluation queries. The public main table uses validation-frozen fixed timestamp routing (`attr1`) for DANA on App-Reviews.

## Index Construction

Build DANA indexes with the commands in `REPRODUCIBILITY.md`. Formal DANA settings were `M=16` and `efConstruction=100`; retained historical settings also record `ef_max=400` and `alpha=1`.

Build one EMA index per full dataset, not per query subset:

```bash
python scripts/baselines/ema_external.py build \
  --ema-root /path/to/EMA \
  --extension-dir /path/to/ema_ftfix_v2_lib \
  --data /artifact/prepared/deep10m \
  --index /artifact/prepared/deep10m/ema-ftfix-v2/index.bin \
  --output /artifact/prepared/deep10m/ema-ftfix-v2/build.json \
  --M 16 --ef-construction 500 --threads 1 --seed 2037
```

EMA uses 128 FT bits, `ef_top=64`, graph seed 100, and clustering seed 1234. The App test subset reuses the index built from the full App base.

## Run The Formal Points

Run the selected paper points with five repetitions using the archived randomized scheduling protocol. App-Reviews uses interleaved evaluation, while DEEP/SIFT use randomized configuration order:

```bash
COMMON="--config configs/dana_ema_paper.json \
  --repo-root . \
  --prepared-root /artifact/prepared \
  --result-root /artifact/reproduced \
  --dana-bin build/apps/dana_external \
  --ema-root /path/to/EMA \
  --ema-extension-dir /path/to/ema_ftfix_v2_lib \
  --ema-python /path/to/ema/python \
  --evaluator-python /path/to/evaluator/python \
  --repeats 5 --selected-only"

python scripts/baselines/run_dana_ema_comparison.py --dataset deep10m $COMMON
python scripts/baselines/run_dana_ema_comparison.py --dataset sift1m_sel10 $COMMON
python scripts/baselines/run_dana_ema_comparison.py --dataset sift1m_sel1 $COMMON
python scripts/baselines/run_dana_ema_comparison.py --dataset app_reviews_test $COMMON
```

Omit `--selected-only` to run the complete parameter grids. Each method warms 10 queries. The runner sets common numerical-library thread variables to one and records environment metadata.

To reproduce App budget selection, first run the full validation grid and choose the highest-QPS measured configuration satisfying each common Recall threshold; then run those frozen budgets on `app_reviews_test`:

```bash
python scripts/baselines/run_dana_ema_comparison.py \
  --dataset app_reviews_validation ${COMMON/--selected-only/}
```

The archived validation choices are DANA `ef=2048/8192` and EMA `ef=16/64` for Recall thresholds `0.95/0.98`, respectively.

## Metrics

The authoritative metric is exact boundary-tie Recall. Strict-ID Recall is also computed internally but is not used to select App-Reviews operating points because tied distances make ID-only credit unstable.

Timing includes routing and the query/search API. It excludes index loading, result serialization, and exact ground-truth evaluation. EMA timing includes its Python wrapper. Pooled QPS is `1000 / pooled_mean_ms`; P50/P95 pool all query latencies, and variability is the standard deviation of the five run means.

The compact published evidence is under `results/ema_comparison/`. Query-level JSONL files are intentionally omitted because the formal archive is large. `reproducibility/audit.json` records the completed local audit of 260 runs and 880,000 query records.

## Remaining Provenance Boundary

The formal source, runner, evaluator, workload hashes, loaded EMA library path, and summary recomputation were verified. Not every historical index has an archived SHA-256. A hash computed later cannot prove which file an earlier run loaded. Fill `reproducibility/INDEX_MANIFEST.template.csv` when rebuilding indexes and keep the resulting manifest with the release artifact.

The server was shared and CPU cores were not exclusively pinned. App measurements were interleaved. DEEP/SIFT jobs were randomized, but no dedicated low-load paired rerun is claimed.

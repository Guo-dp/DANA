# Multi-DSG

> **Partial source snapshot (August 2026).** The experiment server is currently unavailable. This repository contains the locally available DSG source, workload-generation scripts, and deterministic validation datasets. Final Multi-DSG query executables, raw paper logs, and large public-dataset artifacts will be synchronized after the server is restored.

Multi-DSG is an engineering extension of one-dimensional Dynamic Segment Graphs for conjunctive multi-attribute range-filtered approximate nearest-neighbor search. Each indexed scalar attribute retains its own valid one-dimensional DSG. One attribute is selected for graph navigation, while all predicates control result admission. Dynamic updates use a base, delta, tombstone, and periodic-rebuild design.

## Available Now

- Original DSG core and locally available Multi-DSG work-in-progress sources.
- Synthetic workload generators and data-reordering utilities.
- `vector_calc_sanity`, `multiattr_smoke`, and `multiattr_10k` validation data.
- DEEP and BigVectorBench workload-preparation scripts.
- A Python-only release check and GitHub Actions validation.

## Important Snapshot Limitation

This is **not yet the final artifact used for every paper table**. Several server-side benchmark sources and raw logs are unavailable locally. The integrated `rangeSearchMultiDsg` implementation, HNSW comparison applications, rebuilt-index query application, and paper-result logs still need synchronization. See [STATUS.md](STATUS.md).

The partial CMake configuration builds locally complete original DSG applications and skips the incomplete multi-filter target when `include/utils/filter_query.h` is absent.

## Quick Validation

```bash
python3 -m compileall -q scripts
python3 scripts/verify_bundled_data.py
```

Expected final line:

```text
All bundled-data checks passed.
```

Regenerate deterministic datasets:

```bash
python3 scripts/generate_vector_calc_sanity_data.py
python3 scripts/generate_multiattr_smoke_data.py
python3 scripts/generate_multiattr_benchmark_data.py \
  --output data/multiattr_10k --size 10000 --dim 32 \
  --queries 100 --topk 10 --seed 2027
python3 scripts/verify_bundled_data.py
```

## Build Locally Complete DSG Targets

Intended environment: Linux, CMake 3.16+, C++17, and OpenMP.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for data preparation and experiment commands, and [DATA.md](DATA.md) for data formats and publication policy.

## License

Code is released under [LICENSE](LICENSE). Third-party datasets remain subject to their original terms.

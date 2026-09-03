# DANA

DANA extends one-dimensional Dynamic Segment Graphs to conjunctive multi-attribute range-filtered approximate nearest-neighbor search. It keeps one valid 1-D DSG per indexed scalar attribute, chooses one indexed attribute for navigation, admits only points satisfying every predicate into the result heap, and preserves non-matching points as bridge nodes. Dynamic changes use a Base/Delta/Tombstone layer with snapshot rebuilds.

This repository is the synchronized artifact snapshot used by the experiments. It contains the final C++ source, workload generators, benchmark drivers, compact workload definitions, validation datasets, and the complete raw log archive. Public vectors and generated indexes are intentionally excluded because they are large and redistributability varies.

## Method Boundary

DANA is an engineering extension built from multiple legal one-dimensional DSG indexes. It is not a lossless multidimensional generalization of DSG edge labels. Conjunctive filtering is implemented by navigation-attribute selection plus in-search result admission.

## Repository Layout

- `include/`, `src/`: DSG and dynamic DANA implementation.
- `apps/static/`: index builders and static DANA/HNSW benchmarks.
- `apps/dynamic/`: update, snapshot, rebuild-query, and dynamic-index programs.
- `scripts/`: workload preparation, experiment runners, and summarizers.
- `data/`: small deterministic validation workloads only.
- `workloads/`: filters and manifests for paper workloads; no public vectors.
- `results/raw_logs.tar.gz`: all 462 synchronized experiment logs.
- `results/raw_logs_manifest.csv`: per-log path, size, SHA-256, and metric-line count.
- `analysis/`: result extraction and plotting utilities.

## Quick Start

Requirements: Linux x86-64, CMake 3.16+, a C++17 compiler, OpenMP, and Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m compileall -q scripts analysis
python3 scripts/verify_bundled_data.py

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
```

The deterministic vector sanity test verifies squared-L2 distances, filtering, ties, and expected Top-3 results. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for end-to-end commands and [DATA.md](DATA.md) for data formats.

## Reproduced Experiment Families

- DEEP-1M and DEEP-10M, 96 dimensions, synthetic independent scalar attributes.
- SIFT1M, 128 dimensions, four to six generated attributes.
- BigVectorBench App-Reviews, 277,936 vectors, 384 dimensions, three real labels.
- Static DANA, HNSW post-filter, HNSW in-search, prefilter/hybrid, routing ablations, attribute scaling, and dynamic rebuild experiments.

Raw timing logs include the original machine conditions. For shared-server timing claims, use the clean-repeat logs and report the number of repetitions; do not mix known load-anomaly logs with clean measurements.

## Data And Licensing

Code is released under [LICENSE](LICENSE). Third-party datasets are not redistributed and remain subject to their original licenses. Generated `.dsg` and `.hnsw` indexes are reproducible artifacts and are excluded from Git history.

# Partial Snapshot Status

Last updated: 2026-08-29.

## Verified Locally

- All Python scripts pass syntax compilation.
- `vector_calc_sanity`: 8 two-dimensional vectors and 3 exact queries; filtered Top-3 IDs and squared-L2 distances match expected values.
- `multiattr_smoke`: 32 four-dimensional vectors, 32 attribute rows, and 4 filters.
- `multiattr_10k`: 10,000 32-dimensional vectors, 10,000 attribute rows, and 100 filters.
- Smoke rank mappings are valid permutations and reordered vectors map to original vectors.

## Pending Full-Source Sync

```text
include/utils/filter_query.h
apps/static/query_multi_dsg_benchmark.cc
apps/static/build_hnsw_index.cc
apps/static/query_hnsw_postfilter_benchmark.cc
apps/static/query_hnsw_insearch_benchmark.cc
apps/dynamic/query_rebuilt_multi_dsg.cc
apps/dynamic/export_multi_dsg_snapshot.cc
```

Final server versions of `include/dsg.h`, `src/dsg.cc`, `DataWrapper`, CMake target lists, experiment scripts, and raw logs must also be compared and synchronized. The WIP `src/dynamic_multi_dsg.cc` is retained for transparency but is not compiled in this partial snapshot.

## Not Included

- Correct DEEP-1M/10M 96D prepared workloads.
- SIFT1M synthetic-attribute and App-Reviews converted workloads.
- Generated DSG/HNSW indexes.
- Raw logs behind paper tables and figures.

The workstation's old DEEP base is 200D while its public query file is 96D; both were intentionally excluded.

## Completion Criteria

1. Synchronize all missing source and logs.
2. Pass a clean Linux Release build.
3. Pass vector sanity, 32-point smoke, 10K smoke, and a public-data subset.
4. Publish raw logs and normalized result CSV files.
5. Execute all reproduction commands from a fresh clone.

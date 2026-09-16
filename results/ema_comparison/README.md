# DANA/EMA Result Artifact

- `paper_points.csv`: the ten rows forming five common-recall comparisons.
- `repetitions.csv`: one compact summary for each of the 50 formal runs.
- `provenance.json`: source/binary hashes and audit scope.

Recall is exact boundary-tie Recall. QPS is computed from pooled mean per-query latency. The query-level JSONL archive is not stored in Git because it is substantially larger than the compact evidence. The retained audit recomputed 260 DANA/EMA runs and 880,000 query records before export.

The App rows use the frozen 5,000-query test split and fixed timestamp (`attr1`) DANA routing selected without test-outcome tuning. DEEP and SIFT use span-adaptive DANA routing.

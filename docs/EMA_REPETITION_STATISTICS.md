# DANA--EMA repeated-run statistics

This note reports variability for the five formal repetitions behind each
DANA--EMA paper operating point. The source rows are
`results/ema_comparison/repetitions.csv`; the derived table is
`results/ema_comparison/variability.csv`.

Each method reuses one prebuilt index. Before timing, 10 queries are executed
as warm-up. Timed work includes routing and the query/search API, excludes
index loading, serialization, and exact ground-truth evaluation, and includes
the Python wrapper for EMA. All numerical-library thread variables are fixed
to one. App-Reviews uses interleaved evaluation; DEEP/SIFT use randomized
configuration order on a shared server without exclusive CPU pinning.

Values below are arithmetic means across five runs with sample standard
deviations. The paper's pooled QPS remains `1000 / pooled_mean_ms`; the
run-level QPS statistics below are included only to expose variability.

| Workload | Method | Recall | Mean latency (ms) | Mean QPS | Run range (ms) |
|---|---|---:|---:|---:|---:|
| DEEP-10M | DANA | 0.9993 | 6.993 +/- 0.849 | 144.5 +/- 15.2 | [6.426, 8.497] |
| DEEP-10M | EMA-FTFix-V2 | 0.9990 | 19.799 +/- 0.208 | 50.5 +/- 0.5 | [19.595, 20.078] |
| SIFT1M sel=10% | DANA | 0.9996 | 2.438 +/- 0.135 | 411.1 +/- 22.9 | [2.297, 2.594] |
| SIFT1M sel=10% | EMA-FTFix-V2 | 1.0000 | 3.413 +/- 0.191 | 293.6 +/- 15.3 | [3.302, 3.752] |
| SIFT1M sel=1% | DANA | 0.9998 | 3.981 +/- 0.309 | 252.4 +/- 20.2 | [3.586, 4.265] |
| SIFT1M sel=1% | EMA-FTFix-V2 | 0.9999 | 12.595 +/- 0.223 | 79.4 +/- 1.4 | [12.459, 12.986] |
| App-Reviews Recall>=0.95 | DANA | 0.9736 | 3.734 +/- 0.295 | 269.2 +/- 21.9 | [3.331, 4.024] |
| App-Reviews Recall>=0.95 | EMA-FTFix-V2 | 0.9577 | 8.255 +/- 0.541 | 121.6 +/- 7.8 | [7.708, 8.866] |
| App-Reviews Recall>=0.98 | DANA | 0.9870 | 10.469 +/- 0.911 | 96.1 +/- 7.9 | [9.526, 11.950] |
| App-Reviews Recall>=0.98 | EMA-FTFix-V2 | 0.9812 | 22.296 +/- 1.372 | 45.0 +/- 2.7 | [20.886, 24.402] |

The direction of every throughput comparison is stable across the five runs.
DANA has larger relative wall-clock variation on DEEP/SIFT, consistent with
the shared-server limitation already disclosed in the paper. The minimum and
maximum ranges do not reverse any of the five conclusions, but the manuscript
should report the mean and standard deviation rather than imply exclusive-host
timing precision.

Regenerate the derived CSV with:

```bash
python3 scripts/baselines/summarize_repetition_variability.py
```

# DEEP-10M Default-Threshold Dynamic Cycle

Source data for Table 9 and Figure 6(c): DEEP-10M, 96 dimensions, three synthetic independent attributes, 1,000 public queries, Top-10, search ef=1024, seed=2031. Sequential batches contain 166,667 inserts, 166,667 updates and 166,667 deletes. The 5% threshold (500,000 changed IDs) is first exceeded at the sampled 500,001-changed-ID state. Delta and tombstone counts overlap; they must not be summed to estimate distinct changed IDs.

`dynamic_metrics.txt` retains the four committed-state metric records from the original snapshot-export run. `post_rebuild_metrics.txt` retains the metrics from **all three** subsequent rebuilt-index query runs. Only whitespace and run labels are normalized; machine-specific paths and unrelated resource-usage lines are omitted. The post-rebuild logs do not report a scan-stage timer; `delta_scan_ms=0` denotes the absence of a Delta, rather than a measured timer value.

`table9.csv` is generated from these records, not manually transcribed from a figure. The first four states each have one measurement of 1,000 queries. The final row pools three runs of 1,000 queries: mean latency is 14.37046667 ms and throughput is **1,000 / mean latency = 69.58716256 QPS**. QPS is not the arithmetic mean of run QPS. The run-level latency range (9.3682--20.3599 ms) remains in `post_rebuild_runs.csv`; no timing run is excluded. These shared-server measurements do not establish concurrent rebuild availability.

Figure 6(a) and (b) use separate historical Delta-growth and stage-breakdown measurements. They are not intermediate states of this cycle. Earlier DEEP-1M recovery measurements are not used in Figure 6(c).

Recompute and validate the numerical source data:

```bash
python scripts/dynamic_cycle_data.py --write
python -m unittest discover -s tests -p 'test_dynamic_cycle_data.py'
```

Without `--write`, the data script checks that the CSVs match the retained records. Figure-authoring scripts are outside this compact artifact; `table9.csv` supplies the recovery values for plotting. `provenance.json` identifies the original logs by SHA-256; it does not assert historical source/index identity beyond those archived records.

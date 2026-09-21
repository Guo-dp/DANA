# Experiment Results Archive

`raw_logs.tar.gz` contains the complete synchronized `logs/` tree: 462 files from DEEP-1M/10M 96D, SIFT1M, BigVectorBench App-Reviews, synthetic workloads, routing ablations, baselines, and dynamic experiments.

Verify and extract:

```bash
sha256sum -c results/raw_logs.tar.gz.sha256 --ignore-missing
mkdir -p reproduced_logs
tar -xzf results/raw_logs.tar.gz -C reproduced_logs
```

`raw_logs_manifest.csv` contains:

- `path`: path inside the archived `logs/` tree;
- `bytes`: uncompressed file size;
- `sha256`: file checksum;
- `all_metric_lines`: number of aggregate metric rows beginning with `all`.

The archive preserves raw output, including exploratory sweeps and timing runs affected by shared-server load. Paper timing summaries should use explicitly named clean/repeat directories and report the repeat count.

`followup_experiments/` contains the compact logs and per-query outputs for
the controlled navigation--admission ablation and the dynamic committed-state
correctness audit added after the original synchronized archive.

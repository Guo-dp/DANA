# Experiment Results

This compact artifact retains `ema_comparison/` paper operating points and five-run statistics, `dynamic_deep10m/` default-threshold recovery records, and `followup_experiments/` aggregate navigation-admission and committed-state audits. `capture_replay/` and `replay_followup/` contain independent sequential regression evidence. Full historical query outputs and indexes remain outside Git.

`paper_evidence.csv` restores metric-only excerpts from 58 original logs covering
historical HNSW comparisons, hybrid routing, build costs, attribute-count curves,
Delta growth and trigger checks. Each excerpt records its original line and source
log SHA-256. These hashes bind the inspected logs, not historical binaries or indexes.
Table 6's complete original routing/calibration search is not reconstructed by this CSV.

`replay_followup/contracts.csv` covers the new API branches and bounded Delta heap.
`maintenance_regression.csv` retains 60 records from five alternating before/after
runs on synthetic-1K and DEEP-1M-96D. Both use k=10, ef=128/1024 respectively;
DEEP uses the first 100 queries and 50K each of insert/update/delete (seed 2031).
The source logs and measured binaries are hashed. These new measurements do not
replace the historical DEEP-10M table or establish a consistent speedup.

`followup_experiments/manifest.csv` records each retained file's relative path, byte count, SHA-256, and number of aggregate metric rows beginning with `all`.

Verify the compact artifact from the repository root:

```bash
sha256sum -c reproducibility/SHA256SUMS
```

After intentional artifact changes, refresh checksums with:

```bash
python3 scripts/update_reproducibility_hashes.py
```

Historical audit hashes describe the original experiment snapshot. Current release hashes are recorded separately in `reproducibility/SHA256SUMS`. Names and paths in retained logs have been normalized to DANA; numerical measurements are unchanged. Full historical query JSONL inputs and large indexes are not bundled, so the historical full audit requires those external inputs.

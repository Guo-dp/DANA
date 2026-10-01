# Experiment Results

This compact artifact retains `ema_comparison/` paper operating points and five-run statistics, `dynamic_deep10m/` default-threshold recovery records, `stable_id_rebuild/` regression evidence, and `followup_experiments/` aggregate logs and summaries for navigation-admission ablations and dynamic committed-state correctness audits. Raw per-query CSV files, the complete historical log bundle and exploratory timing sweeps are omitted for a compact release. Runners can regenerate query-level output; retained navigation-admission summaries can be recomputed from the aggregate logs alone.

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

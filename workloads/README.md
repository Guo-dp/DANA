# Workload Definitions

This directory mirrors compact filter CSVs and JSON manifests from the experiment server while excluding vectors, generated attribute tables, and indexes.

Use these files to audit query profiles and seeds. Regenerate complete workloads with the scripts under `scripts/`, then place public vectors according to `DATA.md`. Paths are grouped by the original dataset family so they can be copied back under `data/` if desired.

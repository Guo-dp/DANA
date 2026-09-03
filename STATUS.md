# Artifact Status

Synchronized on 2026-09-03 from:

```text
guodp@172.18.51.166:/data/guodp/snap/VD/DRFA/Dynamic-Range-Filtering-ANNS-release_version
```

## Included

- Final `include/`, `src/`, `apps/`, `scripts/`, `tests/`, and `analysis/` trees.
- Final top-level and application CMake configuration.
- Compact paper workload filters/manifests.
- Three deterministic validation datasets.
- Complete server log archive: 462 files.
- Per-log and source synchronization hashes.

## Excluded

- Historical `.before_*`, `.bak_*`, and named checkpoint source copies.
- Build directories and compiler products.
- Public raw datasets and generated attribute tables.
- Reordered vector copies and generated `.dsg`/`.hnsw` indexes.
- Previously invalid DEEP-200D experiment artifacts.

## Integrity

The server-to-local source/log transfer was verified against 567 server-generated SHA-256 entries with zero missing files and zero mismatches before publication. `results/raw_logs_manifest.csv` provides a separate hash for every archived log.

After synchronization, the exact server source completed a fresh Linux Release build of all configured targets. The integrated 8-point, three-attribute query smoke test returned Recall@3 = 1.0000. GitHub Actions repeats the Python/data checks, full C++ build, three small DSG index builds, and integrated query test on Ubuntu.


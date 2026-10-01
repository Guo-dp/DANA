#!/usr/bin/env python3
"""Recompute and validate the DEEP-10M Table 9 / Figure 6(c) source data."""

from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "dynamic_deep10m"
STATES = ("Base", "Insert", "Update", "Delete", "After rebuild")
FIELDS = (
    "state", "queries", "runs", "recall", "approx_ms", "qps",
    "delta_scan_ms", "delta_scanned", "delta_size", "tombstones", "rebuild",
)


def read_metrics(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, *fields = line.split()
        record = {"name": name}
        for field in fields:
            key, value = field.split("=", 1)
            record[key] = value if key == "rebuild" else float(value)
        if record["queries"] <= 0 or record["approx_ms"] <= 0:
            raise ValueError(f"Invalid measurement: {name}")
        if not all(math.isfinite(v) for v in record.values() if isinstance(v, float)):
            raise ValueError(f"Non-finite measurement: {name}")
        if not 0 <= record["recall"] <= 1:
            raise ValueError(f"Invalid Recall: {name}")
        if not math.isclose(record["qps"], 1000 / record["approx_ms"], rel_tol=1e-5):
            raise ValueError(f"Inconsistent QPS: {name}")
        records.append(record)
    return records


def compute_cycle(data: Path = DATA) -> tuple[list[dict], list[dict]]:
    before = read_metrics(data / "dynamic_metrics.txt")
    after = read_metrics(data / "post_rebuild_metrics.txt")
    if [r["name"] for r in before] != ["base", "after_insert", "after_update", "after_delete"]:
        raise ValueError("Expected four ordered committed states")
    if [r["name"] for r in after] != ["run1", "run2", "run3"]:
        raise ValueError("Expected all three post-rebuild runs")
    rows = []
    for state, record in zip(STATES, before):
        rows.append({
            "state": state, "queries": int(record["queries"]), "runs": 1,
            **{key: record[key] for key in FIELDS[3:-1]},
            "rebuild": "triggered" if record["rebuild"] == "yes" else "no",
        })
    for record in after:
        if any(record[key] != 0 for key in ("delta_scanned", "delta_size", "tombstones")):
            raise ValueError("Rebuilt state must have no retained overlay entries")
    queries = sum(r["queries"] for r in after)
    # Pool query time, rather than averaging the reciprocals (per-run QPS).
    latency = sum(r["queries"] * r["approx_ms"] for r in after) / queries
    rows.append({
        "state": STATES[-1], "queries": int(queries), "runs": len(after),
        "recall": sum(r["queries"] * r["recall"] for r in after) / queries,
        "approx_ms": latency, "qps": 1000 / latency, "delta_scan_ms": 0,
        "delta_scanned": 0, "delta_size": 0, "tombstones": 0, "rebuild": "done",
    })
    return rows, after


def csv_text(rows: list[dict], fields: tuple[str, ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: f"{row[key]:.8f}" if isinstance(row[key], float) else row[key]
                         for key in fields})
    return stream.getvalue()


def expected_files(data: Path = DATA) -> dict[str, str]:
    rows, runs = compute_cycle(data)
    run_fields = ("name", "queries", "recall", "approx_ms", "qps",
                  "base_candidates", "delta_scanned", "delta_size", "tombstones", "rebuild")
    return {"table9.csv": csv_text(rows, FIELDS),
            "post_rebuild_runs.csv": csv_text(runs, run_fields)}


def load_dynamic_cycle(data: Path = DATA) -> list[dict]:
    for name, expected in expected_files(data).items():
        if (data / name).read_text(encoding="utf-8") != expected:
            raise ValueError(f"Stale {name}; run python scripts/dynamic_cycle_data.py --write")
    with (data / "table9.csv").open(encoding="utf-8", newline="") as stream:
        return [{key: value if key in ("state", "rebuild") else float(value)
                 for key, value in row.items()} for row in csv.DictReader(stream)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate CSVs from retained metric records")
    args = parser.parse_args()
    if args.write:
        for name, content in expected_files().items():
            (DATA / name).write_text(content, encoding="utf-8", newline="\n")
    for row in load_dynamic_cycle():
        print(f"{row['state']:14s} recall={row['recall']:.4f} "
              f"ms={row['approx_ms']:.2f} qps={row['qps']:.2f}")


if __name__ == "__main__":
    main()

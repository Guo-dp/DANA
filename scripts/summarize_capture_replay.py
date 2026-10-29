#!/usr/bin/env python3
"""Validate and summarize the small sequential replay regression campaign."""
import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


VARIANTS = ("v3_baseline", "journal_off", "journal_on")


def pack(root):
    """Consolidate run CSVs and pass markers without changing measurements."""
    records, validation = [], []
    for variant in VARIANTS:
        for run in range(1, 6):
            stem = f"{variant}_run{run}"
            with (root / f"{stem}.csv").open(encoding="utf-8", newline="") as stream:
                records.extend(csv.DictReader(stream))
            marker = "ALL PASS light_performance_regression"
            if marker not in (root / f"{stem}.log").read_text():
                raise ValueError(f"Run did not pass: {stem}")
            validation.append(f"{stem}: {marker}")
    for name, marker in (("correctness.log", "ALL PASS sequential_capture_replay"),
                         ("stable_ids.log", "ALL PASS independent_operation_replay")):
        if marker not in (root / name).read_text():
            raise ValueError(f"Correctness test incomplete: {name}")
        validation.append(f"{name}: {marker}")
    with (root / "measurements.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    (root / "validation.txt").write_text("\n".join(validation) + "\n", encoding="utf-8")


def summarize(root):
    groups = defaultdict(list)
    rows = []
    compact_path = root / "measurements.csv"
    compact = list(csv.DictReader(compact_path.open(encoding="utf-8"))) if compact_path.exists() else None
    validation_path = root / "validation.txt"
    validation = validation_path.read_text() if validation_path.exists() else None
    if compact is not None and (len(compact) != 130 or
            any(r["variant"] not in VARIANTS or r["run"] not in ("1", "2", "3", "4", "5") for r in compact)):
        raise ValueError("Unexpected compact campaign rows or run identities")
    for variant in VARIANTS:
        for run in range(1, 6):
            path = root / f"{variant}_run{run}.csv"
            records = [dict(r) for r in compact if r["variant"] == variant and int(r["run"]) == run] if compact is not None else list(csv.DictReader(path.open(encoding="utf-8")))
            metrics = set()
            for record in records:
                if record["variant"] != variant or int(record["run"]) != run:
                    raise ValueError(f"Mismatched run identity: {path}")
                metric = record["metric"]
                if metric in metrics:
                    raise ValueError(f"Duplicate metric in {path}: {metric}")
                metrics.add(metric)
                for key in ("total_ms", "per_op_us", "recall"):
                    record[key] = float(record[key])
                    if not math.isfinite(record[key]):
                        raise ValueError(f"Nonfinite {key}: {path}")
                record["operations"] = int(record["operations"])
                if record["total_ms"] <= 0 or record["operations"] <= 0:
                    raise ValueError(f"Invalid measurement: {path}")
                if metric.startswith("query_") and not 0 <= record["recall"] <= 1:
                    raise ValueError(f"Invalid recall: {path}")
                record["qps"] = 1e6 / record["per_op_us"] if metric.startswith("query_") else 0
                record["rss_delta_kib"] = int(record["rss_delta_kib"])
                record["heap_delta_bytes"] = int(record["heap_delta_bytes"])
                groups[variant, metric].append(record)
                rows.append(record)
            required = {"initialize_64", "insert", "update", "erase", "query_base", "query_mutated"}
            if variant == "journal_on":
                required |= {"capture", "journal_copy", "snapshot_write", "rebuild_and_reload",
                             "replay", "query_replayed", "compaction_and_reload", "query_compacted"}
            if metrics != required:
                raise ValueError(f"Missing/unexpected metrics: {path}: {metrics ^ required}")
            marker = "ALL PASS light_performance_regression"
            passed = f"{variant}_run{run}: {marker}" in validation if validation is not None else marker in (root / f"{variant}_run{run}.log").read_text()
            if not passed:
                raise ValueError(f"Run did not pass correctness checks: {variant}, {run}")
    for name, marker in (("correctness.log", "ALL PASS sequential_capture_replay"),
                         ("stable_ids.log", "ALL PASS independent_operation_replay")):
        passed = f"{name}: {marker}" in validation if validation is not None else marker in (root / name).read_text()
        if not passed:
            raise ValueError(f"Correctness test incomplete: {name}")
    fields = ["variant", "metric", "runs", "operations", "total_ms_mean", "total_ms_std",
              "per_op_us_mean", "per_op_us_std", "qps_mean", "qps_std", "recall_mean",
              "rss_delta_kib_mean", "heap_delta_bytes_mean"]
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for (variant, metric), records in sorted(groups.items()):
            if len(records) != 5 or len({r["operations"] for r in records}) != 1:
                raise ValueError("Inconsistent repeat count or operation count")
            summary = {"variant": variant, "metric": metric, "runs": 5,
                       "operations": records[0]["operations"]}
            for key in ("total_ms", "per_op_us", "qps"):
                values = [r[key] for r in records]
                summary[f"{key}_mean"] = statistics.mean(values)
                summary[f"{key}_std"] = statistics.stdev(values)
            for key in ("recall", "rss_delta_kib", "heap_delta_bytes"):
                summary[f"{key}_mean"] = statistics.mean(r[key] for r in records)
            writer.writerow(summary)
            print(f"{variant:12} {metric:24} ms={summary['total_ms_mean']:.6f} "
                  f"+/-{summary['total_ms_std']:.6f} us/op={summary['per_op_us_mean']:.4f} "
                  f"qps={summary['qps_mean']:.1f} recall={summary['recall_mean']:.6f}")
    print(f"PASS: 15 runs, {len(rows)} metric records; sample standard deviation; no runs excluded")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--pack", action="store_true", help="Consolidate raw run CSVs and pass markers")
    args = parser.parse_args()
    if args.pack:
        pack(args.results)
    summarize(args.results)

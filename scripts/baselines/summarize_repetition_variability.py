#!/usr/bin/env python3
"""Summarize variability of the archived DANA/EMA paper runs."""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/ema_comparison/repetitions.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/ema_comparison/variability.csv"),
    )
    return parser.parse_args()


def mean(values):
    return statistics.fmean(values)


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def main():
    args = parse_args()
    groups = defaultdict(list)

    with args.input.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["workload"], row["method"], int(row["ef"]))
            groups[key].append(row)

    fieldnames = [
        "workload",
        "method",
        "ef",
        "runs",
        "recall_mean",
        "latency_ms_mean",
        "latency_ms_std",
        "latency_ms_min",
        "latency_ms_max",
        "qps_mean",
        "qps_std",
        "qps_min",
        "qps_max",
        "p95_ms_mean",
        "p95_ms_std",
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()

        for (workload, method, ef), rows in sorted(groups.items()):
            recalls = [float(row["recall"]) for row in rows]
            latencies = [float(row["mean_ms"]) for row in rows]
            qps_values = [float(row["qps"]) for row in rows]
            p95_values = [float(row["p95_ms"]) for row in rows]

            writer.writerow(
                {
                    "workload": workload,
                    "method": method,
                    "ef": ef,
                    "runs": len(rows),
                    "recall_mean": f"{mean(recalls):.6f}",
                    "latency_ms_mean": f"{mean(latencies):.6f}",
                    "latency_ms_std": f"{sample_std(latencies):.6f}",
                    "latency_ms_min": f"{min(latencies):.6f}",
                    "latency_ms_max": f"{max(latencies):.6f}",
                    "qps_mean": f"{mean(qps_values):.6f}",
                    "qps_std": f"{sample_std(qps_values):.6f}",
                    "qps_min": f"{min(qps_values):.6f}",
                    "qps_max": f"{max(qps_values):.6f}",
                    "p95_ms_mean": f"{mean(p95_values):.6f}",
                    "p95_ms_std": f"{sample_std(p95_values):.6f}",
                }
            )

    print(f"Wrote {len(groups)} summaries to {args.output}")


if __name__ == "__main__":
    main()

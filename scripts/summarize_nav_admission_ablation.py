#!/usr/bin/env python3
"""Summarize bridge-preserving versus hard-pruning benchmark logs."""

import argparse
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path


FILE_PATTERN = re.compile(
    r"(?P<mode>bridge|hard_prune)_ef(?P<ef>\d+)_run(?P<run>\d+)\.log$"
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("log_root", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def metric(line, name):
    match = re.search(rf"\b{name}=([0-9.]+)", line)
    if not match:
        raise ValueError(f"Missing {name} in: {line}")
    return float(match.group(1))


def sample_std(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def main():
    args = parse_args()
    groups = defaultdict(list)

    for path in sorted(args.log_root.glob("*_ef*_run*.log")):
        match = FILE_PATTERN.match(path.name)
        if not match:
            continue

        all_line = next(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("all")
        )
        row = {
            name: metric(all_line, name)
            for name in (
                "recall",
                "graph_ms",
                "qps",
                "hops",
                "dist",
                "pruned",
                "insufficient",
            )
        }
        groups[(match.group("mode"), int(match.group("ef")))].append(row)

    fields = [
        "mode",
        "ef",
        "runs",
        "recall_mean",
        "recall_std",
        "graph_ms_mean",
        "graph_ms_std",
        "pooled_qps",
        "qps_mean",
        "qps_std",
        "hops_mean",
        "dist_mean",
        "pruned_mean",
        "insufficient_mean",
    ]
    rows = []

    for (mode, ef), values in sorted(groups.items()):
        def values_for(name):
            return [row[name] for row in values]

        rows.append(
            {
                "mode": mode,
                "ef": ef,
                "runs": len(values),
                "recall_mean": f"{statistics.fmean(values_for('recall')):.6f}",
                "recall_std": f"{sample_std(values_for('recall')):.6f}",
                "graph_ms_mean": f"{statistics.fmean(values_for('graph_ms')):.6f}",
                "graph_ms_std": f"{sample_std(values_for('graph_ms')):.6f}",
                "pooled_qps": f"{1000.0 / statistics.fmean(values_for('graph_ms')):.6f}",
                "qps_mean": f"{statistics.fmean(values_for('qps')):.6f}",
                "qps_std": f"{sample_std(values_for('qps')):.6f}",
                "hops_mean": f"{statistics.fmean(values_for('hops')):.3f}",
                "dist_mean": f"{statistics.fmean(values_for('dist')):.3f}",
                "pruned_mean": f"{statistics.fmean(values_for('pruned')):.3f}",
                "insufficient_mean": f"{statistics.fmean(values_for('insufficient')):.3f}",
            }
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} rows to {args.output}")
    else:
        writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

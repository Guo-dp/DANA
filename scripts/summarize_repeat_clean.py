#!/usr/bin/env python3
"""Summarize low-load repeat logs with mean/std/p95."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path


ALL_LINE = re.compile(
    r"^all\s+.*?recall=(?P<recall>[\d.]+).*?"
    r"(?:graph_ms|approx_ms)=(?P<graph_ms>[\d.]+).*?"
    r"qps=(?P<qps>[\d.]+).*?"
    r"hops=(?P<hops>[\d.]+).*?"
    r"dist=(?P<dist>[\d.]+)",
    re.MULTILINE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="logs/deep_10m_96d/query/repeat_clean")
    return parser.parse_args()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))


def parse_group(root: Path, glob: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for path in sorted(root.glob(glob)):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = ALL_LINE.search(text)
        if match is None:
            print(f"missing all line: {path}")
            continue
        rows.append({key: float(value) for key, value in match.groupdict().items()})
    return rows


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    groups = {
        "Multi-DSG ef1024": "dsg_ef1024_run*.log",
        "Post-filter c16384": "post_c16384_run*.log",
        "In-search ef256": "insearch_ef256_run*.log",
    }

    print(
        f"{'method':<20} {'runs':>4} {'recall':>8} "
        f"{'graph_mean':>11} {'graph_std':>10} {'graph_p95':>10} "
        f"{'qps_mean':>10} {'dist':>12}"
    )
    for name, glob in groups.items():
        rows = parse_group(root, glob)
        if not rows:
            print(f"{name:<20} {'0':>4} no completed logs")
            continue
        graph = [row["graph_ms"] for row in rows]
        qps = [row["qps"] for row in rows]
        print(
            f"{name:<20} {len(rows):>4} "
            f"{mean([r['recall'] for r in rows]):>8.4f} "
            f"{mean(graph):>11.4f} {std(graph):>10.4f} "
            f"{percentile(graph, 0.95):>10.4f} "
            f"{mean(qps):>10.1f} "
            f"{mean([r['dist'] for r in rows]):>12.1f}"
        )


if __name__ == "__main__":
    main()

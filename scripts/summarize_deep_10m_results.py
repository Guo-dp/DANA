#!/usr/bin/env python3
"""Summarize completed DEEP-10M key-comparison logs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ALL_LINE = re.compile(
    r"^all\s+.*?recall=(?P<recall>[\d.]+).*?"
    r"(?:graph_ms|approx_ms)=(?P<latency>[\d.]+).*?"
    r"qps=(?P<qps>[\d.]+).*?hops=(?P<hops>[\d.]+).*?"
    r"dist=(?P<dist>[\d.]+)",
    re.MULTILINE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", required=True)
    return parser.parse_args()


def parameter(path: Path) -> str:
    stem = path.stem
    if stem.startswith("ef"):
        return stem.removeprefix("ef")
    if stem.startswith("c"):
        return stem.removeprefix("c")
    return stem


def collect(root: Path, directory: str, method: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((root / directory).glob("*.log")):
        match = ALL_LINE.search(path.read_text(encoding="utf-8", errors="replace"))
        if match is None:
            continue
        row: dict[str, object] = {"method": method, "parameter": parameter(path)}
        row.update({name: float(value) for name, value in match.groupdict().items()})
        rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    root = Path(args.log_root)
    rows = [
        *collect(root, "multi_dsg", "Multi-DSG ef"),
        *collect(root, "hnsw_postfilter", "HNSW post c"),
        *collect(root, "hnsw_insearch", "HNSW in-search ef"),
    ]
    if not rows:
        raise SystemExit(f"No completed all-lines found under {root}")

    print(
        f"{'method':<20} {'param':>7} {'recall':>8} {'graph_ms':>10} "
        f"{'qps':>10} {'hops':>12} {'dist':>14}"
    )
    for row in rows:
        print(
            f"{row['method']:<20} {row['parameter']:>7} "
            f"{row['recall']:>8.4f} {row['latency']:>10.4f} "
            f"{row['qps']:>10.1f} {row['hops']:>12.1f} {row['dist']:>14.1f}"
        )


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Estimate hybrid Prefiltering/DANA latency from completed logs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PROFILE_LINE = re.compile(
    r"^(?P<profile>\S+)\s+queries=(?P<queries>\d+).*?"
    r"(?:prefilter_ms|graph_ms)=(?P<ms>[\d.]+).*?"
    r"qps=(?P<qps>[\d.]+)"
)

SCANNED = re.compile(r"scanned=(?P<value>[\d.]+)")
PASSED = re.compile(r"passed=(?P<value>[\d.]+)")
RECALL = re.compile(r"recall=(?P<value>[\d.]+)")

PROFILE_RATIOS = {
    "tiny_all": 0.005 ** 3,
    "small_all": 0.01 ** 3,
    "medium_all": 0.05 ** 3,
    "attr0_narrow": 0.10 * 0.50 * 0.50,
    "attr1_narrow": 0.50 * 0.10 * 0.50,
    "attr2_narrow": 0.50 * 0.50 * 0.10,
    "balanced": 0.20 ** 3,
    "broad": 0.50 ** 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefilter-log", required=True)
    parser.add_argument("--dsg-log", required=True)
    parser.add_argument(
        "--count-source", choices=("observed", "independent"), default="observed",
        help="Observed counts are offline Prefilter results, not an online estimator.",
    )
    parser.add_argument("--N", type=int, default=1_000_000)
    parser.add_argument(
        "--thresholds",
        default="1000,5000,10000,50000",
        help="Comma-separated estimated candidate thresholds.",
    )
    return parser.parse_args()


def parse_log(path: Path) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("all"):
            continue
        match = PROFILE_LINE.search(line)
        if match is None:
            continue
        profile = match.group("profile")
        rows[profile] = {
            "queries": float(match.group("queries")),
            "ms": float(match.group("ms")),
            "qps": float(match.group("qps")),
        }
        scanned = SCANNED.search(line)
        passed = PASSED.search(line)
        recall = RECALL.search(line)
        if scanned is not None:
            rows[profile]["scanned"] = float(scanned.group("value"))
        if passed is not None:
            rows[profile]["passed"] = float(passed.group("value"))
        if recall is not None:
            rows[profile]["recall"] = float(recall.group("value"))
    return rows


def candidate_count(profile, prefilter_row, source, size):
    if source == "independent":
        if size <= 0 or profile not in PROFILE_RATIOS:
            raise ValueError("Independent counts require positive N and a known synthetic profile")
        return size * PROFILE_RATIOS[profile]
    if "passed" not in prefilter_row:
        raise ValueError(f"Missing observed legal count for {profile}")
    return prefilter_row["passed"]


def main() -> None:
    args = parse_args()
    prefilter = parse_log(Path(args.prefilter_log))
    dsg = parse_log(Path(args.dsg_log))
    thresholds = [float(raw) for raw in args.thresholds.split(",") if raw]
    print(f"count_source={args.count_source}; offline log-based latency summary")

    profiles = [profile for profile in prefilter if profile in dsg]
    if not profiles:
        raise SystemExit("No shared profiles found between prefilter and DSG logs.")

    for threshold in thresholds:
        total_queries = 0.0
        total_ms = 0.0
        print(f"===== threshold={threshold:.0f} =====")
        print(
            f"{'profile':<14} {'legal_n':>10} {'choice':>8} "
            f"{'pref_ms':>10} {'dsg_ms':>10} {'dsg_rec':>8} {'hybrid_ms':>10}"
        )
        for profile in profiles:
            queries = prefilter[profile]["queries"]
            est_n = candidate_count(profile, prefilter[profile], args.count_source, args.N)
            use_prefilter = est_n <= threshold
            chosen = prefilter[profile] if use_prefilter else dsg[profile]
            total_queries += queries
            total_ms += chosen["ms"] * queries
            print(
                f"{profile:<14} {est_n:>10.1f} "
                f"{'pref' if use_prefilter else 'dsg':>8} "
                f"{prefilter[profile]['ms']:>10.4f} "
                f"{dsg[profile]['ms']:>10.4f} "
                f"{dsg[profile].get('recall', 0.0):>8.4f} "
                f"{chosen['ms']:>10.4f}"
            )
        avg_ms = total_ms / total_queries
        print(f"hybrid_all avg_ms={avg_ms:.4f} qps={1000.0 / avg_ms:.1f}")


if __name__ == "__main__":
    main()

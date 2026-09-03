#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


PROFILE_RATIOS = {
    "tiny_all": 0.005 * 0.005 * 0.005,
    "small_all": 0.01 * 0.01 * 0.01,
    "medium_all": 0.05 * 0.05 * 0.05,
    "attr0_narrow": 0.10 * 0.50 * 0.50,
    "attr1_narrow": 0.50 * 0.10 * 0.50,
    "attr2_narrow": 0.50 * 0.50 * 0.10,
    "balanced": 0.20 * 0.20 * 0.20,
    "broad": 0.50 * 0.50 * 0.50,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefilter-log", required=True)
    parser.add_argument("--dsg-log", required=True)
    parser.add_argument("--N", type=int, default=1_000_000)
    parser.add_argument("--threshold", type=int, default=5000)
    return parser.parse_args()


def parse_prefilter(path):
    rows = {}
    pattern = re.compile(
        r"^(\S+)\s+queries=(\d+).*prefilter_ms=([\d.]+).*"
        r"qps=([\d.]+).*scanned=([\d.]+).*passed=([\d.]+).*dist=([\d.]+)"
    )

    for line in Path(path).read_text().splitlines():
        m = pattern.search(line)
        if not m:
            continue
        name, q, ms, qps, scanned, passed, dist = m.groups()
        rows[name] = {
            "queries": int(q),
            "ms": float(ms),
            "qps": float(qps),
            "scanned": float(scanned),
            "passed": float(passed),
            "dist": float(dist),
        }
    return rows


def parse_dsg(path):
    rows = {}
    pattern = re.compile(
        r"^(\S+)\s+queries=(\d+).*recall=([\d.]+).*"
        r"graph_ms=([\d.]+).*qps=([\d.]+).*hops=([\d.]+).*dist=([\d.]+)"
    )

    for line in Path(path).read_text().splitlines():
        m = pattern.search(line)
        if not m:
            continue
        name, q, recall, ms, qps, hops, dist = m.groups()
        rows[name] = {
            "queries": int(q),
            "recall": float(recall),
            "ms": float(ms),
            "qps": float(qps),
            "hops": float(hops),
            "dist": float(dist),
        }
    return rows


def main():
    args = parse_args()
    pref = parse_prefilter(args.prefilter_log)
    dsg = parse_dsg(args.dsg_log)

    names = [
        "tiny_all",
        "small_all",
        "medium_all",
        "attr0_narrow",
        "attr1_narrow",
        "attr2_narrow",
        "balanced",
        "broad",
    ]

    print(
        f"{'profile':<14} {'estN':>10} {'pref_ms':>9} "
        f"{'dsg_ms':>9} {'choice':>10} {'hybrid_ms':>10} "
        f"{'pref_qps':>10} {'dsg_qps':>10}"
    )

    total_queries = 0
    total_seconds = 0.0

    for name in names:
        if name not in pref or name not in dsg:
            continue

        est = args.N * PROFILE_RATIOS[name]
        use_pref = est <= args.threshold
        choice = "prefilter" if use_pref else "dsg"
        hybrid_ms = pref[name]["ms"] if use_pref else dsg[name]["ms"]

        q = pref[name]["queries"]
        total_queries += q
        total_seconds += q * hybrid_ms / 1000.0

        print(
            f"{name:<14} {est:10.1f} "
            f"{pref[name]['ms']:9.4f} {dsg[name]['ms']:9.4f} "
            f"{choice:>10} {hybrid_ms:10.4f} "
            f"{pref[name]['qps']:10.1f} {dsg[name]['qps']:10.1f}"
        )

    if total_queries:
        hybrid_ms = total_seconds * 1000.0 / total_queries
        hybrid_qps = total_queries / total_seconds
        print(
            f"{'hybrid_all':<14} {'':>10} {'':>9} {'':>9} "
            f"{'':>10} {hybrid_ms:10.4f} "
            f"{'':>10} {hybrid_qps:10.1f}"
        )


if __name__ == "__main__":
    main()

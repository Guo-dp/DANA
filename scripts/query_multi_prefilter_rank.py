#!/usr/bin/env python3
import argparse
import csv
import struct
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--attrs", required=True)
    parser.add_argument("--rank-root", required=True)
    parser.add_argument("--filters", required=True)
    parser.add_argument("--attr-count", type=int, default=3)
    parser.add_argument("--query-num", type=int, default=1000)
    parser.add_argument("--topk", type=int, default=10)
    return parser.parse_args()


def read_fbin_header(path):
    with Path(path).open("rb") as f:
        return struct.unpack("<II", f.read(8))


def memmap_fbin(path):
    n, dim = read_fbin_header(path)
    arr = np.memmap(
        path,
        dtype="<f4",
        mode="r",
        offset=8,
        shape=(n, dim),
    )
    return arr, n, dim


def read_ibin(path):
    with Path(path).open("rb") as f:
        n = struct.unpack("<I", f.read(4))[0]
    return np.memmap(path, dtype="<u4", mode="r", offset=4, shape=(n,))


def load_attrs(path, count, attr_count):
    attrs = np.empty((attr_count, count), dtype=np.float32)
    with Path(path).open() as f:
        for row in csv.reader(f):
            if not row:
                continue
            idx = int(row[0])
            for attr in range(attr_count):
                attrs[attr, idx] = float(row[attr + 1])
    return attrs


def read_filters(path, attr_count, limit):
    rows = []
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            query_idx = int(row["query_idx"])
            if query_idx >= limit:
                continue
            bounds = []
            for attr in range(attr_count):
                bounds.append(
                    (
                        float(row[f"attr{attr}_low"]),
                        float(row[f"attr{attr}_high"]),
                    )
                )
            rows.append(
                {
                    "query_idx": query_idx,
                    "profile": row["profile"],
                    "bounds": bounds,
                }
            )
            if len(rows) >= limit:
                break
    return rows


def choose_primary(bounds):
    best_attr = 0
    best_width = None
    for attr, (low, high) in enumerate(bounds):
        width = max(0.0, high - low + 1.0)
        if best_width is None or width < best_width:
            best_width = width
            best_attr = attr
    return best_attr


def run_query(base, query, attrs, rank_to_original, case, topk):
    bounds = case["bounds"]
    primary = choose_primary(bounds)
    low, high = bounds[primary]

    low_i = max(0, int(np.ceil(low)))
    high_i = min(rank_to_original[primary].shape[0] - 1, int(np.floor(high)))

    if low_i > high_i:
        return 0, 0, 0, []

    candidate_ids = np.asarray(rank_to_original[primary][low_i: high_i + 1])
    scanned = int(candidate_ids.size)

    if scanned == 0:
        return 0, 0, 0, []

    mask = np.ones(scanned, dtype=bool)

    for attr, (lo, hi) in enumerate(bounds):
        values = attrs[attr, candidate_ids]
        mask &= (values >= lo) & (values <= hi)

    passed_ids = candidate_ids[mask]
    passed = int(passed_ids.size)

    if passed == 0:
        return scanned, passed, 0, []

    vecs = base[passed_ids]
    diff = vecs - query
    dists = np.einsum("ij,ij->i", diff, diff)
    dist_count = int(passed)

    k = min(topk, passed)
    if passed > k:
        part = np.argpartition(dists, k - 1)[:k]
        order = part[np.argsort(dists[part])]
    else:
        order = np.argsort(dists)

    result = passed_ids[order].astype(np.uint32).tolist()
    return scanned, passed, dist_count, result


def main():
    args = parse_args()

    base, n, dim = memmap_fbin(args.base)
    queries, qn, qdim = memmap_fbin(args.query)

    if dim != qdim:
        raise SystemExit(f"dim mismatch: base={dim}, query={qdim}")

    attrs = load_attrs(args.attrs, n, args.attr_count)

    rank_to_original = [
        read_ibin(
            Path(args.rank_root) / f"rank_to_original.attr{attr}.ibin"
        )
        for attr in range(args.attr_count)
    ]

    cases = read_filters(args.filters, args.attr_count, args.query_num)

    metrics = defaultdict(lambda: {
        "queries": 0,
        "seconds": 0.0,
        "scanned": 0,
        "passed": 0,
        "dist": 0,
    })

    for case in cases:
        q = queries[case["query_idx"]]
        start = time.perf_counter()
        scanned, passed, dist, _ = run_query(
            base, q, attrs, rank_to_original, case, args.topk
        )
        elapsed = time.perf_counter() - start

        for key in (case["profile"], "all"):
            metrics[key]["queries"] += 1
            metrics[key]["seconds"] += elapsed
            metrics[key]["scanned"] += scanned
            metrics[key]["passed"] += passed
            metrics[key]["dist"] += dist

    for name in sorted(k for k in metrics if k != "all"):
        m = metrics[name]
        q = m["queries"]
        qps = q / m["seconds"] if m["seconds"] > 0 else 0.0
        print(
            f"{name:<14} queries={q} recall=1.0000 "
            f"prefilter_ms={m['seconds'] * 1000 / q:.4f} "
            f"qps={qps:.4f} "
            f"scanned={m['scanned'] / q:.4f} "
            f"passed={m['passed'] / q:.4f} "
            f"dist={m['dist'] / q:.4f}"
        )

    m = metrics["all"]
    q = m["queries"]
    qps = q / m["seconds"] if m["seconds"] > 0 else 0.0
    print(
        f"{'all':<14} queries={q} recall=1.0000 "
        f"prefilter_ms={m['seconds'] * 1000 / q:.4f} "
        f"qps={qps:.4f} "
        f"scanned={m['scanned'] / q:.4f} "
        f"passed={m['passed'] / q:.4f} "
        f"dist={m['dist'] / q:.4f}"
    )


if __name__ == "__main__":
    main()

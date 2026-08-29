#!/usr/bin/env python3
"""Create dimension-compatible queries derived from an existing fbin base.

This is intended for a dataset bundle whose base and public query files do not
belong to the same vector space. The generated queries are sampled from the
base and perturbed slightly, so they are valid for L2 experiments on that base.
Existing ground truth must not be reused.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output-query", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2032)
    parser.add_argument(
        "--noise-ratio",
        type=float,
        default=0.01,
        help="Gaussian noise std as a fraction of each anchor vector's std.",
    )
    parser.add_argument(
        "--without-replacement",
        action="store_true",
        help="Use distinct base anchors. Requires queries <= base count.",
    )
    return parser.parse_args()


def read_header(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(8)
    if len(header) != 8:
        raise SystemExit(f"Invalid fbin header: {path}")
    return struct.unpack("<II", header)


def validate_fbin(path: Path, count: int, dim: int) -> None:
    expected = 8 + count * dim * 4
    actual = path.stat().st_size
    if actual != expected:
        raise SystemExit(
            f"Invalid fbin size for {path}: expected {expected}, got {actual}"
        )


def main() -> None:
    args = parse_args()
    base_path = Path(args.base)
    output_path = Path(args.output_query)
    metadata_path = (
        Path(args.metadata)
        if args.metadata
        else output_path.with_suffix(output_path.suffix + ".json")
    )

    if args.queries <= 0:
        raise SystemExit("--queries must be positive")
    if args.noise_ratio < 0.0:
        raise SystemExit("--noise-ratio must be non-negative")

    count, dim = read_header(base_path)
    validate_fbin(base_path, count, dim)

    if args.without_replacement and args.queries > count:
        raise SystemExit(
            "--queries exceeds base count with --without-replacement"
        )

    base = np.memmap(
        base_path,
        dtype="<f4",
        mode="r",
        offset=8,
        shape=(count, dim),
    )
    rng = np.random.default_rng(args.seed)
    anchors = rng.choice(
        count,
        size=args.queries,
        replace=not args.without_replacement,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as stream:
        stream.write(struct.pack("<II", args.queries, dim))
        for anchor_id in anchors:
            anchor = np.asarray(base[int(anchor_id)], dtype=np.float32)
            scale = float(anchor.std(dtype=np.float64))
            if not np.isfinite(scale) or scale == 0.0:
                scale = 1.0
            noise = rng.normal(
                loc=0.0,
                scale=args.noise_ratio * scale,
                size=dim,
            ).astype(np.float32)
            query = anchor + noise
            stream.write(query.astype("<f4", copy=False).tobytes())

    anchors_path = output_path.with_suffix(output_path.suffix + ".anchors.ibin")
    with anchors_path.open("wb") as stream:
        stream.write(struct.pack("<II", args.queries, 1))
        stream.write(np.asarray(anchors, dtype="<u4").tobytes())

    metadata = {
        "base": str(base_path),
        "base_count": count,
        "dimension": dim,
        "output_query": str(output_path),
        "query_count": args.queries,
        "seed": args.seed,
        "noise_ratio": args.noise_ratio,
        "anchor_ids": str(anchors_path),
        "groundtruth_status": "must_be_regenerated",
        "workload_name": "base-derived-dimension-repair",
        "warning": (
            "These queries are derived from the supplied base. They do not "
            "match the original public query or ground-truth files."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    generated_count, generated_dim = read_header(output_path)
    validate_fbin(output_path, generated_count, generated_dim)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

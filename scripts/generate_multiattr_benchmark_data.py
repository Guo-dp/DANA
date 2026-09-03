#!/usr/bin/env python3
"""Generate a medium synthetic multi-attribute DSG benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import random
import struct
from pathlib import Path


PROFILES = (
    ("attr0_narrow", 0.10, 0.50, 0.50),
    ("attr1_narrow", 0.50, 0.10, 0.50),
    ("attr2_narrow", 0.50, 0.50, 0.10),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/multiattr_10k")
    parser.add_argument("--size", type=int, default=10_000)
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--skip-expected",
        action="store_true",
        help="Skip slow Python exact Top-K generation.",
    )
    return parser.parse_args()


def write_fbin(path: Path, rows: list[list[float]]) -> None:
    dim = len(rows[0])
    with path.open("wb") as stream:
        stream.write(struct.pack("<II", len(rows), dim))
        row_format = "<" + "f" * dim
        for row in rows:
            stream.write(struct.pack(row_format, *row))


def centered_range(value: int, ratio: float, size: int) -> tuple[int, int]:
    width = max(1, min(size, round(size * ratio)))
    low = value - width // 2
    low = max(0, min(low, size - width))
    return low, low + width - 1


def squared_l2(left: list[float], right: list[float]) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def main() -> None:
    args = parse_args()
    if args.size <= 0 or args.dim <= 0 or args.queries <= 0 or args.topk <= 0:
        raise SystemExit("size, dim, queries, and topk must be positive")

    rng = random.Random(args.seed)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    attr1_values = list(range(args.size))
    attr2_values = list(range(args.size))
    rng.shuffle(attr1_values)
    rng.shuffle(attr2_values)

    attrs: list[tuple[int, int, int, int]] = []
    base: list[list[float]] = []
    for label in range(args.size):
        attr0 = label
        attr1 = attr1_values[label]
        attr2 = attr2_values[label]
        attrs.append((label, attr0, attr1, attr2))

        # Attribute-aware signal plus deterministic noise. Nearby vectors are
        # not trivially identical to nearby primary-attribute labels.
        normalized = (
            attr0 / max(args.size - 1, 1),
            attr1 / max(args.size - 1, 1),
            attr2 / max(args.size - 1, 1),
        )
        row: list[float] = []
        for dim_idx in range(args.dim):
            attr_signal = normalized[dim_idx % 3]
            periodic = ((label * (dim_idx + 3)) % 97) / 97.0
            noise = rng.uniform(-0.025, 0.025)
            row.append(float(attr_signal * 2.0 + periodic * 0.25 + noise))
        base.append(row)

    query_rows: list[list[float]] = []
    filter_rows: list[list[str | int]] = []
    profile_counts = {name: 0 for name, *_ in PROFILES}

    for query_idx in range(args.queries):
        profile_name, ratio0, ratio1, ratio2 = PROFILES[query_idx % len(PROFILES)]
        profile_counts[profile_name] += 1

        anchor = rng.randrange(args.size)
        query = [value + rng.uniform(-0.01, 0.01) for value in base[anchor]]
        query_rows.append(query)

        _, attr0, attr1, attr2 = attrs[anchor]
        bounds = (
            centered_range(attr0, ratio0, args.size),
            centered_range(attr1, ratio1, args.size),
            centered_range(attr2, ratio2, args.size),
        )

        expected = ""
        if not args.skip_expected:
            candidates: list[tuple[float, int]] = []
            for label, value0, value1, value2 in attrs:
                if not (
                    bounds[0][0] <= value0 <= bounds[0][1]
                    and bounds[1][0] <= value1 <= bounds[1][1]
                    and bounds[2][0] <= value2 <= bounds[2][1]
                ):
                    continue
                candidates.append(
                    (squared_l2(query, base[label]), label)
                )

            candidates.sort()
            expected = " ".join(
                str(label)
                for _, label in candidates[: args.topk]
            )
        filter_rows.append(
            [
                query_idx,
                profile_name,
                0,
                bounds[0][0],
                bounds[0][1],
                bounds[1][0],
                bounds[1][1],
                bounds[2][0],
                bounds[2][1],
                expected,
            ]
        )

    write_fbin(output / f"base.{args.size}.fbin", base)
    write_fbin(output / f"query.{args.queries}.fbin", query_rows)

    with (output / "attrs.csv").open("w", newline="") as stream:
        csv.writer(stream).writerows(attrs)

    with (output / "filters.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "query_idx",
                "profile",
                "primary_attr",
                "attr0_low",
                "attr0_high",
                "attr1_low",
                "attr1_high",
                "attr2_low",
                "attr2_high",
                f"expected_top{args.topk}",
            ]
        )
        writer.writerows(filter_rows)

    metadata = {
        "size": args.size,
        "dimension": args.dim,
        "query_count": args.queries,
        "topk": args.topk,
        "attribute_count": 3,
        "primary_attribute": 0,
        "seed": args.seed,
        "profiles": [
            {
                "name": name,
                "attr0_ratio": ratio0,
                "attr1_ratio": ratio1,
                "attr2_ratio": ratio2,
                "query_count": profile_counts[name],
            }
            for name, ratio0, ratio1, ratio2 in PROFILES
        ],
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(f"Wrote benchmark data under {output.resolve()}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

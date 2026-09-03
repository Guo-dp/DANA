#!/usr/bin/env python3

import argparse
import csv
import json
import random
import struct
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=100000)
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--queries", type=int, default=300)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2029)
    return parser.parse_args()


def write_fbin(path, rows):
    dim = len(rows[0])

    with path.open("wb") as stream:
        stream.write(struct.pack("<II", len(rows), dim))
        row_format = "<" + "f" * dim

        for row in rows:
            stream.write(struct.pack(row_format, *row))


def centered_range(value, ratio, size):
    width = max(1, min(size, round(size * ratio)))
    low = value - width // 2
    low = max(0, min(low, size - width))
    return low, low + width - 1


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    # Vector data is generated independently of all filter attributes.
    base = [
        [rng.uniform(-1.0, 1.0) for _ in range(args.dim)]
        for _ in range(args.size)
    ]

    # Each attribute is an independent random permutation.
    attribute_values = []

    for _ in range(3):
        values = list(range(args.size))
        rng.shuffle(values)
        attribute_values.append(values)

    attrs = []

    for original_id in range(args.size):
        attrs.append([
            original_id,
            attribute_values[0][original_id],
            attribute_values[1][original_id],
            attribute_values[2][original_id],
        ])

    profiles = [
        ("attr0_narrow", 0.10, 0.50, 0.50),
        ("attr1_narrow", 0.50, 0.10, 0.50),
        ("attr2_narrow", 0.50, 0.50, 0.10),
    ]

    queries = []
    filters = []
    profile_counts = {name: 0 for name, *_ in profiles}

    for query_idx in range(args.queries):
        name, ratio0, ratio1, ratio2 = \
            profiles[query_idx % len(profiles)]

        profile_counts[name] += 1

        # Query vector is close to a randomly selected vector.
        anchor = rng.randrange(args.size)

        query = [
            value + rng.uniform(-0.01, 0.01)
            for value in base[anchor]
        ]
        queries.append(query)

        # Filter center is selected independently of query-vector anchor.
        filter_anchor = rng.randrange(args.size)

        value0 = attribute_values[0][filter_anchor]
        value1 = attribute_values[1][filter_anchor]
        value2 = attribute_values[2][filter_anchor]

        bound0 = centered_range(value0, ratio0, args.size)
        bound1 = centered_range(value1, ratio1, args.size)
        bound2 = centered_range(value2, ratio2, args.size)

        filters.append([
            query_idx,
            name,
            0,
            bound0[0], bound0[1],
            bound1[0], bound1[1],
            bound2[0], bound2[1],
            "",
        ])

    write_fbin(
        output / f"base.{args.size}.fbin",
        base,
    )

    write_fbin(
        output / f"query.{args.queries}.fbin",
        queries,
    )

    with (output / "attrs.csv").open("w", newline="") as stream:
        csv.writer(stream).writerows(attrs)

    with (output / "filters.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
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
        ])
        writer.writerows(filters)

    metadata = {
        "size": args.size,
        "dimension": args.dim,
        "query_count": args.queries,
        "topk": args.topk,
        "attribute_count": 3,
        "seed": args.seed,
        "vector_attribute_relation": "independent",
        "profiles": [
            {
                "name": name,
                "ratios": [ratio0, ratio1, ratio2],
                "query_count": profile_counts[name],
            }
            for name, ratio0, ratio1, ratio2 in profiles
        ],
    }

    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("Wrote independent benchmark to", output.resolve())
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

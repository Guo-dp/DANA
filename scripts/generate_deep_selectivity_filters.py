#!/usr/bin/env python3
import argparse
import csv
import random
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attrs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--attr-count", type=int, default=3)
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2041)
    return parser.parse_args()


def load_attr_count(path):
    count = 0
    with Path(path).open() as f:
        for row in csv.reader(f):
            if row:
                count += 1
    return count


def centered_range(value, ratio, count):
    width = max(1, min(count, round(count * ratio)))
    low = max(0, min(value - width // 2, count - width))
    return low, low + width - 1


def profile_specs():
    return [
        ("tiny_all", [0.005, 0.005, 0.005]),
        ("small_all", [0.01, 0.01, 0.01]),
        ("medium_all", [0.05, 0.05, 0.05]),
        ("attr0_narrow", [0.10, 0.50, 0.50]),
        ("attr1_narrow", [0.50, 0.10, 0.50]),
        ("attr2_narrow", [0.50, 0.50, 0.10]),
        ("balanced", [0.20, 0.20, 0.20]),
        ("broad", [0.50, 0.50, 0.50]),
    ]


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    count = load_attr_count(args.attrs)
    specs = profile_specs()

    header = ["query_idx", "profile", "primary_attr"]
    for attr in range(args.attr_count):
        header.extend([f"attr{attr}_low", f"attr{attr}_high"])
    header.append("expected_top10")

    with Path(args.output).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for query_idx in range(args.queries):
            name, ratios = specs[query_idx % len(specs)]
            ratios = ratios[:args.attr_count]
            primary_attr = min(
                range(args.attr_count),
                key=lambda attr: (ratios[attr], attr),
            )
            anchor = rng.randrange(count)

            row = [query_idx, name, primary_attr]
            for attr in range(args.attr_count):
                low, high = centered_range(anchor, ratios[attr], count)
                row.extend([low, high])
            row.append("")
            writer.writerow(row)

    print(f"Wrote {args.queries} filters to {args.output}")


if __name__ == "__main__":
    main()

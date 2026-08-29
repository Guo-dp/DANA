#!/usr/bin/env python3
"""Prepare multi-attribute RFANNS workloads from a DEEP-style fbin dataset.

The generated artifacts cover the paper's static, ordered-insertion, and
unordered-insertion workloads. They are shared by feasible multi-attribute
baselines so every method sees identical attributes, filters, and update traces.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import struct
from array import array
from pathlib import Path
from typing import BinaryIO


PROFILE_RATIOS = (
    ("attr0_narrow", (0.10, 0.50, 0.50)),
    ("attr1_narrow", (0.50, 0.10, 0.50)),
    ("attr2_narrow", (0.50, 0.50, 0.10)),
    ("balanced", (0.20, 0.20, 0.20)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--groundtruth")
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=-1)
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--attributes", type=int, default=3)
    parser.add_argument("--initial-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=2031)
    parser.add_argument(
        "--attribute-mode",
        choices=("mixed", "independent"),
        default="mixed",
    )
    parser.add_argument(
        "--allow-dimension-mismatch",
        action="store_true",
        help="Generate metadata only; produced workload is not query-runnable.",
    )
    return parser.parse_args()


def read_header(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(8)
    if len(header) != 8:
        raise SystemExit(f"Invalid vector header: {path}")
    return struct.unpack("<II", header)


def validate_file_size(path: Path, count: int, dim: int, scalar_bytes: int) -> None:
    expected = 8 + count * dim * scalar_bytes
    actual = path.stat().st_size
    if actual != expected:
        raise SystemExit(
            f"Unexpected file size for {path}: expected {expected}, got {actual}"
        )


def read_float_row(stream: BinaryIO, dim: int) -> tuple[float, ...]:
    payload = stream.read(dim * 4)
    if len(payload) != dim * 4:
        raise SystemExit("Unexpected end of fbin payload")
    return struct.unpack("<" + "f" * dim, payload)


def rank_values(values: list[float]) -> list[int]:
    order = sorted(range(len(values)), key=lambda idx: (values[idx], idx))
    ranks = [0] * len(values)
    for rank, original_id in enumerate(order):
        ranks[original_id] = rank
    return ranks


def build_attributes(
    base_path: Path,
    count: int,
    dim: int,
    attr_count: int,
    mode: str,
    rng: random.Random,
) -> list[list[int]]:
    columns: list[list[int]] = []

    if mode == "mixed":
        norms: list[float] = []
        projections: list[float] = []
        signs = [1.0 if i % 2 == 0 else -1.0 for i in range(dim)]
        with base_path.open("rb") as stream:
            stream.seek(8)
            for _ in range(count):
                row = read_float_row(stream, dim)
                norms.append(math.fsum(value * value for value in row))
                projections.append(
                    math.fsum(value * signs[i] for i, value in enumerate(row))
                )
        columns.append(rank_values(norms))
        if attr_count >= 2:
            columns.append(rank_values(projections))

    while len(columns) < attr_count:
        values = list(range(count))
        rng.shuffle(values)
        columns.append(values)

    return columns


def centered_range(value: int, ratio: float, count: int) -> tuple[int, int]:
    width = max(1, min(count, round(count * ratio)))
    low = max(0, min(value - width // 2, count - width))
    return low, low + width - 1


def write_attributes(path: Path, columns: list[list[int]]) -> None:
    count = len(columns[0])
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        for original_id in range(count):
            writer.writerow(
                [original_id, *(column[original_id] for column in columns)]
            )


def write_filters(
    path: Path,
    columns: list[list[int]],
    query_count: int,
    rng: random.Random,
    multi_only: bool,
) -> dict[str, int]:
    attr_count = len(columns)
    count = len(columns[0])
    profile_counts: dict[str, int] = {}

    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        header = ["query_idx", "profile", "primary_attr"]
        for attr in range(attr_count):
            header.extend((f"attr{attr}_low", f"attr{attr}_high"))
        header.append("expected_top10")
        writer.writerow(header)

        for query_idx in range(query_count):
            if multi_only or query_idx % 5 != 0:
                name, base_ratios = PROFILE_RATIOS[
                    query_idx % len(PROFILE_RATIOS)
                ]
                ratios = [
                    base_ratios[attr] if attr < len(base_ratios) else 0.50
                    for attr in range(attr_count)
                ]
                primary_attr = min(
                    range(attr_count), key=lambda attr: (ratios[attr], attr)
                )
            else:
                primary_attr = (query_idx // 5) % attr_count
                name = f"single_attr{primary_attr}"
                ratios = [1.0] * attr_count
                ratios[primary_attr] = 0.10

            anchor = rng.randrange(count)
            row: list[int | str] = [query_idx, name, primary_attr]
            for attr in range(attr_count):
                low, high = centered_range(
                    columns[attr][anchor], ratios[attr], count
                )
                row.extend((low, high))
            row.append("")
            writer.writerow(row)
            profile_counts[name] = profile_counts.get(name, 0) + 1

    return profile_counts


def write_u32_vector(path: Path, values: list[int]) -> None:
    packed = array("I", values)
    if packed.itemsize != 4:
        raise SystemExit("Platform unsigned integer is not 32-bit")
    with path.open("wb") as stream:
        stream.write(struct.pack("<I", len(values)))
        packed.tofile(stream)


def write_traces(
    output: Path,
    columns: list[list[int]],
    initial_ratio: float,
    rng: random.Random,
) -> dict[str, int]:
    count = len(columns[0])
    initial_count = max(1, min(count - 1, round(count * initial_ratio)))

    random_order = list(range(count))
    rng.shuffle(random_order)
    write_u32_vector(output / "unordered_full_order.ibin", random_order)
    write_u32_vector(
        output / "unordered_initial_ids.ibin", random_order[:initial_count]
    )
    write_u32_vector(
        output / "unordered_insert_ids.ibin", random_order[initial_count:]
    )

    for attr, column in enumerate(columns):
        ordered = sorted(range(count), key=lambda idx: (column[idx], idx))
        write_u32_vector(output / f"ordered_attr{attr}_full_order.ibin", ordered)
        write_u32_vector(
            output / f"ordered_attr{attr}_initial_ids.ibin",
            ordered[:initial_count],
        )
        write_u32_vector(
            output / f"ordered_attr{attr}_insert_ids.ibin",
            ordered[initial_count:],
        )

    return {
        "initial_count": initial_count,
        "insert_count": count - initial_count,
    }


def baseline_manifest(attr_count: int) -> dict[str, object]:
    return {
        "fully_feasible": {
            "Prefiltering": {
                "workloads": ["static", "ordered", "unordered"],
                "multi_attribute_rule": "intersect all attribute ranges, exact scan",
            },
            "Postfiltering": {
                "workloads": ["static", "ordered", "unordered"],
                "multi_attribute_rule": "HNSW navigation, conjunction result filter",
            },
            "Acorn": {
                "workloads": ["static", "ordered", "unordered"],
                "multi_attribute_rule": "conjunctive predicate in predicate-aware search",
                "implementation": "external; workload generated only",
            },
            "Multi-DSG": {
                "workloads": ["static", "ordered", "unordered"],
                "multi_attribute_rule": (
                    f"{attr_count} one-dimensional DSG indexes, adaptive navigation"
                ),
            },
        },
        "restricted_extension": {
            "SeRF": {
                "workloads": ["static", "ordered"],
                "restriction": (
                    "one ordered partition attribute per run; remaining attributes "
                    "are result filters"
                ),
            },
            "WinFilter": {
                "workloads": ["static"],
                "restriction": (
                    "segment tree on one selected attribute; remaining attributes "
                    "are result filters"
                ),
            },
            "iRange": {
                "workloads": ["static"],
                "restriction": (
                    "segment tree on one selected attribute; remaining attributes "
                    "are result filters"
                ),
            },
        },
        "skipped": {
            "true_multidimensional_SeRF_WinFilter_iRange": (
                "not generated: direct m-dimensional tree/index extension has "
                "combinatorial space growth and is not present in this repository"
            )
        },
    }


def main() -> None:
    args = parse_args()
    base_path = Path(args.base)
    query_path = Path(args.query)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    base_count, base_dim = read_header(base_path)
    query_count, query_dim = read_header(query_path)
    validate_file_size(base_path, base_count, base_dim, 4)
    validate_file_size(query_path, query_count, query_dim, 4)

    runnable = base_dim == query_dim
    if not runnable and not args.allow_dimension_mismatch:
        raise SystemExit(
            "Base/query dimension mismatch: "
            f"base={base_dim}, query={query_dim}. "
            "Use the matching DEEP base file before generating workloads."
        )

    count = base_count if args.size < 0 else min(args.size, base_count)
    selected_queries = min(args.queries, query_count)
    if args.attributes < 2:
        raise SystemExit("--attributes must be at least 2")
    if not 0.0 < args.initial_ratio < 1.0:
        raise SystemExit("--initial-ratio must be in (0,1)")

    rng = random.Random(args.seed)
    columns = build_attributes(
        base_path,
        count,
        base_dim,
        args.attributes,
        args.attribute_mode,
        rng,
    )
    write_attributes(output / "attrs.csv", columns)

    multi_profiles = write_filters(
        output / "filters.multi_only.csv",
        columns,
        selected_queries,
        random.Random(args.seed + 1),
        multi_only=True,
    )
    compat_profiles = write_filters(
        output / "filters.paper_compat.csv",
        columns,
        selected_queries,
        random.Random(args.seed + 1),
        multi_only=False,
    )
    trace_stats = write_traces(
        output,
        columns,
        args.initial_ratio,
        random.Random(args.seed + 2),
    )

    metadata = {
        "base": str(base_path),
        "query": str(query_path),
        "groundtruth": args.groundtruth,
        "base_count": base_count,
        "selected_count": count,
        "base_dimension": base_dim,
        "query_count": query_count,
        "selected_queries": selected_queries,
        "query_dimension": query_dim,
        "runnable": runnable,
        "attribute_count": args.attributes,
        "attribute_mode": args.attribute_mode,
        "attribute_semantics": [
            "vector_l2_norm_rank" if args.attribute_mode == "mixed" else "random_rank",
            "signed_projection_rank"
            if args.attribute_mode == "mixed"
            else "random_rank",
            *["random_rank"] * max(0, args.attributes - 2),
        ][: args.attributes],
        "multi_only_profiles": multi_profiles,
        "paper_compat_profiles": compat_profiles,
        "dynamic_trace": trace_stats,
        "baseline_applicability": baseline_manifest(args.attributes),
    }
    (output / "workload_manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

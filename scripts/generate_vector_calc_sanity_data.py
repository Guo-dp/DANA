#!/usr/bin/env python3
"""Generate a tiny dataset with hand-checkable L2 distances.

The goal is to verify vector loading, squared L2 computation, filtering, and
Top-K ordering independently from large benchmark noise.
"""

from __future__ import annotations

import csv
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "vector_calc_sanity"


def write_fbin(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dim = len(rows[0])
    with path.open("wb") as stream:
        stream.write(struct.pack("<II", len(rows), dim))
        for row in rows:
            stream.write(struct.pack("<" + "f" * dim, *row))


def squared_l2(lhs: list[float], rhs: list[float]) -> float:
    return sum((a - b) * (a - b) for a, b in zip(lhs, rhs))


def in_filter(attrs: tuple[int, int, int, int],
              bounds: tuple[int, int, int, int, int, int]) -> bool:
    _, attr0, attr1, attr2 = attrs
    a0_low, a0_high, a1_low, a1_high, a2_low, a2_high = bounds
    return (
        a0_low <= attr0 <= a0_high
        and a1_low <= attr1 <= a1_high
        and a2_low <= attr2 <= a2_high
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # Two-dimensional points on simple integer coordinates.
    # Squared L2 distances can be checked by hand.
    base = [
        [0.0, 0.0],   # id 0
        [1.0, 0.0],   # id 1
        [0.0, 2.0],   # id 2
        [3.0, 0.0],   # id 3
        [0.0, 4.0],   # id 4
        [5.0, 0.0],   # id 5
        [0.0, 6.0],   # id 6
        [7.0, 0.0],   # id 7
    ]

    queries = [
        [0.0, 0.0],   # exact nearest id 0, then 1, then 2
        [4.0, 0.0],   # nearest x-axis points id 3 and 5, then id 1
        [0.0, 5.0],   # nearest y-axis points id 4 and 6, then id 2
    ]

    # CSV format: original_id, attr0, attr1, attr2.
    # attr0 equals original_id so a single-attribute rank order is trivial.
    attrs = [
        (0, 0, 0, 0),
        (1, 1, 0, 1),
        (2, 2, 1, 0),
        (3, 3, 0, 1),
        (4, 4, 1, 0),
        (5, 5, 0, 1),
        (6, 6, 1, 0),
        (7, 7, 0, 1),
    ]

    # query_idx, primary_attr, attr0_low/high, attr1_low/high, attr2_low/high.
    filters = [
        # All points. q0 expected by squared L2: 0(0), 1(1), 2(4).
        (0, 0, 0, 7, 0, 1, 0, 1),
        # Keep only x-axis odd ids 1,3,5,7. q1 distances: 3(1), 5(1), 1(9), 7(9).
        # Tie is broken by id because expected sorting uses (distance, id).
        (1, 0, 1, 7, 0, 0, 1, 1),
        # Keep only y-axis even ids 2,4,6. q2 distances: 4(1), 6(1), 2(9).
        (2, 0, 2, 6, 1, 1, 0, 0),
    ]

    write_fbin(OUT / "base.8.fbin", base)
    write_fbin(OUT / "query.3.fbin", queries)

    with (OUT / "attrs.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows(attrs)

    with (OUT / "filters.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "query_idx",
            "primary_attr",
            "attr0_low",
            "attr0_high",
            "attr1_low",
            "attr1_high",
            "attr2_low",
            "attr2_high",
            "expected_top3",
            "expected_squared_l2",
        ])
        for query_idx, primary_attr, *bounds in filters:
            ranked: list[tuple[float, int]] = []
            for row in attrs:
                original_id = row[0]
                if in_filter(row, tuple(bounds)):
                    ranked.append((squared_l2(queries[query_idx], base[original_id]),
                                   original_id))
            ranked.sort()
            top3 = ranked[:3]
            writer.writerow([
                query_idx,
                primary_attr,
                *bounds,
                " ".join(str(original_id) for _, original_id in top3),
                " ".join(f"{distance:.1f}" for distance, _ in top3),
            ])

    with (OUT / "README.md").open("w", encoding="utf-8") as stream:
        stream.write(
            "# vector_calc_sanity\n\n"
            "Purpose: verify fbin loading, squared L2 distance, range filtering, "
            "tie ordering, and Top-K output on a hand-checkable dataset.\n\n"
            "- `base.8.fbin`: 8 vectors, dim=2.\n"
            "- `query.3.fbin`: 3 queries, dim=2.\n"
            "- `attrs.csv`: no header, columns are `id,attr0,attr1,attr2`.\n"
            "- `filters.csv`: expected Top-3 ids and expected squared L2 values.\n\n"
            "Expected rows:\n"
            "- q0 all points: ids `0 1 2`, squared L2 `0.0 1.0 4.0`.\n"
            "- q1 x-axis odd ids: ids `3 5 1`, squared L2 `1.0 1.0 9.0`.\n"
            "- q2 y-axis even ids: ids `4 6 2`, squared L2 `1.0 1.0 9.0`.\n"
        )

    print(f"Wrote vector-calculation sanity data under {OUT}")

    for query_idx, *_ in filters:
        query = queries[query_idx]
        print(f"q{query_idx} query={query}")
    print("Expected Top-3 is stored in filters.csv")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a tiny multi-attribute smoke-test dataset for DSG experiments."""

from __future__ import annotations

import csv
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "multiattr_smoke"


def write_fbin(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dim = len(rows[0])
    with path.open("wb") as f:
        f.write(struct.pack("<II", len(rows), dim))
        for row in rows:
            f.write(struct.pack("<" + "f" * dim, *row))


def l2(a: list[float], b: list[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # attr0 is the primary attribute and equals label/rank.
    attrs: list[tuple[int, int, int, int]] = []
    base: list[list[float]] = []
    for label in range(32):
        attr0 = label
        attr1 = (label % 4) * 10 + label // 8
        attr2 = 100 - label * 2
        attrs.append((label, attr0, attr1, attr2))

        # Four loose clusters with small deterministic offsets.
        cluster = label % 4
        band = label // 4
        base.append([
            float(cluster * 10 + band * 0.10),
            float(cluster * 2 + (label % 8) * 0.05),
            float(attr1) / 10.0,
            float(attr2) / 100.0,
        ])

    queries = [
        base[5][:],
        base[14][:],
        base[23][:],
        [7.5, 1.0, 1.5, 0.6],
    ]

    filters = [
        # query_idx, primary_attr, attr0_low/high, attr1_low/high, attr2_low/high
        (0, 0, 0, 10, 10, 13, 80, 100),
        (1, 0, 8, 18, 20, 23, 60, 90),
        (2, 0, 16, 28, 30, 33, 40, 70),
        (3, 0, 0, 31, 0, 40, 50, 100),
    ]

    write_fbin(OUT / "base.32.fbin", base)
    write_fbin(OUT / "query.4.fbin", queries)

    with (OUT / "attrs.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        for row in attrs:
            writer.writerow(row)

    with (OUT / "filters.csv").open("w", newline="") as f:
        writer = csv.writer(f)
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
        ])
        for flt in filters:
            qidx, _, a0l, a0h, a1l, a1h, a2l, a2h = flt
            candidates: list[tuple[float, int]] = []
            for label, attr0, attr1, attr2 in attrs:
                if a0l <= attr0 <= a0h and a1l <= attr1 <= a1h and a2l <= attr2 <= a2h:
                    candidates.append((l2(queries[qidx], base[label]), label))
            candidates.sort()
            expected = " ".join(str(label) for _, label in candidates[:3])
            writer.writerow([*flt, expected])

    with (OUT / "README.md").open("w", encoding="utf-8") as f:
        f.write(
            "# multiattr_smoke\n\n"
            "Tiny multi-attribute smoke-test dataset.\n\n"
            "- `base.32.fbin`: 32 base vectors, dim=4.\n"
            "- `query.4.fbin`: 4 query vectors, dim=4.\n"
            "- `attrs.csv`: no header, columns are `label,attr0,attr1,attr2`.\n"
            "- `filters.csv`: four multi-attribute query filters and exact top-3 labels.\n\n"
            "Important: `attr0 == label`, so attr0 can be used as the primary attribute\n"
            "without changing the current single-attribute rank assumptions.\n"
        )

    print(f"Wrote smoke-test data under {OUT}")


if __name__ == "__main__":
    main()

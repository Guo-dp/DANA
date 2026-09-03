#!/usr/bin/env python3

import argparse
import csv
import struct
from pathlib import Path


def read_fbin(path):
    with path.open("rb") as f:
        count, dim = struct.unpack("<II", f.read(8))
        values = struct.unpack(
            "<" + "f" * (count * dim),
            f.read(4 * count * dim),
        )

    rows = [
        list(values[i * dim:(i + 1) * dim])
        for i in range(count)
    ]
    return rows, dim


def write_fbin(path, rows, dim):
    with path.open("wb") as f:
        f.write(struct.pack("<II", len(rows), dim))
        for row in rows:
            f.write(
                struct.pack("<" + "f" * dim, *row)
            )


def write_ibin(path, values):
    with path.open("wb") as f:
        f.write(struct.pack("<I", len(values)))
        f.write(
            struct.pack(
                "<" + "I" * len(values),
                *values,
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--attrs", required=True)
    parser.add_argument("--attr-count", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base, dim = read_fbin(Path(args.base))
    count = len(base)

    attrs = [
        [0.0] * count
        for _ in range(args.attr_count)
    ]

    with Path(args.attrs).open(newline="") as f:
        for row in csv.reader(f):
            original_id = int(row[0])
            for attr in range(args.attr_count):
                attrs[attr][original_id] = float(row[attr + 1])

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    for attr in range(args.attr_count):
        order = sorted(
            range(count),
            key=lambda idx: (attrs[attr][idx], idx),
        )

        reordered = [base[original_id]
                     for original_id in order]

        write_fbin(
            output / f"base.attr{attr}.fbin",
            reordered,
            dim,
        )

        write_ibin(
            output / f"rank_to_original.attr{attr}.ibin",
            order,
        )

        print(
            f"attr={attr} vectors={len(reordered)}"
        )


if __name__ == "__main__":
    main()

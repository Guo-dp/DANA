#!/usr/bin/env python3

import argparse
import csv
import struct
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--attrs", required=True)
    parser.add_argument("--attr-count", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk-rows", type=int, default=8192)
    return parser.parse_args()


def read_header(path):
    with path.open("rb") as stream:
        header = stream.read(8)

    if len(header) != 8:
        raise SystemExit(f"Invalid fbin header: {path}")

    return struct.unpack("<II", header)


def load_attributes(path, count, attr_count):
    attrs = np.empty(
        (attr_count, count),
        dtype=np.float32,
    )

    seen = np.zeros(count, dtype=np.bool_)

    with path.open(newline="") as stream:
        reader = csv.reader(stream)
        rows = 0

        for columns in reader:
            if not columns:
                continue

            if len(columns) < attr_count + 1:
                raise SystemExit(
                    f"Malformed attribute row: {columns}"
                )

            original_id = int(columns[0])

            if original_id < 0 or original_id >= count:
                raise SystemExit(
                    f"Attribute ID out of range: {original_id}"
                )

            if seen[original_id]:
                raise SystemExit(
                    f"Duplicate attribute ID: {original_id}"
                )

            for attr in range(attr_count):
                attrs[attr, original_id] = \
                    float(columns[attr + 1])

            seen[original_id] = True
            rows += 1

    if rows != count or not bool(seen.all()):
        raise SystemExit(
            f"Expected {count} attribute rows, "
            f"loaded {rows}"
        )

    return attrs


def write_mapping(path, order):
    with path.open("wb") as stream:
        stream.write(
            struct.pack("<I", order.size)
        )

        stream.write(
            order.astype(
                "<u4",
                copy=False,
            ).tobytes()
        )


def reorder_vectors(
    path,
    base,
    order,
    dim,
    chunk_rows,
):
    with path.open("wb") as stream:
        stream.write(
            struct.pack(
                "<II",
                order.size,
                dim,
            )
        )

        for begin in range(
            0,
            order.size,
            chunk_rows,
        ):
            selected = order[
                begin:begin + chunk_rows
            ]

            block = np.asarray(
                base[selected],
                dtype="<f4",
            )

            stream.write(
                block.tobytes(order="C")
            )


def main():
    args = parse_args()

    base_path = Path(args.base)
    attrs_path = Path(args.attrs)
    output = Path(args.output)

    if args.attr_count <= 0:
        raise SystemExit(
            "--attr-count must be positive"
        )

    if args.chunk_rows <= 0:
        raise SystemExit(
            "--chunk-rows must be positive"
        )

    count, dim = read_header(base_path)

    expected_bytes = (
        8 + count * dim * 4
    )

    if base_path.stat().st_size != expected_bytes:
        raise SystemExit(
            "Base fbin size does not match its header"
        )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Loading attributes: count={count} "
        f"attr_count={args.attr_count}"
    )

    attrs = load_attributes(
        attrs_path,
        count,
        args.attr_count,
    )

    base = np.memmap(
        base_path,
        dtype="<f4",
        mode="r",
        offset=8,
        shape=(count, dim),
    )

    original_ids = np.arange(
        count,
        dtype=np.uint32,
    )

    for attr in range(args.attr_count):
        print(f"Sorting attribute {attr}")

        order = np.lexsort(
            (original_ids, attrs[attr])
        ).astype(
            np.uint32,
            copy=False,
        )

        vector_path = (
            output /
            f"base.attr{attr}.fbin"
        )

        mapping_path = (
            output /
            f"rank_to_original.attr{attr}.ibin"
        )

        print(
            f"Writing reordered vectors for attr={attr}"
        )

        reorder_vectors(
            vector_path,
            base,
            order,
            dim,
            args.chunk_rows,
        )

        write_mapping(
            mapping_path,
            order,
        )

        print(
            f"attr={attr} vectors={count} "
            f"dim={dim} "
            f"vector_file={vector_path} "
            f"mapping={mapping_path}"
        )


if __name__ == "__main__":
    main()

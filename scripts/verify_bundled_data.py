#!/usr/bin/env python3
"""Validate deterministic data bundled with the partial release."""

from __future__ import annotations

import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_fbin(path: Path):
    with path.open("rb") as stream:
        count, dim = struct.unpack("<II", stream.read(8))
        payload = stream.read()
    assert len(payload) == count * dim * 4, f"invalid fbin size: {path}"
    values = struct.unpack(f"<{count * dim}f", payload)
    rows = [tuple(values[i * dim:(i + 1) * dim]) for i in range(count)]
    return count, dim, rows


def read_u32_vector(path: Path):
    with path.open("rb") as stream:
        count = struct.unpack("<I", stream.read(4))[0]
        payload = stream.read()
    assert len(payload) == count * 4, f"invalid mapping size: {path}"
    return struct.unpack(f"<{count}I", payload)


def validate_dataset(directory, base_name, query_name, expected_base, expected_queries):
    root = ROOT / directory
    base_count, base_dim, _ = read_fbin(root / base_name)
    query_count, query_dim, _ = read_fbin(root / query_name)
    with (root / "attrs.csv").open(newline="") as stream:
        attributes = list(csv.reader(stream))
    with (root / "filters.csv").open(newline="") as stream:
        filters = list(csv.DictReader(stream))
    assert base_count == expected_base
    assert query_count == expected_queries
    assert base_dim == query_dim
    assert len(attributes) == base_count
    assert [int(row[0]) for row in attributes] == list(range(base_count))
    assert len(filters) == query_count
    for row in filters:
        assert 0 <= int(row["query_idx"]) < query_count
        for attr in range(3):
            assert float(row[f"attr{attr}_low"]) <= float(row[f"attr{attr}_high"])
    print(f"OK {directory}: base={base_count}x{base_dim}, queries={query_count}")


def validate_vector_sanity():
    root = ROOT / "data/vector_calc_sanity"
    _, dim, base = read_fbin(root / "base.8.fbin")
    _, _, queries = read_fbin(root / "query.3.fbin")
    with (root / "attrs.csv").open(newline="") as stream:
        attributes = [[float(value) for value in row] for row in csv.reader(stream)]
    with (root / "filters.csv").open(newline="") as stream:
        filters = list(csv.DictReader(stream))
    for row in filters:
        query_id = int(row["query_idx"])
        candidates = []
        for values in attributes:
            original_id = int(values[0])
            if all(float(row[f"attr{attr}_low"]) <= values[attr + 1] <= float(row[f"attr{attr}_high"]) for attr in range(3)):
                distance = sum((base[original_id][axis] - queries[query_id][axis]) ** 2 for axis in range(dim))
                candidates.append((distance, original_id))
        candidates.sort()
        actual_ids = " ".join(str(item[1]) for item in candidates[:3])
        actual_distances = " ".join(f"{item[0]:.1f}" for item in candidates[:3])
        assert actual_ids == row["expected_top3"]
        assert actual_distances == row["expected_squared_l2"]
    print("OK vector_calc_sanity: exact filtered Top-3 and squared L2")


def validate_reordering():
    root = ROOT / "data/multiattr_smoke"
    count, _, base = read_fbin(root / "base.32.fbin")
    mapping_root = root / "memmap_test"
    for attr in range(3):
        mapping = read_u32_vector(mapping_root / f"rank_to_original.attr{attr}.ibin")
        reordered_count, _, reordered = read_fbin(mapping_root / f"base.attr{attr}.fbin")
        assert reordered_count == count
        assert sorted(mapping) == list(range(count))
        assert all(reordered[rank] == base[original_id] for rank, original_id in enumerate(mapping))
    print("OK multiattr_smoke: rank mappings and reordered vectors")


def main():
    validate_dataset("data/multiattr_smoke", "base.32.fbin", "query.4.fbin", 32, 4)
    validate_dataset("data/multiattr_10k", "base.10000.fbin", "query.100.fbin", 10000, 100)
    validate_dataset("data/vector_calc_sanity", "base.8.fbin", "query.3.fbin", 8, 3)
    validate_vector_sanity()
    validate_reordering()
    print("All bundled-data checks passed.")


if __name__ == "__main__":
    main()


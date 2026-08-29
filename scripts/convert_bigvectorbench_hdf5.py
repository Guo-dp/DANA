#!/usr/bin/env python3
"""Convert a BigVectorBench filter-ann HDF5 file into this repo's format.

This script avoids the h5py dependency. It uses the HDF5 command-line tool
`h5dump` to export raw little-endian dataset payloads, then writes:

  base.N.fbin
  query.Q.fbin
  attrs.csv
  filters.csv
  groundtruth.topK.ibin

The app_reviews filter expression is:

  text_length in [q_text_length - 30, q_text_length + 30]
  unixtime    in [q_unixtime - 30 days, q_unixtime]
  star        in [head_star[q_star], tail_star[q_star]]
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import struct
import subprocess
from pathlib import Path


HEADER_RE = re.compile(
    r'DATASET "(?P<name>[^"]+)".*?'
    r"DATATYPE\s+(?P<dtype>\S+).*?"
    r"DATASPACE\s+SIMPLE\s+\{\s+\(\s*(?P<shape>[^)]*?)\s*\)",
    re.S,
)

DTYPE_SIZE = {
    "H5T_IEEE_F32LE": 4,
    "H5T_STD_I32LE": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--keep-raw", action="store_true")
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def h5_header(path: Path) -> dict[str, tuple[str, tuple[int, ...]]]:
    text = subprocess.check_output(
        ["h5dump", "-H", str(path)],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    found: dict[str, tuple[str, tuple[int, ...]]] = {}
    for match in HEADER_RE.finditer(text):
        name = match.group("name")
        dtype = match.group("dtype")
        shape = tuple(
            int(part.strip())
            for part in match.group("shape").split(",")
            if part.strip()
        )
        found[name] = (dtype, shape)
    return found


def export_raw(h5_path: Path, dataset: str, raw_path: Path) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    run([
        "h5dump",
        "-d",
        f"/{dataset}",
        "-b",
        "LE",
        "-o",
        str(raw_path),
        str(h5_path),
    ])


def verify_raw(raw_path: Path, dtype: str, shape: tuple[int, ...]) -> None:
    expected = DTYPE_SIZE[dtype]
    for dim in shape:
        expected *= dim
    actual = raw_path.stat().st_size
    if actual != expected:
        raise SystemExit(
            f"raw size mismatch for {raw_path}: expected={expected}, actual={actual}"
        )


def write_fbin(raw_path: Path, out_path: Path, shape: tuple[int, int]) -> None:
    count, dim = shape
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as out:
        out.write(struct.pack("<II", count, dim))
        with raw_path.open("rb") as raw:
            shutil.copyfileobj(raw, out, length=1024 * 1024 * 16)
    print(f"wrote {out_path} count={count} dim={dim}")


def iter_i32_rows(raw_path: Path, cols: int, chunk_rows: int = 65536):
    row_size = cols * 4
    with raw_path.open("rb") as stream:
        while True:
            data = stream.read(row_size * chunk_rows)
            if not data:
                break
            if len(data) % row_size != 0:
                raise SystemExit(f"truncated int32 rows in {raw_path}")
            values = struct.unpack("<" + "i" * (len(data) // 4), data)
            for offset in range(0, len(values), cols):
                yield values[offset: offset + cols]


def write_attrs(raw_path: Path, out_path: Path, rows: int) -> None:
    with out_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        for idx, (text_length, unixtime, star) in enumerate(iter_i32_rows(raw_path, 3)):
            writer.writerow([idx, text_length, unixtime, star])
    print(f"wrote {out_path} rows={rows}")


def star_range(star: int) -> tuple[int, int]:
    head_star = [0, 1, 1, 3, 3, 4]
    tail_star = [0, 2, 2, 4, 5, 5]
    if star < 0 or star >= len(head_star):
        raise SystemExit(f"unexpected star label: {star}")
    return head_star[star], tail_star[star]


def read_neighbors_topk(raw_path: Path, query_count: int, source_topk: int, topk: int) -> list[str]:
    expected = query_count * source_topk * 4
    actual = raw_path.stat().st_size
    if actual != expected:
        raise SystemExit(
            f"neighbor raw size mismatch: expected={expected}, actual={actual}"
        )
    rows: list[str] = []
    with raw_path.open("rb") as stream:
        for _ in range(query_count):
            row = struct.unpack("<" + "i" * source_topk, stream.read(source_topk * 4))
            rows.append(" ".join(str(x) for x in row[:topk]))
    return rows


def write_filters(
    test_label_raw: Path,
    neighbor_raw: Path,
    out_path: Path,
    query_count: int,
    neighbor_topk: int,
    topk: int,
) -> None:
    expected = read_neighbors_topk(neighbor_raw, query_count, neighbor_topk, topk)
    day30 = 30 * 24 * 60 * 60
    with out_path.open("w", newline="") as stream:
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
            f"expected_top{topk}",
        ])
        for query_idx, (text_length, unixtime, star) in enumerate(
            iter_i32_rows(test_label_raw, 3)
        ):
            star_low, star_high = star_range(star)
            writer.writerow([
                query_idx,
                "app_reviews_filter",
                0,
                text_length - 30,
                text_length + 30,
                unixtime - day30,
                unixtime,
                star_low,
                star_high,
                expected[query_idx],
            ])
    print(f"wrote {out_path} rows={query_count}")


def write_ibin_from_raw(raw_path: Path, out_path: Path, shape: tuple[int, int]) -> None:
    count, width = shape
    with out_path.open("wb") as out:
        out.write(struct.pack("<II", count, width))
        with raw_path.open("rb") as raw:
            shutil.copyfileobj(raw, out, length=1024 * 1024 * 16)
    print(f"wrote {out_path} count={count} width={width}")


def main() -> None:
    args = parse_args()
    h5_path = Path(args.input)
    out = Path(args.output)
    raw_dir = out / "_raw"
    out.mkdir(parents=True, exist_ok=True)

    if shutil.which("h5dump") is None:
        raise SystemExit("h5dump is required but was not found in PATH")

    meta = h5_header(h5_path)
    required = ["train_vec", "test_vec", "train_label", "test_label", "neighbors"]
    for name in required:
        if name not in meta:
            raise SystemExit(f"missing dataset: {name}")

    for name in required:
        dtype, shape = meta[name]
        if dtype not in DTYPE_SIZE:
            raise SystemExit(f"unsupported dtype for {name}: {dtype}")
        raw_path = raw_dir / f"{name}.raw"
        if not raw_path.exists():
            export_raw(h5_path, name, raw_path)
        verify_raw(raw_path, dtype, shape)

    train_count, dim = meta["train_vec"][1]
    query_count, query_dim = meta["test_vec"][1]
    if dim != query_dim:
        raise SystemExit(f"dimension mismatch: train={dim}, query={query_dim}")

    write_fbin(raw_dir / "train_vec.raw", out / f"base.{train_count}.fbin", (train_count, dim))
    write_fbin(raw_dir / "test_vec.raw", out / f"query.{query_count}.fbin", (query_count, dim))
    write_attrs(raw_dir / "train_label.raw", out / "attrs.csv", train_count)

    neighbor_shape = meta["neighbors"][1]
    write_ibin_from_raw(raw_dir / "neighbors.raw", out / "groundtruth.top100.ibin", neighbor_shape)
    write_filters(
        raw_dir / "test_label.raw",
        raw_dir / "neighbors.raw",
        out / "filters.csv",
        query_count,
        neighbor_shape[1],
        args.topk,
    )

    with (out / "README.md").open("w", encoding="utf-8") as stream:
        stream.write(
            "# BigVectorBench app_reviews converted dataset\n\n"
            f"- base: {train_count} x {dim}\n"
            f"- query: {query_count} x {dim}\n"
            "- attrs: id,text_length,unixtime,star\n"
            "- filters: text_length +/- 30, unixtime previous 30 days, "
            "star range from BigVectorBench filter_expr_func\n"
            f"- expected_top{args.topk}: copied from /neighbors\n"
        )

    if not args.keep_raw:
        shutil.rmtree(raw_dir)
        print(f"removed {raw_dir}")


if __name__ == "__main__":
    main()

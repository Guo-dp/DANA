"""Create a deterministic query subset from a prepared shared workload."""
import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np


ARRAYS = ("gt.npy", "gt_distances.npy", "valid_counts.npy")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--key", required=True, help="split key, e.g. validation or test")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(output)
    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    if args.key not in split:
        raise KeyError(f"missing split key: {args.key}")
    ids = np.asarray(split[args.key], dtype=np.int64)
    if len(ids) == 0 or len(np.unique(ids)) != len(ids):
        raise ValueError("split IDs must be nonempty and unique")

    meta = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if ids.min() < 0 or ids.max() >= meta["queries"]:
        raise ValueError("split ID out of range")
    output.mkdir(parents=True)

    with np.load(source / "queries.npz") as archive:
        np.savez(output / "queries.npz", **{key: archive[key][ids] for key in archive.files})
        np.save(output / "queries.npy", archive["vector"][ids])
    predicates = json.loads((source / "predicates.ema.json").read_text(encoding="utf-8"))
    write_json(output / "predicates.ema.json", [predicates[int(i)] for i in ids])
    for name in ARRAYS:
        np.save(output / name, np.load(source / name)[ids])

    data_link = output / "data.npz"
    try:
        data_link.symlink_to(source / "data.npz")
    except OSError:
        shutil.copy2(source / "data.npz", data_link)

    meta["queries"] = len(ids)
    meta["query_ids"] = [meta["query_ids"][int(i)] for i in ids]
    meta["subset"] = {"split_file": str(Path(args.split).resolve()), "key": args.key}
    write_json(output / "manifest.json", meta)
    print(f"prepared {len(ids)} queries under {output}")


if __name__ == "__main__":
    main()

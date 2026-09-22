#!/usr/bin/env python3
"""Refresh compact follow-up and top-level artifact SHA-256 manifests."""

from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHA_FILE = ROOT / "reproducibility" / "SHA256SUMS"
FOLLOWUP_ROOT = ROOT / "results" / "followup_experiments"
FOLLOWUP_MANIFEST = FOLLOWUP_ROOT / "manifest.csv"

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def metric_lines(path: Path) -> int:
    if path.suffix != ".log":
        return 0
    return sum(
        1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("all")
    )


def write_followup_manifest() -> None:
    files = sorted(
        path
        for path in FOLLOWUP_ROOT.rglob("*")
        if path.is_file() and path != FOLLOWUP_MANIFEST
    )
    with FOLLOWUP_MANIFEST.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("path", "bytes", "sha256", "all_metric_lines"))
        for path in files:
            writer.writerow(
                (
                    path.relative_to(FOLLOWUP_ROOT).as_posix(),
                    path.stat().st_size,
                    digest(path),
                    metric_lines(path),
                )
            )


def write_sha_file() -> None:
    paths = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
    paths.discard(SHA_FILE.relative_to(ROOT).as_posix())
    missing = [relative for relative in paths if not (ROOT / relative).is_file()]
    if missing:
        raise FileNotFoundError("Missing manifest inputs: " + ", ".join(sorted(missing)))
    lines = [f"{digest(ROOT / relative)}  {relative}" for relative in sorted(paths)]
    SHA_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    write_followup_manifest()
    write_sha_file()
    print(f"Wrote {FOLLOWUP_MANIFEST.relative_to(ROOT)}")
    print(f"Updated {SHA_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

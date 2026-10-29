#!/usr/bin/env python3
"""Export metric-only historical log evidence, or verify the compact public CSV."""
import argparse
import csv
import hashlib
import math
import re
from collections import Counter
from pathlib import Path

PATTERNS = {
    "Table2a": ["logs/deep_10m_96d/query/repeat_clean/*.log"],
    "Table3a": ["logs/sift1m_multiattr/query_sampled_seed20260709/*.log"],
    "Table4a": ["logs/bigvectorbench_app_reviews/query/dsg_ef8192.log",
                "logs/bigvectorbench_app_reviews/query/hnsw_post_c65536.log",
                "logs/bigvectorbench_app_reviews/query/hnsw_insearch_ef8192.log",
                "logs/bigvectorbench_app_reviews/**/*attrs1*.log"],
    "Table6": ["logs/bigvectorbench_app_reviews/routing/*.log"],
    "Table7": ["logs/deep_10m_96d/prefilter_hybrid/prefilter_selectivity.log",
               "logs/deep_10m_96d/prefilter_hybrid/*selectivity_ef1024.log"],
    "Table8": ["logs/deep_10m_96d/build_dsg/attr*.log", "logs/deep_10m_96d/build_hnsw/M16.log"],
    "Figure5": ["logs/deep_1m_96d/followup/attr_scaling/query_m*.log",
                "logs/deep_1m_96d/followup/attr_scaling/build_attr*.log",
                "logs/deep_1m_96d/followup/attr_scaling/high_ef/*.log"],
    "Figure6a": ["logs/deep_10m_96d/followup/dynamic_delta/count[0-9]*.log"],
    "Table10": ["logs/deep_10m_96d/followup/dynamic_cost_breakdown/delta*.log",
                "logs/deep_10m_96d/followup/dynamic_threshold/tau*.log"],
}
FIELDS = ["panel", "source", "source_sha256", "line", "metric", "version_binding"]
REG_FIELDS = ["workload", "version", "run", "phase", "queries", "recall", "mean_ms", "qps",
              "delta_entries", "source_sha256", "binary_sha256"]


def regression(root, before_bin, after_bin, output):
    records = []
    for variant, binary in (("before", before_bin), ("after", after_bin)):
        for workload, executable in (("synthetic_1k", "test_dynamic_capture_replay"),
                                     ("deep_1m_96d", "update_and_query_dana")):
            binary_hash = hashlib.sha256((binary / executable).read_bytes()).hexdigest()
            for run in range(1, 6):
                if workload == "synthetic_1k":
                    path = root / f"perf_{variant}_{run}/performance.csv"
                    with path.open() as stream:
                        source = [r for r in csv.DictReader(stream) if r["metric"] in ("query_base", "query_mutated")]
                    values = [(r["metric"], r["operations"], r["recall"], float(r["per_op_us"]) / 1000,
                               "0" if r["metric"] == "query_base" else "200") for r in source]
                else:
                    path = root / f"deep1m_{variant}_{run}.log"
                    values = []
                    for line in path.read_text().splitlines():
                        if not re.match(r"^(base|after_insert|after_update|after_delete)\s", line):
                            continue
                        metric = dict(re.findall(r"(\w+)=([\d.]+)", line))
                        values.append((line.split()[0], metric["queries"], metric["recall"],
                                       float(metric["approx_ms"]), metric["delta_size"]))
                    if len(values) != 4:
                        raise ValueError(f"Incomplete dynamic run: {path}")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                for phase, queries, recall, ms, delta in values:
                    records.append(dict(zip(REG_FIELDS, (workload, variant, run, phase, queries, recall,
                                                         ms, 1000 / ms, delta, digest, binary_hash))))
    if output.exists():
        raise FileExistsError(output)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REG_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def export(root, output):
    records = []
    for panel, patterns in PATTERNS.items():
        paths = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})
        for path in paths:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            for line, text in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
                text = text.strip()
                if (re.search(r"\bqueries=\d+", text) or text.startswith("selected_attributes") or
                    re.search(r"Maximum resident set size|Elapsed \(wall clock\)|Build Time:|Build finished in|HNSW build_seconds", text)):
                    records.append(dict(zip(FIELDS, (panel, path.relative_to(root).as_posix(), digest,
                                                    line, text, "historical_version_unbound"))))
    if not records:
        raise ValueError("No historical log metrics found")
    if output.exists():
        raise FileExistsError("Use a new output; archived evidence is not overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def verify(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames == REG_FIELDS:
            records = list(reader)
            if len(records) != 60:
                raise ValueError("Expected 60 paired regression records")
            keys = {(r["workload"], r["version"], r["run"], r["phase"]) for r in records}
            expected = {(w, v, str(n), p) for w, phases in
                        (("synthetic_1k", ("query_base", "query_mutated")),
                         ("deep_1m_96d", ("base", "after_insert", "after_update", "after_delete")))
                        for v in ("before", "after") for n in range(1, 6) for p in phases}
            if keys != expected or any(not math.isfinite(float(r["mean_ms"])) or float(r["mean_ms"]) <= 0 or not 0 <= float(r["recall"]) <= 1 for r in records):
                raise ValueError("Invalid regression records")
            for r in records:
                if not all(re.fullmatch(r"[0-9a-f]{64}", r[k]) for k in ("source_sha256", "binary_sha256")):
                    raise ValueError("Missing measurement provenance")
                if not math.isclose(float(r["qps"]), 1000 / float(r["mean_ms"]), rel_tol=1e-12):
                    raise ValueError("Inconsistent latency/QPS")
            print("PASS paired_regression_records=60; binary hashes and per-run source hashes retained")
            return
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected evidence schema")
        records = list(reader)
    seen, hashes = set(), {}
    if not records:
        raise ValueError("Empty evidence file")
    for row in records:
        key = row["panel"], row["source"], int(row["line"])
        source = Path(row["source"])
        if (key in seen or row["panel"] not in PATTERNS or int(row["line"]) <= 0 or
            source.is_absolute() or ".." in source.parts or not row["metric"] or
            not re.fullmatch(r"[0-9a-f]{64}", row["source_sha256"]) or
            row["version_binding"] != "historical_version_unbound"):
            raise ValueError(f"Invalid evidence record: {key}")
        seen.add(key)
        if hashes.setdefault(row["source"], row["source_sha256"]) != row["source_sha256"]:
            raise ValueError("One source is bound to inconsistent hashes")
    print(f"PASS evidence_records={len(records)} source_logs={len(hashes)} panels={dict(Counter(r['panel'] for r in records))}")
    print("Scope: archived metric excerpts and source-log hashes; historical binary/index identities are not reconstructed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path)
    parser.add_argument("--regression-root", type=Path)
    parser.add_argument("--baseline-bin", type=Path)
    parser.add_argument("--current-bin", type=Path)
    parser.add_argument("--file", type=Path, default=Path(__file__).resolve().parents[1] / "results/paper_evidence.csv")
    args = parser.parse_args()
    if args.export_root:
        export(args.export_root, args.file)
    if args.regression_root:
        if not args.baseline_bin or not args.current_bin:
            parser.error("Regression export requires --baseline-bin and --current-bin")
        regression(args.regression_root, args.baseline_bin, args.current_bin, args.file)
    verify(args.file)

"""Restartable, interleaved DANA/EMA measurements under one evaluator."""
import argparse
import csv
import hashlib
import json
import os
import random
import statistics
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command, log_path):
    env = dict(os.environ)
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    print("RUN", " ".join(map(str, command)), flush=True)
    with Path(log_path).open("w", encoding="utf-8") as stream:
        subprocess.run(list(map(str, command)), stdout=stream,
                       stderr=subprocess.STDOUT, env=env, check=True)


def resolve(root, value):
    path = Path(value)
    return path if path.is_absolute() else Path(root) / path


def freeze_dana_inputs(prepared, output):
    output.mkdir(parents=True, exist_ok=True)
    meta = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
    with np.load(prepared / "queries.npz") as archive:
        queries = np.asarray(archive["vector"], dtype="<f4")
        low = archive["predlow"]
        high = archive["predhigh"]
    query_path = output / "queries.fbin"
    with query_path.open("wb") as stream:
        stream.write(struct.pack("<II", *queries.shape))
        queries.tofile(stream)
    filter_path = output / "filters.csv"
    with filter_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["query_idx", "profile", "primary_attr"] +
                        [f"attr{a}_{side}" for a in range(meta["m"])
                         for side in ("low", "high")])
        profiles = meta.get("profiles", ["unified"] * len(queries))
        for qi in range(len(queries)):
            bounds = [float(value) for a in range(meta["m"])
                      for value in (low[qi, a], high[qi, a])]
            writer.writerow([qi, profiles[qi], 0] + bounds)
    return meta, query_path, filter_path


def command_for(method, ef, dataset, meta, prepared, query_path, filter_path, args, raw):
    repo = Path(args.repo_root).resolve()
    if method == "dana":
        command = [args.dana_bin, "-dataset", dataset["label"], "-N", meta["n"],
            "-dataset_path", resolve(repo, dataset["base"]),
            "-query_path", query_path, "-attr_path", resolve(repo, dataset["attrs"]),
            "-attr_count", meta["m"], "-filter_path", filter_path,
            "-query_num", meta["queries"], "-query_k", meta["k"],
            "-index_root", resolve(repo, dataset["dana_index_root"]),
            "-reordered_data_root", resolve(repo, dataset["dana_reordered_root"]),
            "-nav_mode", dataset["dana_route"], "-search_ef", ef,
            "-per_query_path", raw]
        if dataset["dana_route"] == "fixed":
            command += ["-fixed_attr", dataset["fixed_attr"]]
        return command
    index_root = Path(args.prepared_root).resolve() / dataset.get(
        "ema_index_prepared_name", dataset["prepared_name"])
    return [args.ema_python, SCRIPT_DIR / "ema_external.py", "query",
        "--ema-root", args.ema_root, "--extension-dir", args.ema_extension_dir,
        "--data", prepared, "--index", index_root / "ema-ftfix-v2/index.bin",
        "--output", raw, "--ef", ef, "--ef-top", args.ema_ef_top,
        "--threads", 1, "--warmup", 10]


def measure(method, ef, repetition, dataset, meta, prepared, query_path,
            filter_path, output, args):
    stem = output / f"{method}_ef{ef}_run{repetition}"
    raw = Path(str(stem) + ".jsonl")
    summary = Path(str(stem) + ".summary.json")
    if summary.exists():
        return
    if raw.exists():
        raise RuntimeError(f"inspect incomplete output before resuming: {raw}")
    environment = {
        "load": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
    }
    Path(str(stem) + ".environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8")
    run(command_for(method, ef, dataset, meta, prepared, query_path,
                    filter_path, args, raw), Path(str(stem) + ".log"))
    run([args.evaluator_python, SCRIPT_DIR / "evaluate_external.py",
         "--data", prepared, "--results", raw, "--output", summary,
         "--audit-distances"], Path(str(stem) + ".audit.log"))


def summarize(output, methods, repeats):
    rows = []
    for method, values in methods.items():
        for ef in values:
            summaries = [json.loads((output / f"{method}_ef{ef}_run{rep}.summary.json")
                                    .read_text(encoding="utf-8"))
                         for rep in range(1, repeats + 1)]
            times = []
            for rep in range(1, repeats + 1):
                path = output / f"{method}_ef{ef}_run{rep}.jsonl"
                times.extend(json.loads(line)["ms"] for line in path.read_text(
                    encoding="utf-8").splitlines())
            mean_ms = float(np.mean(times))
            rows.append({
                "method": method, "ef": ef, "runs": repeats,
                "recall": statistics.mean(s["exact_boundary_tie_recall"] for s in summaries),
                "mean_ms": mean_ms, "qps": 1000.0 / mean_ms,
                "p50_ms": float(np.percentile(times, 50)),
                "p95_ms": float(np.percentile(times, 95)),
                "std_run_mean_ms": statistics.stdev(s["mean_ms"] for s in summaries)
                if repeats > 1 else 0.0,
                "insufficient": statistics.mean(s["insufficient"] for s in summaries),
            })
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dana_ema_paper.json")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--prepared-root", required=True)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--dana-bin", default="build/apps/dana_external")
    parser.add_argument("--ema-root", required=True)
    parser.add_argument("--ema-extension-dir", required=True)
    parser.add_argument("--ema-python", default=sys.executable)
    parser.add_argument("--evaluator-python", default=sys.executable)
    parser.add_argument("--ema-ef-top", type=int, default=64)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--selected-only", action="store_true")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.dataset not in config["datasets"]:
        raise KeyError(f"unknown dataset: {args.dataset}")
    dataset = config["datasets"][args.dataset]
    prepared = Path(args.prepared_root).resolve() / dataset["prepared_name"]
    output = Path(args.result_root).resolve() / args.dataset
    output.mkdir(parents=True, exist_ok=True)
    meta, query_path, filter_path = freeze_dana_inputs(prepared, output / "frozen_inputs")
    methods = dataset["selected_efs"] if args.selected_only else dataset["grids"]

    provenance = {
        "config_sha256": sha256(args.config),
        "dana_binary_sha256": sha256(args.dana_bin),
        "ema_adapter_sha256": sha256(SCRIPT_DIR / "ema_external.py"),
        "evaluator_sha256": sha256(SCRIPT_DIR / "evaluate_external.py"),
        "timing": config["protocol"]["timing"],
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2),
                                             encoding="utf-8")
    for repetition in range(1, args.repeats + 1):
        jobs = [(method, ef) for method, values in methods.items() for ef in values]
        random.Random(config["protocol"]["seed"] + repetition).shuffle(jobs)
        for method, ef in jobs:
            measure(method, ef, repetition, dataset, meta, prepared, query_path,
                    filter_path, output, args)
    summarize(output, methods, args.repeats)


if __name__ == "__main__":
    main()

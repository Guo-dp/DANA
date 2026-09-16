"""Export compact DANA/EMA paper points and per-run summaries."""
import argparse
import csv
import json
from pathlib import Path


PAPER_POINTS = {
    "deep10m": {"dana": 1024, "ema-ftfix-v2": 128},
    "sift1m_sel10": {"dana": 512, "ema-ftfix-v2": 128},
    "sift1m_sel1": {"dana": 1024, "ema-ftfix-v2": 64},
}
APP_POINTS = {
    "app_reviews_r95": {"fixed1": 2048, "ema-ftfix-v2": 16},
    "app_reviews_r98": {"fixed1": 8192, "ema-ftfix-v2": 64},
}


def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-batch", required=True)
    parser.add_argument("--app-batch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paper = Path(args.paper_batch)
    app = Path(args.app_batch)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    audit = json.loads((paper / "audit_report.json").read_text(encoding="utf-8"))
    app_rows = list(csv.DictReader((app / "summary.csv").open(encoding="utf-8")))
    points = []
    repeats = []

    for dataset, methods in PAPER_POINTS.items():
        for method, ef in methods.items():
            row = next(item for item in audit["selected"]
                       if item["dataset"] == dataset and item["method"] == method)
            points.append({"workload": dataset, "threshold": row["target"],
                "method": "DANA" if method == "dana" else "EMA-FTFix-V2",
                "ef": ef, "runs": row["runs"], "recall": row["exact_boundary_recall"],
                "mean_ms": row["mean_ms"], "qps": row["qps"],
                "p50_ms": row["pooled_p50_ms"], "p95_ms": row["pooled_p95_ms"],
                "std_run_mean_ms": row["std_run_mean_ms"],
                "insufficient": row["insufficient"],
                "distance_evaluations": row["distance_evaluations"]})
            for rep in range(1, 6):
                summary = json.loads((paper / dataset /
                    f"{method}_ef{ef}_run{rep}.summary.json").read_text(encoding="utf-8"))
                repeats.append({"workload": dataset, "method": points[-1]["method"],
                    "ef": ef, "run": rep, "queries": summary["queries"],
                    "recall": summary["exact_boundary_tie_recall"],
                    "mean_ms": summary["mean_ms"], "qps": summary["qps"],
                    "p50_ms": summary["p50_ms"], "p95_ms": summary["p95_ms"],
                    "insufficient": summary["insufficient"],
                    "distance_evaluations": summary["distance_evaluations"]})

    for workload, methods in APP_POINTS.items():
        threshold = 0.95 if workload.endswith("r95") else 0.98
        for method, ef in methods.items():
            row = next(item for item in app_rows
                       if item["method"] == method and int(item["ef"]) == ef)
            label = "DANA" if method == "fixed1" else "EMA-FTFix-V2"
            points.append({"workload": workload, "threshold": threshold,
                "method": label, "ef": ef, "runs": row["runs"],
                "recall": row["recall"], "mean_ms": row["mean_ms"],
                "qps": row["qps"], "p50_ms": row["p50_ms"],
                "p95_ms": row["p95_ms"], "std_run_mean_ms": row["std_run_mean_ms"],
                "insufficient": row["insufficient"], "distance_evaluations": ""})
            for rep in range(1, 6):
                summary = json.loads((app / "test" /
                    f"{method}_ef{ef}_run{rep}.summary.json").read_text(encoding="utf-8"))
                repeats.append({"workload": workload, "method": label, "ef": ef,
                    "run": rep, "queries": summary["queries"],
                    "recall": summary["exact_boundary_tie_recall"],
                    "mean_ms": summary["mean_ms"], "qps": summary["qps"],
                    "p50_ms": summary["p50_ms"], "p95_ms": summary["p95_ms"],
                    "insufficient": summary["insufficient"],
                    "distance_evaluations": summary["distance_evaluations"]})

    write_csv(output / "paper_points.csv", points)
    write_csv(output / "repetitions.csv", repeats)
    print(f"exported {len(points)} points and {len(repeats)} runs")


if __name__ == "__main__":
    main()

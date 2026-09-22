"""Audit the archived DANA/EMA paper results without rerunning search."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "results/external_baselines/paper_comparison_v1"
APP = ROOT / "results/external_baselines/app_final_interleaved_v1"
OUT_JSON = ROOT / "results/external_baselines/dana_ema_reproducibility_audit_20260915.json"
OUT_MD = ROOT / "docs/DANA_EMA正式结果可信度审计_20260915.md"

EXPECTED_V2_SUFFIX = (
    "baselines/ema_ftfix_v2_lib/"
    "hashannlib.cpython-311-x86_64-linux-gnu.so"
)
EXPECTED_V2_SHA256 = (
    "4abff11883bab17fcc6a69699dcdcaee48a0738d85bcaeb6a9a6d48254ad90a4"
)

LOCAL_HASH_TARGETS = {
    "baselines/ema_external.py": ROOT / "scripts/baselines/ema_external.py",
    "baselines/dana_external.cpp": ROOT / "scripts/baselines/dana_external.cpp",
    "baselines/evaluate_external.py": ROOT / "scripts/baselines/evaluate_external.py",
    "apps/static/query_dana_benchmark.cc":
        ROOT / "apps/static/query_dana_benchmark.cc",
    "src/dsg.cc": ROOT / "src/dsg.cc",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def archived_hash_by_suffix(archived: dict[str, str], suffix: str) -> str:
    normalized = suffix.replace("\\", "/")
    matches = [value for key, value in archived.items()
               if key.replace("\\", "/").endswith(normalized)]
    assert len(matches) == 1, (suffix, matches)
    return matches[0]


def log_value_has_suffix(log: str, prefix: str, suffix: str) -> bool:
    return any(line.startswith(prefix) and line[len(prefix):].replace("\\", "/").endswith(suffix)
               for line in log.splitlines())


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def close(actual: float | str, expected: float | str) -> None:
    assert math.isclose(
        float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9
    ), (actual, expected)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def verify_archived_code_hashes() -> dict:
    archived = json.loads((PAPER / "code_sha256.json").read_text())
    checked = {}
    for archived_suffix, local_path in LOCAL_HASH_TARGETS.items():
        actual = sha256(local_path)
        expected = archived_hash_by_suffix(archived, archived_suffix)
        assert actual == expected, (local_path, actual, expected)
        checked[str(local_path.relative_to(ROOT))] = actual
    return {
        "status": "pass",
        "local_files_rehashed": checked,
        "formal_dana_source_snapshot": "this release repository",
        "release_matches_formal_source_hashes": True,
        "dana_server_executable_sha256": archived_hash_by_suffix(
            archived, "baselines/dana_external"
        ),
        "ema_v2_library_path_suffix": EXPECTED_V2_SUFFIX,
        "ema_v2_library_sha256_from_server_binary_audit": EXPECTED_V2_SHA256,
        "note": (
            "This release repository matches the archived formal DANA source hashes. "
            "The EMA shared object is not included and was not rehashed here."
        ),
    }


def verify_paper_batch() -> dict:
    dataset_names = ["deep10m", "sift1m_sel10", "sift1m_sel1", "app_reviews"]
    methods = {"dana", "ema-ftfix-v2"}
    run_count = 0
    query_records = 0
    ema_log_bindings = 0

    for dataset in dataset_names:
        root = PAPER / dataset
        frozen = json.loads((root / "frozen.json").read_text())
        meta = frozen["manifest"]
        assert frozen["protocol"] == "paper_comparison_v1"
        assert frozen["repeats"] == 5
        assert "warm query API including routing" in frozen["timing"]

        summary_rows = [r for r in rows(root / "summary.csv") if r["method"] in methods]
        assert len(summary_rows) == 12
        for row in summary_rows:
            method = row["method"]
            ef = int(row["ef"])
            all_times = []
            summaries = []
            for repetition in range(1, 6):
                stem = root / f"{method}_ef{ef}_run{repetition}"
                summary = json.loads(
                    Path(str(stem) + ".summary.json").read_text()
                )
                raw = [
                    json.loads(line)
                    for line in Path(str(stem) + ".jsonl").read_text().splitlines()
                ]
                assert len(raw) == meta["queries"] == summary["queries"]
                assert [item["q"] for item in raw] == list(range(len(raw)))
                assert all(
                    summary[key] == 0
                    for key in ("illegal", "duplicate_ids", "empty_errors", "distance_errors")
                )
                times = [float(item["ms"]) for item in raw]
                assert all(math.isfinite(value) and value > 0 for value in times)
                close(statistics.mean(times), summary["mean_ms"])
                all_times.extend(times)
                summaries.append(summary)
                run_count += 1
                query_records += len(raw)

                if method == "ema-ftfix-v2":
                    log = Path(str(stem) + ".log").read_text(errors="replace")
                    expected_index = f"prepared/{dataset}/ema-ftfix-v2/index.bin"
                    assert log_value_has_suffix(
                        log, "hashannlib_extension=", EXPECTED_V2_SUFFIX
                    )
                    assert log_value_has_suffix(log, "index path: ", expected_index)
                    assert "index loaded" in log
                    ema_log_bindings += 1

            pooled_mean = statistics.mean(all_times)
            checks = {
                "mean_ms": pooled_mean,
                "qps": 1000.0 / pooled_mean,
                "pooled_p50_ms": percentile(all_times, 0.50),
                "pooled_p95_ms": percentile(all_times, 0.95),
                "std_run_mean_ms": statistics.stdev(
                    float(summary["mean_ms"]) for summary in summaries
                ),
                "id_recall": statistics.mean(
                    float(summary["recall"]) for summary in summaries
                ),
                "exact_boundary_recall": statistics.mean(
                    float(summary["exact_boundary_tie_recall"])
                    for summary in summaries
                ),
            }
            for key, value in checks.items():
                close(row[key], value)

    target_rows = rows(PAPER / "target_recall_points.csv")
    selected = {}
    for dataset in ("deep10m", "sift1m_sel10", "sift1m_sel1"):
        target = 0.999
        curve = rows(PAPER / dataset / "summary.csv")
        selected[dataset] = {}
        for method in methods:
            valid = [
                row for row in curve
                if row["method"] == method
                and float(row["exact_boundary_recall"]) >= target
            ]
            best = min(valid, key=lambda row: float(row["mean_ms"]))
            archived = next(
                row for row in target_rows
                if row["dataset"] == dataset and row["method"] == method
            )
            assert int(best["ef"]) == int(archived["ef"])
            selected[dataset][method] = int(best["ef"])

    return {
        "status": "pass",
        "runs_recomputed": run_count,
        "query_records_recomputed": query_records,
        "ema_v2_log_to_index_bindings": ema_log_bindings,
        "selected_budgets_verified": selected,
        "recall_metric": "exact_boundary_tie_recall",
    }


def verify_app_final() -> dict:
    protocol = json.loads((APP / "protocol.json").read_text())
    selection_path = APP / "selection.json"
    split_path = APP / "split.json"
    assert sha256(selection_path) == protocol["selection_sha256"]
    assert sha256(split_path) == protocol["split_sha256"]
    assert protocol["repeats"] == 5

    split = json.loads(split_path.read_text())
    assert (len(split["train"]), len(split["validation"]), len(split["test"])) == (
        5000, 2000, 5000
    )
    selection = json.loads(selection_path.read_text())
    assert selection["fixed1"] == {"0.95": 2048, "0.98": 8192}
    assert selection["ema-ftfix-v2"] == {"0.95": 16, "0.98": 64}

    summary_rows = {
        (row["method"], int(row["ef"])): row
        for row in rows(APP / "summary.csv")
        if row["method"] in {"fixed1", "ema-ftfix-v2"}
    }
    assert set(summary_rows) == {
        ("fixed1", 2048),
        ("fixed1", 8192),
        ("ema-ftfix-v2", 16),
        ("ema-ftfix-v2", 64),
    }

    run_count = 0
    query_records = 0
    for (method, ef), row in summary_rows.items():
        all_times = []
        summaries = []
        for repetition in range(1, 6):
            stem = APP / "test" / f"{method}_ef{ef}_run{repetition}"
            summary = json.loads(stem.with_suffix(".summary.json").read_text())
            raw = [
                json.loads(line)
                for line in stem.with_suffix(".jsonl").read_text().splitlines()
            ]
            assert len(raw) == 5000
            assert all(
                summary[key] == 0
                for key in ("illegal", "duplicate_ids", "empty_errors", "distance_errors")
            )
            times = [float(item["ms"]) for item in raw]
            close(statistics.mean(times), summary["mean_ms"])
            all_times.extend(times)
            summaries.append(summary)
            run_count += 1
            query_records += len(raw)

            if method == "ema-ftfix-v2":
                log = stem.with_suffix(".log").read_text(errors="replace")
                assert log_value_has_suffix(
                    log, "hashannlib_extension=", EXPECTED_V2_SUFFIX
                )
                assert log_value_has_suffix(
                    log, "index path: ",
                    "prepared/app_reviews/ema-ftfix-v2/index.bin"
                )
                assert "index loaded" in log

        pooled_mean = statistics.mean(all_times)
        checks = {
            "mean_ms": pooled_mean,
            "qps": 1000.0 / pooled_mean,
            "p50_ms": percentile(all_times, 0.50),
            "p95_ms": percentile(all_times, 0.95),
            "std_run_mean_ms": statistics.stdev(
                float(summary["mean_ms"]) for summary in summaries
            ),
            "recall": statistics.mean(
                float(summary["exact_boundary_tie_recall"]) for summary in summaries
            ),
        }
        for key, value in checks.items():
            close(row[key], value)

    inventory = json.loads((APP / "index_inventory.json").read_text())
    app_indexes = {
        method: {
            "bytes": inventory[method]["bytes"],
            "files": inventory[method]["files"],
            "paths": [entry["path"] for entry in inventory[method]["entries"]],
        }
        for method in ("dana", "ema-ftfix-v2")
    }
    build = json.loads((APP / "build_metadata.json").read_text())["ema-ftfix-v2"]
    assert build["extension_path"] == EXPECTED_V2_PATH
    assert build["index_bytes"] == inventory["ema-ftfix-v2"]["bytes"]
    assert build["params"]["threads"] == 1

    return {
        "status": "pass",
        "runs_recomputed": run_count,
        "query_records_recomputed": query_records,
        "selection_hash_verified": True,
        "split_hash_verified": True,
        "frozen_selection": {
            "dana_fixed_timestamp": selection["fixed1"],
            "ema_ftfix_v2": selection["ema-ftfix-v2"],
        },
        "index_metadata": app_indexes,
    }


def verify_timing_disclosure() -> dict:
    runner = (ROOT / "scripts/baselines/run_paper_comparison.py").read_text()
    dana = (ROOT / "scripts/baselines/dana_external.cpp").read_text()
    ema = (ROOT / "scripts/baselines/ema_external.py").read_text()
    required_runner = [
        "OMP_NUM_THREADS='1'",
        "OPENBLAS_NUM_THREADS='1'",
        "MKL_NUM_THREADS='1'",
        "NUMEXPR_NUM_THREADS='1'",
        "warm query API including routing",
        "excludes loading, serialization and exact evaluation",
    ]
    assert all(token in runner for token in required_runner)
    assert "std::chrono::steady_clock::now()" in dana
    assert "std::min<size_t>(10, cases.size())" in dana
    assert "time.perf_counter_ns()" in ema
    assert "default=10" in ema
    return {
        "status": "pass",
        "warmup_queries": 10,
        "query_threads": 1,
        "included": "routing, predicate/rank handling, search, returned-ID materialization",
        "excluded": "loading, serialization, exact ground-truth and recall evaluation",
        "ema_wrapper_included": True,
    }


def main() -> None:
    checks = {
        "archived_code_and_library_version": verify_archived_code_hashes(),
        "paper_batch_raw_recalculation": verify_paper_batch(),
        "app_final_raw_recalculation": verify_app_final(),
        "timing_disclosure": verify_timing_disclosure(),
    }
    total_runs = (
        checks["paper_batch_raw_recalculation"]["runs_recomputed"]
        + checks["app_final_raw_recalculation"]["runs_recomputed"]
    )
    total_records = (
        checks["paper_batch_raw_recalculation"]["query_records_recomputed"]
        + checks["app_final_raw_recalculation"]["query_records_recomputed"]
    )
    report = {
        "status": "PASS_WITH_LIMITATIONS",
        "checks": checks,
        "totals": {
            "runs_recomputed": total_runs,
            "query_records_recomputed": total_records,
        },
        "limitations": [
            "Formal index contents are not fully bound by archived SHA-256 values.",
            "A hash computed now cannot by itself prove which file an earlier run loaded.",
            "The EMA V2 shared-object hash comes from the retained server binary audit; "
            "the shared object is not present in the local package.",
            "Five repetitions reuse one index and do not measure construction variance.",
            "The shared server was not exclusively core-pinned.",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    markdown = f"""# DANA/EMA 正式结果可信度审计

审计日期：2026-09-15。

## 结论

**PASS WITH LIMITATIONS**。方法版本与索引路径对应、Recall 规则、计时范围和现有原始结果复算均通过。共复算 {total_runs} 次运行、{total_records:,} 条逐查询记录。

| 检查项 | 结果 |
|---|---|
| DANA/EMA 查询源码哈希 | PASS |
| EMA-FTFix-V2 加载路径与正式索引路径 | PASS |
| DEEP/SIFT 达标工作点预算选择 | PASS |
| App 验证集冻结预算与测试集结果 | PASS |
| exact boundary-tie Recall 口径 | PASS |
| pooled mean、QPS、P50/P95 与 run-mean SD 复算 | PASS |
| 非法 ID、重复 ID、距离错误、空查询错误 | PASS，均为 0 |
| 全部正式索引内容 SHA-256 | PARTIAL，尚未完整归档 |

## 发布源码注意

本发布仓库中的 `apps/static/query_dana_benchmark.cc` 和 `src/dsg.cc` 均与服务器正式实验归档哈希一致。后续开发版本若修改这些文件，应使用新的版本号和结果包，不能继续声明为本次正式结果对应源码。

## 可用于论文的结论

正式结果确实由标记为 EMA-FTFix-V2 的库路径加载，并读取对应的 `ema-ftfix-v2/index.bin`；DANA 与 EMA 使用同一冻结 workload 和同一事后评测器。Recall 使用 exact boundary-tie 规则，逐查询结果与延迟可以从本地原始 JSONL 复算。计时包含查询 API 内的路由和搜索，不包含索引加载、序列化及精确 GT 评估，EMA 包含 Python wrapper 开销。

## 边界

该审计不能用当前文件哈希倒推过去运行时的索引内容，也不代表五次独立建图。全部索引 SHA-256 可在开源归档时补充，但不影响本次对方法版本、评测规则、计时范围和结果可复算性的核验。

机器可读报告：`results/external_baselines/dana_ema_reproducibility_audit_20260915.json`。
"""
    OUT_MD.write_text(markdown, encoding="utf-8")
    print(json.dumps(report["totals"], indent=2))
    print(report["status"])


if __name__ == "__main__":
    main()

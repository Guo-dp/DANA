# DANA/EMA 正式结果可信度审计

审计日期：2026-09-15。

## 结论

**PASS WITH LIMITATIONS**。方法版本与索引路径对应、Recall 规则、计时范围和现有原始结果复算均通过。共复算 260 次运行、880,000 条逐查询记录。

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

本发布仓库中的 `apps/static/query_multi_dsg_benchmark.cc` 和 `src/dsg.cc` 均与服务器正式实验归档哈希一致。后续开发版本若修改这些文件，应使用新的版本号和结果包，不能继续声明为本次正式结果对应源码。

## 可用于论文的结论

正式结果确实由标记为 EMA-FTFix-V2 的库路径加载，并读取对应的 `ema-ftfix-v2/index.bin`；DANA 与 EMA 使用同一冻结 workload 和同一事后评测器。Recall 使用 exact boundary-tie 规则，逐查询结果与延迟可以从本地原始 JSONL 复算。计时包含查询 API 内的路由和搜索，不包含索引加载、序列化及精确 GT 评估，EMA 包含 Python wrapper 开销。

## 边界

该审计不能用当前文件哈希倒推过去运行时的索引内容，也不代表五次独立建图。全部索引 SHA-256 可在开源归档时补充，但不影响本次对方法版本、评测规则、计时范围和结果可复算性的核验。

机器可读报告：`results/external_baselines/dana_ema_reproducibility_audit_20260915.json`。

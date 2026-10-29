# Dynamic Validation

This guide collects the controlled navigation--admission ablation, stable-ID maintenance, sequential capture/replay, and independent regression evidence. Historical performance measurements remain bound to their recorded source versions; correctness checks and ANN Recall are evaluated separately.

## Controlled Ablation and Audit Semantics

### Navigation--admission ablation

`bridge` and `hard_prune` call the same `rangeSearchDana()` implementation.
The runner fixes the dataset, three DSG files, 1,000 queries, filters, adaptive
route, `k=10`, and `search_ef=1024`, and alternates execution order across three
runs.

The following components are shared:

- deterministic boundary, midpoint, and quartile anchor schedule;
- radius-64 nearby-seed probing and the 4,096-item fallback scan;
- candidate, exploration, and result heaps;
- compatible-edge decoding, navigation-width rule, and stopping predicate;
- full-predicate result admission.

The mode flag is consulted only before a seed or fetched neighbor enters the
navigation frontier. `hard_prune` rejects a full-predicate-invalid object;
`bridge` may expand it but still excludes it from the result heap. Therefore
the seed-generation schedule is identical, while the actually admitted seeds
may differ as the intended consequence of hard pruning.

### Dynamic visibility counters

Every field ending in `_violations` is a violation count, not an object count:

- `inserted_visibility_violations=0`: no inserted ID expected in the committed
  snapshot was missing;
- `updated_visibility_violations=0`: no updated ID was missing or left at Base
  version zero in the pre-rebuild audit;
- `deleted_visibility_violations=0`: no deleted ID remained in the committed
  snapshot.

The audit separately counts stale returned versions, returned deleted IDs,
duplicate result IDs, predicate violations, and IDs absent from the committed
snapshot. `scripts/run_dynamic_correctness_audit.sh` exits nonzero when any
`*_violations` value is positive. Recall remains a retrieval-quality metric and
is not used by itself to establish version correctness.

### Evaluated search policy and current implementation

The frozen `4a13275` search uses a distance-only frontier comparator; its
exploration heap resolves equal distances by internal rank. Result admission
uses distance and Base-local ID (equal to original ID in the static workloads).
Evicted exploration entries remain in the frontier: there is no membership-based
lazy-deletion test. Termination requires both a full exploration heap and enough
results, and a frontier distance strictly worse than the exploration threshold.
These details must not be described as three heaps uniformly ordered by stable ID.

For navigation intervals smaller than 2% of Base, envelope-label checks are
skipped while neighbor ranks remain restricted to the interval. Full-predicate
result admission is still enforced. This reuses the same optimization as the
single-attribute search, rather than the unconditional ValidLabel-only graph
view stated in the simplified pseudocode.

The dynamic wrapper removes tombstoned Base candidates after each graph call,
then retries with a larger budget if needed; exclusions are not currently passed
into the graph's result heap. This is the process that the published recovery
measurements evaluate. The current Delta path now retains only k candidates in
a distance/stable-ID max-heap before merging. Its new measurements are separate
from historical timings of the collect-all-and-sort path.

Current APIs support an explicit query mask (`MultiRangeQuery.active_attributes`),
empty graph deployment and attribute-ID-mapped partial dynamic deployment. Empty
query masks retain the legacy all-attributes convention. A query with no active
deployed graph scans live Base exactly and merges the latest Delta Top-k.
`updateFields(id, optional_vector, attribute_pairs)` preserves omitted fields.
The dynamic CLIs accept `-indexed_attrs 0,2` or `none` and `-query_attrs "0 2"`,
`all`, or `none`. Static filter CSVs can append a `query_attrs` column containing
space-separated IDs, `all`, or `none`; omission preserves old workload semantics.

Run `test_dynamic_replay_followup contracts OUTPUT_DIR` for independent full-sort
checks, non-contiguous IDs, ties, partial-field updates, disjoint/empty deployment,
Delta-heap bounds, and post-capture replay. The static parser also recognizes
the bundled sanity CSV's missing profile column rather than shifting its bounds.

## Stable IDs After Snapshot Rebuild

### Stable-ID handling after compaction

After compaction, Base row numbers and stable IDs can differ. With stable IDs
`{0, 2, 3}`, the Base contains three rows, but stable ID `3` is still a Base
object. Testing `id < base_size` incorrectly left that object visible after a
delete and failed to suppress its old version after an update. Attribute-only
updates could also read a different vector or access beyond the Base array.

`DynamicDanaIndex` now builds a stable-ID-to-Base-row map. Base deletion and
replacement use map membership; attribute updates retrieve vectors by mapped
row. Updates require a currently live object, so gaps and deleted IDs cannot
be silently resurrected by `update()` or `updateAttributes()`.

Automatic ID allocation uses a 64-bit high-water mark, rejects unsigned-ID
exhaustion, and does not advance for rejected insertions. Snapshot export saves
`next_original_id` in `snapshot.meta`; the rebuild helper copies that metadata
alongside the stable-ID mapping. Supply it as the sixth constructor argument
when installing a rebuilt Base. Deriving this value from active IDs alone is
insufficient after deleting the largest allocated ID.

Legacy snapshots remain queryable. Loading an explicit stable-ID mapping
without allocation history disables automatic `insert()` and emits a warning
in the rebuilt-query app. Recover the original allocator high-water mark from
the exporting process or operation history before continuing automatic inserts.
Do not substitute `max(active_id) + 1` for missing history. `insertWithId()` is
an explicit-ID upsert/import API; the caller controls its ID namespace.

### Independent regression

The test uses its own ordered map of ID, vector, and attributes and applies
operations to that map independently. DANA snapshots are compared against this
reference; expected query answers are computed directly from that reference. Checks use
exceptions rather than `assert`, so Release builds execute all checks.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2 --target test_dynamic_stable_ids
OMP_NUM_THREADS=1 ./build/apps/test_dynamic_stable_ids /tmp/dana-stable-id-test
```

The focused cases cover sparse IDs, deleting stable ID 3 from a three-row Base,
updating and then deleting a Base object, deleting a newly inserted object,
high-ID attribute updates preserving the correct vector, consecutive updates,
unknown/deleted update rejection, duplicate mappings, failed-insert allocation,
legacy allocation rejection, and unsigned-ID exhaustion.

The integration case starts with 1,000 eight-dimensional vectors and three
attributes. It builds three real DSGs, saves and reloads them, applies mixed
operations, exports a compact snapshot, rebuilds three DSGs, reloads, applies
another mixed batch, and repeats the snapshot/rebuild cycle. Both snapshots
are read back from disk and compared against the independent reference.

At every phase, 40 exact filtered Top-10 queries must match the reference.
ANN results are checked for deleted IDs, invalid IDs, duplicates, predicate
violations, and incorrect Base/Delta source versions. ANN Recall is printed
separately and is not a state-correctness pass condition. Success ends with
`ALL PASS independent_operation_replay`. The same test runs in Linux CI.

### Observed server result (2026-10-01)

The regression passed on `gpu02` with GNU C++ 13.3.0, a Release build, and
`OMP_NUM_THREADS=1`. The complete output is archived in
[`server.log`](../results/stable_id_rebuild/server.log).

| Phase | Live objects | Next allocated ID | Exact queries | ANN Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| Initial Base | 1000 | 1000 | 40 | 1.000000 |
| Round 1 mutations | 910 | 1012 | 40 | 1.000000 |
| Round 1 rebuilt/reloaded | 910 | 1012 | 40 | 1.000000 |
| Round 2 mutations | 908 | 1013 | 40 | 1.000000 |
| Round 2 rebuilt/reloaded | 908 | 1013 | 40 | 0.995000 |
| Insert after second rebuild | 909 | 1014 | 40 | 0.995000 |

The two focused sparse-ID cases add 80 exact queries, for 320 independently
checked exact queries in total. All matched the operation-replay reference.
All snapshot content and allocator checks passed, and ANN result state/source
violations were zero. The approximate misses above are reported separately;
state checks and ANN Recall are evaluated as separate criteria.
Nine actual attribute DSGs were built, saved, and reloaded across the initial
Base and the two rebuilds. This is a correctness regression, not a performance
benchmark.

### Existing measurements and scope

The static query implementation, DSG build algorithm, navigation policy, and
distance function are unchanged by this patch. Historical dynamic measurements
on the initial identity-mapped Base perform the same live-object operations.
Historical post-rebuild measurements only query the reloaded Base; they do not
exercise subsequent mutations after reloading. The changed mutation paths are
therefore outside those historical post-rebuild query measurements. The
additional reverse-map memory and initialization cost are not included in
those historical measurements. This regression reports state correctness;
timing and peak-RSS measurements remain associated with their recorded source
versions.

The validated workflow is sequential: apply updates, export a snapshot,
rebuild and reload the Base, then continue updating. The two-round regression
checks stable IDs, object contents, deletion state, and allocation history
through that workflow.

A subsequent small experiment adds explicit post-capture journaling and ordered
replay; see [Sequential Capture and Replay](#sequential-capture-and-replay) for its
independent state checks and separately measured new costs. The frozen v3 artifact
and the historical performance measurements above are not overwritten.

## Sequential Capture and Replay

### 结论与范围

2026-10-02 在服务器上完成两项小规模补充实验。捕获快照后发生的操作能够按原 stable ID 和提交序号重放到重建 Base；两轮重放后的对象内容、删除状态和 ID 分配水位与独立参照一致。性能回归使用冻结的 `paper-artifact-v3` 作基线，未修改或替换论文的大规模历史性能数字。

本次验证的是**顺序、内存中捕获与重放交接**。没有并发线程、后台无阻塞切换或崩溃恢复测试；操作日志不是持久化 WAL。索引构建本身仍离线执行。

### 实现

- `include/dynamic_dana.h` / `src/dynamic_dana.cc` 增加 `captureForRebuild()`、`journalSince()`、`replayAfterCapture()` 和带确认批次的 `finishCapture()`。
- 捕获保存对象镜像、提交序号、版本计数器和 stable-ID 分配水位。捕获期间提交的插入、向量/属性更新记录完整对象镜像，删除记录 ID；属性更新镜像保留当时向量。
- 重放前检查新 Base 与捕获内容、分配水位一致，并校验全部记录的顺序、长度、版本和最终水位。重复重放、日志截断、乱序和错误镜像被拒绝。
- 导出日志后如果又有操作提交，不能用旧批次结束捕获。顺序交接必须在最终批次导出至确认之间暂停旧实例的写入；拒绝检查不能代替线程同步。
- 日志默认关闭，只有显式捕获期间保存记录。新 Base 中已重放的操作仍在 Delta；后续合并重建才能清空 Delta。

### 实验 1：正确性

数据为固定公式生成的 1,000 个 8 维向量、3 个数值属性。参数：每属性 DSG `M=8, ef_construction=40, ef_max=48, seed=2051`；查询 `k=10, ef=128`。初始建图及两轮捕获快照重建共构建、保存、重新加载 9 个真实 DSG。

独立参照为测试中的 `Reference::live` 字典：单独应用预先指定操作，不用 DANA 快照或日志生成预期状态。快照只是实际序列化输入，重新加载后逐项与该参照比较。

| 检查状态 | 活跃对象数 | 下一个 stable ID | 精确查询一致 | ANN strict-ID Recall | ANN boundary-tie Recall |
|---|---:|---:|---|---:|---:|
| 第一轮捕获后旧实例 | 989 | 1002 | 40/40 | 1.0000 | 1.0000 |
| 第一轮新 Base 重放后 | 989 | 1002 | 40/40 | 1.0000 | 1.0000 |
| 第二轮捕获后旧实例 | 988 | 1004 | 40/40 | 1.0000 | 1.0000 |
| 第二轮新 Base 重放后 | 988 | 1004 | 40/40 | 0.9500 | 0.9525 |
| 两轮重放后再次插入 | 989 | 1005 | 40/40 | 0.9500 | 0.9525 |

两轮共重放 **80 条操作**，新增 **200 次精确查询逐 ID/顺序一致检查**，另有 **48 次重放对象的提交后可见性检查**。此前两轮 stable-ID 回归也重新运行通过，其 320 次精确检查保持一致。

覆盖捕获后删除、向量/属性更新、插入后删除、同 ID 连续更新再删除、最高 ID 删除后再插入、两轮交接，以及空日志。两轮合计 24 次异常调用检查和额外的空日志重复重放检查均拒绝了不合法输入；拒绝批次后检查新 Base 未被改变。

| 违规类型 | 数量 |
|---|---:|
| 删除/无效 ID 返回 | 0 |
| 重复 ID | 0 |
| 当前谓词违规 | 0 |
| 旧内容或旧版本来源/编号 | 0 |
| 分配水位/历史 ID 复用 | 0 |
| 提交后对象不可见 | 0 |

这里的 `visibility_violations=0` 表示**可见性违规次数为零**，不是可见对象数为零。版本检查结合完整对象镜像核对、ANN Base/Delta 来源和返回的版本编号；其范围是本测试指定的操作与查询，不是对任意并发执行的证明。

ANN Recall 单独报告。第二轮重新建图后确有近似搜索漏召回；边界并列处理只从 0.9500 提升至 0.9525，不能将全部漏召回解释为距离并列。这不改变精确结果和状态一致性检查，但不能宣称“重放后 ANN 始终满召回”。

### 实验 2：轻量性能回归

AMD EPYC 7542、128 逻辑 CPU、503 GiB 内存，Ubuntu/Linux，GCC 13.3.0、CMake 3.28.3；Release 使用仓库现有 `-Ofast -march=native` 等选项。OpenMP/BLAS/MKL 线程数均为 1，共享机器，未独占绑核。

三个配置各重复 5 次，按固定轮换顺序交错运行，共 15 次，没有剔除计时样本。每次插入、更新、删除各 100 个对象；40 条固定查询先预热 40 次，再循环 10 次，共计时 400 次/状态。独立 GT 和状态核对在计时区间外，查询计时覆盖整个 `search()`（Base + Delta + 合并），不含 GT、打印、磁盘加载或建图。

冻结基线为 `c10676c0056b5b9a2c35e15b8361422bc194332f` 的动态头文件/实现，其他构建参数和实验夹具相同。该基线**已包含 stable-ID 修复**，因此下面比较隔离的是新增捕获/日志/重放机制，并不单独量化早先反向映射修复的增量成本。

以下为每次均值的均值 ± 样本标准差：

| 指标 | 冻结 v3 | 新版日志关闭 | 新版日志开启 |
|---|---:|---:|---:|
| 初始化，微秒/索引 | 23.628 ± 0.783 | 23.527 ± 0.639 | 22.603 ± 0.220 |
| 插入，微秒/操作 | 0.1300 ± 0.0039 | 0.1420 ± 0.0022 | 0.2102 ± 0.0140 |
| 更新，微秒/操作 | 0.1860 ± 0.0353 | 0.1776 ± 0.0029 | 0.2309 ± 0.0036 |
| 删除，微秒/操作 | 0.0641 ± 0.0283 | 0.0584 ± 0.0011 | 0.0700 ± 0.0007 |
| Base 查询，ms/查询 | 0.048073 ± 0.000036 | 0.047931 ± 0.000094 | 0.047874 ± 0.000051 |
| 更新后查询，ms/查询 | 0.095568 ± 0.000074 | 0.095546 ± 0.000134 | 0.095481 ± 0.000195 |

| 新增步骤 | 总时间 ms，均值 ± 标准差 |
|---|---:|
| 捕获 1,000 对象快照 | 0.081803 ± 0.002835 |
| 复制导出 300 条日志 | 0.010975 ± 0.000306 |
| 快照文件写出 | 1.414037 ± 0.019170 |
| 捕获快照的三图重建、保存/加载 | 173.963145 ± 0.118076 |
| 校验并重放 300 条操作 | **0.161645 ± 0.001321** |
| 再次合并重建、保存/加载 | 173.168949 ± 0.133713 |

重放计时包含匹配捕获 Base 的内容核对、完整批次校验和操作执行；约 0.539 微秒/操作。表中的“再次合并重建”还包括快照写出，不与前一行构建时间作纯建图比较。

| 日志开启的阶段 | ms/查询 | 五次均值 QPS | strict-ID Recall |
|---|---:|---:|---:|
| 初始 Base | 0.047874 | 20888.1 | 1.0000 |
| 修改后旧实例 | 0.095481 | 10473.3 | 1.0000 |
| 捕获 Base + 重放 Delta | 0.095201 | 10504.1 | 1.0000 |
| 再次合并重建后 | 0.048164 | 20762.5 | 0.9500 |

QPS 是逐次 `400 / measured_seconds` 的算术均值，不是平均延迟的倒数。新增日志在本例中增加了写入成本，但没有观察到明显查询回归；这不是统计显著性检验，不能外推为生产级更新吞吐或大规模零开销保证。

#### 内存解释

共用同一 Base/图，批量创建 64 个 overlay，测量 glibc `mallinfo2().uordblks`：冻结 v3 平均每个约 **56,792 字节**，新版约 **56,850 字节**，增量约 **58 字节/索引**，包含分配器取整影响。Base 向量、共享图的构建成本不在此增量内。

捕获对象镜像约增加 143,920 字节活动堆；复制 300 条日志约增加 37,152 字节，重放阶段约增加 45,232 字节。它们是各独立步骤的活动堆观测量，不应混加成一个精确的总峰值。

进程 RSS 在这些小步骤中的增量均未被采样分辨出来；**这不表示零内存开销**。日志开启的夹具包含额外建图和多个同时存活的 Base，不拿其进程总峰值与只执行初始建图的基线作算法内存差比较。

### 随机多轮重放与 ANN 质量扩展

2026-10-03 以同样的 1,000 对象、8 维、3 属性夹具扩大覆盖。5 个操作种子各连续进行 5 轮捕获与真实 DSG 重建，每轮捕获后执行 1,000 条混合操作。独立参照直接执行生成的原始操作；日志逐条核对序号、stable ID、对象镜像和版本。热 ID 重复修改、插入后删除及最高 ID 删除后继续插入被重点覆盖。

| 检查项 | 结果 |
|---|---:|
| 种子 / 捕获重放轮数 / 总操作数 | 5 / 25 / 25,000 |
| 插入 / 向量更新 / 属性更新 / 删除 | 6,276 / 7,152 / 5,987 / 5,585 |
| 旧实例 / 重放实例精确查询核对 | 1,000 / 1,000 |
| 活跃 ID、内容、版本、分配水位及查询状态违规 | 0 |

每 200 次操作和每轮结束核对状态，重放后还核对精确过滤查询与 ANN 结果的删除、重复、谓词及 Base/Delta 来源。结果逐轮保存在 `results/replay_followup/random_rounds.csv`。零违规是本夹具的观察结果，不是任意操作序列的形式证明。

另以固定两轮操作和 40 条固定查询，在三个建图种子 2051、2052、2053 下测量同一最终逻辑状态。下表为三个种子的每查询均值，Recall 使用 strict-ID 规则。

| 阶段 | ef | Recall | 平均 ms | 距离计算 |
|---|---:|---:|---:|---:|
| 旧活跃实例 | 128 | 1.0000 | 0.0636 | 314.7 |
| 旧活跃实例 | 256 | 1.0000 | 0.0935 | 388.2 |
| 旧活跃实例 | 512 | 1.0000 | 0.1280 | 501.4 |
| Base + 重放 Delta | 128 | 0.9508 | 0.0601 | 298.6 |
| Base + 重放 Delta | 256 | 0.9833 | 0.0946 | 384.1 |
| Base + 重放 Delta | 512 | 0.9833 | 0.1276 | 496.3 |
| 再次合并重建 | 128 | 0.9750 | 0.0487 | 227.2 |
| 再次合并重建 | 256 | 1.0000 | 0.0713 | 281.6 |
| 再次合并重建 | 512 | 1.0000 | 0.0986 | 373.2 |

全部 27 个条件的精确结果与独立参照一致，结果不足和状态违规为零。重放后的前两个种子在 `ef=256/512` 均为 0.975，第三个种子为 1.0；继续加宽未必恢复全部召回。再次合并后 `ef=256` 在三个种子均达 1.0。没有单独隔离图拓扑、rank 重排与 Delta 组成的因果作用。

`results/replay_followup/quality_curve.csv` 保留各种子 strict-ID 和 boundary-tie Recall 及距离分项。距离计数累计所有 Base 图搜索、Base 候选重排和通过过滤的 Delta 点计算，不含精确真值扫描。每个条件只计时一次 40 条查询，共享服务器上的延迟仅作探索性观察，不用于大规模吞吐优势或显著性结论。该统计计数是后续增加的，前述 2026-10-02 性能测量所用源码指纹见 `environment.txt`，不把历史计时当作加入计数后的重新测量。

### 复现与产物

仅正确性，不需要原始 DEEP/SIFT/App 数据：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2 --target test_dynamic_capture_replay test_dynamic_stable_ids
OMP_NUM_THREADS=1 ./build/apps/test_dynamic_capture_replay correctness /tmp/dana-capture-replay
OMP_NUM_THREADS=1 ./build/apps/test_dynamic_stable_ids /tmp/dana-stable-ids
cmake --build build -j 2 --target test_dynamic_replay_followup
OMP_NUM_THREADS=1 ./build/apps/test_dynamic_replay_followup random /tmp/dana-replay-random
OMP_NUM_THREADS=1 ./build/apps/test_dynamic_replay_followup quality /tmp/dana-replay-quality
```

完整性能对照需要 Git 历史中的 v3 源码：

```bash
# 若使用浅克隆，先获取冻结基线；普通完整克隆无需此步。
git fetch origin tag paper-artifact-v3
OUT_DIR=/tmp/dana-replay-results bash scripts/run_capture_replay_experiments.sh
python3 scripts/summarize_capture_replay.py /tmp/dana-replay-results
```

最小归档只保留 `results/capture_replay/measurements.csv` 中 15 次运行的 130 条原始测量、`validation.txt` 的运行通过记录、`environment.txt` 的环境与历史源码指纹，以及 `results/replay_followup/` 的两份逐轮/逐种子 CSV。`summarize_capture_replay.py` 从原始测量重算均值和样本标准差，生成的 `summary.csv` 不重复上传。构建日志、逐次计时文本、可由夹具重新生成的操作轨迹和索引不上传。冻结 v3 不移动；新增结果属于新的验证版本，范围为顺序、内存中的捕获与重放。

### 2026-10-29 接口与 Delta 候选界限补测

本轮新增显式查询属性、空部署/部分部署精确回退、部分字段更新和容量 k 的 Delta 最大堆。默认查询与部署仍沿用原来的全属性约定。`contracts` 模式的 32 次查询检查均通过，覆盖非连续 stable ID、完全并列的 Delta 向量、k=1/3/10/1000、仅部署 attr2、查询与部署不相交、字段保留、错误字段拒绝、候选规模界限及捕获后字段更新重放。已有两轮重建、顺序重放、25轮随机重放及三种子质量曲线也重新通过。

另使用冻结 `4a13275` 与新版二进制交错运行 5 组对照，单线程、共享机器，不剔除样本。1K 夹具每状态先预热40次，再测400次；DEEP-1M-96D 使用既有索引、100条查询、k=10、ef=1024、seed=2031，插入/更新/删除各50K，无专门查询预热。DEEP 的100K Delta 为混合操作状态，与历史 Table 10 的 insert-only 状态不同。

| 每查询时延 ms，均值 ± 样本标准差 | 4a13275 | 新版 |
|---|---:|---:|
| 1K，更新前 | 0.048314 ± 0.000279 | 0.048374 ± 0.000257 |
| 1K，更新后 | 0.096244 ± 0.000351 | 0.096678 ± 0.000606 |
| DEEP-1M，删除阶段后，100K Delta | 11.3491 ± 0.2051 | 13.6298 ± 4.5598 |

两版本所有测量状态 Recall 相同：1K 为1.0，DEEP为0.9990。新版本符合候选界限，但本轮未显示稳定的时延改善；保留全部波动结果，不将其归因为单一因素，也不替换旧版论文性能数字。60条逐次记录及对应二进制/原始指标文件哈希位于 `results/replay_followup/maintenance_regression.csv`。

## Retained Controlled-Experiment Records

`results/followup_experiments/nav_admission_deep10m/` retains three alternating bridge/hard-prune pairs and their summary. Recompute it with:

```bash
python3 scripts/summarize_nav_admission_ablation.py results/followup_experiments/nav_admission_deep10m
```

`results/followup_experiments/dynamic_correctness/` retains the 100K workload audit after 1,000 insertions, updates, and deletions, and the post-rebuild audit of the 100-operation snapshot. The preparation sequence is in `REPRODUCIBILITY.md`. The early single-run DEEP-1M navigation check is superseded by the retained DEEP-10M pairs; it remains accessible in Git history. The follow-up manifest records each retained file's size, SHA-256, and aggregate metric-row count.

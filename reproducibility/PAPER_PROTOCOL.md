# Frozen Paper Artifact and Evaluation Protocol

Release ref: **`paper-artifact-v4`**.

The implementation baseline is commit
`ceac51b61a7275bbb71f0364e6409fa22e87148c`. The freeze commit adds
this protocol record, updates the README release link, and refreshes the
existing checksums. It does not change implementation code, experiment
configurations, workloads, evaluators, or measured results. The commit resolved
by the release tag identifies the complete frozen artifact. Earlier tags,
including the `paper-artifact-v3` regression baseline, remain unchanged.

## 1. Authoritative Files

| Evidence | Frozen input or record |
|---|---|
| Formal DANA/EMA configuration | `configs/dana_ema_paper.json` |
| App query partition | `configs/app_reviews_split.json` |
| Formal operating points | `results/ema_comparison/paper_points.csv` |
| Five query-run repetitions | `results/ema_comparison/repetitions.csv` |
| Run-level variability | `results/ema_comparison/variability.csv` |
| Historical measurement provenance | `results/ema_comparison/provenance.json`, `reproducibility/audit.json` |
| Historical HNSW and supplementary metrics | `results/paper_evidence.csv` |
| DEEP-10M default-threshold cycle | `results/dynamic_deep10m/table9.csv`, `post_rebuild_runs.csv` |
| Current dynamic validation | `docs/DYNAMIC_VALIDATION.md`, `results/capture_replay/`, `results/replay_followup/` |
| Current release file identities | `reproducibility/SHA256SUMS` |

The source-log hashes in historical records and the current release checksums
serve different purposes. Current checksums do not establish the identity of
past binaries or indexes. Compact extracts are retained; full historical query
archives and large indexes are not bundled. Reproduction commands are in
`REPRODUCIBILITY.md` and `DANA_EMA_REPRODUCIBILITY.md` at this release ref.

## 2. Formal Static DANA/EMA Comparison

- Both methods use the same prepared vectors, queries, conjunctive predicates,
  and filtered float64 squared-L2 ground truth.
- `k=10`, one query thread, ten warmup queries, and five measured query-run
  repetitions on the retained indexes. These are not five independent builds.
- Recall uses exact boundary-tie credit: substitution is allowed only at the
  exact boundary distance, without a tolerance or replacement of closer objects.
  Correctly empty results receive credit 1 and are included in the query mean;
  empty-result errors are audited separately.
- QPS is pooled from measured query time. API timing includes routing and search,
  including EMA's Python wrapper, and excludes loading, serialization,
  ground-truth evaluation, and DANA's evaluation-only returned-ID distance
  recomputation. Slow runs are not automatically removed.
- DEEP/SIFT use randomized configuration order. App uses interleaved evaluation.
  The measurements used a shared server without exclusive CPU pinning; there
  was no dedicated low-load paired DEEP/SIFT rerun.
- Report the measured configuration with the highest throughput satisfying
  each common Recall floor. App configurations are selected on validation and
  then frozen. A common floor is not identical measured Recall.
- EMA is **EMA-FTFix-V2**, a non-official evaluation variant. The three isolated
  FT patches and rebuilt-index protocol remain disclosed. DANA uses `M=16`,
  `efConstruction=100`; EMA uses `M=16`, `efConstruction=500`, 128 FT bits,
  `ef_top=64`, and FT routing. Full grids and seeds are in the frozen config.

| Workload | Recall floor | DANA route | DANA ef | EMA ef | API QPS: DANA / EMA |
|---|---:|---|---:|---:|---:|
| DEEP-10M, 1,000 queries | 0.999 | Span-adaptive | 1024 | 128 | 143.0 / 50.5 |
| SIFT1M sel10, 1,000 sampled queries | 0.999 | Span-adaptive | 512 | 128 | 410.1 / 293.0 |
| SIFT1M sel1, 1,000 sampled queries | 0.999 | Span-adaptive | 1024 | 64 | 251.2 / 79.4 |
| App-Reviews, 5,000 evaluation queries | 0.95 | Fixed timestamp, attr1 | 2048 | 16 | 267.8 / 121.1 |
| App-Reviews, 5,000 evaluation queries | 0.98 | Fixed timestamp, attr1 | 8192 | 64 | 95.5 / 44.9 |

App uses seed 2041 and **3,000 fitting + 2,000 validation + 5,000 evaluation**
queries. The archived configuration key `test` denotes this evaluation set;
`train` is the union of fitting and validation. The partition is of the existing
workload, not an external test set. SIFT samples use seed 20260709; `sel10` and
`sel1` are profile names rather than measured joint selectivities. Formal search
grids, inputs, and budgets must not be tuned on App evaluation outcomes.

## 3. Separate Historical and Diagnostic Protocols

- Historical HNSW comparisons use `M=16`, `efConstruction=100`, and strict-ID
  Recall. The main DEEP-10M point
  uses three low-load repetitions, averaging latency and QPS separately; its
  mean QPS is therefore not the reciprocal of mean latency. Do not combine
  these timings with the separate formal EMA API measurements.
- The Table 6 calibrated-router diagnostic uses **5,000 fitting + 5,000
  evaluation** queries. Its fixed weights are `(12.0, 0.25, 0.25)`. This is
  separate from the formal App EMA partition and fixed-timestamp policy.
  The complete historical calibration grid and training-selection tie rule
  were not retained. Oracle routing is an offline descriptive bound.
- Hybrid threshold summaries are offline, profile-level cost analyses using
  separately measured Prefilter/DSG timings and observed mean feasible counts.
  The independence-based count estimate is a separate reported statistic;
  the summaries are not end-to-end measurements of an online estimator.
- Attribute-count scaling deploys the first `m` of six independent attributes
  while all queries constrain all six. It is not a sweep of constrained
  attribute count. Navigation hard pruning gates both seeds and neighbors;
  its ablation does not hold admitted seed sets identical.

## 4. Dynamic Maintenance and Current Validation

The historical DEEP-10M default-5% cycle uses the recorded unique changed-ID
set, with the first sampled triggering state at 500,001 IDs. Its published
pre/post-rebuild values are **22.38 / 69.59 QPS** and **0.9994 / 0.9991 Recall**.
The post-rebuild summary pools three runs. Historical growth and cost breakdown
measurements used the earlier collect-and-sort Delta path.

The current implementation separately validates stable-ID maintenance,
sequential in-memory capture/replay, explicit/partial deployment, partial-field
updates, exact fallback, and a bounded Delta heap. The five-seed, 25-cycle
randomized validation and three-graph-seed ANN-quality records remain distinct
from historical large-scale performance results. They do not represent a
concurrent background service or durable crash recovery.

The five-pair implementation regression uses DEEP-1M-96D, 100 queries, `k=10`,
`ef=1024`, seed 2031, and 50K each of insert/update/delete, without a dedicated
query warmup. At its mixed-operation 100K-Delta state, Recall is 0.9990 in both
versions; latency is **11.35 +/- 0.21 ms** before and **13.63 +/- 4.56 ms** after
(mean +/- sample SD). This satisfies the new candidate bound but does not
establish a stable speedup. It neither replaces the DEEP-10M timings nor
isolates the Delta heap as the only changed factor.

## 5. Citation and Later Changes

Use the fixed `paper-artifact-v4` release URL, rather than the moving `main`
branch, for this artifact. Select the full commit resolved by the tag when a
commit-based citation is required. The current release is a reproducible code
and evidence package, not a claim that every historical measurement ran the
latest source byte for byte. Historical source identities remain in provenance.

Later code or protocol changes require a new version and a new measurement
campaign where affected. Do not move this tag, overwrite the archived paper
points, relabel an old timing as a current-version measurement, or silently
change a workload split, Recall rule, timing boundary, or repetition policy.

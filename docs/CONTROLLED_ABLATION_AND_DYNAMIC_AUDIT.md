# Controlled ablation and dynamic-audit semantics

## Navigation--admission ablation

`bridge` and `hard_prune` call the same `rangeSearchMultiDsg()` implementation.
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

## Dynamic visibility counters

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

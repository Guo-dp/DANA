# Controlled ablation and dynamic-audit semantics

## Navigation--admission ablation

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

## Evaluated search policy and current implementation

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

# Stable IDs After Snapshot Rebuild

## Defect and repair

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

## Independent regression

The test uses its own ordered map of ID, vector, and attributes and applies
operations to that map independently. DANA snapshots are compared against this
reference; they are never used to generate expected query answers. Checks use
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

## Observed server result (2026-10-01)

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
the test does not claim that state correctness implies perfect ANN Recall.
Nine actual attribute DSGs were built, saved, and reloaded across the initial
Base and the two rebuilds. This is a correctness regression, not a performance
benchmark or evidence for post-capture replay.

## Existing measurements and scope

The static query implementation, DSG build algorithm, navigation policy, and
distance function are unchanged by this patch. Historical dynamic measurements
on the initial identity-mapped Base perform the same live-object operations.
Historical post-rebuild measurements only query the reloaded Base; they do not
exercise the previously faulty subsequent mutations. This repair does not by
itself invalidate those query measurements, but the additional reverse-map
memory and initialization cost were not measured in them. No updated timing
or peak-RSS claim is made by this correctness regression.

This test establishes sequential updates after installing a rebuilt Base.
Capture-time logging, replay of operations issued after snapshot capture,
concurrent queries/updates, and background Base replacement are not implemented
or validated by this patch. A manuscript equation describing post-capture
replay must be labelled as a proposed protocol rather than implemented
functionality until that operation log and replay path exist.

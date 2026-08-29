# vector_calc_sanity

Purpose: verify fbin loading, squared L2 distance, range filtering, tie ordering, and Top-K output on a hand-checkable dataset.

- `base.8.fbin`: 8 vectors, dim=2.
- `query.3.fbin`: 3 queries, dim=2.
- `attrs.csv`: no header, columns are `id,attr0,attr1,attr2`.
- `filters.csv`: expected Top-3 ids and expected squared L2 values.

Expected rows:
- q0 all points: ids `0 1 2`, squared L2 `0.0 1.0 4.0`.
- q1 x-axis odd ids: ids `3 5 1`, squared L2 `1.0 1.0 9.0`.
- q2 y-axis even ids: ids `4 6 2`, squared L2 `1.0 1.0 9.0`.

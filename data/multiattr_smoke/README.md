# multiattr_smoke

Tiny multi-attribute smoke-test dataset.

- `base.32.fbin`: 32 base vectors, dim=4.
- `query.4.fbin`: 4 query vectors, dim=4.
- `attrs.csv`: no header, columns are `label,attr0,attr1,attr2`.
- `filters.csv`: four multi-attribute query filters and exact top-3 labels.

Important: `attr0 == label`, so attr0 can be used as the primary attribute
without changing the current single-attribute rank assumptions.

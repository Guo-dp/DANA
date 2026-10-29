# Data

## Bundled Validation Data

Attribute CSV files have no header and use `id,attr0,attr1,...`. Filter CSV files have a header.

| Directory | Base | Query | Purpose |
|---|---:|---:|---|
| `data/vector_calc_sanity` | 8 x 2 | 3 x 2 | Squared L2, filtering, ties, Top-3 |

`attrs.csv` contains three attributes per row; `filters.csv` includes expected
Top-3 IDs and squared-L2 distances. The hand-checkable answers are:

| Query | Expected IDs | Squared L2 |
|---|---|---|
| q0 | `0 1 2` | `0.0 1.0 4.0` |
| q1 | `3 5 1` | `1.0 1.0 9.0` |
| q2 | `4 6 2` | `1.0 1.0 9.0` |

`.fbin` format:

```text
uint32 count
uint32 dimension
float32[count][dimension]
```

Rank mapping format:

```text
uint32 count
uint32[count] rank_to_original
```

## Paper Workload Definitions

`workloads/` contains compact generated filters and JSON manifests for DEEP, SIFT, App-Reviews, and synthetic experiments. The original vectors, generated attribute tables, reordered vector copies, and indexes are not included.

The checked-in manifests record seeds, dimensions, query counts, attribute counts, and selectivity profiles where available. Filters are deterministic experiment inputs and can be paired with regenerated attributes using the corresponding preparation scripts.

Paths under `workloads/` follow the dataset families used by the preparation
scripts. Regenerate full workloads first, then compare the filters and manifests
against these compact inputs. SIFT's retained filter files contain the 1,000-query
paper workloads, not the superseded 500-query exploratory subsets.

Use `scripts/prepare_dana_data_memmap.py` for both initial attribute ordering and
snapshot rebuilding. It sorts by `(attribute value, original row ID)`, writes
vectors in chunks, and emits the rank mappings used by the builders.

## Public Dataset Inputs

- DEEP: use dimension-matched 96D base/query files. The main artifact uses the first 1M or all 10M base vectors and public 10K queries.
- SIFT1M: 128D vectors with generated independent scalar attributes.
- BigVectorBench App-Reviews: 277,936 training vectors, 10,000 test vectors, 384 dimensions, and three integer labels.

Validate DEEP dimensions before running L2 search:

```bash
python3 - <<'PY'
import struct
from pathlib import Path
for name in ("base.10M.fbin", "query.public.10K.fbin"):
    path = Path("data/deep") / name
    with path.open("rb") as stream:
        count, dim = struct.unpack("<II", stream.read(8))
    print(path, count, dim)
PY
```

Do not commit public vectors, reordered `base.attr*.fbin` files, `.dsg`, or `.hnsw` indexes to ordinary Git history. They are large reproducible artifacts and third-party data remains governed by its source license.

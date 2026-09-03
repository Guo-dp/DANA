# Data

## Bundled Validation Data

Attribute CSV files have no header and use `id,attr0,attr1,...`. Filter CSV files have a header.

| Directory | Base | Query | Purpose |
|---|---:|---:|---|
| `data/vector_calc_sanity` | 8 x 2 | 3 x 2 | Squared L2, filtering, ties, Top-3 |
| `data/multiattr_smoke` | 32 x 4 | 4 x 4 | Three-attribute smoke workload |
| `data/multiattr_10k` | 10,000 x 32 | 100 x 32 | Medium synthetic benchmark |

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

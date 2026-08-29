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

## Public Data

Paper experiments use public vector datasets plus generated scalar attributes and filters. Raw public vectors are not redistributed. Place matching 96D DEEP base/query files under `data/deep/` and verify dimensions before L2 search.

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

Do not commit raw public datasets, reordered vectors, `.dsg`, or `.hnsw` files to ordinary Git history. They are large reproducible artifacts. Third-party datasets remain governed by their original terms.

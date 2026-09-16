"""Thin adapter using the official EMA HashANN build and query APIs."""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

from prepare_external import fbin, write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['build', 'query'])
    p.add_argument('--ema-root', required=True)
    p.add_argument('--extension-dir', help='Isolated patched hashannlib directory')
    p.add_argument('--data', required=True)
    p.add_argument('--index', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--ef', type=int, default=128)
    p.add_argument('--ef-top', type=int, default=64)
    p.add_argument('--M', type=int, default=16)
    p.add_argument('--ef-construction', type=int, default=500)
    p.add_argument('--threads', type=int, default=1)
    p.add_argument('--seed', type=int, default=2037)
    p.add_argument('--warmup', type=int, default=10)
    p.add_argument('--no-ft', action='store_true', help='Diagnostic ablation only')
    p.add_argument('--no-routing', action='store_true', help='Diagnostic ablation only')
    a = p.parse_args()
    sys.path.insert(0, str(Path(a.ema_root) / 'tests'))
    if a.extension_dir:
        sys.path.insert(0, a.extension_dir)
    from hashann import HashANN
    import hashannlib
    print('hashannlib_extension=' + str(Path(hashannlib.__file__).resolve()), flush=True)
    root = Path(a.data)
    meta = json.loads((root / 'manifest.json').read_text())
    params = dict(M=a.M, ef_construction=a.ef_construction, metric='l2',
                  dim=meta['dim'], N=meta['n'], ft_bits=128, threads=a.threads,
                  k=meta['k'], name='HNSW')
    ann = HashANN()
    ann.init_params(params)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    if a.mode == 'build':
        if Path(a.index).exists():
            raise FileExistsError(a.index)
        Path(a.index).parent.mkdir(parents=True, exist_ok=True)
        np.random.seed(a.seed)
        base = fbin(meta['sources']['base'])
        attrs = np.load(root / 'attrs.ema.npy')[:, :, None].tolist()
        start = time.perf_counter()
        ann.build_index(params, base, attrs, [0] * meta['m'], a.index, a.threads)
        write_json(a.output, dict(method='EMA-FTFix' if a.extension_dir else 'EMA',
            extension_path=str(Path(hashannlib.__file__).resolve()), seconds=time.perf_counter() - start,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            index_bytes=Path(a.index).stat().st_size, params=params, seed=a.seed,
            clustering_seed=1234, graph_seed=100))
        return
    index = ann.load_index(params, [0] * meta['m'], a.index, 1)
    index.set_ef(a.ef)
    index.set_ef_top(a.ef_top)
    index.set_ft_flag(not a.no_ft)
    index.set_ft_routing_flag(not a.no_routing)
    index.set_ft_routing_min_deg(0)
    queries = np.load(root / 'queries.npy')
    preds = json.loads((root / 'predicates.ema.json').read_text())
    # Reject an impossible single-attribute interval without consulting GT.
    def query(i):
        if any(lo > hi for lo, hi in preds[i]):
            return [], [], 0, 0
        ids, distances, counts, hops = index.hybrid_knn_query_with_stats(
            queries[i:i+1], [preds[i]], k=meta['k'])
        pairs = [(int(v), float(d)) for v, d in zip(ids[0], distances[0])
                 if 0 <= int(v) < meta['n']]
        return [v for v, _ in pairs], [d for _, d in pairs], float(counts[0]), float(hops[0])
    for qi in range(min(a.warmup, len(queries))):
        query(qi)
    with open(a.output, 'x') as stream:
        for qi in range(len(queries)):
            start = time.perf_counter_ns()
            ids, distances, count, hops = query(qi)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            stream.write(json.dumps(dict(q=qi, ms=elapsed, ids=ids,
                distances=distances, dist=count, hops=hops)) + '\n')


if __name__ == '__main__':
    main()

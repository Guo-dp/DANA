"""Convert fbin/CSV inputs without changing row IDs or conjunction semantics."""
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

import numpy as np


def fbin(path):
    path = Path(path)
    with path.open('rb') as stream:
        n, d = struct.unpack('<II', stream.read(8))
    if path.stat().st_size != 8 + 4 * n * d:
        raise ValueError(f'Invalid fbin size: {path}')
    return np.memmap(path, dtype='<f4', offset=8, shape=(n, d), mode='r')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def prepare(base, queries, attrs, low, high, ids, profiles, out, k, sources):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    n, d = base.shape
    if queries.shape[1] != d or attrs.shape[0] != n:
        raise ValueError('Vector dimensions or attribute row count differ')
    if not np.isfinite(attrs).all() or np.isnan(low).any() or np.isnan(high).any():
        raise ValueError('Nonfinite attributes or NaN predicates')
    if np.any(low > high):
        raise ValueError('Reversed input range')
    encoded = np.empty(attrs.shape, dtype=np.int32)
    elo = np.empty(low.shape, dtype=np.int32)
    ehi = np.empty(high.shape, dtype=np.int32)
    for j in range(attrs.shape[1]):
        values, inverse = np.unique(attrs[:, j], return_inverse=True)
        if len(values) >= np.iinfo(np.int32).max:
            raise ValueError('Too many distinct values for EMA int interface')
        encoded[:, j] = inverse
        elo[:, j] = np.searchsorted(values, low[:, j], side='left')
        ehi[:, j] = np.searchsorted(values, high[:, j], side='right') - 1
        np.save(out / f'values.attr{j}.npy', values)
    np.save(out / 'attrs.ema.npy', encoded)
    np.savez(out / 'data.npz', vector=base, attributes=attrs.astype(np.float64))
    np.savez(out / 'queries.npz', vector=queries, predlow=low.astype(np.float64),
             predhigh=high.astype(np.float64))
    np.save(out / 'queries.npy', queries)
    write_json(out / 'predicates.ema.json', np.stack([elo, ehi], axis=2).tolist())
    gt = np.full((len(queries), k), -1, dtype=np.int64)
    gd = np.full((len(queries), k), np.inf, dtype=np.float64)
    counts = []
    for qi, q in enumerate(queries):
        raw_mask = np.all((attrs >= low[qi]) & (attrs <= high[qi]), axis=1)
        enc_mask = np.all((encoded >= elo[qi]) & (encoded <= ehi[qi]), axis=1)
        if not np.array_equal(raw_mask, enc_mask):
            raise AssertionError(f'Predicate mismatch q{qi}')
        valid = np.flatnonzero(raw_mask)
        counts.append(len(valid))
        best_ids = np.empty(0, dtype=np.int64)
        best_dist = np.empty(0, dtype=np.float64)
        for start in range(0, len(valid), 16384):
            block_ids = valid[start:start + 16384]
            delta = np.asarray(base[block_ids], dtype=np.float64) - q.astype(np.float64)
            distances = np.einsum('ij,ij->i', delta, delta)
            best_ids = np.concatenate([best_ids, block_ids])
            best_dist = np.concatenate([best_dist, distances])
            order = np.lexsort((best_ids, best_dist))[:k]
            best_ids, best_dist = best_ids[order], best_dist[order]
        gt[qi, :len(best_ids)], gd[qi, :len(best_ids)] = best_ids, best_dist
        if qi % 100 == 0:
            print(f'exact q={qi}/{len(queries)} valid={len(valid)}', flush=True)
    np.save(out / 'gt.npy', gt)
    np.save(out / 'gt_distances.npy', gd)
    np.save(out / 'valid_counts.npy', np.asarray(counts))
    # A single metadata contract is consumed by both runners and the evaluator.
    write_json(out / 'manifest.json', dict(n=n, dim=d, m=attrs.shape[1], k=k,
        queries=len(queries), query_ids=list(map(int, ids)), profiles=profiles,
        sources=sources, attribute_semantics='float32 closed intervals',
        ema_encoding='dense ordinal per distinct float32 value; ties preserved',
        ground_truth='filtered exact float64 squared L2, tie order original ID',
        predicate_equivalence_checked=len(queries),
        input_vector_sha256=hashlib.sha256(np.ascontiguousarray(queries).tobytes()).hexdigest()))
    print(f'Prepared {out}', flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--base')
    p.add_argument('--query')
    p.add_argument('--attrs')
    p.add_argument('--filters')
    p.add_argument('--attr-count', type=int, default=3)
    p.add_argument('--query-count', type=int)
    p.add_argument('--topk', type=int, default=10)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--high-cardinality', action='store_true')
    a = p.parse_args()
    if a.smoke:
        rng = np.random.default_rng(2037)
        base = rng.normal(size=(4096, 16)).astype(np.float32)
        queries = rng.normal(size=(20, 16)).astype(np.float32)
        attrs = rng.integers(0, 16, size=(4096, 3)).astype(np.float32)
        low = rng.integers(0, 6, size=(20, 3)).astype(np.float32)
        high = low + 9
        low[0], high[0] = 0, 15
        low[1], high[1] = 16, 17  # Empty predicate, no false positive allowed.
        low[2], high[2] = attrs[0], attrs[0]  # Equality / duplicate values.
        low[3], high[3] = -np.inf, np.inf
        if a.high_cardinality:
            attrs = np.column_stack([rng.permutation(4096) for _ in range(3)]).astype(np.float32)
            low = rng.integers(0, 2048, size=(20, 3)).astype(np.float32)
            high = low + 2048
            low[0], high[0] = 0, 4095
            low[1], high[1] = 4096, 4097
            low[2], high[2] = 0, 4095
            low[2, 0] = 4095  # Maximum-value equality must remain reachable.
            low[3], high[3] = -np.inf, np.inf
        raw = Path(a.output).with_name(Path(a.output).name + '_base.fbin')
        raw.parent.mkdir(parents=True, exist_ok=True)
        with raw.open('xb') as f:
            f.write(struct.pack('<II', *base.shape))
            base.tofile(f)
        sources = dict(base=str(raw.resolve()), smoke_seed=2037, high_cardinality=a.high_cardinality)
        ids, profiles = range(20), ['smoke'] * 20
    else:
        if not all([a.base, a.query, a.attrs, a.filters]):
            p.error('--base --query --attrs --filters are required')
        base, all_queries = fbin(a.base), fbin(a.query)
        attrs = np.empty((len(base), a.attr_count), dtype=np.float32)
        seen = np.zeros(len(base), dtype=bool)
        with open(a.attrs, newline='') as f:
            for row in csv.reader(f):
                if len(row) != a.attr_count + 1:
                    raise ValueError('Expected headerless original_id,attr0,... CSV')
                ident = int(row[0])
                if ident < 0 or ident >= len(base) or seen[ident]:
                    raise ValueError(f'Duplicate/out-of-range original ID {ident}')
                seen[ident] = True
                attrs[ident] = row[1:]
        if not seen.all():
            raise ValueError('Missing attribute rows')
        with open(a.filters, newline='') as f:
            rows = list(csv.DictReader(f))
        if a.query_count is not None:
            if a.query_count <= 0 or a.query_count > len(rows):
                raise ValueError('Invalid query-count')
            rows = rows[:a.query_count]
        ids = [int(r['query_idx']) for r in rows]
        if not ids or min(ids) < 0 or max(ids) >= len(all_queries):
            raise ValueError('Invalid query IDs')
        queries = np.asarray(all_queries[ids])
        low = np.array([[r[f'attr{j}_low'] for j in range(a.attr_count)] for r in rows], dtype=np.float32)
        high = np.array([[r[f'attr{j}_high'] for j in range(a.attr_count)] for r in rows], dtype=np.float32)
        profiles = [r.get('profile', 'all') for r in rows]
        sources = {name: str(Path(getattr(a, name)).resolve()) for name in ['base', 'query', 'attrs', 'filters']}
    prepare(base, queries, attrs, low, high, ids, profiles, a.output, a.topk, sources)


if __name__ == '__main__':
    main()

"""Evaluate saved IDs after timing, against one shared exact reference."""
import argparse
import json
from pathlib import Path

import numpy as np

from prepare_external import fbin, write_json
from audit_ema_plateau import tie_credit


def evaluate(data, results, audit_distances=False):
    root = Path(data)
    meta = json.loads((root / 'manifest.json').read_text())
    gt, gt_dist = np.load(root / 'gt.npy'), np.load(root / 'gt_distances.npy')
    counts = np.load(root / 'valid_counts.npy')
    with np.load(root / 'data.npz') as source:
        attrs = source['attributes']
    with np.load(root / 'queries.npz') as source:
        low, high, queries = source['predlow'], source['predhigh'], source['vector']
    base = fbin(meta['sources']['base'])
    rows = [json.loads(line) for line in Path(results).read_text().splitlines()]
    if [r['q'] for r in rows] != list(range(len(gt))):
        raise ValueError('Missing, repeated, or misordered query results')
    recalls, tied_recalls, latencies = [], [], []
    exact_boundary, tolerant_boundary = [], []
    illegal = duplicates = distance_errors = insufficient = empty_errors = 0
    for qi, row in enumerate(rows):
        ids = np.asarray(row['ids'], dtype=np.int64)
        if len(ids) > meta['k']:
            raise ValueError('More than k results')
        duplicates += len(ids) - len(set(ids.tolist()))
        mask = (ids >= 0) & (ids < meta['n'])
        illegal += int((~mask).sum())
        valid_ids = ids[mask]
        legal = np.all((attrs[valid_ids] >= low[qi]) & (attrs[valid_ids] <= high[qi]), axis=1)
        illegal += int((~legal).sum())
        valid_ids = np.unique(valid_ids[legal])
        target = min(meta['k'], int(counts[qi]))
        insufficient += len(valid_ids) < target
        empty_errors += target == 0 and len(ids) > 0
        expected = set(gt[qi, :target].tolist())
        recalls.append(len(expected.intersection(valid_ids.tolist())) / target if target else float(len(ids) == 0))
        delta = np.asarray(base[valid_ids], dtype=np.float64) - queries[qi].astype(np.float64)
        actual = np.einsum('ij,ij->i', delta, delta)
        radius = gt_dist[qi, target - 1] if target else 0.0
        exact_boundary.append(tie_credit(gt_dist[qi, :target], actual, 0.0))
        tolerant_boundary.append(tie_credit(gt_dist[qi, :target], actual,
            max(1e-9, abs(radius)*1e-7)))
        tied_recalls.append(min(target, int(np.sum(actual <= radius + max(1e-9, abs(radius)*1e-7)))) / target
                            if target else float(len(ids) == 0))
        if audit_distances and len(ids) and mask.all():
            delta = np.asarray(base[ids], dtype=np.float64) - queries[qi].astype(np.float64)
            exact = np.einsum('ij,ij->i', delta, delta)
            if not np.allclose(exact, row['distances'], rtol=2e-5, atol=1e-5):
                distance_errors += 1
        latencies.append(row['ms'])
    latency = np.asarray(latencies)
    if not np.isfinite(latency).all() or np.any(latency < 0) or latency.sum() <= 0:
        raise ValueError('Invalid latency values')
    result = dict(queries=len(rows), recall=float(np.mean(recalls)),
        exact_boundary_tie_recall=float(np.mean(exact_boundary)),
        tolerant_boundary_tie_recall=float(np.mean(tolerant_boundary)),
        tie_aware_recall_definition='legacy radius-only; use boundary tie metrics for stricter credit',
        tie_aware_recall=float(np.mean(tied_recalls)), mean_ms=float(latency.mean()),
        p50_ms=float(np.percentile(latency, 50)), p95_ms=float(np.percentile(latency, 95)),
        qps=float(1000 * len(rows) / latency.sum()), illegal=illegal,
        duplicate_ids=duplicates, insufficient=int(insufficient),
        empty_queries=int(np.sum(counts == 0)), empty_errors=int(empty_errors),
        distance_errors=distance_errors,
        distance_evaluations=float(np.mean([r['dist'] for r in rows])) if all('dist' in r for r in rows) else None)
    if illegal or duplicates or distance_errors or empty_errors:
        raise ValueError(f'Correctness audit failed: {result}')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True)
    p.add_argument('--results', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--audit-distances', action='store_true')
    p.add_argument('--require-recall', type=float, default=0)
    a = p.parse_args()
    result = evaluate(a.data, a.results, a.audit_distances)
    write_json(a.output, result)
    print(json.dumps(result, indent=2))
    if result['recall'] < a.require_recall:
        raise SystemExit('Recall below requested smoke threshold')

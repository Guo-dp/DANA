"""Offline diagnostic only: strict ID recall versus boundary-tie credit."""
import argparse
import json
from pathlib import Path
import numpy as np
from prepare_external import fbin, write_json


def tie_credit(expected_dist, actual_dist, tol):
    k = len(expected_dist)
    if not k:
        return float(len(actual_dist) == 0)
    radius = expected_dist[-1]
    # Strictly nearer slots cannot be replaced with extra kth-distance ties.
    strict_slots = int(np.sum(expected_dist < radius - tol))
    strict_hits = min(strict_slots, int(np.sum(actual_dist < radius - tol)))
    boundary_hits = int(np.sum(np.abs(actual_dist - radius) <= tol))
    return (strict_hits + min(k - strict_slots, boundary_hits)) / k


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True)
    p.add_argument('--results', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    assert tie_credit(np.array([1., 2., 3.]), np.array([2., 3., 3.]), 0) == 2/3
    root = Path(a.data)
    meta = json.loads((root/'manifest.json').read_text())
    base = fbin(meta['sources']['base'])
    query = np.load(root/'queries.npy')
    gt = np.load(root/'gt.npy')
    gd = np.load(root/'gt_distances.npy')
    valid = np.load(root/'valid_counts.npy')
    rows = [json.loads(x) for x in Path(a.results).read_text().splitlines()]
    assert [r['q'] for r in rows] == list(range(len(gt)))
    scores = []
    examples = []
    identical_pairs = 0
    tied_recovery_queries = 0
    for q, r in enumerate(rows):
        k = min(meta['k'], int(valid[q]))
        ids = np.array(r['ids'], dtype=np.int64)
        assert len(set(ids.tolist())) == len(ids)
        assert np.all((ids >= 0) & (ids < len(base)))
        delta = base[ids].astype(np.float64) - query[q].astype(np.float64)
        d = np.einsum('ij,ij->i', delta, delta)
        strict = len(set(ids.tolist()) & set(gt[q,:k].tolist())) / k if k else float(len(ids)==0)
        exact_tie = tie_credit(gd[q,:k], d, 0.)
        tol = max(1e-9, abs(float(gd[q,k-1]))*1e-7) if k else 0.
        tolerant = tie_credit(gd[q,:k], d, tol)
        scores.append([strict, exact_tie, tolerant])
        tied_recovery_queries += exact_tie > strict + 1e-10
        missing = sorted(set(gt[q,:k].tolist()) - set(ids.tolist()))
        extra = sorted(set(ids.tolist()) - set(gt[q,:k].tolist()))
        pairs = [(x,y) for x in missing for y in extra if np.array_equal(base[x], base[y])]
        identical_pairs += len(pairs)
        if strict < 1 and len(examples) < 30:
            examples.append(dict(q=q, valid_count=int(valid[q]), strict=strict,
                exact_boundary_tie=exact_tie, tolerant_boundary_tie=tolerant,
                missing=missing, extra=extra, identical_vector_pairs=pairs))
    values=np.array(scores)
    result=dict(queries=len(rows), strict_id_recall=float(values[:,0].mean()),
        exact_boundary_tie_recall=float(values[:,1].mean()),
        tolerant_boundary_tie_recall=float(values[:,2].mean()),
        queries_improved_by_exact_ties=int(tied_recovery_queries),
        identical_vector_replacement_pairs=identical_pairs,
        imperfect_exact_tie_queries=int(np.sum(values[:,1] < 1-1e-10)),
        examples=examples)
    write_json(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k != 'examples'},indent=2))


if __name__ == '__main__':
    main()

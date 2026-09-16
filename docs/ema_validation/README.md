# Why The Baseline Is Labelled EMA-FTFix-V2

The formal comparison uses an explicitly labelled EMA variant with three isolated FT implementation changes:

| Patch | Purpose |
|---|---|
| `ema_closed_range.patch` | Include the closed upper bucket used by the shared numerical range predicate. |
| `ema_ft_initialization.patch` | Initialize the node FT after the level-0 memory region is cleared. |
| `ema_bucket_coverage.patch` | Ensure the last mapping bucket covers the largest stored attribute value. |

These changes do not alter the shared query vectors, predicates, exact ground truth, EMA search budget, FT enablement, or routing enablement. Indexes must be rebuilt after applying them.

The retained original EMA code was also tested on an EMA-native YouTube-8M subset and was operational at high recall. A separate original-versus-V2 boundary regression and full-factorial patch ablation showed that the shared closed-range workload remained sensitive to FT construction and boundary semantics. Consequently:

- the formal baseline is called `EMA-FTFix-V2`, not EMA-original;
- the patches are not presented as author-confirmed upstream fixes;
- original-code diagnostics do not define EMA's general performance ceiling;
- the paper compares static query performance only, not dynamic maintenance.

Detailed diagnostic query logs are not part of the main repository path. The three patch files, their application script, formal result summaries, and audit metadata provide the evidence needed to understand the reported baseline version.

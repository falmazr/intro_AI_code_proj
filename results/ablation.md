Ablation at 128x128 (generated maps). Cost ratio relative to flat A* on the same query.

| Variant | Weight model | Leg goal | Post-process | Nodes (mean) | Cost ratio mean | p95 | max | Runtime ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flat A* | - | - | - | 1254 | 1.000 | 1.000 | 1.000 | 2.87 |
| Weighted A* (1.5) | - | - | - | 686 | 1.010 | 1.052 | 1.107 | 1.59 |
| Two-tier W0 (hops) | W0 hops | first cell | none | 227 | 1.033 | 1.217 | 1.526 | 0.67 |
| Two-tier W1 (centroids) | W1 centroid | first cell | none | 166 | 1.012 | 1.075 | 1.310 | 1.07 |
| Two-tier W1, nearest-entry legs | W1 centroid | nearest entry | none | 166 | 1.012 | 1.075 | 1.310 | 0.84 |
| Two-tier W1 + corridor refine | W1 centroid | first cell | corridor refine r=2 | 430 | 1.012 | 1.075 | 1.310 | 2.23 |
| Two-tier W2 (HPA*, rooms) | W2 portal dist. | chosen portal | none | 664 | 1.000 | 1.000 | 1.000 | 1.22 |
| HPA*, 16x16 blocks | W2 on 16x16 blocks | chosen portal | none | 680 | 1.000 | 1.000 | 1.000 | 4.06 |

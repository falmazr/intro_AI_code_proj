Ablation at 128x128 (generated maps). Cost ratio relative to flat A* on the same query.

| Variant | Weight model | Leg goal | Post-process | Nodes (mean) | Cost ratio mean | p95 | max | Runtime ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flat A* | - | - | - | 2172 | 1.000 | 1.000 | 1.000 | 9.88 |
| Weighted A* (1.5) | - | - | - | 865 | 1.014 | 1.055 | 1.152 | 3.78 |
| Two-tier W1 (centroids) | W1 centroid | first cell | none | 192 | 1.023 | 1.093 | 1.263 | 1.51 |
| Two-tier W2 (HPA*, rooms) | W2 portal dist. | chosen portal | none | 714 | 1.000 | 1.000 | 1.005 | 3.43 |

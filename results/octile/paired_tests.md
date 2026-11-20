Paired comparison with flat A* on identical queries (generated maps).

| Size | Variant | n | Geometric mean nodes ratio (variant / A*) | 95% CI | Queries with fewer nodes | Sign-test p |
| --- | --- | --- | --- | --- | --- | --- |
| 32 | Weighted A* (1.5) | 150 | 0.683 | [0.650, 0.718] | 135/150 | 2.6e-25 |
| 32 | Two-tier W1 (centroids) | 150 | 0.339 | [0.311, 0.370] | 141/150 | 1.2e-31 |
| 32 | Two-tier W2 (HPA*, rooms) | 150 | 1.059 | [0.958, 1.170] | 72/150 | 0.68 |
| 64 | Weighted A* (1.5) | 150 | 0.524 | [0.485, 0.567] | 146/150 | 2.9e-38 |
| 64 | Two-tier W1 (centroids) | 150 | 0.208 | [0.190, 0.227] | 148/150 | 1.6e-41 |
| 64 | Two-tier W2 (HPA*, rooms) | 150 | 0.732 | [0.658, 0.814] | 105/150 | 1.1e-06 |
| 128 | Weighted A* (1.5) | 150 | 0.381 | [0.354, 0.412] | 149/150 | 2.1e-43 |
| 128 | Two-tier W1 (centroids) | 150 | 0.111 | [0.101, 0.123] | 149/150 | 2.1e-43 |
| 128 | Two-tier W2 (HPA*, rooms) | 150 | 0.403 | [0.361, 0.451] | 133/150 | 1.7e-23 |
| 256 | Weighted A* (1.5) | 150 | 0.251 | [0.226, 0.278] | 147/150 | 7.9e-40 |
| 256 | Two-tier W1 (centroids) | 150 | 0.058 | [0.051, 0.066] | 149/150 | 2.1e-43 |
| 256 | Two-tier W2 (HPA*, rooms) | 150 | 0.212 | [0.186, 0.241] | 141/150 | 1.2e-31 |

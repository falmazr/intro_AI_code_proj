| Variant | First size where runtime < flat A* | First size where nodes < flat A* | Nodes saved at largest size |
| --- | --- | --- | --- |
| Two-tier W0 (hops) | 32 | 32 | 18.2x at 512 |
| Two-tier W1 (centroids) | 32 | 16 | 27.0x at 512 |
| Two-tier W1, nearest-entry legs | 32 | 16 | 27.0x at 512 |
| Two-tier W1 + corridor refine | 128 | 32 | 10.6x at 512 |
| Two-tier W2 (HPA*, rooms) | 64 | 64 | 7.0x at 512 |
| HPA*, 16x16 blocks | never | 128 | 4.0x at 512 |

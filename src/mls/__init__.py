"""mls - Multi-Layered Search for grid-world path planning (CSCI218 Topic 4).

Modules owned by Member 1 (world & partition):
    grid       - Grid: the cell-level world, loading/saving, neighbours.
    partition  - area labelling, connected-component split, AreaGraph.
    generator  - seeded procedural maps and the uniform-block partitioner.
"""

from .grid import Cell, Grid
from .partition import AreaGraph, Portal, build_area_graph, split_disconnected_areas

__all__ = [
    "Cell",
    "Grid",
    "AreaGraph",
    "Portal",
    "build_area_graph",
    "split_disconnected_areas",
]

"""Heuristic functions for grid search.

All of them are admissible for the stated connectivity and, except
``min_to_set`` over a changing set, consistent. See the design doc, section 3.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .grid import Cell

SQRT2_MINUS_1 = 2 ** 0.5 - 1


def zero(_: Cell) -> float:
    """h = 0: turns A* into Dijkstra / uniform-cost search."""
    return 0.0


def manhattan(goal: Cell) -> Callable[[Cell], float]:
    """|dx| + |dy|. Admissible and consistent for 4-connected unit-cost grids."""
    gx, gy = goal

    def h(c: Cell) -> float:
        return abs(c[0] - gx) + abs(c[1] - gy)

    return h


def octile(goal: Cell) -> Callable[[Cell], float]:
    """max(dx, dy) + (sqrt2 - 1) * min(dx, dy). Admissible and consistent for 8-connected grids."""
    gx, gy = goal

    def h(c: Cell) -> float:
        dx, dy = abs(c[0] - gx), abs(c[1] - gy)
        return max(dx, dy) + SQRT2_MINUS_1 * min(dx, dy)

    return h


def euclidean(goal: Cell) -> Callable[[Cell], float]:
    """Straight-line distance. Admissible for both connectivities but dominated by the two above."""
    gx, gy = goal

    def h(c: Cell) -> float:
        return ((c[0] - gx) ** 2 + (c[1] - gy) ** 2) ** 0.5

    return h


def for_connectivity(goal: Cell, connectivity: int) -> Callable[[Cell], float]:
    """The strongest admissible single-goal heuristic for the grid's connectivity."""
    return manhattan(goal) if connectivity == 4 else octile(goal)


def min_to_set(targets: Iterable[Cell], connectivity: int = 4) -> Callable[[Cell], float]:
    """Minimum distance to any cell in ``targets``: the multi-goal heuristic of a refinement leg.

    Admissible because the leg ends at *some* target, and the distance to the
    nearest one is a lower bound. Consistent because each per-target
    heuristic is, and a minimum of consistent heuristics is consistent.
    """
    ts = list(targets)
    if not ts:
        return zero
    hs = [for_connectivity(t, connectivity) for t in ts]

    def h(c: Cell) -> float:
        return min(hf(c) for hf in hs)

    return h

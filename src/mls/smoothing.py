"""Post-processing that recovers some of the two-tier planner's lost optimality cheaply.

On a 4-connected grid the classic "string pulling" (replace a path segment
by a straight line when there is line of sight) does not apply, because a
straight line is not a legal 4-connected path. The equivalent cheap fix is
*corridor refinement*: run A* again, but only inside a corridor of cells
within ``radius`` of the hierarchical path. The corridor is tiny compared
with the map, so the extra expansions are small, and the result removes the
local detours that greedy entry-cell choices introduce. The path is never
made worse (the original path is inside the corridor).

Expansions of the refinement are reported so the experiments can show the
cost of the improvement.
"""

from __future__ import annotations

from .grid import Cell, Grid
from .heuristics import for_connectivity
from .search import SearchResult, astar


def corridor_refine(grid: Grid, path: list[Cell], radius: int = 2) -> SearchResult[Cell]:
    """Re-plan ``path`` inside a corridor of width ``2*radius+1`` around it."""
    if len(path) < 2:
        return SearchResult(list(path), 0.0, 0, 0, 0)
    corridor: set[Cell] = set()
    for x, y in path:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                c = (x + dx, y + dy)
                if grid.is_free(c):
                    corridor.add(c)
    start, goal = path[0], path[-1]
    r = astar(start, lambda c: c == goal,
              lambda c: [n for n in grid.neighbours(c) if n in corridor],
              for_connectivity(goal, grid.connectivity), Grid.step_cost)
    assert r.success  # the original path lies inside the corridor
    return r


def smoothed(result: SearchResult[Cell], grid: Grid, radius: int = 2) -> SearchResult[Cell]:
    """Apply corridor refinement to a planner result, adding its expansions to the totals."""
    if not result.success:
        return result
    assert result.path is not None
    r = corridor_refine(grid, result.path, radius)
    assert r.path is not None
    return SearchResult(
        path=r.path,
        cost=r.cost,
        expanded=result.expanded + r.expanded,
        generated=result.generated + r.generated,
        peak_open=max(result.peak_open, r.peak_open),
        extra={**result.extra, "smoothing_expanded": r.expanded, "cost_before_smoothing": result.cost},
    )

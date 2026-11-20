"""Single-level planners over the cell graph: the baselines.

* ``FlatAStar``   - A* with Manhattan (4-conn) or octile (8-conn): complete, optimal.
* ``Dijkstra``    - A* with h = 0 (uniform-cost search): optimal, uninformed.
* ``BFS``         - breadth-first search: optimal for unit costs, uninformed.
* ``WeightedAStar`` - f = g + eps*h: the standard non-hierarchical way to trade
  optimality for speed; cost is at most eps times optimal.
"""

from __future__ import annotations

from ..grid import Cell, Grid
from ..heuristics import for_connectivity, zero
from ..search import SearchResult, astar, bfs
from .base import Planner, register


@register
class FlatAStar(Planner):
    name = "astar"

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None, "call prepare(grid) first"
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        return astar(start, lambda c: c == goal, grid.neighbours,
                     for_connectivity(goal, grid.connectivity), Grid.step_cost)


@register
class WeightedAStar(Planner):
    name = "wastar"

    def __init__(self, epsilon: float = 1.5) -> None:
        super().__init__()
        self.epsilon = epsilon
        self.name = f"wastar{epsilon:g}"

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        return astar(start, lambda c: c == goal, grid.neighbours,
                     for_connectivity(goal, grid.connectivity), Grid.step_cost, weight=self.epsilon)


@register
class Dijkstra(Planner):
    name = "dijkstra"

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        return astar(start, lambda c: c == goal, grid.neighbours, zero, Grid.step_cost)


@register
class BFS(Planner):
    name = "bfs"

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        if grid.connectivity != 4:
            raise ValueError("BFS is only optimal for unit step costs (4-connectivity)")
        return bfs(start, lambda c: c == goal, grid.neighbours)

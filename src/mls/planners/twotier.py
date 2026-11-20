"""The two-tiered (hierarchical) planner: design doc section 4.

Tier 1 searches the area graph for an area sequence A_1 .. A_m.
Tier 2 runs one small A* per consecutive pair, confined to those two areas,
and a final leg inside A_m to the goal. The legs are concatenated.

Design knobs (each is an ablation in the report):

``weight_model``
    ``"W0"`` hop count, ``"W1"`` centroid distance (default), ``"W2"``
    portal distances (HPA*-style, implemented in :mod:`mls.planners.hpa`;
    selecting it here delegates to that planner).

``leg_goal``
    ``"first"``  (default) multi-goal leg: stop at the first cell of the
    next area that A* reaches, heuristic = min distance to its entry cells.
    ``"nearest"`` the brief's literal suggestion: pick the entry cell of the
    next area nearest (Manhattan) to the current position, then A* to it.

Both are greedy across legs, so the planner is complete but not optimal.
"""

from __future__ import annotations

from ..grid import Cell, Grid
from ..heuristics import for_connectivity, manhattan, min_to_set
from ..partition import AreaGraph, build_area_graph
from ..search import SearchResult, astar
from .base import Planner, register


@register
class TwoTierPlanner(Planner):
    name = "twotier"

    def __init__(self, weight_model: str = "W1", leg_goal: str = "first", max_replans: int = 50) -> None:
        super().__init__()
        if weight_model not in ("W0", "W1"):
            raise ValueError("TwoTierPlanner supports W0 and W1; use HPAPlanner for W2")
        if leg_goal not in ("first", "nearest"):
            raise ValueError("leg_goal must be 'first' or 'nearest'")
        self.weight_model = weight_model
        self.leg_goal = leg_goal
        self.max_replans = max_replans
        self.name = f"twotier-{weight_model}-{leg_goal}"
        self.graph: AreaGraph | None = None

    # ------------------------------------------------------------ prepare

    def prepare(self, grid: Grid, enforce_connected: bool = True) -> None:
        super().prepare(grid)
        self.graph = build_area_graph(grid, enforce_connected=enforce_connected)

    # ------------------------------------------------------------- tier 1

    def abstract_plan(self, start_area: int, goal_area: int, goal: Cell,
                      banned: set[tuple[int, int]]) -> SearchResult[int]:
        """A* over areas. Heuristic: Manhattan from the area's closest cell to the goal."""
        g = self.graph
        assert g is not None
        cache: dict[int, float] = {}

        def h(area: int) -> float:
            if area not in cache:
                cache[area] = manhattan(goal)(g.closest_cell_to(area, goal))
            return cache[area]

        def nbrs(area: int):
            return [b for b in g.neighbours(area) if (area, b) not in banned]

        def cost(a: int, b: int) -> float:
            return g.weight(a, b, self.weight_model)

        return astar(start_area, lambda a: a == goal_area, nbrs,
                     h if self.weight_model != "W0" else (lambda a: 0.0), cost)

    # ------------------------------------------------------------- tier 2

    def _confined_neighbours(self, allowed: set[int]):
        grid = self.grid
        assert grid is not None

        def nbrs(c: Cell):
            return [n for n in grid.neighbours(c) if grid.area_of(n) in allowed]

        return nbrs

    def leg(self, p: Cell, from_area: int, to_area: int) -> SearchResult[Cell]:
        """One refinement leg from ``p`` (in ``from_area``) into ``to_area``."""
        grid, g = self.grid, self.graph
        assert grid is not None and g is not None
        allowed = {from_area, to_area}
        entries = g.entry_cells(from_area, to_area)
        if not entries:
            return SearchResult.failure()
        if self.leg_goal == "nearest":
            target = min(entries, key=lambda e: (abs(e[0] - p[0]) + abs(e[1] - p[1]), e))
            return astar(p, lambda c: c == target, self._confined_neighbours(allowed),
                         for_connectivity(target, grid.connectivity), Grid.step_cost)
        return astar(p, lambda c: grid.area_of(c) == to_area, self._confined_neighbours(allowed),
                     min_to_set(entries, grid.connectivity), Grid.step_cost)

    def final_leg(self, p: Cell, goal: Cell, area: int) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None
        return astar(p, lambda c: c == goal, self._confined_neighbours({area}),
                     for_connectivity(goal, grid.connectivity), Grid.step_cost)

    # --------------------------------------------------------------- plan

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid, g = self.grid, self.graph
        assert grid is not None and g is not None, "call prepare(grid) first"
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        sa, ga = grid.area_of(start), grid.area_of(goal)
        if sa == ga:
            r = self.final_leg(start, goal, sa)
            if not r.success:
                # Only possible when A1 is violated (the area is not connected):
                # last-resort flat A*, so the planner stays complete.
                return self._flat_fallback(start, goal, r)
            r.extra = {"areas": [sa], "legs": 1, "abstract_expanded": 0, "replans": 0}
            return r

        banned: set[tuple[int, int]] = set()
        total_expanded = total_generated = 0
        peak = 0
        for replan in range(self.max_replans + 1):
            abstract = self.abstract_plan(sa, ga, goal, banned)
            total_expanded += abstract.expanded
            total_generated += abstract.generated
            peak = max(peak, abstract.peak_open)
            if not abstract.success:
                # Every abstract route was banned by a failed leg (A1 violated): last resort.
                return self._flat_fallback(start, goal,
                                           SearchResult.failure(total_expanded, total_generated, peak))
            seq = abstract.path
            assert seq is not None

            path = [start]
            cost = 0.0
            p = start
            leg_expanded: list[int] = []
            ok = True
            for t in range(1, len(seq)):
                r = self.leg(p, seq[t - 1], seq[t])
                total_expanded += r.expanded
                total_generated += r.generated
                peak = max(peak, r.peak_open)
                leg_expanded.append(r.expanded)
                if not r.success:
                    banned.add((seq[t - 1], seq[t]))
                    banned.add((seq[t], seq[t - 1]))
                    ok = False
                    break
                assert r.path is not None
                path += r.path[1:]
                cost += r.cost
                p = r.path[-1]
            if not ok:
                continue
            last = self.final_leg(p, goal, ga)
            total_expanded += last.expanded
            total_generated += last.generated
            peak = max(peak, last.peak_open)
            leg_expanded.append(last.expanded)
            if not last.success:
                # Only possible when A1 is violated: the leg entered a piece of the goal
                # area that is cut off from the goal. Fall back so the planner stays complete.
                return self._flat_fallback(start, goal,
                                           SearchResult.failure(total_expanded, total_generated, peak))
            assert last.path is not None
            path += last.path[1:]
            cost += last.cost
            return SearchResult(path, cost, total_expanded, total_generated, peak, extra={
                "areas": seq,
                "legs": len(seq),
                "abstract_expanded": abstract.expanded,
                "leg_expanded": leg_expanded,
                "replans": replan,
            })
        return self._flat_fallback(start, goal,
                                   SearchResult.failure(total_expanded, total_generated, peak))

    def _flat_fallback(self, start: Cell, goal: Cell, spent: SearchResult) -> SearchResult[Cell]:
        """Unconfined A* over the whole grid, charged with the work already spent.

        Reached only when the partition violates A1 (an area is not connected).
        ``extra['fallback']`` is set so experiments can count how often it fired.
        """
        grid = self.grid
        assert grid is not None
        r = astar(start, lambda c: c == goal, grid.neighbours,
                  for_connectivity(goal, grid.connectivity), Grid.step_cost)
        r.expanded += spent.expanded
        r.generated += spent.generated
        r.peak_open = max(r.peak_open, spent.peak_open)
        r.extra = {"areas": [], "legs": 0, "abstract_expanded": spent.expanded,
                   "replans": self.max_replans, "fallback": True}
        return r

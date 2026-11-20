"""HPA*-style two-tier planner: weight model W2 (precomputed portal distances).

Botea, Muller & Schaeffer (2004), "Near Optimal Hierarchical Path-Finding",
adapted from fixed square clusters to our semantic areas.

Preprocessing (once per map)
----------------------------
* The *portal cells* of an area are its cells that touch another area.
* For every portal cell, a search confined to its area records the exact
  in-area shortest distance to every other portal cell of that area.

Per query
---------
* The start and goal are inserted as temporary nodes: one confined search
  from each gives its distance to every portal cell of its area.
* Tier 1 is A* over portal cells (plus start and goal). Moving between two
  portal cells of the same area costs the precomputed in-area distance;
  stepping across a boundary costs one move.
* Tier 2 refines each in-area hop with a confined A* to the *specific*
  portal cell Tier 1 chose, so the only source of suboptimality left is
  that the path is forced through portal cells, never the choice of area or
  the greedy choice of entry cell.

Running this planner on ``generator.uniform_blocks(grid, B)`` gives the
original HPA* with B x B clusters, for the partition comparison.
"""

from __future__ import annotations

from collections import defaultdict, deque

from ..grid import Cell, Grid
from ..heuristics import for_connectivity, zero
from ..partition import AreaGraph, build_area_graph
from ..search import SearchResult, astar
from .base import Planner, register


@register
class HPAPlanner(Planner):
    name = "twotier-W2"

    def __init__(self) -> None:
        super().__init__()
        self.graph: AreaGraph | None = None
        self.portals_of: dict[int, list[Cell]] = {}
        self.intra: dict[Cell, dict[Cell, float]] = {}       # portal cell -> {portal cell: dist}
        self.cross: dict[Cell, list[Cell]] = defaultdict(list)  # portal cell -> adjacent cells in other areas
        self.preprocess_expanded = 0

    # ------------------------------------------------------------ prepare

    def prepare(self, grid: Grid, enforce_connected: bool = True) -> None:
        super().prepare(grid)
        g = build_area_graph(grid, enforce_connected=enforce_connected)
        self.graph = g
        self.portals_of = {}
        self.intra = {}
        self.cross = defaultdict(list)
        self.preprocess_expanded = 0
        for a in g.areas:
            ps: set[Cell] = set()
            for b in g.neighbours(a):
                for u, v in g.portals[(a, b)]:
                    ps.add(u)
                    self.cross[u].append(v)
            self.portals_of[a] = sorted(ps)
        for a, ps in self.portals_of.items():
            targets = set(ps)
            for p in ps:
                self.intra[p] = self._distances_within(p, a, targets)

    def _distances_within(self, source: Cell, area: int, targets: set[Cell]) -> dict[Cell, float]:
        """Exact in-area distances from ``source`` to every cell in ``targets`` (early stop)."""
        grid = self.grid
        assert grid is not None
        dist: dict[Cell, float] = {source: 0.0}
        found: dict[Cell, float] = {}
        if source in targets:
            found[source] = 0.0
        remaining = len(targets) - (1 if source in targets else 0)
        if grid.connectivity == 4:
            queue = deque([source])
            while queue and remaining > 0:
                c = queue.popleft()
                self.preprocess_expanded += 1
                for n in grid.neighbours(c):
                    if n in dist or grid.area_of(n) != area:
                        continue
                    dist[n] = dist[c] + 1
                    if n in targets:
                        found[n] = dist[n]
                        remaining -= 1
                    queue.append(n)
            return found
        # 8-connectivity: Dijkstra (non-uniform step costs)
        import heapq
        heap = [(0.0, source)]
        done: set[Cell] = set()
        while heap and remaining > 0:
            d, c = heapq.heappop(heap)
            if c in done:
                continue
            done.add(c)
            self.preprocess_expanded += 1
            for n in grid.neighbours(c):
                if grid.area_of(n) != area:
                    continue
                nd = d + Grid.step_cost(c, n)
                if nd < dist.get(n, float("inf")):
                    dist[n] = nd
                    heapq.heappush(heap, (nd, n))
                    if n in targets and n not in found:
                        found[n] = nd
                        remaining -= 1
        return found

    # --------------------------------------------------------------- plan

    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        grid, g = self.grid, self.graph
        assert grid is not None and g is not None, "call prepare(grid) first"
        if not (grid.is_free(start) and grid.is_free(goal)):
            return SearchResult.failure()
        sa, ga = grid.area_of(start), grid.area_of(goal)
        h = for_connectivity(goal, grid.connectivity)

        # Same area: one confined search (identical to TwoTierPlanner's final leg).
        if sa == ga:
            r = self._refine(start, goal, sa)
            r.extra = {"areas": [sa], "legs": 1, "abstract_expanded": 0, "replans": 0}
            return r

        # Insert start and goal: distances to the portal cells of their areas.
        before = self.preprocess_expanded
        from_start = self._distances_within(start, sa, set(self.portals_of[sa]))
        to_goal = self._distances_within(goal, ga, set(self.portals_of[ga]))
        insertion_expanded = self.preprocess_expanded - before
        self.preprocess_expanded = before  # insertion work is per-query, not preprocessing

        def nbrs(c: Cell):
            # Cross-boundary steps first (a start or goal that is itself a portal cell has them too).
            out: list[Cell] = list(self.cross.get(c, ()))
            if c == start:
                out += [q for q in from_start if q != start]
                return out
            out += [q for q in self.intra.get(c, {}) if q != c]
            if grid.area_of(c) == ga and c in to_goal:
                out.append(goal)
            return out

        def cost(a: Cell, b: Cell) -> float:
            if grid.area_of(a) != grid.area_of(b):
                return Grid.step_cost(a, b)
            if a == start:
                return from_start[b]
            if b == goal:
                return to_goal[a]
            return self.intra[a][b]

        abstract = astar(start, lambda c: c == goal, nbrs, h, cost)
        abs_expanded = abstract.expanded + insertion_expanded
        if not abstract.success:
            return SearchResult.failure(abs_expanded, abstract.generated, abstract.peak_open)
        waypoints = abstract.path
        assert waypoints is not None

        # Tier 2: refine each in-area hop; cross-area hops are single steps.
        path = [start]
        total_cost = 0.0
        expanded, generated, peak = abs_expanded, abstract.generated, abstract.peak_open
        leg_expanded: list[int] = []
        areas = [sa]
        for i in range(1, len(waypoints)):
            a, b = waypoints[i - 1], waypoints[i]
            if grid.area_of(a) != grid.area_of(b):
                path.append(b)
                total_cost += Grid.step_cost(a, b)
                areas.append(grid.area_of(b))
                continue
            r = self._refine(a, b, grid.area_of(a))
            expanded += r.expanded
            generated += r.generated
            peak = max(peak, r.peak_open)
            leg_expanded.append(r.expanded)
            if not r.success:  # impossible if the precomputed distance exists
                return SearchResult.failure(expanded, generated, peak)
            assert r.path is not None
            path += r.path[1:]
            total_cost += r.cost
        return SearchResult(path, total_cost, expanded, generated, peak, extra={
            "areas": areas,
            "legs": len(areas),
            "abstract_expanded": abs_expanded,
            "leg_expanded": leg_expanded,
            "replans": 0,
        })

    def _refine(self, a: Cell, b: Cell, area: int) -> SearchResult[Cell]:
        grid = self.grid
        assert grid is not None
        if a == b:
            return SearchResult([a], 0.0, 0, 0, 0)
        return astar(a, lambda c: c == b,
                     lambda c: [n for n in grid.neighbours(c) if grid.area_of(n) == area],
                     for_connectivity(b, grid.connectivity), Grid.step_cost)

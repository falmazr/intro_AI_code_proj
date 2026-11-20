"""Generic best-first search routines shared by every planner.

One ``astar`` routine serves the flat baseline, the abstract (area-level)
search and every refinement leg, so "nodes expanded" means exactly the same
thing wherever it is reported: the number of nodes popped from the open list
and expanded (stale duplicates skipped). This is what makes the comparison
between planners honest.

``astar`` is generic over the node type: cells for grid searches, area ids
or portal cells for abstract searches.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Generic, Hashable, Iterable, TypeVar

N = TypeVar("N", bound=Hashable)


@dataclass
class SearchResult(Generic[N]):
    """Outcome of one search (or one planner call, when several searches are summed).

    Attributes
    ----------
    path:
        Sequence of nodes from start to goal inclusive, or ``None`` on failure.
    cost:
        Sum of step costs along ``path`` (``inf`` on failure).
    expanded:
        Nodes popped and expanded.
    generated:
        Successor nodes pushed onto the open list.
    peak_open:
        Largest size the open list reached (memory proxy).
    extra:
        Planner-specific details (e.g. the area sequence, per-leg counts).
    """

    path: list[N] | None
    cost: float
    expanded: int
    generated: int
    peak_open: int
    extra: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.path is not None

    @property
    def length(self) -> int:
        """Number of moves (path length minus one), 0 on failure."""
        return len(self.path) - 1 if self.path else 0

    @staticmethod
    def failure(expanded: int = 0, generated: int = 0, peak_open: int = 0) -> "SearchResult":
        return SearchResult(None, float("inf"), expanded, generated, peak_open)

    def merged_with(self, other: "SearchResult") -> "SearchResult":
        """Concatenate two successful results (``other`` starts where ``self`` ends)."""
        assert self.path and other.path and self.path[-1] == other.path[0]
        return SearchResult(
            path=self.path + other.path[1:],
            cost=self.cost + other.cost,
            expanded=self.expanded + other.expanded,
            generated=self.generated + other.generated,
            peak_open=max(self.peak_open, other.peak_open),
            extra={**self.extra, **other.extra},
        )


def _reconstruct(parent: dict, node) -> list:
    path = [node]
    while node in parent:
        node = parent[node]
        path.append(node)
    path.reverse()
    return path


def astar(
    start: N,
    is_goal: Callable[[N], bool],
    neighbours: Callable[[N], Iterable[N]],
    heuristic: Callable[[N], float],
    cost: Callable[[N, N], float] = lambda a, b: 1.0,
    weight: float = 1.0,
) -> SearchResult[N]:
    """A* with a binary-heap open list and a closed set.

    * ``f(n) = g(n) + weight * h(n)``; ``weight = 1`` is plain A*, ``> 1`` is
      Weighted A* (bounded suboptimal), ``heuristic = zero`` gives Dijkstra /
      uniform-cost search.
    * Ties on ``f`` are broken toward smaller ``h`` (closer to the goal), then
      by insertion order, so results are deterministic.
    * Lazy deletion: a popped entry whose ``g`` is stale is skipped, not
      counted as an expansion.
    * Closed nodes are never reopened. That keeps A* optimal when the
      heuristic is consistent (every heuristic in ``heuristics.py`` is), and
      keeps Weighted A* within its ``weight`` bound. An inconsistent
      heuristic would need reopening to stay optimal; none is used here.
    """
    g: dict[N, float] = {start: 0.0}
    parent: dict[N, N] = {}
    closed: set[N] = set()
    counter = 0
    h0 = heuristic(start)
    open_heap: list[tuple[float, float, int, N]] = [(weight * h0, h0, counter, start)]
    expanded = generated = 0
    peak_open = 1

    while open_heap:
        f, h, _, node = heapq.heappop(open_heap)
        if node in closed:
            continue
        if g[node] + weight * h < f - 1e-9:  # stale entry (a cheaper one was pushed later)
            continue
        if is_goal(node):
            return SearchResult(_reconstruct(parent, node), g[node], expanded, generated, peak_open)
        closed.add(node)
        expanded += 1
        gn = g[node]
        for nxt in neighbours(node):
            if nxt in closed:
                continue
            tentative = gn + cost(node, nxt)
            if tentative < g.get(nxt, float("inf")):
                g[nxt] = tentative
                parent[nxt] = node
                hn = heuristic(nxt)
                counter += 1
                heapq.heappush(open_heap, (tentative + weight * hn, hn, counter, nxt))
                generated += 1
                if len(open_heap) > peak_open:
                    peak_open = len(open_heap)
    return SearchResult.failure(expanded, generated, peak_open)


def bfs(
    start: N,
    is_goal: Callable[[N], bool],
    neighbours: Callable[[N], Iterable[N]],
) -> SearchResult[N]:
    """Breadth-first search: optimal for unit step costs, uninformed.

    Included as the lecture's baseline uninformed strategy. The goal test is
    applied when a node is generated (as in the lecture's graph-search BFS),
    which is correct for unit costs; expansions count dequeued nodes.
    """
    if is_goal(start):
        return SearchResult([start], 0.0, 0, 0, 1)
    parent: dict[N, N] = {}
    seen = {start}
    queue = deque([start])
    expanded = generated = 0
    peak_open = 1
    while queue:
        node = queue.popleft()
        expanded += 1
        for nxt in neighbours(node):
            if nxt in seen:
                continue
            seen.add(nxt)
            parent[nxt] = node
            generated += 1
            if is_goal(nxt):
                path = _reconstruct(parent, nxt)
                return SearchResult(path, float(len(path) - 1), expanded, generated, peak_open)
            queue.append(nxt)
            peak_open = max(peak_open, len(queue))
    return SearchResult.failure(expanded, generated, peak_open)

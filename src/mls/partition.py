"""Areas, portals and the area graph (the abstract search space).

Pipeline
--------
1. :func:`label_areas` turns the raw characters of a :class:`~mls.grid.Grid`
   into integer area ids (``grid.area_ids``).
2. :func:`split_disconnected_areas` enforces assumption A1 of the design:
   every area is 4-connected. An area that is not is split into its
   connected components, each getting a fresh id.
3. :func:`build_area_graph` scans every free cell once and records, for each
   pair of adjacent areas, the *portals* (adjacent cell pairs on their
   boundary). From the portals it derives the edges of the area graph.

The resulting :class:`AreaGraph` is what Tier 1 searches over. It exposes
three edge-weight models named in the design doc:

* ``W0`` hop count: every edge costs 1.
* ``W1`` centroid distance: Manhattan distance between the two areas' centroids.
* ``W2`` portal distance is *not* built here; it needs in-area shortest paths
  and lives with the HPA* variant (``planners/hpa.py``).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable

from .grid import BLOCKED, OFFSETS_4, Cell, Grid

Portal = tuple[Cell, Cell]
"""A pair ``(u, v)`` of adjacent free cells with ``u`` in one area and ``v`` in another."""


# --------------------------------------------------------------- labelling

def label_areas(grid: Grid) -> dict[int, str]:
    """Assign integer ids to the raw area characters, in first-seen order.

    Fills ``grid.area_ids`` in place and returns ``{id: raw_label}``.
    Ids are dense from 0 so they can index lists.
    """
    ids: dict[str, int] = {}
    names: dict[int, str] = {}
    for y in range(grid.height):
        for x in range(grid.width):
            ch = grid.labels[y][x]
            if ch == BLOCKED:
                grid.area_ids[y][x] = -1
                continue
            if ch not in ids:
                ids[ch] = len(ids)
                names[ids[ch]] = ch
            grid.area_ids[y][x] = ids[ch]
    return names


def connected_components(grid: Grid, cells: Iterable[Cell]) -> list[list[Cell]]:
    """Split ``cells`` into 4-connected components (BFS). Order is deterministic."""
    pending = set(cells)
    comps: list[list[Cell]] = []
    # Iterate in a fixed order so component numbering does not depend on set order.
    for seed in sorted(pending, key=lambda c: (c[1], c[0])):
        if seed not in pending:
            continue
        comp: list[Cell] = []
        queue = deque([seed])
        pending.discard(seed)
        while queue:
            c = queue.popleft()
            comp.append(c)
            x, y = c
            for dx, dy in OFFSETS_4:
                n = (x + dx, y + dy)
                if n in pending:
                    pending.discard(n)
                    queue.append(n)
        comps.append(comp)
    return comps


def split_disconnected_areas(grid: Grid) -> dict[int, int]:
    """Enforce A1: every area is 4-connected.

    Any area with more than one component keeps its id for the first
    component and gets fresh ids for the others. Returns ``{new_id: parent_id}``
    for every area created (empty means the map already satisfied A1).
    """
    by_area: dict[int, list[Cell]] = defaultdict(list)
    for c in grid.free_cells():
        by_area[grid.area_of(c)].append(c)
    next_id = max(by_area) + 1 if by_area else 0
    created: dict[int, int] = {}
    for aid in sorted(by_area):
        comps = connected_components(grid, by_area[aid])
        for comp in comps[1:]:
            for x, y in comp:
                grid.area_ids[y][x] = next_id
            created[next_id] = aid
            next_id += 1
    return created


# --------------------------------------------------------------- area graph

@dataclass
class AreaGraph:
    """Undirected graph whose nodes are areas and whose edges are shared boundaries.

    Attributes
    ----------
    cells:
        ``cells[a]`` = list of cells belonging to area ``a``.
    portals:
        ``portals[(a, b)]`` = list of ``(u, v)`` with ``u`` in ``a`` and ``v``
        in ``b`` adjacent. Stored for both orderings so lookups are symmetric.
    adjacency:
        ``adjacency[a]`` = sorted list of neighbouring area ids.
    centroid:
        ``centroid[a]`` = mean ``(x, y)`` of the area's cells.
    names:
        ``names[a]`` = the raw character the area came from (or ``"?"``
        for areas created by a split).
    """

    cells: dict[int, list[Cell]] = field(default_factory=dict)
    portals: dict[tuple[int, int], list[Portal]] = field(default_factory=dict)
    adjacency: dict[int, list[int]] = field(default_factory=dict)
    centroid: dict[int, tuple[float, float]] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)

    # -- structure

    @property
    def areas(self) -> list[int]:
        return sorted(self.cells)

    @property
    def edges(self) -> list[tuple[int, int]]:
        """Each undirected edge once, as ``(a, b)`` with ``a < b``."""
        return sorted(e for e in self.portals if e[0] < e[1])

    def neighbours(self, area: int) -> list[int]:
        return self.adjacency.get(area, [])

    def has_edge(self, a: int, b: int) -> bool:
        return (a, b) in self.portals

    def entry_cells(self, from_area: int, to_area: int) -> list[Cell]:
        """Cells of ``to_area`` that can be stepped into directly from ``from_area``.

        This is ``Entry(i, j)`` in the design doc, the goal set of a
        refinement leg and the target set of its heuristic.
        """
        return sorted({v for _, v in self.portals.get((from_area, to_area), [])})

    def exit_cells(self, from_area: int, to_area: int) -> list[Cell]:
        """Cells of ``from_area`` on the boundary with ``to_area``."""
        return sorted({u for u, _ in self.portals.get((from_area, to_area), [])})

    # -- geometry used by heuristics and weights

    def size(self, area: int) -> int:
        return len(self.cells[area])

    def closest_cell_to(self, area: int, target: Cell) -> Cell:
        """The cell of ``area`` with the smallest Manhattan distance to ``target``.

        Used by the abstract heuristic h_abs(i) = Manhattan(closest cell of i, g).
        """
        tx, ty = target
        return min(self.cells[area], key=lambda c: (abs(c[0] - tx) + abs(c[1] - ty), c))

    def weight(self, a: int, b: int, model: str = "W1") -> float:
        """Edge weight under model ``W0`` (hop count) or ``W1`` (centroid Manhattan distance)."""
        if not self.has_edge(a, b):
            raise KeyError(f"areas {a} and {b} are not adjacent")
        if model == "W0":
            return 1.0
        if model == "W1":
            (ax, ay), (bx, by) = self.centroid[a], self.centroid[b]
            return abs(ax - bx) + abs(ay - by)
        raise ValueError(f"unknown weight model {model!r}; W2 lives in planners/hpa.py")

    # -- debugging aids

    def describe(self) -> str:
        """Human-readable summary, used in tests and the demo."""
        lines = [f"{len(self.cells)} areas, {len(self.edges)} edges"]
        for a in self.areas:
            cx, cy = self.centroid[a]
            lines.append(
                f"  area {a} ({self.names.get(a, '?')}): {self.size(a)} cells, "
                f"centroid ({cx:.1f}, {cy:.1f}), neighbours {self.adjacency[a]}"
            )
        for a, b in self.edges:
            lines.append(f"  edge {a}-{b}: {len(self.portals[(a, b)])} portal(s), "
                         f"W1 = {self.weight(a, b, 'W1'):.1f}")
        return "\n".join(lines)


def build_area_graph(grid: Grid, *, enforce_connected: bool = True) -> AreaGraph:
    """Label the grid's areas and build its :class:`AreaGraph` in one O(|F|) pass.

    Parameters
    ----------
    grid:
        The grid. Its ``area_ids`` are (re)computed in place.
    enforce_connected:
        Apply :func:`split_disconnected_areas` first (assumption A1). Turn off
        only to test the planner's fallback path on a deliberately broken map.
    """
    names = label_areas(grid)
    if enforce_connected:
        for new_id, parent in split_disconnected_areas(grid).items():
            names[new_id] = names[parent]

    g = AreaGraph()
    portals: dict[tuple[int, int], list[Portal]] = defaultdict(list)
    cells: dict[int, list[Cell]] = defaultdict(list)

    for c in grid.free_cells():
        a = grid.area_of(c)
        cells[a].append(c)
        x, y = c
        # Only look right and up: each adjacent pair is then visited exactly once.
        for dx, dy in ((1, 0), (0, 1)):
            n = (x + dx, y + dy)
            if not grid.is_free(n):
                continue
            b = grid.area_of(n)
            if a != b:
                portals[(a, b)].append((c, n))
                portals[(b, a)].append((n, c))

    g.cells = dict(cells)
    g.portals = dict(portals)
    g.names = {a: names.get(a, "?") for a in g.cells}
    g.adjacency = {a: sorted({b for (x, b) in g.portals if x == a}) for a in g.cells}
    g.centroid = {
        a: (sum(x for x, _ in cs) / len(cs), sum(y for _, y in cs) / len(cs))
        for a, cs in g.cells.items()
    }
    return g


def area_of_label(grid: Grid, graph: AreaGraph, label: str) -> int:
    """Convenience for tests and demos: the id of the area with raw character ``label``."""
    for a, n in graph.names.items():
        if n == label:
            return a
    raise KeyError(label)

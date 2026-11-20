"""The one interface the experiment runner, CLI and visualiser call."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..grid import Cell, Grid
from ..search import SearchResult


class Planner(ABC):
    """A path planner for one grid.

    Lifecycle: ``prepare(grid)`` once per map (preprocessing, timed separately
    by the runner), then ``plan(s, g)`` any number of times.
    """

    name: str = "planner"

    def __init__(self) -> None:
        self.grid: Grid | None = None

    def prepare(self, grid: Grid) -> None:
        """Preprocess the map. The default does nothing but remember the grid."""
        self.grid = grid

    @abstractmethod
    def plan(self, start: Cell, goal: Cell) -> SearchResult[Cell]:
        """Find a path from ``start`` to ``goal`` on the prepared grid."""

    def __repr__(self) -> str:
        return self.name


PLANNERS: dict[str, type[Planner]] = {}


def register(cls: type[Planner]) -> type[Planner]:
    """Class decorator: make a planner available by name to the runner and CLI."""
    PLANNERS[cls.name] = cls
    return cls


def make(name: str, **kwargs) -> Planner:
    """Instantiate a registered planner by name (imports the modules that register them)."""
    from . import flat  # noqa: F401  (registration side effects)

    if name not in PLANNERS:
        raise KeyError(f"unknown planner {name!r}; known: {sorted(PLANNERS)}")
    return PLANNERS[name](**kwargs)

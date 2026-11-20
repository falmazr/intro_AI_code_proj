"""The cell-level grid world.

Coordinates
-----------
A cell is ``(x, y)`` with ``x`` running left to right and ``y`` running
*bottom to top*, exactly as in Figure 1 of the project brief, so the
lower-left cell is ``(0, 0)`` and the upper-right cell of an 8x8 world is
``(7, 7)``.

Everything outside the stored rectangle is blocked. This is how the brief's
rule "the perimeter of the world is always enclosed by blocked cells" is
represented without shifting the coordinates of the sample world.

Map file format (``.map``)
--------------------------
Plain text, one row per line, *top row first* (so the last line is y = 0)::

    PPP#WWWW
    PPPWWWWW
    ...

* ``#`` is a blocked cell.
* Any other non-space character is a free cell and names its area. Areas
  are identified by that character, so ``M`` cells form area ``M``.
* Lines starting with ``;`` are comments and blank lines are ignored.

Area ids are turned into small integers by :mod:`mls.partition`; the grid
itself only stores the raw labels so that loading is trivial and lossless.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

Cell = tuple[int, int]

BLOCKED = "#"
COMMENT = ";"

# Neighbour offsets. 4-connectivity is the default used throughout the project;
# 8-connectivity is an optional variant (diagonal step cost sqrt(2)).
OFFSETS_4: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
OFFSETS_8: tuple[Cell, ...] = OFFSETS_4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


@dataclass
class Grid:
    """A rectangular grid of free and blocked cells with an area label per free cell.

    Attributes
    ----------
    width, height:
        Size of the stored rectangle. Cells with ``0 <= x < width`` and
        ``0 <= y < height`` are inside; everything else is blocked.
    labels:
        ``labels[y][x]`` is ``"#"`` for a blocked cell or the raw area
        character for a free cell. Row 0 is y = 0 (the *bottom* row).
    area_ids:
        ``area_ids[y][x]`` is an integer area id for free cells and ``-1``
        for blocked cells. Filled in by :func:`mls.partition.label_areas`;
        until then every free cell has id ``-1`` as well.
    connectivity:
        4 or 8.
    """

    width: int
    height: int
    labels: list[list[str]]
    area_ids: list[list[int]] = field(default_factory=list)
    connectivity: int = 4

    def __post_init__(self) -> None:
        if self.connectivity not in (4, 8):
            raise ValueError("connectivity must be 4 or 8")
        if len(self.labels) != self.height or any(len(r) != self.width for r in self.labels):
            raise ValueError("labels must be height rows of width columns")
        if not self.area_ids:
            self.area_ids = [[-1] * self.width for _ in range(self.height)]

    # ------------------------------------------------------------------ I/O

    @classmethod
    def loads(cls, text: str, connectivity: int = 4) -> "Grid":
        """Parse a map from its text (see the module docstring for the format)."""
        rows = [
            line.rstrip("\n")
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(COMMENT)
        ]
        if not rows:
            raise ValueError("empty map")
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise ValueError("all map rows must have the same length")
        # File is top row first; we store y = 0 as the bottom row.
        labels = [list(r) for r in reversed(rows)]
        return cls(width=width, height=len(rows), labels=labels, connectivity=connectivity)

    @classmethod
    def load(cls, path: str | Path, connectivity: int = 4) -> "Grid":
        """Load a ``.map`` file."""
        return cls.loads(Path(path).read_text(encoding="utf-8"), connectivity)

    def dumps(self) -> str:
        """Serialise back to the text format (top row first)."""
        return "\n".join("".join(row) for row in reversed(self.labels)) + "\n"

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.dumps(), encoding="utf-8")

    @classmethod
    def from_blocked(cls, width: int, height: int, blocked: Iterable[Cell],
                     fill: str = ".", connectivity: int = 4) -> "Grid":
        """Build a grid from a set of blocked cells; every free cell gets label ``fill``."""
        labels = [[fill] * width for _ in range(height)]
        for x, y in blocked:
            labels[y][x] = BLOCKED
        return cls(width=width, height=height, labels=labels, connectivity=connectivity)

    # ------------------------------------------------------------- queries

    def in_bounds(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_free(self, cell: Cell) -> bool:
        """True if the cell is inside the rectangle and not blocked."""
        x, y = cell
        return self.in_bounds(cell) and self.labels[y][x] != BLOCKED

    def is_blocked(self, cell: Cell) -> bool:
        return not self.is_free(cell)

    def label_of(self, cell: Cell) -> str:
        x, y = cell
        return self.labels[y][x]

    def area_of(self, cell: Cell) -> int:
        """Integer area id of a free cell (``-1`` if blocked or not yet labelled)."""
        x, y = cell
        if not self.in_bounds(cell):
            return -1
        return self.area_ids[y][x]

    def neighbours(self, cell: Cell) -> list[Cell]:
        """Free cells adjacent to ``cell`` under the grid's connectivity.

        With 8-connectivity a diagonal move is refused when it would cut a
        corner between two blocked cells (the robot cannot squeeze through).
        """
        x, y = cell
        offsets = OFFSETS_4 if self.connectivity == 4 else OFFSETS_8
        out: list[Cell] = []
        for dx, dy in offsets:
            nxt = (x + dx, y + dy)
            if not self.is_free(nxt):
                continue
            if dx and dy and not (self.is_free((x + dx, y)) and self.is_free((x, y + dy))):
                continue
            out.append(nxt)
        return out

    @staticmethod
    def step_cost(a: Cell, b: Cell) -> float:
        """Cost of one move between adjacent cells: 1, or sqrt(2) for a diagonal."""
        return 1.0 if a[0] == b[0] or a[1] == b[1] else 2 ** 0.5

    def free_cells(self) -> Iterator[Cell]:
        """All free cells, row by row from the bottom."""
        for y in range(self.height):
            row = self.labels[y]
            for x in range(self.width):
                if row[x] != BLOCKED:
                    yield (x, y)

    def count_free(self) -> int:
        return sum(1 for _ in self.free_cells())

    def random_free_cell(self, rng: random.Random, exclude: Sequence[Cell] = ()) -> Cell:
        """A uniformly random free cell, drawn from ``rng`` so runs are reproducible."""
        cells = [c for c in self.free_cells() if c not in set(exclude)]
        if not cells:
            raise ValueError("no free cell available")
        return rng.choice(cells)

    # ------------------------------------------------------------ display

    def render(self, path: Sequence[Cell] = (), start: Cell | None = None,
               goal: Cell | None = None) -> str:
        """ASCII picture, top row first, with an optional path drawn as ``*``."""
        on_path = set(path)
        lines = []
        for y in range(self.height - 1, -1, -1):
            chars = []
            for x in range(self.width):
                c = (x, y)
                if c == start:
                    chars.append("S")
                elif c == goal:
                    chars.append("G")
                elif c in on_path:
                    chars.append("*")
                else:
                    chars.append(self.labels[y][x])
            lines.append("".join(chars))
        return "\n".join(lines)

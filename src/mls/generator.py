

from __future__ import annotations

import random
import string
from collections import defaultdict
from dataclasses import dataclass

from .grid import BLOCKED, OFFSETS_4, Cell, Grid

ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits


@dataclass(frozen=True)
class RoomSpec:
 

    rooms_per_side: int = 3
    corridor_width: int = 2
    min_doors: int = 1
    max_doors: int = 2
    obstacle_density: float = 0.08
    


def min_size(spec: RoomSpec) -> int:
  
    r, cw = spec.rooms_per_side, spec.corridor_width
    return (r + 1) * cw + r * 4


def rooms_and_corridors(size: int, rng: random.Random, spec: RoomSpec = RoomSpec()) -> Grid:
  
    r, cw = spec.rooms_per_side, spec.corridor_width
    if size < min_size(spec):
        raise ValueError(f"size {size} too small; need at least {min_size(spec)} for {spec}")
    room_outer = (size - (r + 1) * cw) // r
    interior = room_outer - 2
    leftover = size - (r + 1) * cw - r * room_outer  # absorbed by the last lane

    # region[y][x]: -1 blocked, otherwise a region id. Regions become areas.
    region = [[-1] * size for _ in range(size)]
    next_region = 0

    def new_region() -> int:
        nonlocal next_region
        next_region += 1
        return next_region - 1

    # 1. Lane positions.
    lanes: list[tuple[int, int]] = []
    pos = 0
    for i in range(r + 1):
        width = cw + (leftover if i == r else 0)
        lanes.append((pos, pos + width))
        pos += width + room_outer

    def lane_index(v: int) -> int | None:
        for i, (a, b) in enumerate(lanes):
            if a <= v < b:
                return i
        return None

    # 2. Corridor regions: junctions and straight segments between them.
    junction: dict[tuple[int, int], int] = {}
    v_segment: dict[tuple[int, int], int] = {}  # (vertical lane, gap index)
    h_segment: dict[tuple[int, int], int] = {}  # (horizontal lane, gap index)

    def gap_index(v: int) -> int:
        
        return sum(1 for _, b in lanes if b <= v) - 1

    for y in range(size):
        for x in range(size):
            vi, hi = lane_index(x), lane_index(y)
            if vi is None and hi is None:
                continue
            if vi is not None and hi is not None:
                table, key = junction, (vi, hi)
            elif vi is not None:
                table, key = v_segment, (vi, gap_index(y))
            else:
                table, key = h_segment, (hi, gap_index(x))
            if key not in table:
                table[key] = new_region()
            region[y][x] = table[key]

    # 3. Rooms.
    rooms: list[tuple[int, int, int, int, int]] = []  # x0, y0, x1, y1 (exclusive), region
    for ry in range(r):
        for rx in range(r):
            x0, y0 = lanes[rx][1] + 1, lanes[ry][1] + 1
            x1, y1 = x0 + interior, y0 + interior
            rid = new_region()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    region[y][x] = rid
            rooms.append((x0, y0, x1, y1, rid))

    # 4. Doors: a wall cell becomes part of the corridor region it touches.
    doors: set[Cell] = set()
    for x0, y0, x1, y1, _ in rooms:
        n_doors = rng.randint(spec.min_doors, spec.max_doors)
        walls = ["left", "right", "bottom", "top"]
        rng.shuffle(walls)
        for side in walls[:n_doors]:
            if side == "left":
                d, outside = (x0 - 1, rng.randrange(y0, y1)), (x0 - 2, None)
            elif side == "right":
                d, outside = (x1, rng.randrange(y0, y1)), (x1 + 1, None)
            elif side == "bottom":
                d, outside = (rng.randrange(x0, x1), y0 - 1), (None, y0 - 2)
            else:
                d, outside = (rng.randrange(x0, x1), y1), (None, y1 + 1)
            ox = outside[0] if outside[0] is not None else d[0]
            oy = outside[1] if outside[1] is not None else d[1]
            region[d[1]][d[0]] = region[oy][ox]
            doors.add(d)

    # 5. Obstacles inside rooms, never next to a door (so every door stays usable).
    for x0, y0, x1, y1, _ in rooms:
        cells = [(x, y) for y in range(y0, y1) for x in range(x0, x1)]
        k = int(len(cells) * spec.obstacle_density)
        for x, y in rng.sample(cells, k):
            if any((x + dx, y + dy) in doors for dx, dy in OFFSETS_4):
                continue
            region[y][x] = -1

    # 6. Greedy colouring of regions into characters.
    labels = _colour_regions(region, size, size)
    grid = Grid(width=size, height=size, labels=labels)
    _keep_largest_component(grid)
    return grid


def _colour_regions(region: list[list[int]], width: int, height: int) -> list[list[str]]:

    adj: dict[int, set[int]] = defaultdict(set)
    for y in range(height):
        for x in range(width):
            a = region[y][x]
            if a < 0:
                continue
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if nx < width and ny < height:
                    b = region[ny][nx]
                    if b >= 0 and b != a:
                        adj[a].add(b)
                        adj[b].add(a)
    colour: dict[int, str] = {}
    ids = sorted({region[y][x] for y in range(height) for x in range(width) if region[y][x] >= 0})
    for rid in ids:
        used = {colour[n] for n in adj[rid] if n in colour}
        colour[rid] = next(ch for ch in ALPHABET if ch not in used)
    return [[BLOCKED if region[y][x] < 0 else colour[region[y][x]] for x in range(width)]
            for y in range(height)]


def _keep_largest_component(grid: Grid) -> None:
    """Fill in any pocket of free space cut off by obstacles, so every query is solvable."""
    from .partition import connected_components  # local import avoids a cycle

    comps = connected_components(grid, grid.free_cells())
    if len(comps) <= 1:
        return
    comps.sort(key=len, reverse=True)
    for comp in comps[1:]:
        for x, y in comp:
            grid.labels[y][x] = BLOCKED


def uniform_blocks(grid: Grid, block: int) -> Grid:

    per_row = (grid.width + block - 1) // block
    region = [[-1 if grid.labels[y][x] == BLOCKED else (y // block) * per_row + (x // block)
               for x in range(grid.width)] for y in range(grid.height)]
    labels = _colour_regions(region, grid.width, grid.height)
    return Grid(width=grid.width, height=grid.height, labels=labels, connectivity=grid.connectivity)


def random_query(grid: Grid, rng: random.Random, min_distance: int = 1) -> tuple[Cell, Cell]:

    cells = list(grid.free_cells())
    for _ in range(10_000):
        s, g = rng.sample(cells, 2)
        if abs(s[0] - g[0]) + abs(s[1] - g[1]) >= min_distance:
            return s, g
    raise ValueError("could not find a query far enough apart")

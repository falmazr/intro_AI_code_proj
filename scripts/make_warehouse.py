"""Build maps/warehouse.map: a hand-designed logistics warehouse floor.

This is the project's non-generated test map: a realistic layout a mobile
robot would work in, rather than the random rooms the generator makes.
It is written as a script so the layout is reproducible and easy to edit.

Layout (60 x 40 cells, 1 cell = 1 m, y points up, (0,0) lower-left):

    y 34-39  packing & staging (P)   | dispatch dock apron (D)   | charging bay (H)
    y 31-33  north cross-aisle (N)
    y 20-30  racking block, north half: aisles between pallet racks (a..i)
    y 18-19  middle cross-aisle (M)
    y  7-17  racking block, south half: aisles between pallet racks (j..r)
    y  4- 6  south cross-aisle (S)
    y  0- 3  inbound dock apron / receiving (R)
    x  0- 3  offices and lift lobby on the west edge (O), door onto the south cross-aisle

Areas: every aisle segment, cross-aisle and zone is its own area, which is
exactly the partition a two-tier planner wants: Tier 1 decides "which aisles
and cross-aisles", Tier 2 drives along them.

Run:  python scripts/make_warehouse.py  (writes maps/warehouse.map and prints it)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mls.grid import BLOCKED, Grid  # noqa: E402
from mls.partition import build_area_graph  # noqa: E402

W, H = 60, 40


def build() -> Grid:
    g = [[BLOCKED] * W for _ in range(H)]

    def fill(x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        """Paint the inclusive rectangle [x0..x1] x [y0..y1]."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = ch

    # Zones along the south and north edges.
    fill(4, 0, 55, 3, "R")       # receiving apron (inbound docks on the south wall)
    fill(4, 4, 55, 6, "S")       # south cross-aisle
    fill(4, 18, 55, 19, "M")     # middle cross-aisle
    fill(4, 31, 55, 33, "N")     # north cross-aisle
    fill(4, 34, 29, 39, "P")     # packing and staging
    fill(31, 34, 51, 39, "D")    # dispatch dock apron (outbound docks on the north wall)
    fill(53, 34, 55, 39, "H")    # robot charging bay
    g[36][30] = "P"              # doorway packing -> dispatch (wall at x=30 otherwise)
    g[37][30] = "P"
    g[36][52] = "D"              # doorway dispatch -> charging bay

    # Racking block: pallet racks are 2 cells deep, aisles 2 cells wide,
    # running north-south between the south and north cross-aisles.
    # x = 4..55 holds 9 aisles: rack(2) aisle(2) rack(2) ... ending with a rack.
    south_labels = "jklmnopqr"   # aisle segments south of the middle cross-aisle
    north_labels = "abcdefghi"   # aisle segments north of it
    x = 4
    for i in range(9):
        x += 2                   # skip a rack (already blocked)
        fill(x, 7, x + 1, 17, south_labels[i])
        fill(x, 20, x + 1, 30, north_labels[i])
        x += 2
    # x is now 40: the last rack is at 40-41; the strip 42..55 is bulk floor storage.
    fill(42, 7, 55, 17, "B")     # bulk storage, south: open floor with block-stacked pallets
    fill(42, 20, 55, 30, "U")    # bulk storage, north
    for (bx, by) in [(44, 9), (44, 13), (49, 9), (49, 13), (44, 23), (44, 27), (49, 23), (49, 27)]:
        fill(bx, by, bx + 2, by + 1, BLOCKED)   # 3x2 pallet stacks
    fill(54, 7, 55, 17, BLOCKED)   # east wall shelving
    fill(54, 20, 55, 30, BLOCKED)

    # Offices and lift lobby on the west edge, one door onto the south cross-aisle.
    fill(0, 7, 2, 30, "O")
    fill(1, 4, 1, 6, "O")        # lobby passage down to the cross-aisle level
    fill(2, 5, 3, 5, "O")        # door cells; (3,5) touches the south cross-aisle at (4,5)
    fill(0, 14, 2, 14, BLOCKED)  # internal partition walls between offices
    g[14][1] = "O"               # with a doorway
    fill(0, 22, 2, 22, BLOCKED)
    g[22][1] = "O"

    return Grid(width=W, height=H, labels=g)


def main() -> None:
    grid = build()
    out = ROOT / "maps" / "warehouse.map"
    header = (
        "; Logistics warehouse floor, 60x40, 1 cell = 1 m. Built by scripts/make_warehouse.py.\n"
        "; R receiving  S/M/N cross-aisles  a-i north aisles  j-r south aisles  B/U bulk floor\n"
        "; P packing  D dispatch  H charging bay  O offices  # racks and walls\n"
    )
    out.write_text(header + grid.dumps(), encoding="utf-8")
    ag = build_area_graph(grid)
    print(grid.render())
    print()
    print(ag.describe().splitlines()[0], "->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()

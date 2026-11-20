"""The hand-designed warehouse map must stay consistent with scripts/make_warehouse.py."""

import subprocess
import sys
from pathlib import Path

from mls.grid import Grid
from mls.partition import build_area_graph, connected_components

ROOT = Path(__file__).resolve().parents[1]


def test_warehouse_map_matches_script(tmp_path):
    """Regenerating the map must produce the committed file (no hand edits out of sync)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_warehouse  # noqa: WPS433

    committed = Grid.load(ROOT / "maps" / "warehouse.map")
    assert make_warehouse.build().labels == committed.labels


def test_warehouse_is_connected_and_partitioned():
    g = Grid.load(ROOT / "maps" / "warehouse.map")
    assert (g.width, g.height) == (60, 40)
    assert len(connected_components(g, g.free_cells())) == 1
    ag = build_area_graph(g)
    names = set(ag.names.values())
    assert {"R", "S", "M", "N", "P", "D", "H", "O", "B", "U"} <= names
    assert set("abcdefghijklmnopqr") <= names        # 18 aisle segments
    # every aisle segment joins exactly two cross-aisles
    for a in ag.areas:
        if ag.names[a] in "abcdefghijklmnopqr":
            assert len(ag.neighbours(a)) == 2

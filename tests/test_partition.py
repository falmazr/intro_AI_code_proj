"""Tests for mls.partition: labelling, A1 enforcement, portals, area graph."""

from pathlib import Path

import pytest

from mls.grid import Grid
from mls.partition import (
    AreaGraph,
    area_of_label,
    build_area_graph,
    connected_components,
    label_areas,
    split_disconnected_areas,
)

MAPS = Path(__file__).resolve().parents[1] / "maps"


@pytest.fixture
def fig1() -> tuple[Grid, AreaGraph]:
    g = Grid.load(MAPS / "figure1.map")
    return g, build_area_graph(g)


def ids(fig1):
    g, ag = fig1
    return {ch: area_of_label(g, ag, ch) for ch in "MBYPW"}


def test_figure1_has_five_areas(fig1):
    g, ag = fig1
    assert len(ag.areas) == 5
    assert sorted(ag.names.values()) == sorted("MBYPW")


def test_figure1_edges_match_the_brief(fig1):
    """Magenta touches yellow and pink; yellow and pink both touch white; blue hangs off yellow."""
    g, ag = fig1
    a = ids(fig1)
    expected = {
        tuple(sorted((a["B"], a["Y"]))),
        tuple(sorted((a["M"], a["Y"]))),
        tuple(sorted((a["M"], a["P"]))),
        tuple(sorted((a["Y"], a["W"]))),
        tuple(sorted((a["P"], a["W"]))),
    }
    assert set(ag.edges) == expected
    assert not ag.has_edge(a["M"], a["B"])
    assert not ag.has_edge(a["M"], a["W"])


def test_figure1_portals_and_entry_cells(fig1):
    """The brief: from (0,0) the nearest yellow cell is (3,2); from there the nearest white is (7,4)."""
    g, ag = fig1
    a = ids(fig1)
    assert ag.portals[(a["M"], a["Y"])] == [((2, 2), (3, 2))]
    assert ag.entry_cells(a["M"], a["Y"]) == [(3, 2)]
    assert ag.exit_cells(a["M"], a["Y"]) == [(2, 2)]
    assert ag.entry_cells(a["Y"], a["W"]) == [(7, 4)]
    assert ag.entry_cells(a["M"], a["P"]) == [(1, 4)]
    assert ag.entry_cells(a["P"], a["W"]) == [(3, 6)]
    assert ag.entry_cells(a["B"], a["Y"]) == [(5, 2)]
    assert ag.entry_cells(a["M"], a["B"]) == []  # not adjacent: (3,0) and (3,1) are walls


def test_portals_are_symmetric(fig1):
    g, ag = fig1
    for (x, y), plist in ag.portals.items():
        rev = ag.portals[(y, x)]
        assert sorted((v, u) for u, v in plist) == sorted(rev)


def test_every_free_cell_in_exactly_one_area(fig1):
    g, ag = fig1
    seen = [c for cells in ag.cells.values() for c in cells]
    assert len(seen) == len(set(seen)) == g.count_free()
    for a, cells in ag.cells.items():
        assert all(g.area_of(c) == a for c in cells)


def test_areas_are_connected(fig1):
    g, ag = fig1
    for a, cells in ag.cells.items():
        assert len(connected_components(g, cells)) == 1


def test_closest_cell_and_weights(fig1):
    g, ag = fig1
    a = ids(fig1)
    assert ag.closest_cell_to(a["Y"], (7, 7)) == (7, 3)
    assert ag.closest_cell_to(a["M"], (7, 7)) == (2, 3)
    assert ag.weight(a["M"], a["Y"], "W0") == 1.0
    assert ag.weight(a["M"], a["Y"], "W1") > ag.weight(a["M"], a["Y"], "W0")
    with pytest.raises(KeyError):
        ag.weight(a["B"], a["W"])
    with pytest.raises(ValueError):
        ag.weight(a["M"], a["Y"], "W2")


def test_split_disconnected_areas():
    # Two 'A' regions separated by a wall: A1 is violated until split.
    g = Grid.loads("A#A\nA#A\n")
    label_areas(g)
    assert g.area_of((0, 0)) == g.area_of((2, 0))
    created = split_disconnected_areas(g)
    assert len(created) == 1 and list(created.values()) == [0]
    assert g.area_of((0, 0)) != g.area_of((2, 0))
    assert g.area_of((2, 0)) == g.area_of((2, 1))


def test_build_without_enforcing_a1_keeps_broken_area():
    g = Grid.loads("A#A\nABA\n")
    ag = build_area_graph(g, enforce_connected=False)
    assert len(ag.areas) == 2          # A (disconnected) and B
    ag2 = build_area_graph(Grid.loads("A#A\nABA\n"))
    assert len(ag2.areas) == 3         # A, B and the split-off A


def test_describe_runs(fig1):
    g, ag = fig1
    text = ag.describe()
    assert "5 areas, 5 edges" in text

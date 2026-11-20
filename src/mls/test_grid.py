"""Tests for mls.grid: loading, coordinates, neighbours, round-trip."""

import random
from pathlib import Path

import pytest

from mls.grid import Grid

MAPS = Path(__file__).resolve().parents[1] / "maps"


@pytest.fixture
def fig1() -> Grid:
    return Grid.load(MAPS / "figure1.map")


def test_figure1_shape_and_corners(fig1: Grid):
    assert (fig1.width, fig1.height) == (8, 8)
    assert fig1.label_of((0, 0)) == "M"      # S is magenta, lower-left
    assert fig1.label_of((7, 7)) == "W"      # G is white, upper-right
    assert fig1.is_blocked((3, 0))
    assert fig1.label_of((5, 1)) == "B"


def test_y_axis_points_up(fig1: Grid):
    # Top line of the file is y = 7: "PPP#WWWW"
    assert [fig1.label_of((x, 7)) for x in range(8)] == list("PPP#WWWW")
    # Bottom line is y = 0: "MMM#BBB#"
    assert [fig1.label_of((x, 0)) for x in range(8)] == list("MMM#BBB#")


def test_outside_is_blocked(fig1: Grid):
    assert fig1.is_blocked((-1, 0))
    assert fig1.is_blocked((0, 8))
    assert fig1.area_of((99, 99)) == -1


def test_neighbours_4(fig1: Grid):
    assert sorted(fig1.neighbours((0, 0))) == [(0, 1), (1, 0)]
    # (3,2) is the single yellow cell adjoining magenta
    assert sorted(fig1.neighbours((3, 2))) == [(2, 2), (4, 2)]
    assert sorted(fig1.neighbours((7, 4))) == [(7, 3), (7, 5)]


def test_neighbours_8_no_corner_cutting():
    g = Grid.loads("..\n#.\n", connectivity=8)
    # From (0,1) [top-left] to (1,0) [bottom-right]: (0,0) is blocked -> diagonal refused.
    assert (1, 0) not in g.neighbours((0, 1))
    g2 = Grid.loads("..\n..\n", connectivity=8)
    assert sorted(g2.neighbours((0, 0))) == [(0, 1), (1, 0), (1, 1)]


def test_step_cost():
    assert Grid.step_cost((0, 0), (1, 0)) == 1.0
    assert Grid.step_cost((0, 0), (1, 1)) == pytest.approx(2 ** 0.5)


def test_round_trip(fig1: Grid, tmp_path: Path):
    out = tmp_path / "copy.map"
    fig1.save(out)
    again = Grid.load(out)
    assert again.labels == fig1.labels


def test_loads_rejects_ragged():
    with pytest.raises(ValueError):
        Grid.loads("abc\nab\n")


def test_count_free(fig1: Grid):
    # 64 cells minus the blocked ones in the sample world.
    assert fig1.count_free() == 64 - fig1.dumps().count("#")


def test_random_free_cell_is_seeded(fig1: Grid):
    a = fig1.random_free_cell(random.Random(7))
    b = fig1.random_free_cell(random.Random(7))
    assert a == b and fig1.is_free(a)


def test_render_marks_path(fig1: Grid):
    pic = fig1.render(path=[(1, 0), (2, 0)], start=(0, 0), goal=(7, 7))
    assert pic.splitlines()[-1].startswith("S**")
    assert pic.splitlines()[0].endswith("G")

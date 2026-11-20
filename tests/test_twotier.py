"""Tests for the two-tier planner (W0/W1 weights, both leg-goal rules, fallback). W2 tests live in test_hpa.py."""

import random
from pathlib import Path

import pytest

from mls.generator import random_query, rooms_and_corridors, uniform_blocks
from mls.grid import Grid
from mls.partition import area_of_label
from mls.planners import make
from mls.planners.twotier import TwoTierPlanner

MAPS = Path(__file__).resolve().parents[1] / "maps"

ALL_TWO_TIER = [
    ("twotier", {"weight_model": "W1", "leg_goal": "first"}),
    ("twotier", {"weight_model": "W1", "leg_goal": "nearest"}),
    ("twotier", {"weight_model": "W0", "leg_goal": "first"}),
]


def _valid_path(g: Grid, path, s, t):
    assert path[0] == s and path[-1] == t
    for a, b in zip(path, path[1:]):
        assert b in g.neighbours(a), (a, b)


def test_figure1_worked_example_from_the_brief():
    """S=(0,0) -> nearest yellow (3,2) -> nearest white (7,4) -> G=(7,7), cost 14 (optimal here)."""
    g = Grid.load(MAPS / "figure1.map")
    p = TwoTierPlanner(weight_model="W1", leg_goal="nearest")
    p.prepare(g)
    r = p.plan((0, 0), (7, 7))
    assert r.success and r.cost == 14
    names = [p.graph.names[a] for a in r.extra["areas"]]
    assert names == ["M", "Y", "W"]
    assert (3, 2) in r.path and (7, 4) in r.path
    _valid_path(g, r.path, (0, 0), (7, 7))
    assert r.extra["legs"] == 3 and r.extra["replans"] == 0


def test_figure1_same_area_query():
    g = Grid.load(MAPS / "figure1.map")
    p = TwoTierPlanner()
    p.prepare(g)
    r = p.plan((0, 0), (2, 3))
    assert r.success and r.cost == 5 and r.extra["legs"] == 1


@pytest.mark.parametrize("name,kwargs", ALL_TWO_TIER)
def test_two_tier_is_complete_and_valid_on_generated_maps(name, kwargs):
    g = rooms_and_corridors(96, random.Random(11), )
    p = make(name, **kwargs)
    p.prepare(g)
    rng = random.Random(12)
    for _ in range(15):
        s, t = random_query(g, rng, min_distance=30)
        r = p.plan(s, t)
        assert r.success, (name, s, t)
        _valid_path(g, r.path, s, t)
        assert r.expanded > 0


@pytest.mark.parametrize("name,kwargs", ALL_TWO_TIER)
def test_two_tier_cost_is_never_below_optimal(name, kwargs):
    g = rooms_and_corridors(96, random.Random(13))
    a, p = make("astar"), make(name, **kwargs)
    a.prepare(g)
    p.prepare(g)
    rng = random.Random(14)
    ratios = []
    for _ in range(15):
        s, t = random_query(g, rng, min_distance=30)
        ra, rp = a.plan(s, t), p.plan(s, t)
        assert rp.cost >= ra.cost - 1e-9
        ratios.append(rp.cost / ra.cost)
    assert max(ratios) < 2.0  # sanity: never wildly off on these maps


def test_two_tier_expands_fewer_nodes_than_flat_on_a_large_map():
    g = rooms_and_corridors(192, random.Random(15))
    a, p = make("astar"), make("twotier")
    a.prepare(g)
    p.prepare(g)
    rng = random.Random(16)
    wins = 0
    for _ in range(10):
        s, t = random_query(g, rng, min_distance=120)
        if p.plan(s, t).expanded < a.plan(s, t).expanded:
            wins += 1
    assert wins >= 8


def test_fallback_on_a_map_that_violates_a1():
    """Area A is two disconnected pieces; with A1 enforcement off, the abstract plan
    through 'A' can pick a leg that cannot be completed, and the planner must recover."""
    text = (
        "AAA#CCC\n"
        "A#A#C#C\n"
        "AAABBBB\n"
        "###B###\n"
        "AAABBBB\n"
        "A#A#D#D\n"
        "AAA#DDD\n"
    )
    g = Grid.loads(text)
    p = TwoTierPlanner()
    p.prepare(g, enforce_connected=False)          # keep the broken labelling on purpose
    assert len(p.graph.areas) == 4                  # A (broken), B, C, D
    a = make("astar")
    a.prepare(g)
    for s, t in [((0, 6), (6, 0)), ((0, 0), (6, 6)), ((0, 6), (0, 0))]:
        r = p.plan(s, t)
        assert r.success, (s, t)
        _valid_path(g, r.path, s, t)
        assert r.cost >= a.plan(s, t).cost - 1e-9
    # and with enforcement on (the default) the same queries work with no replans
    q = TwoTierPlanner()
    q.prepare(g)
    assert len(q.graph.areas) == 5
    for s, t in [((0, 6), (6, 0)), ((0, 0), (6, 6))]:
        assert q.plan(s, t).extra["replans"] == 0


def test_fallback_when_the_final_leg_enters_a_cut_off_piece_of_the_goal_area():
    """Area A is two pieces with a wall between them. With A1 enforcement off, the
    abstract route S -> A enters the piece that cannot reach the goal, so the final
    leg fails; the planner must still return a valid path via the flat fallback."""
    g = Grid.loads("SA#AC\nSCCCC\n")
    a = make("astar")
    a.prepare(g)
    for kw in ({"weight_model": "W1", "leg_goal": "first"},
               {"weight_model": "W1", "leg_goal": "nearest"},
               {"weight_model": "W0", "leg_goal": "first"}):
        p = TwoTierPlanner(**kw)
        p.prepare(g, enforce_connected=False)
        r = p.plan((0, 1), (3, 1))
        assert r.success, kw
        _valid_path(g, r.path, (0, 1), (3, 1))
        assert r.extra.get("fallback") is True
        assert r.cost >= a.plan((0, 1), (3, 1)).cost - 1e-9


def test_unreachable_is_reported_as_failure():
    g = Grid.loads("A#B\nA#B\n")
    for name, kw in ALL_TWO_TIER:
        p = make(name, **kw)
        p.prepare(g)
        assert not p.plan((0, 0), (2, 1)).success


def test_registry_names():
    from mls.planners import PLANNERS
    assert {"astar", "bfs", "dijkstra", "wastar", "twotier"} <= set(PLANNERS)

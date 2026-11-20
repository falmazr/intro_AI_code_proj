"""Tests for mls.search and the flat planners."""

import random
from pathlib import Path

import pytest

from mls.generator import random_query, rooms_and_corridors
from mls.grid import Grid
from mls.heuristics import manhattan, min_to_set, octile, zero
from mls.planners import make
from mls.search import astar, bfs

MAPS = Path(__file__).resolve().parents[1] / "maps"


def test_astar_on_figure1_is_optimal():
    g = Grid.load(MAPS / "figure1.map")
    p = make("astar")
    p.prepare(g)
    r = p.plan((0, 0), (7, 7))
    assert r.success and r.cost == 14          # equals the Manhattan distance here
    assert r.path[0] == (0, 0) and r.path[-1] == (7, 7)
    for a, b in zip(r.path, r.path[1:]):
        assert b in g.neighbours(a)


def test_all_optimal_planners_agree():
    g = rooms_and_corridors(64, random.Random(1))
    planners = [make(n) for n in ("astar", "dijkstra", "bfs")]
    for p in planners:
        p.prepare(g)
    rng = random.Random(2)
    for _ in range(10):
        s, t = random_query(g, rng, min_distance=20)
        costs = {p.name: p.plan(s, t).cost for p in planners}
        assert len(set(costs.values())) == 1, costs


def test_astar_expands_fewer_than_dijkstra_and_bfs():
    g = rooms_and_corridors(64, random.Random(3))
    a, d, b = make("astar"), make("dijkstra"), make("bfs")
    for p in (a, d, b):
        p.prepare(g)
    s, t = random_query(g, random.Random(4), min_distance=40)
    assert a.plan(s, t).expanded < d.plan(s, t).expanded
    assert a.plan(s, t).expanded < b.plan(s, t).expanded


def test_weighted_astar_is_bounded_suboptimal():
    g = rooms_and_corridors(64, random.Random(5))
    a, w = make("astar"), make("wastar", epsilon=2.0)
    a.prepare(g)
    w.prepare(g)
    rng = random.Random(6)
    for _ in range(10):
        s, t = random_query(g, rng, min_distance=20)
        ca, cw = a.plan(s, t).cost, w.plan(s, t).cost
        assert ca <= cw <= 2.0 * ca + 1e-9


def test_unreachable_goal_fails_cleanly():
    g = Grid.loads("A#B\nA#B\n")
    p = make("astar")
    p.prepare(g)
    r = p.plan((0, 0), (2, 0))
    assert not r.success and r.cost == float("inf") and r.expanded == 2


def test_start_equals_goal():
    g = Grid.load(MAPS / "figure1.map")
    p = make("astar")
    p.prepare(g)
    r = p.plan((1, 1), (1, 1))
    assert r.success and r.cost == 0 and r.path == [(1, 1)]


def test_blocked_endpoint_fails():
    g = Grid.load(MAPS / "figure1.map")
    p = make("astar")
    p.prepare(g)
    assert not p.plan((3, 0), (7, 7)).success


def test_heuristics_values():
    assert manhattan((3, 4))((0, 0)) == 7
    assert octile((3, 3))((0, 0)) == pytest.approx(3 * 2 ** 0.5)
    assert zero((5, 5)) == 0
    assert min_to_set([(0, 5), (5, 0)])((1, 1)) == 5


def test_8_connectivity_octile_optimal_matches_dijkstra():
    g = rooms_and_corridors(48, random.Random(7))
    g8 = Grid(g.width, g.height, g.labels, connectivity=8)
    a, d = make("astar"), make("dijkstra")
    a.prepare(g8)
    d.prepare(g8)
    rng = random.Random(8)
    for _ in range(5):
        s, t = random_query(g8, rng, min_distance=20)
        assert a.plan(s, t).cost == pytest.approx(d.plan(s, t).cost)


def test_generic_astar_on_a_tiny_graph():
    edges = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    w = {("a", "b"): 1, ("a", "c"): 5, ("b", "d"): 1, ("c", "d"): 1}
    r = astar("a", lambda n: n == "d", lambda n: edges[n], lambda n: 0.0, lambda u, v: w[(u, v)])
    assert r.path == ["a", "b", "d"] and r.cost == 2
    r2 = bfs("a", lambda n: n == "d", lambda n: edges[n])
    assert r2.path in (["a", "b", "d"], ["a", "c", "d"])

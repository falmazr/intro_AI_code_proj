"""Tests for the W2 / HPA*-style planner (planners/hpa.py)."""

import random
from pathlib import Path

import pytest

from mls.generator import random_query, rooms_and_corridors, uniform_blocks
from mls.grid import Grid
from mls.planners import make

MAPS = Path(__file__).resolve().parents[1] / "maps"


def _valid_path(g: Grid, path, s, t):
    assert path[0] == s and path[-1] == t
    for a, b in zip(path, path[1:]):
        assert b in g.neighbours(a), (a, b)


def test_hpa_is_registered():
    from mls.planners import PLANNERS
    assert "twotier-W2" in PLANNERS


def test_hpa_figure1_is_optimal():
    g = Grid.load(MAPS / "figure1.map")
    p = make("twotier-W2")
    p.prepare(g)
    r = p.plan((0, 0), (7, 7))
    assert r.success and r.cost == 14
    _valid_path(g, r.path, (0, 0), (7, 7))


def test_hpa_is_complete_and_valid_on_generated_maps():
    g = rooms_and_corridors(96, random.Random(11))
    p = make("twotier-W2")
    p.prepare(g)
    rng = random.Random(12)
    for _ in range(15):
        s, t = random_query(g, rng, min_distance=30)
        r = p.plan(s, t)
        assert r.success, (s, t)
        _valid_path(g, r.path, s, t)


def test_hpa_cost_is_never_below_optimal():
    g = rooms_and_corridors(96, random.Random(13))
    a, p = make("astar"), make("twotier-W2")
    a.prepare(g)
    p.prepare(g)
    rng = random.Random(14)
    for _ in range(15):
        s, t = random_query(g, rng, min_distance=30)
        assert p.plan(s, t).cost >= a.plan(s, t).cost - 1e-9


def test_hpa_unreachable_is_reported_as_failure():
    g = Grid.loads("A#B\nA#B\n")
    p = make("twotier-W2")
    p.prepare(g)
    assert not p.plan((0, 0), (2, 1)).success


def test_hpa_is_at_least_as_good_as_greedy_legs_on_average():
    g = rooms_and_corridors(128, random.Random(17))
    w1, w2, a = make("twotier"), make("twotier-W2"), make("astar")
    for p in (w1, w2, a):
        p.prepare(g)
    rng = random.Random(18)
    over1 = over2 = 0.0
    for _ in range(20):
        s, t = random_query(g, rng, min_distance=60)
        opt = a.plan(s, t).cost
        over1 += w1.plan(s, t).cost / opt
        over2 += w2.plan(s, t).cost / opt
    assert over2 <= over1 + 1e-9


def test_hpa_on_uniform_blocks():
    g = uniform_blocks(rooms_and_corridors(64, random.Random(19)), 8)
    p, a = make("twotier-W2"), make("astar")
    p.prepare(g)
    a.prepare(g)
    rng = random.Random(20)
    for _ in range(10):
        s, t = random_query(g, rng, min_distance=20)
        r = p.plan(s, t)
        assert r.success
        _valid_path(g, r.path, s, t)
        assert r.cost >= a.plan(s, t).cost - 1e-9

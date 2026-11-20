"""Tests for mls.generator: reproducibility, structure, A1, connectivity, block partition."""

import random

import pytest

from mls.generator import RoomSpec, min_size, random_query, rooms_and_corridors, uniform_blocks
from mls.grid import BLOCKED, Grid
from mls.partition import build_area_graph, connected_components


@pytest.mark.parametrize("size", [32, 64, 128])
def test_same_seed_same_map(size):
    a = rooms_and_corridors(size, random.Random(1))
    b = rooms_and_corridors(size, random.Random(1))
    assert a.labels == b.labels


def test_different_seed_different_map():
    a = rooms_and_corridors(64, random.Random(1))
    b = rooms_and_corridors(64, random.Random(2))
    assert a.labels != b.labels


def test_too_small_is_rejected():
    spec = RoomSpec()
    with pytest.raises(ValueError):
        rooms_and_corridors(min_size(spec) - 1, random.Random(0), spec)
    rooms_and_corridors(min_size(spec), random.Random(0), spec)  # boundary is fine


@pytest.mark.parametrize("size,r", [(32, 2), (64, 3), (128, 5), (256, 8)])
def test_free_space_is_connected(size, r):
    g = rooms_and_corridors(size, random.Random(3), RoomSpec(rooms_per_side=r))
    assert len(connected_components(g, g.free_cells())) == 1


@pytest.mark.parametrize("size,r", [(64, 3), (128, 5)])
def test_area_count_and_structure(size, r):
    """r*r rooms + (r+1)^2 junctions + 2*r*(r+1) corridor segments, possibly a few more
    if an obstacle split a room (A1 enforcement), never fewer."""
    g = rooms_and_corridors(size, random.Random(5), RoomSpec(rooms_per_side=r))
    ag = build_area_graph(g)
    expected = r * r + (r + 1) ** 2 + 2 * r * (r + 1)
    assert len(ag.areas) >= expected
    # every room must be reachable, i.e. the area graph is connected
    seen, stack = set(), [ag.areas[0]]
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        stack.extend(ag.neighbours(a))
    assert seen == set(ag.areas)


def test_adjacent_areas_have_different_labels():
    g = rooms_and_corridors(256, random.Random(9), RoomSpec(rooms_per_side=8))
    ag = build_area_graph(g)
    for a, b in ag.edges:
        assert ag.names[a] != ag.names[b]


def test_uniform_blocks_partition():
    g = rooms_and_corridors(64, random.Random(2))
    ub = uniform_blocks(g, 8)
    # obstacles untouched
    for y in range(64):
        for x in range(64):
            assert (ub.labels[y][x] == BLOCKED) == (g.labels[y][x] == BLOCKED)
    ag = build_area_graph(ub)
    # at most 8x8 cells per area, and at least as many areas as non-empty blocks
    assert all(ag.size(a) <= 64 for a in ag.areas)
    assert len(ag.areas) >= 64 - sum(
        1 for by in range(8) for bx in range(8)
        if all(g.labels[y][x] == BLOCKED for y in range(by * 8, by * 8 + 8) for x in range(bx * 8, bx * 8 + 8))
    )


def test_random_query_is_seeded_and_far_enough():
    g = rooms_and_corridors(64, random.Random(0))
    s1, g1 = random_query(g, random.Random(11), min_distance=20)
    s2, g2 = random_query(g, random.Random(11), min_distance=20)
    assert (s1, g1) == (s2, g2)
    assert s1 != g1 and g.is_free(s1) and g.is_free(g1)
    assert abs(s1[0] - g1[0]) + abs(s1[1] - g1[1]) >= 20


def test_generated_map_round_trips_through_text():
    g = rooms_and_corridors(64, random.Random(4))
    assert Grid.loads(g.dumps()).labels == g.labels

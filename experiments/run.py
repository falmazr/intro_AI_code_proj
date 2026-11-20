"""Experiment runner: every planner on every query of every map, results to CSV.

    python -m experiments.run --config configs/experiment.json [--sizes 16 32] [--planners astar twotier-W1]

Design (report section 6):
* Maps are generated from fixed seeds: map seed = config seed * 1000 + size + 7 * map index.
* Queries are drawn from a per-map ``random.Random`` so every planner sees the
  same (start, goal) pairs.
* ``runtime_ms`` is the median of ``timing_repeats`` timed calls (``perf_counter_ns``);
  node counts come from the first call and are deterministic.
* Preprocessing (``prepare``) is timed separately into ``prep.csv``.
* ``"connectivity": 8`` in the config evaluates the 8-connected variant (octile heuristic).
* Rows are appended as they are produced and existing rows are skipped on
  restart, so a long run can be resumed.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mls.generator import RoomSpec, random_query, rooms_and_corridors, uniform_blocks  # noqa: E402
from mls.grid import Cell, Grid  # noqa: E402
from mls.partition import build_area_graph  # noqa: E402
from mls.planners import make  # noqa: E402
from mls.smoothing import smoothed  # noqa: E402

FIELDS = [
    "map", "size", "map_seed", "query", "sx", "sy", "gx", "gy", "manhattan",
    "planner", "success", "cost", "expanded", "generated", "peak_open", "runtime_ms",
    "legs", "abstract_expanded", "replans", "fallback",
]
PREP_FIELDS = ["map", "size", "map_seed", "planner", "prep_ms", "free_cells", "areas", "edges"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def setting(cfg: dict, size: int, key: str):
    return cfg.get("overrides", {}).get(str(size), {}).get(key, cfg[key])


def map_instances(cfg: dict, sizes: list[int]):
    """Yield (map_id, size, map_seed, grid, queries)."""
    base = cfg["seed"]
    for path in cfg.get("include_maps", []):
        g = Grid.load(ROOT / path, connectivity=cfg.get("connectivity", 4))
        rng = random.Random(base * 1000 + 1)
        n = cfg.get("named_map_queries", 30)
        md = max(1, min(g.width, g.height) // 2)
        qs = [random_query(g, rng, min_distance=md) for _ in range(n)]
        if Path(path).stem == "figure1":
            qs = [((0, 0), (7, 7))] + qs[: n - 1]      # the brief's query first
        yield Path(path).stem, max(g.width, g.height), -1, g, qs
    for size in sizes:
        r = cfg["rooms_per_side"][str(size)]
        for m in range(setting(cfg, size, "maps_per_size")):
            seed = base * 1000 + size + 7 * m
            g = rooms_and_corridors(size, random.Random(seed), RoomSpec(rooms_per_side=r))
            g.connectivity = cfg.get("connectivity", 4)
            rng = random.Random(seed + 1)
            md = int(size * cfg.get("min_distance_fraction", 0.5))
            qs = [random_query(g, rng, min_distance=md) for _ in range(setting(cfg, size, "queries_per_map"))]
            yield f"gen{size}-{m}", size, seed, g, qs


def build_planner(spec: dict, grid: Grid) -> tuple[object, Grid]:
    """Instantiate a planner for ``grid`` and return it with the grid it should plan on."""
    p = make(spec["name"], **spec.get("kwargs", {}))
    g = grid
    if spec.get("partition") == "blocks":
        g = uniform_blocks(grid, spec["block"])
    return p, g


def timed_plan(p, grid: Grid, s: Cell, t: Cell, repeats: int, smooth: int | None):
    times = []
    result = None
    for _ in range(max(1, repeats)):
        t0 = time.perf_counter_ns()
        r = p.plan(s, t)
        if smooth:
            r = smoothed(r, grid, smooth)
        times.append((time.perf_counter_ns() - t0) / 1e6)
        result = result or r
    return result, statistics.median(times)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/experiment.json")
    ap.add_argument("--sizes", nargs="*", type=int)
    ap.add_argument("--planners", nargs="*")
    ap.add_argument("--no-named-maps", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(ROOT / args.config)
    sizes = args.sizes or cfg["sizes"]
    if args.no_named_maps:
        cfg["include_maps"] = []
    specs = [s for s in cfg["planners"] if not args.planners or s["id"] in args.planners]

    out = ROOT / cfg["output"]
    prep_out = ROOT / cfg["prep_output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple] = set()
    if out.exists():
        with out.open(newline="") as f:
            for row in csv.DictReader(f):
                done.add((row["map"], int(row["query"]), row["planner"]))
    new_file = not out.exists()
    fout = out.open("a", newline="")
    w = csv.DictWriter(fout, fieldnames=FIELDS)
    if new_file:
        w.writeheader()
    prep_new = not prep_out.exists()
    fprep = prep_out.open("a", newline="")
    wp = csv.DictWriter(fprep, fieldnames=PREP_FIELDS)
    if prep_new:
        wp.writeheader()

    for map_id, size, map_seed, grid, queries in map_instances(cfg, sizes):
        repeats = setting(cfg, size, "timing_repeats") if map_seed >= 0 else cfg["timing_repeats"]
        for spec in specs:
            if size < spec.get("min_size", 0) or size > spec.get("max_size", 10**9):
                continue
            pending = [(i, q) for i, q in enumerate(queries) if (map_id, i, spec["id"]) not in done]
            if not pending:
                continue
            p, g = build_planner(spec, grid)
            t0 = time.perf_counter_ns()
            p.prepare(g)
            prep_ms = (time.perf_counter_ns() - t0) / 1e6
            ag = getattr(p, "graph", None)
            if ag is None:
                ag = build_area_graph(Grid(g.width, g.height, [r[:] for r in g.labels]))
            wp.writerow({"map": map_id, "size": size, "map_seed": map_seed, "planner": spec["id"],
                         "prep_ms": f"{prep_ms:.3f}", "free_cells": g.count_free(),
                         "areas": len(ag.areas), "edges": len(ag.edges)})
            fprep.flush()
            t_start = time.perf_counter()
            for i, (s, t) in pending:
                r, ms = timed_plan(p, g, s, t, repeats, spec.get("smooth"))
                w.writerow({
                    "map": map_id, "size": size, "map_seed": map_seed, "query": i,
                    "sx": s[0], "sy": s[1], "gx": t[0], "gy": t[1],
                    "manhattan": abs(s[0] - t[0]) + abs(s[1] - t[1]),
                    "planner": spec["id"], "success": int(r.success),
                    "cost": f"{r.cost:.4f}" if r.success else "",
                    "expanded": r.expanded, "generated": r.generated, "peak_open": r.peak_open,
                    "runtime_ms": f"{ms:.4f}",
                    "legs": r.extra.get("legs", 1), "abstract_expanded": r.extra.get("abstract_expanded", 0),
                    "replans": r.extra.get("replans", 0), "fallback": int(bool(r.extra.get("fallback", False))),
                })
            fout.flush()
            print(f"{map_id:>12} {spec['id']:>20}: {len(pending):3d} queries, prep {prep_ms:7.1f} ms, "
                  f"{time.perf_counter() - t_start:6.1f} s", flush=True)
    fout.close()
    fprep.close()


if __name__ == "__main__":
    main()

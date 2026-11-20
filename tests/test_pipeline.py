"""End-to-end smoke tests: smoothing and the experiment runner + analysis."""

import csv
import random
import subprocess
import sys
from pathlib import Path

import pytest

from mls.generator import random_query, rooms_and_corridors
from mls.grid import Grid
from mls.planners import make
from mls.smoothing import smoothed

ROOT = Path(__file__).resolve().parents[1]


def test_corridor_refine_never_worsens_and_counts_expansions():
    g = rooms_and_corridors(64, random.Random(21))
    p = make("twotier")
    p.prepare(g)
    rng = random.Random(22)
    for _ in range(10):
        s, t = random_query(g, rng, min_distance=20)
        r = p.plan(s, t)
        r2 = smoothed(r, g, radius=2)
        assert r2.cost <= r.cost + 1e-9
        assert r2.expanded >= r.expanded and r2.extra["smoothing_expanded"] >= 0
        assert r2.path[0] == s and r2.path[-1] == t


def test_runner_and_analyze_on_smoke_config(tmp_path):
    """The experiment pipeline runs end to end on a tiny config and produces consistent files."""
    import json
    cfg = json.loads((ROOT / "configs" / "smoke.json").read_text())
    cfg["output"] = str(tmp_path / "smoke.csv")
    cfg["prep_output"] = str(tmp_path / "smoke_prep.csv")
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    env = {"PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-m", "experiments.run", "--config", str(cfg_path)],
                   cwd=ROOT, check=True, capture_output=True, env={**env, **_path_env()})
    rows = list(csv.DictReader((tmp_path / "smoke.csv").open()))
    assert rows and all(r["success"] == "1" for r in rows)
    planners = {r["planner"] for r in rows}
    assert "astar" in planners and "twotier-W1" in planners
    # optimal planners agree with A*; two-tier never beats it
    opt = {(r["map"], r["query"]): float(r["cost"]) for r in rows if r["planner"] == "astar"}
    for r in rows:
        c = float(r["cost"])
        if r["planner"] in ("bfs", "dijkstra", "twotier-W2"):
            assert c == pytest.approx(opt[(r["map"], r["query"])])
        else:
            assert c >= opt[(r["map"], r["query"])] - 1e-9
    # resume: a second run adds nothing
    before = len(rows)
    subprocess.run([sys.executable, "-m", "experiments.run", "--config", str(cfg_path)],
                   cwd=ROOT, check=True, capture_output=True, env={**env, **_path_env()})
    assert len(list(csv.DictReader((tmp_path / "smoke.csv").open()))) == before
    # analysis
    subprocess.run([sys.executable, "-m", "experiments.analyze", "--results", str(tmp_path / "smoke.csv"),
                    "--prep", str(tmp_path / "smoke_prep.csv"), "--ablation-size", "32", "--outdir", str(tmp_path / "out")],
                   cwd=ROOT, check=True, capture_output=True, env={**env, **_path_env()})
    assert (tmp_path / "out" / "summary.csv").exists()
    assert (tmp_path / "out" / "figures" / "nodes_vs_size.png").exists()


def _path_env():
    import os
    return {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "TEMP", "TMP")}

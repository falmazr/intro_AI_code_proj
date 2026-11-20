"""Summary statistics and figures from results/main.csv.

    python -m experiments.analyze [--results results/main.csv] [--ablation-size 128]

Writes:
    results/summary.csv       per (size, planner): n, mean/std/CI95 of nodes, runtime, cost ratio; median/max ratio
    results/summary.md        the same as a Markdown table for the report
    results/ablation.md       the ablation table at --ablation-size (weight model x leg goal x smoothing)
    results/crossover.md      the smallest size at which each two-tier variant beats flat A* on runtime and on nodes
    results/distance_buckets.md  nodes and cost ratio by start-goal distance
    results/paired_tests.md   paired log-ratio of nodes vs A* with CI and sign-test p-values
    results/environment.txt   python, OS and CPU the timings came from
    results/figures/*.png     nodes-vs-size, runtime-vs-size, cost-overhead bars, savings-vs-overhead scatter, prep time

Cost ratio = planner cost / flat A* cost on the same (map, query); 1.0 = optimal.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Fixed categorical order (validated palette, light mode). Identity follows the planner, never its rank.
PALETTE = {
    "astar": "#2a78d6", "twotier-W1": "#eb6834", "twotier-W2": "#1baf7a", "wastar1.5": "#eda100",
    "bfs": "#e87ba4", "dijkstra": "#008300", "hpa-blocks16": "#6250d6", "twotier-W1-smooth": "#e34948",
    "twotier-W0": "#d55181", "twotier-W1-nearest": "#d55181",
}
LABEL = {
    "astar": "Flat A*", "bfs": "BFS", "dijkstra": "Dijkstra", "wastar1.5": "Weighted A* (1.5)",
    "twotier-W0": "Two-tier W0 (hops)", "twotier-W1": "Two-tier W1 (centroids)",
    "twotier-W1-nearest": "Two-tier W1, nearest-entry legs", "twotier-W1-smooth": "Two-tier W1 + corridor refine",
    "twotier-W2": "Two-tier W2 (HPA*, rooms)", "hpa-blocks16": "HPA*, 16x16 blocks",
}
MAIN_LINES = ["astar", "bfs", "dijkstra", "wastar1.5", "twotier-W1", "twotier-W2"]
DIRECT_LABELS = ["astar", "wastar1.5", "twotier-W1", "twotier-W2"]  # <= 4 direct labels; the legend carries the rest
VARIANTS = ["twotier-W0", "twotier-W1", "twotier-W1-nearest", "twotier-W1-smooth", "twotier-W2", "hpa-blocks16"]
PLOT_VARIANTS = ["twotier-W0", "twotier-W1", "twotier-W1-smooth", "twotier-W2", "hpa-blocks16"]  # W1-nearest is identical to W1 on these maps


def ci95(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))


def load(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["size"] = int(r["size"])
        r["expanded"] = int(r["expanded"])
        r["runtime_ms"] = float(r["runtime_ms"])
        r["success"] = int(r["success"])
        r["cost"] = float(r["cost"]) if r["cost"] else math.inf
        r["generated"] = int(r["generated"])
        r["peak_open"] = int(r["peak_open"])
        r["fallback"] = int(r.get("fallback", 0) or 0)
    return rows


def attach_ratios(rows: list[dict]) -> None:
    opt = {(r["map"], r["query"]): r for r in rows if r["planner"] == "astar"}
    for r in rows:
        a = opt.get((r["map"], r["query"]))
        o = a["cost"] if a else None
        r["ratio"] = (r["cost"] / o) if (o and r["success"] and o > 0) else math.nan
        r["nodes_saved"] = (a["expanded"] / r["expanded"]) if (a and r["expanded"]) else math.nan


def group(rows: list[dict], generated_only: bool = True):
    g: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in rows:
        if generated_only and not r["map"].startswith("gen"):
            continue
        g[(r["size"], r["planner"])].append(r)
    return g


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for (size, planner), rs in sorted(group(rows).items()):
        ex = [r["expanded"] for r in rs]
        rt = [r["runtime_ms"] for r in rs]
        ra = [r["ratio"] for r in rs if not math.isnan(r["ratio"])]
        out.append({
            "size": size, "planner": planner, "n": len(rs),
            "success_rate": sum(r["success"] for r in rs) / len(rs),
            "nodes_mean": statistics.mean(ex), "nodes_std": statistics.pstdev(ex), "nodes_ci95": ci95(ex),
            "runtime_ms_mean": statistics.mean(rt), "runtime_ms_std": statistics.pstdev(rt), "runtime_ms_ci95": ci95(rt),
            "ratio_mean": statistics.mean(ra) if ra else math.nan,
            "ratio_std": statistics.pstdev(ra) if ra else math.nan,
            "ratio_median": statistics.median(ra) if ra else math.nan,
            "ratio_max": max(ra) if ra else math.nan,
            "ratio_p95": sorted(ra)[int(0.95 * (len(ra) - 1))] if ra else math.nan,
            "fallbacks": sum(r["fallback"] for r in rs),
        })
    return out


def write_summary(summary: list[dict], out_csv: Path, out_md: Path) -> None:
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    lines = ["| Size | Planner | n | Nodes expanded (mean ± 95% CI) | Runtime ms (mean ± 95% CI) | Cost ratio mean | median | max |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in summary:
        lines.append(f"| {s['size']} | {LABEL.get(s['planner'], s['planner'])} | {s['n']} | "
                     f"{s['nodes_mean']:.0f} ± {s['nodes_ci95']:.0f} | {s['runtime_ms_mean']:.2f} ± {s['runtime_ms_ci95']:.2f} | "
                     f"{s['ratio_mean']:.3f} | {s['ratio_median']:.3f} | {s['ratio_max']:.3f} |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_crossover(summary: list[dict], out: Path) -> None:
    by = {(s["size"], s["planner"]): s for s in summary}
    sizes = sorted({s["size"] for s in summary})
    lines = ["| Variant | First size where runtime < flat A* | First size where nodes < flat A* | Nodes saved at largest size |",
             "| --- | --- | --- | --- |"]
    for v in VARIANTS:
        rt = next((n for n in sizes if (n, v) in by and by[(n, v)]["runtime_ms_mean"] < by[(n, "astar")]["runtime_ms_mean"]), None)
        nd = next((n for n in sizes if (n, v) in by and by[(n, v)]["nodes_mean"] < by[(n, "astar")]["nodes_mean"]), None)
        big = max((n for n in sizes if (n, v) in by), default=None)
        saved = (by[(big, "astar")]["nodes_mean"] / by[(big, v)]["nodes_mean"]) if big else math.nan
        lines.append(f"| {LABEL[v]} | {rt or 'never'} | {nd or 'never'} | {saved:.1f}x at {big} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ablation(rows: list[dict], size: int, out: Path) -> None:
    g = group(rows)
    lines = [f"Ablation at {size}x{size} (generated maps). Cost ratio relative to flat A* on the same query.", "",
             "| Variant | Weight model | Leg goal | Post-process | Nodes (mean) | Cost ratio mean | p95 | max | Runtime ms |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    meta = {
        "twotier-W0": ("W0 hops", "first cell", "none"), "twotier-W1": ("W1 centroid", "first cell", "none"),
        "twotier-W1-nearest": ("W1 centroid", "nearest entry", "none"), "twotier-W1-smooth": ("W1 centroid", "first cell", "corridor refine r=2"),
        "twotier-W2": ("W2 portal dist.", "chosen portal", "none"), "hpa-blocks16": ("W2 on 16x16 blocks", "chosen portal", "none"),
        "astar": ("-", "-", "-"), "wastar1.5": ("-", "-", "-"),
    }
    for v in ["astar", "wastar1.5"] + VARIANTS:
        rs = g.get((size, v), [])
        if not rs:
            continue
        ra = [r["ratio"] for r in rs if not math.isnan(r["ratio"])]
        wm, lg, pp = meta[v]
        lines.append(f"| {LABEL[v]} | {wm} | {lg} | {pp} | {statistics.mean(r['expanded'] for r in rs):.0f} | "
                     f"{statistics.mean(ra):.3f} | {sorted(ra)[int(0.95 * (len(ra) - 1))]:.3f} | {max(ra):.3f} | "
                     f"{statistics.mean(r['runtime_ms'] for r in rs):.2f} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_distance_buckets(rows: list[dict], out: Path) -> None:
    """Nodes and cost ratio by start-goal Manhattan distance (as a fraction of the grid side)."""
    buckets = [(0.5, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, 9.0)]
    planners = ["astar", "wastar1.5", "twotier-W1", "twotier-W2"]
    lines = ["Results by start-goal Manhattan distance, as a fraction of the grid side (generated maps, all sizes pooled).", "",
             "| Distance / side | n | " + " | ".join(f"{LABEL[p]} nodes" for p in planners) + " | W1 cost ratio | W1 % suboptimal |",
             "| --- | --- | " + " | ".join("---" for _ in planners) + " | --- | --- |"]
    for lo, hi in buckets:
        sel = [r for r in rows if r["map"].startswith("gen") and lo <= int(r["manhattan"]) / r["size"] < hi]
        if not sel:
            continue
        cells = []
        for p in planners:
            rs = [r for r in sel if r["planner"] == p]
            cells.append(f"{statistics.mean(r['expanded'] for r in rs):.0f}" if rs else "-")
        w1 = [r for r in sel if r["planner"] == "twotier-W1" and not math.isnan(r["ratio"])]
        n = len({(r["map"], r["query"]) for r in sel})
        lines.append(f"| {lo:.2f}-{hi:.2f} | {n} | " + " | ".join(cells) +
                     f" | {statistics.mean(r['ratio'] for r in w1):.3f} | {100 * sum(r['ratio'] > 1.0005 for r in w1) / len(w1):.0f}% |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_paired_tests(rows: list[dict], out: Path) -> None:
    """Paired comparison of nodes expanded against flat A* on identical queries.

    For each size and variant: mean of the per-query log-ratio log(nodes_variant / nodes_astar),
    its 95% CI, and the sign-test p-value (two-sided, exact binomial) for "variant expands fewer".
    A paired test is the right one here because every planner saw the same (map, query) pairs.
    """
    from math import comb

    def sign_test_p(wins: int, n: int) -> float:
        k = min(wins, n - wins)
        return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

    base = {(r["map"], r["query"]): r["expanded"] for r in rows if r["planner"] == "astar"}
    sizes = sorted({r["size"] for r in rows if r["map"].startswith("gen")})
    lines = ["Paired comparison with flat A* on identical queries (generated maps).", "",
             "| Size | Variant | n | Geometric mean nodes ratio (variant / A*) | 95% CI | Queries with fewer nodes | Sign-test p |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for n_ in sizes:
        for v in ["wastar1.5", "twotier-W1", "twotier-W2", "hpa-blocks16"]:
            rs = [r for r in rows if r["map"].startswith("gen") and r["size"] == n_ and r["planner"] == v]
            if not rs:
                continue
            logs = [math.log(r["expanded"] / base[(r["map"], r["query"])]) for r in rs if r["expanded"] and base[(r["map"], r["query"])]]
            wins = sum(1 for x in logs if x < 0)
            m, c = statistics.mean(logs), ci95(logs)
            lines.append(f"| {n_} | {LABEL[v]} | {len(logs)} | {math.exp(m):.3f} | [{math.exp(m - c):.3f}, {math.exp(m + c):.3f}] | "
                         f"{wins}/{len(logs)} | {sign_test_p(wins, len(logs)):.2g} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_environment(out: Path) -> None:
    import platform
    import sys as _sys
    lines = [f"python: {_sys.version.split()[0]}", f"platform: {platform.platform()}",
             f"machine: {platform.machine()}", f"processor: {platform.processor() or 'n/a'}"]
    try:
        cpu = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        lines.append(f"cpu: {cpu}")
    except Exception:
        pass
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def figures(rows: list[dict], summary: list[dict], prep_rows: list[dict], outdir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6,
                         "axes.edgecolor": "#8a8a8a", "legend.frameon": False})
    outdir.mkdir(parents=True, exist_ok=True)
    by = {(s["size"], s["planner"]): s for s in summary}
    sizes = sorted({s["size"] for s in summary})

    def line_plot(metric: str, ylabel: str, fname: str, planners: list[str], title: str):
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ends: list[tuple[float, float, str]] = []
        for p in planners:
            xs = [n for n in sizes if (n, p) in by]
            ys = [by[(n, p)][f"{metric}_mean"] for n in xs]
            es = [by[(n, p)][f"{metric}_ci95"] for n in xs]
            if not xs:
                continue
            ax.errorbar(xs, ys, yerr=es, color=PALETTE[p], lw=2, marker="o", ms=5, capsize=3, label=LABEL[p])
            if p in DIRECT_LABELS:
                ends.append((xs[-1], ys[-1], LABEL[p]))
        # Direct labels at the line ends, pushed apart (log scale) so they never overlap.
        ends.sort(key=lambda e: e[1])
        placed: list[float] = []
        for x, y, text in ends:
            yy = y
            if placed and yy / placed[-1] < 1.35:
                yy = placed[-1] * 1.35
            placed.append(yy)
            ax.annotate(text, (x, yy), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8.5, color="#333333")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks(sizes)
        ax.set_xticklabels([f"{n}x{n}" for n in sizes])
        ax.set_xlabel("Grid size (cells per side)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontsize=11)
        ax.legend(fontsize=8.5, loc="upper left")
        fig.tight_layout()
        fig.savefig(outdir / fname, dpi=160)
        plt.close(fig)

    line_plot("nodes", "Nodes expanded (mean, 95% CI)", "nodes_vs_size.png", MAIN_LINES,
              "Hierarchical search expands far fewer nodes as the map grows")
    line_plot("runtime_ms", "Query runtime, ms (mean, 95% CI)", "runtime_vs_size.png", MAIN_LINES,
              "Runtime follows node counts once the map is large enough")

    # Cost overhead per size: mean excess over optimal, and share of queries that are suboptimal
    g = group(rows)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 6.2), sharex=True)
    width = 0.8 / len(PLOT_VARIANTS)
    for k, v in enumerate(PLOT_VARIANTS):
        xs, ov, sh = [], [], []
        for i, n in enumerate(sizes):
            rs = g.get((n, v), [])
            ra = [r["ratio"] for r in rs if not math.isnan(r["ratio"])]
            if not ra:
                continue
            xs.append(i + (k - (len(PLOT_VARIANTS) - 1) / 2) * width)
            ov.append(100 * (statistics.mean(ra) - 1))
            sh.append(100 * sum(1 for x in ra if x > 1.0005) / len(ra))
        ax1.bar(xs, ov, width=width * 0.92, color=PALETTE[v], label=LABEL[v])
        ax2.bar(xs, sh, width=width * 0.92, color=PALETTE[v], label=LABEL[v])
    ax1.set_ylabel("Mean path-cost overhead, %")
    ax2.set_ylabel("Queries longer than optimal, %")
    ax2.set_xticks(range(len(sizes)))
    ax2.set_xticklabels([f"{n}x{n}" for n in sizes])
    ax2.set_xlabel("Grid size (cells per side)")
    ax1.set_title("Greedy two-tier paths are a few percent long; W2 (HPA*) is optimal on these maps", loc="left", fontsize=11)
    ax1.set_ylim(0, ax1.get_ylim()[1] * 1.45)
    ax1.legend(fontsize=8.5, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(outdir / "cost_overhead.png", dpi=160)
    plt.close(fig)

    # Savings vs overhead scatter at the largest size with both planners
    big = max(sizes)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for v in ["twotier-W1", "twotier-W2", "wastar1.5"]:
        rs = g.get((big, v), [])
        xs = [r["nodes_saved"] for r in rs if not math.isnan(r["nodes_saved"])]
        ys = [r["ratio"] for r in rs if not math.isnan(r["nodes_saved"])]
        ax.scatter(xs, ys, s=22, color=PALETTE[v], alpha=0.75, edgecolor="white", lw=0.6, label=LABEL[v])
    ax.axhline(1.0, color="#8a8a8a", lw=1, ls="--")
    ax.set_xscale("log")
    ax.set_xlabel("Node savings vs flat A* (x fewer expansions, log)")
    ax.set_ylabel("Path cost / optimal")
    ax.set_title(f"Per-query trade-off at {big}x{big}: savings against overhead", loc="left", fontsize=11)
    ax.legend(fontsize=8.5)
    fig.tight_layout()
    fig.savefig(outdir / "savings_vs_overhead.png", dpi=160)
    plt.close(fig)

    # Preprocessing time per map size
    if prep_rows:
        pb: dict[tuple[int, str], list[float]] = defaultdict(list)
        for r in prep_rows:
            if r["map"].startswith("gen"):
                pb[(int(r["size"]), r["planner"])].append(float(r["prep_ms"]))
        fig, ax = plt.subplots(figsize=(6.4, 3.8))
        for v in ["twotier-W1", "twotier-W2", "hpa-blocks16"]:
            xs = [n for n in sizes if (n, v) in pb]
            if not xs:
                continue
            ax.plot(xs, [statistics.mean(pb[(n, v)]) for n in xs], color=PALETTE[v], lw=2, marker="o", ms=5, label=LABEL[v])
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks(sizes)
        ax.set_xticklabels([f"{n}x{n}" for n in sizes])
        ax.set_ylabel("Preprocessing per map, ms")
        ax.set_title("One-off preprocessing cost grows roughly linearly with cells", loc="left", fontsize=11)
        ax.legend(fontsize=8.5)
        fig.tight_layout()
        fig.savefig(outdir / "prep_time.png", dpi=160)
        plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="results/main.csv")
    ap.add_argument("--prep", default="results/prep.csv")
    ap.add_argument("--ablation-size", type=int, default=128)
    ap.add_argument("--outdir", default="results", help="where summary/ablation/figures are written")
    args = ap.parse_args(argv)
    rows = load(ROOT / args.results)
    attach_ratios(rows)
    summary = summarise(rows)
    res = ROOT / args.outdir if not Path(args.outdir).is_absolute() else Path(args.outdir)
    res.mkdir(parents=True, exist_ok=True)
    write_summary(summary, res / "summary.csv", res / "summary.md")
    write_crossover(summary, res / "crossover.md")
    write_ablation(rows, args.ablation_size, res / "ablation.md")
    write_distance_buckets(rows, res / "distance_buckets.md")
    write_paired_tests(rows, res / "paired_tests.md")
    write_environment(res / "environment.txt")
    prep_rows = []
    if (ROOT / args.prep).exists():
        with (ROOT / args.prep).open(newline="") as f:
            prep_rows = list(csv.DictReader(f))
    figures(rows, summary, prep_rows, res / "figures")
    print((res / "crossover.md").read_text())
    print((res / "ablation.md").read_text())


if __name__ == "__main__":
    main()

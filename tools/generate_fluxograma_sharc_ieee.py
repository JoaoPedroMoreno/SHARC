"""Generate the IEEE SHARC workflow flowchart as PNG/PDF."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "figuras" / "fluxograma_sharc_ieee"


STEPS = [
    ("Input YAML File", "scenario parameters, victim system,\nMSS_DC topology and physical models"),
    ("SHARC Python Engine", "parameter parsing, initialization\nand pseudo-random seed control"),
    ("Monte Carlo Loop", "10 000 snapshots"),
    ("Geometry Generation", "NGSO satellites, active beams and FS receiver"),
    ("Spatial Criteria", "visibility, elevation, service area and exclusion"),
    ("Mitigation", "power back-off and exclusion zone"),
    ("Link Budget Calculation", "antenna gains and propagation losses"),
    ("Aggregate Interference", "summation of active beam contributions"),
    ("I/N Calculation", "received interference and thermal noise"),
    ("Statistical Results", "CSV files, CDF/CCDF, percentiles\nand protection margins"),
]


def add_box(ax, x: float, y: float, w: float, h: float, step: int, title: str, desc: str, module: bool) -> None:
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor="#f8fafc" if module else "white",
        edgecolor="#111827",
        linewidth=1.35,
    )
    ax.add_patch(rect)
    badge = Circle((x + 0.055, y + h - 0.055), 0.032, facecolor="#1f4e79", edgecolor="#1f4e79", linewidth=0.7)
    ax.add_patch(badge)
    ax.text(x + 0.055, y + h - 0.058, str(step), ha="center", va="center", color="white", fontsize=14, fontweight="bold")
    ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=16, fontweight="bold", color="#111827")
    ax.text(x + w / 2, y + h * 0.28, desc, ha="center", va="center", fontsize=12.6, color="#374151", linespacing=1.18)


def add_arrow(ax, x: float, y0: float, y1: float) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x, y0),
            (x, y1),
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.15,
            color="#111827",
            shrinkA=0,
            shrinkB=0,
        )
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(3.5, 7.0), dpi=600)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.982, "SHARC Simulation Workflow", ha="center", va="top", fontsize=19, fontweight="bold", color="#111827")

    x, w = 0.08, 0.84
    h = 0.064
    y_positions = [0.89, 0.79, 0.69, 0.575, 0.49, 0.405, 0.32, 0.235, 0.15, 0.045]
    loop = FancyBboxPatch(
        (0.045, 0.123),
        0.91,
        0.555,
        boxstyle="round,pad=0.006,rounding_size=0.014",
        facecolor="none",
        edgecolor="#1f2937",
        linewidth=1.1,
        linestyle=(0, (4, 3)),
    )
    ax.add_patch(loop)
    ax.text(0.07, 0.662, "Processing in Each Snapshot", ha="left", va="center", fontsize=15.5, fontweight="bold", color="#111827")

    for idx, ((title, desc), y) in enumerate(zip(STEPS, y_positions), start=1):
        box_h = 0.072 if idx in {1, 2, 10} else h
        add_box(ax, x if idx not in range(4, 10) else 0.115, y, w if idx not in range(4, 10) else 0.77, box_h, idx, title, desc, idx in range(4, 10))
        if idx < 10:
            y0 = y - 0.002
            y1 = y_positions[idx] + (0.072 if idx + 1 in {1, 2, 10} else h) + 0.002
            add_arrow(ax, 0.5, y0, y1)

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_BASE.with_suffix(".png"), dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT_BASE.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"[ok] {OUT_BASE.with_suffix('.png')}")
    print(f"[ok] {OUT_BASE.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()

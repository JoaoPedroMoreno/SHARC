"""Generate the compact IEEE workflow figure for campaign 02 DC-MSS-to-FS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "figuras" / "fluxograma_sharc_ieee"

INK = "#111827"
SECONDARY_INK = "#374151"
ACCENT = "#1f4e79"
SNAPSHOT_FILL = "#f8fafc"


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    description: str


STEPS = {
    1: Step(
        1,
        "Input YAML Configuration",
        "scenario, DC-MSS-IMT / FS, propagation",
    ),
    2: Step(
        2,
        "Engine Initialization and Monte Carlo Loop",
        "parameters, seeds, 10,000 snapshots",
    ),
    3: Step(
        3,
        "Geometry Generation",
        "NGSO constellation, grid and FS receiver",
    ),
    4: Step(
        4,
        "Satellite / Cell Selection",
        r"$5^\circ$ eligibility / highest elevation / $32^\circ$ threshold",
    ),
    5: Step(
        5,
        "Scenario-Specific Beam Control",
        "candidate filter ($R_{\\mathrm{ez}}$) / 10 dB back-off",
    ),
    6: Step(
        6,
        "Beam Assignment / Activity",
        "beam placement; LF-based activation",
    ),
    7: Step(
        7,
        "Per-Beam Interference",
        "gains, losses and spectral overlap",
    ),
    8: Step(
        8,
        "Aggregate Interference and INR",
        "linear beam sum; FS thermal noise",
    ),
    9: Step(
        9,
        "Statistical Post-Processing",
        "$\\mathrm{INR}_{20\\%}$, bootstrap $\\mathrm{CI}_{95\\%}$, $M_{20}$ classification",
    ),
}


def add_box(
    ax,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    step: Step,
    snapshot_step: bool,
    title_size: float = 16.6,
    description_size: float = 14.4,
) -> None:
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.006,rounding_size=0.014",
        facecolor=SNAPSHOT_FILL if snapshot_step else "white",
        edgecolor=INK,
        linewidth=1.05,
    )
    ax.add_patch(box)

    badge_x = x + 0.004
    badge_y = y + height / 2
    ax.text(
        badge_x,
        badge_y,
        str(step.number),
        ha="center",
        va="center",
        color="white",
        fontsize=15.0,
        fontweight="bold",
        bbox={
            "boxstyle": "circle,pad=0.20",
            "facecolor": ACCENT,
            "edgecolor": ACCENT,
            "linewidth": 0.5,
        },
        zorder=4,
    )

    content_center_x = x + width / 2 + 0.024
    ax.text(
        content_center_x,
        y + height * 0.70,
        step.title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="bold",
        color=INK,
        linespacing=0.90,
    )
    ax.text(
        content_center_x,
        y + height * 0.25,
        step.description,
        ha="center",
        va="center",
        fontsize=description_size,
        color=SECONDARY_INK,
        linespacing=0.90,
    )


def add_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    connectionstyle: str = "arc3",
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=8.5,
            linewidth=0.95,
            color=INK,
            shrinkA=1.0,
            shrinkB=1.0,
            connectionstyle=connectionstyle,
            zorder=3,
        )
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(7.1, 7.6), dpi=600)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.145, 1.04)
    ax.axis("off")

    ax.text(
        0.5,
        1.025,
        "Simulation Workflow",
        ha="center",
        va="top",
        fontsize=18.0,
        fontweight="bold",
        color=INK,
    )

    full_x = 0.035
    full_width = 0.93
    outer_box_height = 0.090
    add_box(
        ax,
        x=full_x,
        y=0.855,
        width=full_width,
        height=outer_box_height,
        step=STEPS[1],
        snapshot_step=False,
    )
    add_box(
        ax,
        x=full_x,
        y=0.730,
        width=full_width,
        height=outer_box_height,
        step=STEPS[2],
        snapshot_step=False,
        title_size=14.4,
    )
    add_arrow(ax, (0.5, 0.854), (0.5, 0.821))

    snapshot_x = 0.035
    snapshot_y = -0.015
    snapshot_width = 0.93
    snapshot_height = 0.710
    snapshot_frame = FancyBboxPatch(
        (snapshot_x, snapshot_y),
        snapshot_width,
        snapshot_height,
        boxstyle="round,pad=0.005,rounding_size=0.012",
        facecolor="none",
        edgecolor="#1f2937",
        linewidth=0.9,
        linestyle=(0, (4, 3)),
    )
    ax.add_patch(snapshot_frame)
    ax.text(
        0.5,
        snapshot_y + snapshot_height - 0.026,
        "Processing in Each Snapshot",
        ha="center",
        va="center",
        fontsize=15.3,
        fontweight="bold",
        color=INK,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8},
        zorder=4,
    )

    snapshot_box_x = 0.050
    snapshot_box_width = 0.90
    snapshot_box_height = 0.090
    snapshot_rows = (0.545, 0.435, 0.325, 0.215, 0.105, -0.005)
    for number, y in zip(range(3, 9), snapshot_rows):
        add_box(
            ax,
            x=snapshot_box_x,
            y=y,
            width=snapshot_box_width,
            height=snapshot_box_height,
            step=STEPS[number],
            snapshot_step=True,
            description_size=13.8 if number == 4 else 14.4,
        )

    add_arrow(ax, (0.5, 0.729), (0.5, snapshot_y + snapshot_height))
    for upper_y, lower_y in zip(snapshot_rows, snapshot_rows[1:]):
        add_arrow(ax, (0.5, upper_y), (0.5, lower_y + snapshot_box_height))

    final_y = -0.130
    final_height = 0.090
    add_box(
        ax,
        x=full_x,
        y=final_y,
        width=full_width,
        height=final_height,
        step=STEPS[9],
        snapshot_step=False,
        title_size=16.0,
        description_size=14.4,
    )
    add_arrow(
        ax,
        (0.5, snapshot_rows[-1]),
        (0.5, final_y + final_height),
    )

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_BASE.with_suffix(".png"), dpi=600, bbox_inches="tight", pad_inches=0.015)
    fig.savefig(OUT_BASE.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.015)
    fig.savefig(OUT_BASE.with_suffix(".svg"), bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)
    print(f"[ok] {OUT_BASE.with_suffix('.png')}")
    print(f"[ok] {OUT_BASE.with_suffix('.pdf')}")
    print(f"[ok] {OUT_BASE.with_suffix('.svg')}")


if __name__ == "__main__":
    main()

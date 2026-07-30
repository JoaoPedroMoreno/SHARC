"""Generate a simplified INR CCDF figure that visually explains protection margin.

The plot is intended for a paper: it uses only a few representative curves and
annotates the margin definition at 20% exceedance:

    protection_margin = -6 dB - INR_20%

Positive margin: INR_20% is left of the -6 dB criterion.
Negative margin: INR_20% is right of the -6 dB criterion.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_system_inr_ccdf import (
    AREA_LABELS,
    FIELD,
    Y_LOG_FLOOR,
    Scenario,
    compute_ccdf,
    discover_scenarios,
    read_series_csv,
    scenario_sort_key,
)


PROTECTION_LIMIT_DB = -6.0
EXCEEDANCE_PROBABILITY = 0.2
FIG_WIDTH_IN = 7.16
FIG_HEIGHT_IN = 3.45
IEEE_DPI = 600

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 9.5,
        "axes.titlesize": 9.8,
        "axes.labelsize": 10.0,
        "xtick.labelsize": 9.0,
        "ytick.labelsize": 9.0,
        "legend.fontsize": 8.2,
        "lines.linewidth": 1.7,
        "axes.linewidth": 0.8,
        "savefig.dpi": IEEE_DPI,
    }
)


def inr_at_exceedance_probability(samples: np.ndarray, probability: float) -> float:
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return math.nan
    x.sort()
    index = int(math.ceil((1.0 - probability) * x.size)) - 1
    index = max(0, min(index, x.size - 1))
    return float(x[index])


def select_scenarios(
    scenarios: list[Scenario],
    area: str,
    altitude_km: int,
    fs_height_m: int,
    margins_km: set[int],
) -> list[Scenario]:
    selected = [
        scenario
        for scenario in scenarios
        if scenario.area == area
        and scenario.altitude_km == altitude_km
        and scenario.fs_height_m == fs_height_m
        and scenario.margin_km in margins_km
        and scenario.load_factor_pct in {20, 50}
    ]
    return sorted(selected, key=scenario_sort_key)


def style_for(scenario: Scenario) -> tuple[str, str]:
    colors = {
        0: "#D55E00",
        60: "#0072B2",
    }
    if scenario.margin_km not in colors:
        colors[scenario.margin_km] = "#009E73"
    linestyle = "-" if scenario.load_factor_pct == 20 else "--"
    return colors[scenario.margin_km], linestyle


def plot_explainer(scenarios: list[Scenario], out_path: Path) -> None:
    if not scenarios:
        raise ValueError("no scenarios selected")

    fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN), dpi=IEEE_DPI, constrained_layout=True)

    loaded: list[tuple[Scenario, np.ndarray, float]] = []
    for scenario in scenarios:
        samples = read_series_csv(scenario.folder / f"{FIELD}.csv", FIELD)
        if samples is None or samples.size == 0:
            print(f"[skip] no data in {scenario.folder / f'{FIELD}.csv'}")
            continue
        inr_20 = inr_at_exceedance_probability(samples, EXCEEDANCE_PROBABILITY)
        loaded.append((scenario, samples, inr_20))

        xs, ys = compute_ccdf(samples)
        color, linestyle = style_for(scenario)
        ax.plot(
            xs,
            ys,
            color=color,
            linestyle=linestyle,
            linewidth=1.8,
            alpha=0.98,
            label=rf"LF={scenario.load_factor_pct}%, $D_{{\mathrm{{border}}}}={scenario.margin_km}$ km",
        )

    xmin, xmax = ax.get_xlim()
    if not loaded:
        raise ValueError("no usable samples found")

    ax.plot(
        [PROTECTION_LIMIT_DB, PROTECTION_LIMIT_DB],
        [1.0, EXCEEDANCE_PROBABILITY],
        color="0.15",
        linestyle=":",
        linewidth=1.55,
    )
    ax.plot(
        [xmin, PROTECTION_LIMIT_DB],
        [EXCEEDANCE_PROBABILITY, EXCEEDANCE_PROBABILITY],
        color="0.35",
        linestyle=":",
        linewidth=1.15,
    )

    positive = next((item for item in loaded if item[2] < PROTECTION_LIMIT_DB), None)
    negative = next((item for item in loaded if item[2] > PROTECTION_LIMIT_DB and item[0].load_factor_pct == 50), None)

    if positive is not None:
        scenario, _samples, inr_20 = positive
        color, _linestyle = style_for(scenario)
        ax.scatter([inr_20], [EXCEEDANCE_PROBABILITY], color=color, s=34, zorder=6)
        ax.annotate(
            "",
            xy=(PROTECTION_LIMIT_DB, 0.115),
            xytext=(inr_20, 0.115),
            arrowprops=dict(arrowstyle="<->", color="#007A3D", linewidth=1.45),
        )
        ax.text(
            (inr_20 + PROTECTION_LIMIT_DB) / 2,
            0.085,
            "positive margin",
            ha="center",
            va="center",
            fontsize=8.4,
            color="#007A3D",
        )

    if negative is not None:
        scenario, _samples, inr_20 = negative
        color, _linestyle = style_for(scenario)
        ax.scatter([inr_20], [EXCEEDANCE_PROBABILITY], color=color, s=34, zorder=6)
        ax.annotate(
            "",
            xy=(inr_20, 0.32),
            xytext=(PROTECTION_LIMIT_DB, 0.32),
            arrowprops=dict(arrowstyle="<->", color="#B00020", linewidth=1.45),
        )
        ax.text(
            (inr_20 + PROTECTION_LIMIT_DB) / 2,
            0.43,
            "negative margin",
            ha="center",
            va="center",
            fontsize=8.4,
            color="#B00020",
        )

    first = loaded[0][0]
    area_label = AREA_LABELS.get(first.area, first.area)
    ax.set_title(f"{area_label}, System 3, {first.altitude_km} km, FS {first.fs_height_m} m")
    ax.set_xlabel("INR (dB)")
    ax.set_ylabel("Exceedance probability")
    ax.set_yscale("log")
    ax.set_ylim(Y_LOG_FLOOR, 1.0)
    ax.grid(True, which="both", alpha=0.28, linewidth=0.55)
    ax.tick_params(axis="both", which="major", width=0.8, length=3.2)
    ax.tick_params(axis="both", which="minor", width=0.6, length=2.0)

    handles, labels = ax.get_legend_handles_labels()
    label_to_handle: dict[str, object] = {}
    for handle, label in zip(handles, labels):
        label_to_handle[label] = handle
    ordered_labels = [
        r"LF=20%, $D_{\mathrm{border}}=0$ km",
        r"LF=50%, $D_{\mathrm{border}}=0$ km",
        r"LF=20%, $D_{\mathrm{border}}=60$ km",
        r"LF=50%, $D_{\mathrm{border}}=60$ km",
    ]
    ordered_handles = [label_to_handle[label] for label in ordered_labels if label in label_to_handle]
    ordered_labels = [label for label in ordered_labels if label in label_to_handle]
    ax.legend(
        ordered_handles,
        ordered_labels,
        loc="lower left",
        frameon=True,
        fancybox=False,
        framealpha=0.9,
        ncol=2,
        handlelength=2.2,
        columnspacing=1.0,
        borderpad=0.35,
        labelspacing=0.35,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02)
    try:
        fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    except PermissionError:
        print(f"[skip] PDF is locked: {out_path.with_suffix('.pdf')}")
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    campaign_dir = script_dir.parent
    parser = argparse.ArgumentParser(description="Generate simplified INR CCDF margin explainer plot.")
    parser.add_argument("--output-root", type=Path, default=campaign_dir / "output")
    parser.add_argument("--plots-dir", type=Path, default=campaign_dir / "plots" / "system_inr_ccdf_article")
    parser.add_argument("--area", choices=("BR_AR_Paraguay", "SouthAmerica"), default="BR_AR_Paraguay")
    parser.add_argument("--altitude-km", type=int, default=525)
    parser.add_argument("--fs-height-m", type=int, default=40)
    parser.add_argument("--margins-km", type=int, nargs="+", default=[0, 60])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scenarios = discover_scenarios(args.output_root.resolve(), all_runs=False)
    selected = select_scenarios(
        scenarios,
        area=args.area,
        altitude_km=args.altitude_km,
        fs_height_m=args.fs_height_m,
        margins_km=set(args.margins_km),
    )
    if not selected:
        print("No matching scenarios found.")
        return 1

    margin_label = "_".join(f"M{margin}km" for margin in sorted(set(args.margins_km)))
    out_path = (
        args.plots_dir.resolve()
        / f"system_inr_ccdf_margin_explainer_{args.area}_Sys3_{args.altitude_km}km_FS{args.fs_height_m}m_{margin_label}.png"
    )
    plot_explainer(selected, out_path)
    print(f"[ok] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

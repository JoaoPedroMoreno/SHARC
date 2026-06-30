"""Plot protection-margin curves from System INR SHARC results.

This script replaces the old heatmap idea with margin curves, which are easier
to discuss in a paper:

    x-axis: border margin / exclusion distance in km
    y-axis: protection margin against the -6 dB criterion at 20% time

The protection margin is computed as:

    protection_margin_db = -6 - INR_20%

Positive values pass the criterion. Negative values fail it.

Use --demo to generate a fictional CSV and a sketch plot before running all
server simulations.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_system_inr_ccdf import FIELD, Scenario, discover_scenarios, read_series_csv, scenario_sort_key


PROTECTION_LIMIT_DB = -6.0
EXCEEDANCE_PROBABILITY = 0.2

AREA_LABELS = {
    "BR_AR_Paraguay": "BR, AR, PY",
    "SouthAmerica": "South America",
}

FS_COLORS = {
    20: "tab:blue",
    40: "tab:orange",
}

LF_STYLES = {
    20: "-",
    50: "--",
}

LF_MARKERS = {
    20: "o",
    50: "s",
}


@dataclass(frozen=True)
class MarginPoint:
    area: str
    system: int
    altitude_km: int
    fs_height_m: int
    load_factor_pct: int
    border_margin_km: int
    azimuth_mode: str
    inr_20_pct_db: float
    protection_margin_db: float
    source_count: int


def inr_at_exceedance_probability(samples: np.ndarray, probability: float) -> float:
    """Return the empirical INR value exceeded by the given probability."""
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return math.nan

    x.sort()
    quantile = 1.0 - probability
    index = int(math.ceil(quantile * x.size)) - 1
    index = max(0, min(index, x.size - 1))
    return float(x[index])


def point_sort_key(point: MarginPoint) -> tuple[int, int, int, int, int]:
    area_order = 0 if point.area == "BR_AR_Paraguay" else 1
    return (
        area_order,
        point.altitude_km,
        point.fs_height_m,
        point.load_factor_pct,
        point.border_margin_km,
    )


def collect_points_from_outputs(
    scenarios: list[Scenario],
    area: str,
    azimuth_mode: str,
) -> list[MarginPoint]:
    raw_rows: list[dict[str, object]] = []

    for scenario in sorted(scenarios, key=scenario_sort_key):
        if scenario.area != area:
            continue
        if scenario.margin_km <= 0:
            continue

        samples = read_series_csv(scenario.folder / f"{FIELD}.csv", FIELD)
        if samples is None or samples.size == 0:
            print(f"[skip] sem dados em {scenario.folder / f'{FIELD}.csv'}")
            continue

        inr_20_pct = inr_at_exceedance_probability(samples, EXCEEDANCE_PROBABILITY)
        raw_rows.append(
            {
                "scenario": scenario,
                "inr_20_pct_db": inr_20_pct,
                "protection_margin_db": PROTECTION_LIMIT_DB - inr_20_pct,
            }
        )

    if azimuth_mode == "separate":
        return [
            MarginPoint(
                area=row["scenario"].area,
                system=row["scenario"].system,
                altitude_km=row["scenario"].altitude_km,
                fs_height_m=row["scenario"].fs_height_m,
                load_factor_pct=row["scenario"].load_factor_pct,
                border_margin_km=row["scenario"].margin_km,
                azimuth_mode=f"Azi{row['scenario'].azimuth_deg}",
                inr_20_pct_db=float(row["inr_20_pct_db"]),
                protection_margin_db=float(row["protection_margin_db"]),
                source_count=1,
            )
            for row in raw_rows
        ]

    grouped: dict[tuple[int, int, int, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in raw_rows:
        scenario = row["scenario"]
        grouped[
            (
                scenario.system,
                scenario.altitude_km,
                scenario.fs_height_m,
                scenario.load_factor_pct,
                scenario.margin_km,
            )
        ].append(row)

    points: list[MarginPoint] = []
    for (system, altitude_km, fs_height_m, load_factor_pct, margin_km), rows in grouped.items():
        margins = np.asarray([float(row["protection_margin_db"]) for row in rows], dtype=float)
        inrs = np.asarray([float(row["inr_20_pct_db"]) for row in rows], dtype=float)

        if azimuth_mode == "mean":
            protection_margin = float(np.mean(margins))
            inr_20_pct = float(np.mean(inrs))
        else:
            worst_index = int(np.argmin(margins))
            protection_margin = float(margins[worst_index])
            inr_20_pct = float(inrs[worst_index])

        points.append(
            MarginPoint(
                area=area,
                system=system,
                altitude_km=altitude_km,
                fs_height_m=fs_height_m,
                load_factor_pct=load_factor_pct,
                border_margin_km=margin_km,
                azimuth_mode=azimuth_mode,
                inr_20_pct_db=inr_20_pct,
                protection_margin_db=protection_margin,
                source_count=len(rows),
            )
        )

    return sorted(points, key=point_sort_key)


def generate_demo_points(area: str) -> list[MarginPoint]:
    """Create fictional values only to preview the curve style."""
    points: list[MarginPoint] = []
    for altitude_km in (340, 525):
        for fs_height_m in (20, 40):
            for load_factor_pct in (20, 50):
                for border_margin_km in range(10, 101, 10):
                    altitude_bonus = 3.2 if altitude_km == 525 else 0.0
                    fs_bonus = 0.5 if fs_height_m == 40 else 0.0
                    lf_penalty = 0.0 if load_factor_pct == 20 else -4.0
                    curve = -8.5 + 0.13 * border_margin_km + 1.5 * math.log10(border_margin_km / 10)
                    protection_margin = curve + altitude_bonus + fs_bonus + lf_penalty
                    inr_20_pct = PROTECTION_LIMIT_DB - protection_margin

                    points.append(
                        MarginPoint(
                            area=area,
                            system=3,
                            altitude_km=altitude_km,
                            fs_height_m=fs_height_m,
                            load_factor_pct=load_factor_pct,
                            border_margin_km=border_margin_km,
                            azimuth_mode="demo",
                            inr_20_pct_db=inr_20_pct,
                            protection_margin_db=protection_margin,
                            source_count=0,
                        )
                    )

    return points


def save_points_csv(points: list[MarginPoint], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "area",
                "system",
                "altitude_km",
                "fs_height_m",
                "load_factor_pct",
                "border_margin_km",
                "azimuth_mode",
                "inr_20_pct_db",
                "protection_margin_db",
                "source_count",
            ],
        )
        writer.writeheader()
        for point in sorted(points, key=point_sort_key):
            writer.writerow(
                {
                    "area": point.area,
                    "system": point.system,
                    "altitude_km": point.altitude_km,
                    "fs_height_m": point.fs_height_m,
                    "load_factor_pct": point.load_factor_pct,
                    "border_margin_km": point.border_margin_km,
                    "azimuth_mode": point.azimuth_mode,
                    "inr_20_pct_db": f"{point.inr_20_pct_db:.6f}",
                    "protection_margin_db": f"{point.protection_margin_db:.6f}",
                    "source_count": point.source_count,
                }
            )


def plot_margin_curves(points: list[MarginPoint], out_path: Path, demo: bool) -> None:
    if not points:
        raise ValueError("no margin points to plot")

    area = points[0].area
    area_label = AREA_LABELS.get(area, area)
    altitudes = sorted({point.altitude_km for point in points})

    fig, axes = plt.subplots(
        1,
        len(altitudes),
        figsize=(6.4 * len(altitudes), 4.8),
        dpi=180,
        sharey=True,
    )
    if len(altitudes) == 1:
        axes = [axes]

    for ax, altitude_km in zip(axes, altitudes):
        subset = [point for point in points if point.altitude_km == altitude_km]
        for fs_height_m in sorted({point.fs_height_m for point in subset}):
            for load_factor_pct in sorted({point.load_factor_pct for point in subset}):
                curve = sorted(
                    [
                        point
                        for point in subset
                        if point.fs_height_m == fs_height_m and point.load_factor_pct == load_factor_pct
                    ],
                    key=lambda item: item.border_margin_km,
                )
                if not curve:
                    continue

                x_values = [point.border_margin_km for point in curve]
                y_values = [point.protection_margin_db for point in curve]
                ax.plot(
                    x_values,
                    y_values,
                    color=FS_COLORS.get(fs_height_m),
                    linestyle=LF_STYLES.get(load_factor_pct, "-"),
                    marker=LF_MARKERS.get(load_factor_pct, "o"),
                    linewidth=2.0,
                    markersize=5.0,
                    label=f"FS={fs_height_m} m, LF={load_factor_pct}%",
                )

        ax.axhline(0.0, color="black", linestyle=":", linewidth=1.8, label="Protection criterion")
        ax.set_title(f"System 3 - {altitude_km} km")
        ax.set_xlabel("Border margin / exclusion distance (km)")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8)

    axes[0].set_ylabel("Protection margin at 20% time (dB)")

    title_suffix = "fictional sketch" if demo else "SHARC results"
    fig.suptitle(f"{area_label}: INR Protection Margin Curves ({title_suffix})", fontsize=14, fontweight="bold")
    fig.text(
        0.01,
        0.01,
        "Criterion: INR_20% <= -6 dB. Positive margin passes; negative margin fails. "
        "Default real-data mode aggregates azimuths using the worst case.",
        fontsize=8,
        color="#333333",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    campaign_dir = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Generate margin curves against the -6 dB INR criterion at 20% time."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=campaign_dir / "output",
        help="Folder containing SHARC output_* result directories.",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=campaign_dir / "plots" / "system_inr_margin_curves",
        help="Folder where the PNG and CSV will be saved.",
    )
    parser.add_argument(
        "--area",
        choices=sorted(AREA_LABELS),
        default="BR_AR_Paraguay",
        help="Area to plot. SouthAmerica has no border-margin sweep in the current outputs.",
    )
    parser.add_argument(
        "--azimuth-mode",
        choices=("worst", "mean", "separate"),
        default="worst",
        help="How to handle multiple azimuths at the same margin. Default: worst protection margin.",
    )
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Use every matching output folder instead of only the latest run per scenario.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate fictional 10-100 km values to preview the curve style.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plots_dir = args.plots_dir.resolve()

    if args.demo:
        points = generate_demo_points(args.area)
        suffix = "demo"
    else:
        output_root = args.output_root.resolve()
        if not output_root.is_dir():
            print(f"Output root not found: {output_root}")
            return 2
        scenarios = discover_scenarios(output_root, all_runs=args.all_runs)
        points = collect_points_from_outputs(scenarios, area=args.area, azimuth_mode=args.azimuth_mode)
        suffix = args.azimuth_mode

    if not points:
        print("No usable margin data found.")
        return 1

    csv_path = plots_dir / f"system_inr_margin_curves_{args.area}_{suffix}.csv"
    png_path = plots_dir / f"system_inr_margin_curves_{args.area}_{suffix}.png"

    save_points_csv(points, csv_path)
    plot_margin_curves(points, png_path, demo=args.demo)

    print(f"[ok] {png_path}")
    print(f"[ok] {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

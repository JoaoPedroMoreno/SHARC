"""Generate the standard System INR CCDF plots for campaign 02_DC_MSS_to_FS 2.

The script reads SHARC output folders named like:

    output_dc_mss_to_fs_BR_AR_Paraguay_Sys3_340km_FS20m_LF20_M25km_Azi90deg_2026-06-25_01

It then creates one plot for each (area, altitude, FS height) group, using the
same ECDF/CCDF logic used by GUI_new.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import numpy as np


FIELD = "system_inr"
Y_LOG_FLOOR = 1e-4
IEEE_TEXT_WIDTH_IN = 7.16
IEEE_CCDF_HEIGHT_IN = 3.35
IEEE_DPI = 300

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 9.5,
        "axes.titlesize": 9.8,
        "axes.labelsize": 10.0,
        "xtick.labelsize": 9.0,
        "ytick.labelsize": 9.0,
        "legend.fontsize": 8.5,
        "lines.linewidth": 1.6,
        "axes.linewidth": 0.8,
        "savefig.dpi": IEEE_DPI,
    }
)

OUTPUT_NAME_RE = re.compile(
    r"^output_dc_mss_to_fs_"
    r"(?P<area>BR_AR_Paraguay|SouthAmerica)_"
    r"Sys(?P<system>\d+)_"
    r"(?P<altitude>\d+)km_"
    r"FS(?P<fs_height>\d+)m_"
    r"LF(?P<load_factor>\d+)_"
    r"(?P<distance_type>M|EZ)(?P<margin>\d+)km_"
    r"Azi(?P<azimuth>\d+)deg"
    r"(?:_(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+))?$",
    re.IGNORECASE,
)

AREA_ORDER = {
    "BR_AR_Paraguay": 0,
    "SouthAmerica": 1,
}

AREA_LABELS = {
    "BR_AR_Paraguay": "Brazil/Argentina",
    "SouthAmerica": "South America",
}

@dataclass(frozen=True)
class Scenario:
    folder: Path
    area: str
    system: int
    altitude_km: int
    fs_height_m: int
    load_factor_pct: int
    distance_type: str
    margin_km: int
    azimuth_deg: int
    date: str
    run: int

    @property
    def group_key(self) -> tuple[str, int, int]:
        return (self.area, self.altitude_km, self.fs_height_m)

    @property
    def scenario_key(self) -> tuple[str, int, int, int, str, int, int]:
        return (
            self.area,
            self.altitude_km,
            self.fs_height_m,
            self.load_factor_pct,
            self.distance_type,
            self.margin_km,
            self.azimuth_deg,
        )

    @property
    def latest_key(self) -> tuple[str, int]:
        return (self.date, self.run)

    @property
    def label(self) -> str:
        return f"LF={self.load_factor_pct}%, {self.distance_type}={self.margin_km} km"


def parse_scenario(folder: Path) -> Scenario | None:
    match = OUTPUT_NAME_RE.match(folder.name)
    if not match:
        return None

    data = match.groupdict()
    return Scenario(
        folder=folder,
        area=data["area"],
        system=int(data["system"]),
        altitude_km=int(data["altitude"]),
        fs_height_m=int(data["fs_height"]),
        load_factor_pct=int(data["load_factor"]),
        distance_type=data["distance_type"].upper(),
        margin_km=int(data["margin"]),
        azimuth_deg=int(data["azimuth"]),
        date=data.get("date") or "0000-00-00",
        run=int(data.get("run") or 0),
    )


def read_series_csv(path: Path, field: str) -> np.ndarray | None:
    """Read a SHARC result CSV following the GUI_new field-selection behavior."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if not header:
                return None

            if field in header:
                value_index = header.index(field)
            elif len(header) == 1:
                value_index = 0
            elif "value" in header:
                value_index = header.index("value")
            else:
                return None

            values: list[float] = []
            for row in reader:
                if value_index >= len(row):
                    continue
                try:
                    value = float(row[value_index])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(value)
    except OSError:
        return None

    if not values:
        return None
    return np.asarray(values, dtype=float)


def compute_ccdf(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    x.sort()
    y = 1.0 - (np.arange(1, x.size + 1) / x.size)
    y = np.clip(y, Y_LOG_FLOOR, 1.0)
    return x, y


def discover_scenarios(output_root: Path, all_runs: bool) -> list[Scenario]:
    scenarios = [
        parsed
        for folder in output_root.iterdir()
        if folder.is_dir()
        for parsed in [parse_scenario(folder)]
        if parsed is not None
    ]

    if all_runs:
        return sorted(scenarios, key=scenario_sort_key)

    latest_by_scenario: dict[tuple[str, int, int, int, str, int, int], Scenario] = {}
    for scenario in scenarios:
        previous = latest_by_scenario.get(scenario.scenario_key)
        if previous is None or scenario.latest_key > previous.latest_key:
            latest_by_scenario[scenario.scenario_key] = scenario

    return sorted(latest_by_scenario.values(), key=scenario_sort_key)


def scenario_sort_key(scenario: Scenario) -> tuple[int, int, int, int, str, int, int, str, int]:
    return (
        AREA_ORDER.get(scenario.area, 99),
        scenario.altitude_km,
        scenario.fs_height_m,
        scenario.load_factor_pct,
        scenario.distance_type,
        scenario.margin_km,
        scenario.azimuth_deg,
        scenario.date,
        scenario.run,
    )


def group_sort_key(group_key: tuple[str, int, int]) -> tuple[int, int, int]:
    area, altitude_km, fs_height_m = group_key
    return (AREA_ORDER.get(area, 99), altitude_km, fs_height_m)


def plot_group(group_key: tuple[str, int, int], group: list[Scenario], plots_dir: Path) -> Path | None:
    area, altitude_km, fs_height_m = group_key
    margins = sorted({item.margin_km for item in group})
    margin_norm = Normalize(vmin=min(margins), vmax=max(margins))
    colormap = plt.get_cmap("viridis")

    fig, ax = plt.subplots(figsize=(IEEE_TEXT_WIDTH_IN, IEEE_CCDF_HEIGHT_IN), dpi=IEEE_DPI, constrained_layout=True)
    plotted = 0

    for scenario in sorted(group, key=scenario_sort_key):
        csv_path = scenario.folder / f"{FIELD}.csv"
        samples = read_series_csv(csv_path, FIELD)
        if samples is None or samples.size == 0:
            print(f"[skip] no data in {csv_path}")
            continue

        xs, ys = compute_ccdf(samples)
        line_style = "-" if scenario.load_factor_pct == 20 else "--"
        ax.plot(
            xs,
            ys,
            color=colormap(margin_norm(scenario.margin_km)),
            linestyle=line_style,
            linewidth=1.55,
            alpha=0.98,
        )
        plotted += 1

    ax.plot(
        [-6.0, -6.0],
        [1.0, 0.2],
        color="black",
        linestyle=":",
        linewidth=1.7,
    )

    area_label = AREA_LABELS.get(area, area)
    azimuths = sorted({scenario.azimuth_deg for scenario in group})
    azimuth_label = f", azimuth {azimuths[0]} deg" if len(azimuths) == 1 else ""
    ax.set_title(f"{area_label}, System 3, {altitude_km} km, FS {fs_height_m} m{azimuth_label}", pad=4)
    ax.set_xlabel("INR [dB]")
    ax.set_ylabel("Exceedance probability")
    ax.set_yscale("log")
    ax.set_ylim(Y_LOG_FLOOR, 1.0)
    ax.grid(True, which="both", alpha=0.28, linewidth=0.55)
    ax.tick_params(axis="both", which="major", width=0.8, length=3.2)
    ax.tick_params(axis="both", which="minor", width=0.6, length=2.0)

    if plotted:
        distance_label = "Exclusion radius" if group[0].distance_type == "EZ" else "Border margin"
        scalar_mappable = ScalarMappable(norm=margin_norm, cmap=colormap)
        scalar_mappable.set_array([])
        cbar = fig.colorbar(scalar_mappable, ax=ax, pad=0.012, fraction=0.04)
        cbar.set_label(f"{distance_label} (km)", fontsize=9.5)
        cbar.ax.tick_params(labelsize=8.5, width=0.7, length=2.8)

        legend_handles = [
            Line2D([0], [0], color="0.15", linestyle="-", linewidth=1.8, label="LF=20%"),
            Line2D([0], [0], color="0.15", linestyle="--", linewidth=1.8, label="LF=50%"),
            Line2D([0], [0], color="black", linestyle=":", linewidth=1.8, label="-6 dB criterion"),
        ]
        ax.legend(
            handles=legend_handles,
            loc="lower left",
            frameon=False,
            fancybox=False,
            handlelength=2.2,
            borderpad=0.2,
            labelspacing=0.25,
        )
    else:
        ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)

    plots_dir.mkdir(parents=True, exist_ok=True)
    out_path = plots_dir / f"system_inr_ccdf_{area}_Sys3_{altitude_km}km_FS{fs_height_m}m.png"
    fig.savefig(out_path, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    return out_path if plotted else None


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    campaign_dir = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Generate grouped System INR CCDF log plots for campaign 02_DC_MSS_to_FS 2."
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
        default=campaign_dir / "plots" / "system_inr_ccdf",
        help="Folder where the PNG plots will be saved.",
    )
    parser.add_argument(
        "--all-runs",
        action="store_true",
        help="Plot every matching output folder instead of only the latest run per scenario.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_root = args.output_root.resolve()
    plots_dir = args.plots_dir.resolve()

    if not output_root.is_dir():
        print(f"Output root not found: {output_root}")
        return 2

    scenarios = discover_scenarios(output_root, all_runs=args.all_runs)
    if not scenarios:
        print(f"No matching output folders found in: {output_root}")
        return 1

    groups: dict[tuple[str, int, int], list[Scenario]] = {}
    for scenario in scenarios:
        groups.setdefault(scenario.group_key, []).append(scenario)

    saved: list[Path] = []
    for group_key in sorted(groups, key=group_sort_key):
        path = plot_group(group_key, groups[group_key], plots_dir)
        if path is not None:
            saved.append(path)
            print(f"[ok] {path}")

    print(f"Generated {len(saved)} plot(s) in {plots_dir}")
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
import numpy as np


FIELD = "system_inr"
Y_LOG_FLOOR = 1e-4

OUTPUT_NAME_RE = re.compile(
    r"^output_dc_mss_to_fs_"
    r"(?P<area>BR_AR_Paraguay|SouthAmerica)_"
    r"Sys(?P<system>\d+)_"
    r"(?P<altitude>\d+)km_"
    r"FS(?P<fs_height>\d+)m_"
    r"LF(?P<load_factor>\d+)_"
    r"(?:M|EZ)(?P<margin>\d+)km_"
    r"Azi(?P<azimuth>\d+)deg"
    r"(?:_(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+))?$",
    re.IGNORECASE,
)

AREA_ORDER = {
    "BR_AR_Paraguay": 0,
    "SouthAmerica": 1,
}

COLOR_CYCLE = [
    "tab:blue",
    "tab:orange",
    "tab:green",
    "tab:red",
    "tab:purple",
    "tab:brown",
    "tab:pink",
    "tab:gray",
]


@dataclass(frozen=True)
class Scenario:
    folder: Path
    area: str
    system: int
    altitude_km: int
    fs_height_m: int
    load_factor_pct: int
    margin_km: int
    azimuth_deg: int
    date: str
    run: int

    @property
    def group_key(self) -> tuple[str, int, int]:
        return (self.area, self.altitude_km, self.fs_height_m)

    @property
    def scenario_key(self) -> tuple[str, int, int, int, int, int]:
        return (
            self.area,
            self.altitude_km,
            self.fs_height_m,
            self.load_factor_pct,
            self.margin_km,
            self.azimuth_deg,
        )

    @property
    def latest_key(self) -> tuple[str, int]:
        return (self.date, self.run)

    @property
    def label(self) -> str:
        return (
            f"h={self.fs_height_m}m, "
            f"azi={self.azimuth_deg}deg,"
            f"lf={self.load_factor_pct}%,"
            f"M={self.margin_km}km"
        )


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

    latest_by_scenario: dict[tuple[str, int, int, int, int, int], Scenario] = {}
    for scenario in scenarios:
        previous = latest_by_scenario.get(scenario.scenario_key)
        if previous is None or scenario.latest_key > previous.latest_key:
            latest_by_scenario[scenario.scenario_key] = scenario

    return sorted(latest_by_scenario.values(), key=scenario_sort_key)


def scenario_sort_key(scenario: Scenario) -> tuple[int, int, int, int, int, int, str, int]:
    return (
        AREA_ORDER.get(scenario.area, 99),
        scenario.altitude_km,
        scenario.fs_height_m,
        scenario.load_factor_pct,
        scenario.margin_km,
        scenario.azimuth_deg,
        scenario.date,
        scenario.run,
    )


def group_sort_key(group_key: tuple[str, int, int]) -> tuple[int, int, int]:
    area, altitude_km, fs_height_m = group_key
    return (AREA_ORDER.get(area, 99), altitude_km, fs_height_m)


def color_map_for_group(group: list[Scenario]) -> dict[tuple[int, int], str]:
    tokens = sorted({(item.margin_km, item.azimuth_deg) for item in group})
    return {token: COLOR_CYCLE[index % len(COLOR_CYCLE)] for index, token in enumerate(tokens)}


def plot_group(group_key: tuple[str, int, int], group: list[Scenario], plots_dir: Path) -> Path | None:
    area, altitude_km, fs_height_m = group_key
    colors = color_map_for_group(group)

    fig, ax = plt.subplots(figsize=(9.5, 6.0), dpi=140)
    plotted = 0

    for scenario in sorted(group, key=scenario_sort_key):
        csv_path = scenario.folder / f"{FIELD}.csv"
        samples = read_series_csv(csv_path, FIELD)
        if samples is None or samples.size == 0:
            print(f"[skip] sem dados em {csv_path}")
            continue

        xs, ys = compute_ccdf(samples)
        line_style = "-" if scenario.load_factor_pct == 20 else ":"
        ax.plot(
            xs,
            ys,
            label=scenario.label,
            color=colors[(scenario.margin_km, scenario.azimuth_deg)],
            linestyle=line_style,
            linewidth=1.8,
        )
        plotted += 1

    ax.plot(
        [-6.0, -6.0],
        [1.0, 0.2],
        color="black",
        linestyle=":",
        linewidth=2.0,
        label="6dB [20% of the time]",
    )

    ax.set_title(f"System 3_{altitude_km}km - {area} - FS={fs_height_m}m")
    ax.set_xlabel("INR [dB]")
    ax.set_ylabel("CCDF")
    ax.set_yscale("log")
    ax.set_ylim(Y_LOG_FLOOR, 1.0)
    ax.grid(True, which="both", alpha=0.3)

    if plotted:
        ax.legend(fontsize=8.0)
    else:
        ax.text(0.5, 0.5, "sem dados", ha="center", va="center", transform=ax.transAxes)

    fig.tight_layout()
    plots_dir.mkdir(parents=True, exist_ok=True)
    out_path = plots_dir / f"system_inr_ccdf_{area}_Sys3_{altitude_km}km_FS{fs_height_m}m.png"
    fig.savefig(out_path, bbox_inches="tight")
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

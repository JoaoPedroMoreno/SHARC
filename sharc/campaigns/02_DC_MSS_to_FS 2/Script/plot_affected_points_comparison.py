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


SA_RE = re.compile(
    r"^output_dc_mss_to_fs_SouthAmerica_"
    r"Sys(?P<system>\d+)_(?P<altitude>\d+)km_"
    r"FS(?P<fs_height>\d+)m_LF(?P<load_factor>\d+)_"
    r"EZ(?P<distance>\d+)km_Azi(?P<azimuth>\d+)deg_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+)$",
    re.IGNORECASE,
)

BRARG_RE = re.compile(
    r"^output_dc_mss_to_fs_BR_AR_Paraguay_"
    r"Sys(?P<system>\d+)_(?P<altitude>\d+)km_"
    r"FS(?P<fs_height>\d+)m_LF(?P<load_factor>\d+)_"
    r"M(?P<distance>\d+)km_Azi(?P<azimuth>\d+)deg_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Scenario:
    folder: Path
    method: str
    system: int
    altitude_km: int
    fs_height_m: int
    load_factor_pct: int
    distance_km: int
    azimuth_deg: int
    date: str
    run: int

    @property
    def scenario_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.system,
            self.altitude_km,
            self.fs_height_m,
            self.load_factor_pct,
            self.azimuth_deg,
        )

    @property
    def latest_key(self) -> tuple[str, int]:
        return (self.date, self.run)


def read_numeric_csv(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None

    values: list[float] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            try:
                value = float(row[0])
            except ValueError:
                continue
            if math.isfinite(value):
                values.append(value)

    if not values:
        return None
    return np.asarray(values, dtype=float)


def parse_folder(folder: Path) -> Scenario | None:
    for method, regex in [("sa", SA_RE), ("brarg", BRARG_RE)]:
        match = regex.match(folder.name)
        if not match:
            continue
        data = match.groupdict()
        return Scenario(
            folder=folder,
            method=method,
            system=int(data["system"]),
            altitude_km=int(data["altitude"]),
            fs_height_m=int(data["fs_height"]),
            load_factor_pct=int(data["load_factor"]),
            distance_km=int(data["distance"]),
            azimuth_deg=int(data["azimuth"]),
            date=data["date"],
            run=int(data["run"]),
        )
    return None


def discover_latest(output_root: Path) -> list[Scenario]:
    latest: dict[tuple[str, int, int, int, int, int, int], Scenario] = {}
    for folder in output_root.iterdir():
        if not folder.is_dir():
            continue
        scenario = parse_folder(folder)
        if scenario is None:
            continue
        key = (
            scenario.method,
            scenario.system,
            scenario.altitude_km,
            scenario.fs_height_m,
            scenario.load_factor_pct,
            scenario.distance_km,
            scenario.azimuth_deg,
        )
        previous = latest.get(key)
        if previous is None or scenario.latest_key > previous.latest_key:
            latest[key] = scenario
    return list(latest.values())


def select_scenarios(
    scenarios: list[Scenario],
    *,
    system: int,
    altitude_km: int,
    fs_height_m: int,
    load_factor_pct: int,
    azimuth_deg: int,
) -> list[Scenario]:
    return [
        scenario for scenario in scenarios
        if scenario.system == system
        and scenario.altitude_km == altitude_km
        and scenario.fs_height_m == fs_height_m
        and scenario.load_factor_pct == load_factor_pct
        and scenario.azimuth_deg == azimuth_deg
    ]


def affected_by_exclusion(scenarios: list[Scenario]) -> list[tuple[int, float, float]]:
    by_distance = {scenario.distance_km: scenario for scenario in scenarios if scenario.method == "sa"}
    baseline = by_distance.get(0)
    if baseline is None:
        return []

    baseline_active = read_numeric_csv(baseline.folder / "num_of_active_beams.csv")
    if baseline_active is None:
        return []

    points: list[tuple[int, float, float]] = []
    for distance, scenario in sorted(by_distance.items()):
        active = read_numeric_csv(scenario.folder / "num_of_active_beams.csv")
        if active is None:
            continue
        n = min(baseline_active.size, active.size)
        affected = np.maximum(0.0, baseline_active[:n] - active[:n])
        points.append((distance, float(np.mean(affected)), float(np.percentile(affected, 95))))
    return points


def count_power_backoff_by_snapshot(scenario: Scenario, nominal_power_dbm: float) -> np.ndarray | None:
    active = read_numeric_csv(scenario.folder / "num_of_active_beams.csv")
    tx_power = read_numeric_csv(scenario.folder / "imt_dl_tx_power.csv")
    if active is None or tx_power is None:
        return None

    counts: list[int] = []
    cursor = 0
    for active_count in active.astype(int):
        next_cursor = cursor + active_count
        if next_cursor > tx_power.size:
            break
        snapshot_power = tx_power[cursor:next_cursor]
        counts.append(int(np.sum(snapshot_power < nominal_power_dbm - 0.1)))
        cursor = next_cursor

    if not counts:
        return None
    return np.asarray(counts, dtype=float)


def affected_by_power_backoff(scenarios: list[Scenario], nominal_power_dbm: float) -> list[tuple[int, float, float]]:
    points: list[tuple[int, float, float]] = []
    for scenario in sorted([s for s in scenarios if s.method == "brarg"], key=lambda s: s.distance_km):
        affected = count_power_backoff_by_snapshot(scenario, nominal_power_dbm)
        if affected is None:
            continue
        points.append((scenario.distance_km, float(np.mean(affected)), float(np.percentile(affected, 95))))
    return points


def plot_comparison(
    exclusion_points: list[tuple[int, float, float]],
    backoff_points: list[tuple[int, float, float]],
    output_path: Path,
    *,
    title_suffix: str,
) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 6.0), dpi=140)

    for points, label, color, marker in [
        (exclusion_points, "Celulas do grid removidas - zona de exclusao (output SA)", "tab:blue", "o"),
        (backoff_points, "Celulas do grid com backoff - power backoff (output BRARG)", "tab:orange", "s"),
    ]:
        if not points:
            continue
        x = np.asarray([point[0] for point in points], dtype=float)
        y_mean = np.asarray([point[1] for point in points], dtype=float)
        y_p95 = np.asarray([point[2] for point in points], dtype=float)
        ax.plot(x, y_mean, color=color, marker=marker, linewidth=2.0, label=f"{label} - media")
        ax.plot(x, y_p95, color=color, marker=marker, linewidth=1.4, linestyle="--", alpha=0.8, label=f"{label} - p95")

    ax.set_title(f"Celulas do grid afetadas por metodo de mitigacao{title_suffix}")
    ax.set_xlabel("Distancia / margem de coordenacao [km]")
    ax.set_ylabel("Celulas/feixes do grid afetados por snapshot")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def write_summary(
    exclusion_points: list[tuple[int, float, float]],
    backoff_points: list[tuple[int, float, float]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "distance_km", "affected_mean", "affected_p95"])
        for distance, mean, p95 in exclusion_points:
            writer.writerow(["Celulas do grid removidas - zona de exclusao (SA)", distance, f"{mean:.6f}", f"{p95:.6f}"])
        for distance, mean, p95 in backoff_points:
            writer.writerow(["Celulas do grid com backoff - power backoff (BRARG)", distance, f"{mean:.6f}", f"{p95:.6f}"])


def main() -> None:
    campaign_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Compara pontos afetados por zona de exclusao e power backoff.")
    parser.add_argument("--output-root", type=Path, default=campaign_dir / "output")
    parser.add_argument("--plots-dir", type=Path, default=campaign_dir / "plots" / "mitigation_comparison")
    parser.add_argument("--system", type=int, default=3)
    parser.add_argument("--altitude-km", type=int, default=340)
    parser.add_argument("--fs-height-m", type=int, default=20)
    parser.add_argument("--load-factor-pct", type=int, default=20)
    parser.add_argument("--azimuth-deg", type=int, default=90)
    parser.add_argument("--nominal-power-dbm", type=float, default=42.8)
    args = parser.parse_args()

    scenarios = select_scenarios(
        discover_latest(args.output_root),
        system=args.system,
        altitude_km=args.altitude_km,
        fs_height_m=args.fs_height_m,
        load_factor_pct=args.load_factor_pct,
        azimuth_deg=args.azimuth_deg,
    )

    exclusion_points = affected_by_exclusion(scenarios)
    backoff_points = affected_by_power_backoff(scenarios, args.nominal_power_dbm)
    if not exclusion_points and not backoff_points:
        raise SystemExit("Nao foram encontrados outputs SA/BRARG compativeis para este filtro.")

    suffix = (
        f" - Sys{args.system} {args.altitude_km} km, "
        f"FS {args.fs_height_m} m, LF {args.load_factor_pct}%, "
        f"Az {args.azimuth_deg} deg"
    )
    plot_path = args.plots_dir / (
        f"affected_points_Sys{args.system}_{args.altitude_km}km_"
        f"FS{args.fs_height_m}m_LF{args.load_factor_pct}_Azi{args.azimuth_deg}.png"
    )
    csv_path = plot_path.with_suffix(".csv")

    plot_comparison(exclusion_points, backoff_points, plot_path, title_suffix=suffix)
    write_summary(exclusion_points, backoff_points, csv_path)

    print(f"Gerado: {plot_path}")
    print(f"Gerado: {csv_path}")


if __name__ == "__main__":
    main()

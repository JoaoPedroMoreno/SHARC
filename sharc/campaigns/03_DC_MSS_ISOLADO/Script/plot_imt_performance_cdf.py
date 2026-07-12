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


PERFORMANCE_FIELDS = {
    "imt_dl_sinr": ("01", "Downlink SINR [dB]", "CDF de Downlink SINR"),
    "imt_dl_tput": ("02", "Throughput [bits/s/Hz]", "CDF de Throughput Downlink"),
    "imt_dl_snr": ("03", "Downlink SNR [dB]", "CDF de Downlink SNR"),
    "imt_path_loss": ("04", "Path Loss [dB]", "CDF de Path Loss"),
}

OUTPUT_NAME_RE = re.compile(
    r"^output_dc_mss_isolado_"
    r"Sys(?P<system>\d+)_"
    r"(?P<altitude>\d+)km_"
    r"FS(?P<fs_height>\d+)m_"
    r"LF(?P<load_factor>\d+)"
    r"(?:_(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+))?$",
    re.IGNORECASE,
)

COLOR_BY_ALTITUDE = {
    340: "tab:blue",
    525: "tab:orange",
}

LINESTYLE_BY_LOAD = {
    20: "-",
    50: "--",
}


@dataclass(frozen=True)
class Scenario:
    folder: Path
    system: int
    altitude_km: int
    fs_height_m: int
    load_factor_pct: int
    date: str
    run: int
    snapshots: int

    @property
    def scenario_key(self) -> tuple[int, int, int, int]:
        return (self.system, self.altitude_km, self.fs_height_m, self.load_factor_pct)

    @property
    def latest_key(self) -> tuple[str, int]:
        return (self.date, self.run)

    @property
    def label(self) -> str:
        return f"Sys{self.system} {self.altitude_km} km, LF {self.load_factor_pct}%"


def read_numeric_csv(path: Path, field: str | None = None) -> np.ndarray | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if not header:
                return None

            if field and field in header:
                value_index = header.index(field)
            elif len(header) == 1:
                value_index = 0
            elif "samples" in header:
                value_index = header.index("samples")
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


def count_snapshots(folder: Path) -> int:
    samples = read_numeric_csv(folder / "num_of_active_beams.csv")
    if samples is None:
        return 0
    return int(samples.size)


def parse_scenario(folder: Path) -> Scenario | None:
    match = OUTPUT_NAME_RE.match(folder.name)
    if not match:
        return None
    data = match.groupdict()
    return Scenario(
        folder=folder,
        system=int(data["system"]),
        altitude_km=int(data["altitude"]),
        fs_height_m=int(data["fs_height"]),
        load_factor_pct=int(data["load_factor"]),
        date=data.get("date") or "0000-00-00",
        run=int(data.get("run") or 0),
        snapshots=count_snapshots(folder),
    )


def scenario_sort_key(scenario: Scenario) -> tuple[int, int, int, int, str, int]:
    return (
        scenario.altitude_km,
        scenario.load_factor_pct,
        scenario.fs_height_m,
        scenario.system,
        scenario.date,
        scenario.run,
    )


def discover_scenarios(
    output_root: Path,
    *,
    all_runs: bool,
    min_snapshots: int,
    representative_fs_height: int | None,
) -> list[Scenario]:
    scenarios = [
        parsed
        for folder in output_root.iterdir()
        if folder.is_dir()
        for parsed in [parse_scenario(folder)]
        if parsed is not None
    ]

    scenarios = [scenario for scenario in scenarios if scenario.snapshots >= min_snapshots]
    if representative_fs_height is not None:
        scenarios = [
            scenario for scenario in scenarios
            if scenario.fs_height_m == representative_fs_height
        ]

    if all_runs:
        return sorted(scenarios, key=scenario_sort_key)

    latest_by_scenario: dict[tuple[int, int, int, int], Scenario] = {}
    for scenario in scenarios:
        previous = latest_by_scenario.get(scenario.scenario_key)
        if previous is None or scenario.latest_key > previous.latest_key:
            latest_by_scenario[scenario.scenario_key] = scenario
    return sorted(latest_by_scenario.values(), key=scenario_sort_key)


def compute_cdf(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    x.sort()
    y = np.arange(1, x.size + 1) / x.size
    return x, y


def style_for(scenario: Scenario) -> dict[str, object]:
    return {
        "color": COLOR_BY_ALTITUDE.get(scenario.altitude_km),
        "linestyle": LINESTYLE_BY_LOAD.get(scenario.load_factor_pct, "-"),
        "linewidth": 1.8,
    }


def plot_performance_cdf(scenarios: list[Scenario], field: str, plots_dir: Path) -> Path | None:
    prefix, xlabel, title = PERFORMANCE_FIELDS[field]
    fig, ax = plt.subplots(figsize=(9.5, 6.0), dpi=140)
    plotted = 0

    for scenario in scenarios:
        samples = read_numeric_csv(scenario.folder / f"{field}.csv", field)
        if samples is None:
            continue
        x, y = compute_cdf(samples)
        ax.plot(x, y, label=scenario.label, **style_for(scenario))
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return None

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Probabilidade acumulada")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()

    output_path = plots_dir / f"{prefix}_{field}_cdf.png"
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def plot_satellite_counts_cdf(scenarios: list[Scenario], plots_dir: Path) -> Path | None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4), dpi=140, sharey=True)
    plotted = 0

    panels = [
        ("num_of_sat", "Satélites ativos", "Número de satélites ativos por snapshot"),
        ("num_of_candidate_sats", "Satélites candidatos", "Número de satélites candidatos por snapshot"),
    ]

    for ax, (field, title, xlabel) in zip(axes, panels):
        for scenario in scenarios:
            samples = read_numeric_csv(scenario.folder / f"{field}.csv")
            if samples is None:
                continue
            x, y = compute_cdf(samples)
            style = style_for(scenario)
            ax.plot(
                x,
                y,
                label=scenario.label,
                **style,
            )
            plotted += 1

        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.grid(True, which="both", alpha=0.3)

    if plotted == 0:
        plt.close(fig)
        return None

    axes[0].set_ylabel("Probabilidade acumulada")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=4,
        fontsize=8,
        frameon=True,
    )
    fig.suptitle("CDF de satélites ativos e candidatos", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.12, 1, 0.90))

    output_path = plots_dir / "06_satellite_counts_cdf.png"
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def write_summary_csv(scenarios: list[Scenario], plots_dir: Path) -> Path:
    output_path = plots_dir / "00_scenario_summary.csv"
    fields = [
        "scenario",
        "snapshots",
        "avg_active_beams",
        "max_active_beams",
        "avg_active_satellites",
        "avg_candidate_satellites",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario in scenarios:
            active_beams = read_numeric_csv(scenario.folder / "num_of_active_beams.csv")
            active_satellites = read_numeric_csv(scenario.folder / "num_of_sat.csv")
            candidate_satellites = read_numeric_csv(scenario.folder / "num_of_candidate_sats.csv")
            writer.writerow({
                "scenario": scenario.label,
                "snapshots": scenario.snapshots,
                "avg_active_beams": f"{np.mean(active_beams):.3f}" if active_beams is not None else "",
                "max_active_beams": f"{np.max(active_beams):.0f}" if active_beams is not None else "",
                "avg_active_satellites": f"{np.mean(active_satellites):.3f}" if active_satellites is not None else "",
                "avg_candidate_satellites": f"{np.mean(candidate_satellites):.3f}" if candidate_satellites is not None else "",
            })
    return output_path


def main() -> None:
    campaign_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Gera os graficos da Parte A para DC-MSS isolado.")
    parser.add_argument("--output-root", type=Path, default=campaign_dir / "output")
    parser.add_argument("--plots-dir", type=Path, default=campaign_dir / "plots" / "imt_performance")
    parser.add_argument("--all-runs", action="store_true")
    parser.add_argument("--min-snapshots", type=int, default=2000)
    parser.add_argument(
        "--representative-fs-height",
        type=int,
        default=20,
        help="Usa apenas uma altura FS como representante; use 0 para manter FS20 e FS40.",
    )
    args = parser.parse_args()

    representative_fs_height = args.representative_fs_height or None
    scenarios = discover_scenarios(
        args.output_root,
        all_runs=args.all_runs,
        min_snapshots=args.min_snapshots,
        representative_fs_height=representative_fs_height,
    )
    if not scenarios:
        raise SystemExit(
            f"Nenhum output completo encontrado em {args.output_root}. "
            f"Reduza --min-snapshots se quiser plotar resultados parciais."
        )

    args.plots_dir.mkdir(parents=True, exist_ok=True)
    print(f"Cenarios usados: {len(scenarios)}")
    for scenario in scenarios:
        print(f" - {scenario.label}: {scenario.snapshots} snapshots")

    generated = [write_summary_csv(scenarios, args.plots_dir)]
    for field in PERFORMANCE_FIELDS:
        output_path = plot_performance_cdf(scenarios, field, args.plots_dir)
        if output_path:
            generated.append(output_path)

    for plotter in [plot_satellite_counts_cdf]:
        output_path = plotter(scenarios, args.plots_dir)
        if output_path:
            generated.append(output_path)

    for path in generated:
        print(f"Gerado: {path}")


if __name__ == "__main__":
    main()

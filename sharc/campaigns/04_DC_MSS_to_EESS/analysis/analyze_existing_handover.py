"""Audit completed DC-MSS -> EESS handover runs without rerunning SHARC.

The OFF run defines the baseline top-1% and top-0.1% snapshots.  ON and OFF
samples are paired by scenario, campaign seed and snapshot row.  A run is
accepted only when the aggregate-interference file has exactly the configured
number of snapshots; ON runs must also have one handover-metrics row for every
snapshot with contiguous snapshot_id values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml


RUN_RE = re.compile(
    r"^system_(?P<altitude>\d+)km_EESS_(?P<eess>[BD])_"
    r"(?P<coverage>[A-Z]+)_(?P<position>[A-Z]+)_OM_(?P<margin>[-\d.]+)_"
    r"lf_(?P<load>[\d.]+)_GB_(?P<gb>\d+)MHz_HO_(?P<ho>ON|OFF)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<run>\d+)$"
)
AGGREGATE_FILE = "system_dl_interf_power_per_mhz.csv"
METRICS_FILE = "interference_aware_handover_snapshot_metrics.csv"
TOPOLOGY_FILES = (
    "num_of_active_beams.csv",
    "num_of_candidate_sats.csv",
    "num_of_sat.csv",
)


@dataclass
class Run:
    directory: Path
    altitude_km: int
    eess_system: str
    coverage: str
    position: str
    margin: float
    load_factor: float
    guard_band_mhz: int
    handover: str
    date: str
    run_number: int
    seed: int
    expected_snapshots: int
    interference_dbw_mhz: np.ndarray
    metrics: dict[str, np.ndarray] | None

    @property
    def scenario_key(self) -> tuple:
        return (
            self.altitude_km, self.eess_system, self.coverage, self.position,
            self.margin, self.load_factor, self.guard_band_mhz,
        )

    @property
    def identity(self) -> tuple:
        return self.scenario_key + (self.handover, self.seed)


def read_one_column(path: Path) -> np.ndarray:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        next(reader)
        return np.asarray([float(row[0]) for row in reader if row], dtype=float)


def load_metrics(path: Path) -> dict[str, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return {}
    integer_fields = {
        "snapshot_id", "active_beams_evaluated", "primary_main_main_count",
        "handover_trigger_count", "successful_handover_count",
        "unresolved_count",
    }
    return {
        field: np.asarray(
            [int(row[field]) if field in integer_fields else float(row[field]) for row in rows]
        )
        for field in rows[0]
    }


def load_yaml_metadata(directory: Path) -> tuple[int, int]:
    yaml_files = list(directory.glob("*.yaml"))
    if len(yaml_files) != 1:
        raise ValueError(f"Expected one YAML in {directory}, found {len(yaml_files)}")
    with yaml_files[0].open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    return int(config["general"]["seed"]), int(config["general"]["num_snapshots"])


def discover_completed_runs(output_dir: Path) -> tuple[list[Run], list[dict]]:
    latest: dict[tuple, Run] = {}
    inventory: list[dict] = []
    for directory in sorted(output_dir.iterdir()):
        match = RUN_RE.match(directory.name) if directory.is_dir() else None
        if match is None:
            continue
        try:
            seed, expected = load_yaml_metadata(directory)
        except (ValueError, KeyError) as error:
            inventory.append({"run": directory.name, "complete": False, "reason": str(error)})
            continue
        aggregate_path = directory / AGGREGATE_FILE
        if not aggregate_path.is_file():
            inventory.append({"run": directory.name, "complete": False, "reason": "missing aggregate CSV"})
            continue
        try:
            values = read_one_column(aggregate_path)
        except (ValueError, UnicodeError) as error:
            inventory.append({
                "run": directory.name,
                "complete": False,
                "reason": f"invalid/truncated aggregate CSV: {error}",
            })
            continue
        reason = "complete"
        metrics = None
        if values.size != expected:
            reason = f"aggregate rows {values.size} != expected {expected}"
        elif not np.all(np.isfinite(values)):
            reason = "non-finite aggregate interference"
        elif match["ho"] == "ON":
            metrics_path = directory / METRICS_FILE
            if not metrics_path.is_file():
                reason = "missing handover metrics"
            else:
                metrics = load_metrics(metrics_path)
                ids = metrics.get("snapshot_id", np.asarray([], dtype=int))
                if ids.size != expected:
                    reason = f"metrics rows {ids.size} != expected {expected}"
                elif not np.array_equal(ids, np.arange(1, expected + 1)):
                    reason = "non-contiguous snapshot_id"

        complete = reason == "complete"
        inventory.append({"run": directory.name, "complete": complete, "reason": reason})
        if not complete:
            continue
        run = Run(
            directory=directory,
            altitude_km=int(match["altitude"]), eess_system=match["eess"],
            coverage=match["coverage"], position=match["position"],
            margin=float(match["margin"]), load_factor=float(match["load"]),
            guard_band_mhz=int(match["gb"]), handover=match["ho"],
            date=match["date"], run_number=int(match["run"]), seed=seed,
            expected_snapshots=expected,
            interference_dbw_mhz=values - 30.0,
            metrics=metrics,
        )
        previous = latest.get(run.identity)
        if previous is None or (run.date, run.run_number) > (previous.date, previous.run_number):
            latest[run.identity] = run
    return sorted(latest.values(), key=lambda item: item.identity), inventory


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def empirical_top_mask(values: np.ndarray, exceedance: float) -> np.ndarray:
    count = max(1, math.ceil(values.size * exceedance))
    indices = np.argsort(-values, kind="stable")[:count]
    mask = np.zeros(values.size, dtype=bool)
    mask[indices] = True
    return mask


def empirical_exceedance_level(values: np.ndarray, exceedance: float) -> float:
    return float(np.min(values[empirical_top_mask(values, exceedance)]))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pair_runs(runs: list[Run]) -> tuple[list[tuple[Run, Run]], list[dict]]:
    by_scenario: dict[tuple, dict[str, Run]] = {}
    for run in runs:
        by_scenario.setdefault(run.scenario_key, {})[run.handover] = run
    pairs, excluded = [], []
    for scenario, variants in sorted(by_scenario.items()):
        if set(variants) != {"ON", "OFF"}:
            excluded.append({"scenario": repr(scenario), "reason": "missing complete ON/OFF partner"})
            continue
        off, on = variants["OFF"], variants["ON"]
        if off.seed != on.seed or off.expected_snapshots != on.expected_snapshots:
            excluded.append({"scenario": repr(scenario), "reason": "seed/snapshot mismatch"})
            continue
        pairs.append((off, on))
    return pairs, excluded


def analyze_pair(off: Run, on: Run) -> tuple[dict, list[dict]]:
    assert on.metrics is not None
    n = off.expected_snapshots
    top1 = empirical_top_mask(off.interference_dbw_mhz, 0.01)
    top01 = empirical_top_mask(off.interference_dbw_mhz, 0.001)
    trigger = on.metrics["handover_trigger_count"] > 0
    success = on.metrics["successful_handover_count"] > 0
    delta = on.interference_dbw_mhz - off.interference_dbw_mhz
    off_rank = np.empty(n, dtype=int)
    off_rank[np.argsort(-off.interference_dbw_mhz, kind="stable")] = np.arange(1, n + 1)
    on_rank = np.empty(n, dtype=int)
    on_rank[np.argsort(-on.interference_dbw_mhz, kind="stable")] = np.arange(1, n + 1)
    hashes_equal = all(
        sha256(off.directory / name) == sha256(on.directory / name)
        for name in TOPOLOGY_FILES
    )
    common = {
        "guard_band_mhz": off.guard_band_mhz, "altitude_km": off.altitude_km,
        "eess_system": off.eess_system, "load_factor": off.load_factor,
        "position": off.position, "coverage": off.coverage,
        "margin": off.margin, "seed": off.seed, "snapshots": n,
    }
    summary = {
        **common,
        "off_run": off.directory.name, "on_run": on.directory.name,
        "topology_hashes_equal": hashes_equal,
        "beams_per_sat_hash_equal": (
            sha256(off.directory / "num_of_beams_per_sat.csv")
            == sha256(on.directory / "num_of_beams_per_sat.csv")
        ),
        "off_p99_dbw_mhz": empirical_exceedance_level(off.interference_dbw_mhz, 0.01),
        "on_p99_dbw_mhz": empirical_exceedance_level(on.interference_dbw_mhz, 0.01),
        "on_minus_off_p99_db": empirical_exceedance_level(on.interference_dbw_mhz, 0.01) - empirical_exceedance_level(off.interference_dbw_mhz, 0.01),
        "off_p99_9_dbw_mhz": empirical_exceedance_level(off.interference_dbw_mhz, 0.001),
        "on_p99_9_dbw_mhz": empirical_exceedance_level(on.interference_dbw_mhz, 0.001),
        "on_minus_off_p99_9_db": empirical_exceedance_level(on.interference_dbw_mhz, 0.001) - empirical_exceedance_level(off.interference_dbw_mhz, 0.001),
        "off_snapshots_above_minus154": int(np.sum(off.interference_dbw_mhz > -154.0)),
        "on_snapshots_above_minus154": int(np.sum(on.interference_dbw_mhz > -154.0)),
        "off_exceedance_minus154_pct": float(np.mean(off.interference_dbw_mhz > -154.0) * 100),
        "on_exceedance_minus154_pct": float(np.mean(on.interference_dbw_mhz > -154.0) * 100),
        "trigger_events": int(np.sum(on.metrics["handover_trigger_count"])),
        "successful_handover_events": int(np.sum(on.metrics["successful_handover_count"])),
        "unresolved_events": int(np.sum(on.metrics["unresolved_count"])),
        "snapshots_with_trigger": int(np.sum(trigger)),
        "snapshots_with_trigger_pct": float(np.mean(trigger) * 100),
        "snapshots_with_handover": int(np.sum(success)),
        "snapshots_with_handover_pct": float(np.mean(success) * 100),
        "off_top1_snapshots_with_trigger": int(np.sum(top1 & trigger)),
        "off_top1_snapshots_with_trigger_pct": float(np.mean(trigger[top1]) * 100),
        "off_top1_snapshots_with_handover": int(np.sum(top1 & success)),
        "off_top1_snapshots_with_handover_pct": float(np.mean(success[top1]) * 100),
        "off_top01_snapshots_with_trigger": int(np.sum(top01 & trigger)),
        "best_off_rank_among_trigger_snapshots": int(np.min(off_rank[trigger])) if np.any(trigger) else "",
        "worst_off_rank_among_trigger_snapshots": int(np.max(off_rank[trigger])) if np.any(trigger) else "",
        "mean_delta_all_db": float(np.mean(delta)),
        "mean_delta_off_top1_db": float(np.mean(delta[top1])),
        "median_delta_off_top1_db": float(np.median(delta[top1])),
        "max_reduction_off_top1_db": float(-np.min(delta[top1])),
        "changed_snapshot_count": int(np.sum(~np.isclose(delta, 0.0, rtol=0.0, atol=1e-12))),
    }
    snapshots = []
    for index in range(n):
        snapshots.append({
            **common, "snapshot_id": index + 1,
            "off_interference_dbw_mhz": off.interference_dbw_mhz[index],
            "on_interference_dbw_mhz": on.interference_dbw_mhz[index],
            "on_minus_off_db": delta[index], "off_top_1pct": bool(top1[index]),
            "off_top_0_1pct": bool(top01[index]),
            "off_rank_desc": int(off_rank[index]), "on_rank_desc": int(on_rank[index]),
            "trigger_count": int(on.metrics["handover_trigger_count"][index]),
            "successful_handover_count": int(on.metrics["successful_handover_count"][index]),
            "unresolved_count": int(on.metrics["unresolved_count"][index]),
        })
    return summary, snapshots


def ccdf(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.sort(values)
    return x, (values.size - np.arange(values.size)) / values.size


def make_plots(pairs: list[tuple[Run, Run]], snapshots: list[dict], plot_dir: Path) -> None:
    plot_dir.mkdir(parents=True, exist_ok=True)
    grouped = sorted({(off.altitude_km, off.eess_system, off.load_factor) for off, _ in pairs})
    fig, axes = plt.subplots(1, len(grouped), figsize=(8 * len(grouped), 6), squeeze=False)
    colors = plt.get_cmap("viridis")(np.linspace(0.05, 0.95, 6))
    for ax, group in zip(axes[0], grouped):
        for off, on in pairs:
            if (off.altitude_km, off.eess_system, off.load_factor) != group:
                continue
            for run, style in ((off, "-"), (on, "--")):
                x, y = ccdf(run.interference_dbw_mhz)
                ax.plot(x, y, style, color=colors[run.guard_band_mhz // 2],
                        label=f"GB {run.guard_band_mhz}, HO {run.handover}")
        ax.axvline(-154, color="black", linewidth=1.2)
        ax.set(title=f"{group[0]} km, EESS {group[1]}, LF {group[2]}",
               xlabel="I_agg [dBW/MHz]", ylabel="Exceedance probability")
        ax.set_yscale("log"); ax.grid(True, linestyle=":", alpha=.4); ax.legend(fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(plot_dir / "01_ccdf_ho_on_off.png", dpi=180); plt.close(fig)

    rows = snapshots
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    no_trigger = [r["off_interference_dbw_mhz"] for r in rows if r["trigger_count"] == 0]
    trigger = [r["off_interference_dbw_mhz"] for r in rows if r["trigger_count"] > 0]
    axes[0].hist(no_trigger, bins=80, density=True, alpha=.55, label="No trigger")
    if trigger:
        axes[0].rug = axes[0].scatter(trigger, np.zeros(len(trigger)), marker="|", s=120, label="Trigger")
    axes[0].set(xlabel="Baseline I_agg [dBW/MHz]", ylabel="Density", title="Triggers versus aggregate interference")
    axes[0].legend(); axes[0].grid(True, linestyle=":", alpha=.4)

    values = np.asarray([r["off_interference_dbw_mhz"] for r in rows])
    triggered = np.asarray([r["trigger_count"] > 0 for r in rows])
    handed = np.asarray([r["successful_handover_count"] > 0 for r in rows])
    order = np.argsort(values, kind="stable")
    bins = np.array_split(order, 20)
    centers = np.arange(2.5, 100, 5)
    axes[1].plot(centers, [100*np.mean(triggered[b]) for b in bins], "o-", label="Trigger")
    axes[1].plot(centers, [100*np.mean(handed[b]) for b in bins], "s--", label="Handover")
    axes[1].set(xlabel="Baseline interference percentile bin", ylabel="Conditional probability [%]",
                title="Trigger/handover conditional on I_agg percentile")
    axes[1].legend(); axes[1].grid(True, linestyle=":", alpha=.4)
    fig.tight_layout(); fig.savefig(plot_dir / "02_trigger_location.png", dpi=180); plt.close(fig)

    delta = np.asarray([r["on_minus_off_db"] for r in rows])
    baseline = np.asarray([r["off_interference_dbw_mhz"] for r in rows])
    event = np.asarray([r["successful_handover_count"] > 0 for r in rows])
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].scatter(baseline[event], delta[event], s=28, alpha=.8)
    axes[0].axhline(0, color="black", linewidth=1)
    axes[0].set(xlabel="Baseline I_agg [dBW/MHz]", ylabel="I_ON - I_OFF [dB]",
                title="Paired effect at handover snapshots")
    axes[0].grid(True, linestyle=":", alpha=.4)
    changed = delta[~np.isclose(delta, 0, rtol=0, atol=1e-12)]
    if changed.size:
        axes[1].hist(changed, bins=min(30, max(5, changed.size)), alpha=.8)
    axes[1].axvline(0, color="black", linewidth=1)
    axes[1].set(xlabel="I_ON - I_OFF [dB]", ylabel="Snapshots",
                title="Distribution of non-zero paired differences")
    axes[1].grid(True, linestyle=":", alpha=.4)
    fig.tight_layout(); fig.savefig(plot_dir / "03_paired_difference.png", dpi=180); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    campaign = Path(__file__).resolve().parents[1]
    parser.add_argument("--campaign", type=Path, default=campaign)
    args = parser.parse_args()
    analysis_dir = args.campaign / "analysis"
    runs, inventory = discover_completed_runs(args.campaign / "output")
    pairs, excluded = pair_runs(runs)
    summaries, snapshot_rows = [], []
    for off, on in pairs:
        summary, rows = analyze_pair(off, on)
        summaries.append(summary); snapshot_rows.extend(rows)
    write_csv(analysis_dir / "run_inventory.csv", inventory)
    write_csv(analysis_dir / "pair_exclusions.csv", excluded)
    write_csv(analysis_dir / "scenario_summary.csv", summaries)
    write_csv(analysis_dir / "paired_snapshots.csv", snapshot_rows)
    make_plots(pairs, snapshot_rows, analysis_dir / "plots")
    print(f"Complete runs selected: {len(runs)}")
    print(f"Valid ON/OFF pairs: {len(pairs)}")
    print(f"Analyzed paired snapshots: {len(snapshot_rows)}")
    print(f"Analysis directory: {analysis_dir}")


if __name__ == "__main__":
    main()

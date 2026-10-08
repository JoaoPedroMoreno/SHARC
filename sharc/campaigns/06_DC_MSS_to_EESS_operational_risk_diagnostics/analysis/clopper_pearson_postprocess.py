"""Clopper-Pearson intervals for the completed operational-risk campaign.

This is a read-only post-processing utility.  It never instantiates SHARC's
simulation classes and therefore cannot consume RNG or change physical results.

Outputs
-------
analysis/clopper_pearson/scenario_exceedance_cp95.csv
    Exact 95% binomial intervals for before/after exceedance in every run.
analysis/clopper_pearson/risk_curve_bins_cp95_by_scenario.csv
    Exact 95% intervals inside every scenario/bin used by Figure 8.
analysis/clopper_pearson/risk_curve_bins_cp95_balanced.csv
    Pooled descriptive intervals and conservative simultaneous intervals for
    the equally weighted mean of the eight scenario risks.
"""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import beta


CAMPAIGN = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
OUTPUT = CAMPAIGN / "output"
FINAL_CAMPAIGN = CAMPAIGN.parent / "04_DC_MSS_to_EESS"
FINAL_OUTPUT = FINAL_CAMPAIGN / "output"
DESTINATION = CAMPAIGN / "analysis" / "clopper_pearson"
FIGURE_SCRIPTS = (
    CAMPAIGN.parent / "04_DC_MSS_to_EESS" / "figures" / "scripts"
)
if str(FIGURE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(FIGURE_SCRIPTS))

RUN_PATTERN = re.compile(
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(10|60|65|70|75|80)MHz_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)
FINAL_GB5_PATTERN = re.compile(
    r"^system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_5MHz_STRATEGY_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)
THRESHOLD_DBW_PER_MHZ = -154.0
ALPHA = 0.05


def clopper_pearson(successes: int, total: int, alpha: float = ALPHA) -> tuple[float, float]:
    """Return the equal-tailed exact binomial confidence interval."""
    if total <= 0 or successes < 0 or successes > total:
        return np.nan, np.nan
    lower = 0.0 if successes == 0 else float(
        beta.ppf(alpha / 2.0, successes, total - successes + 1)
    )
    upper = 1.0 if successes == total else float(
        beta.ppf(1.0 - alpha / 2.0, successes + 1, total - successes)
    )
    return lower, upper


def count_rows(path: Path) -> int:
    with path.open("rb") as stream:
        return max(sum(1 for _ in stream) - 1, 0)


def completed_runs() -> dict[tuple[int, str, float, int], Path]:
    """Select the latest complete run for each campaign combination."""
    selected: dict[tuple[int, str, float, int], tuple[tuple[str, int], Path]] = {}
    for directory in OUTPUT.iterdir():
        match = RUN_PATTERN.fullmatch(directory.name) if directory.is_dir() else None
        if not match:
            continue
        source = directory / "operational_risk_snapshot.csv"
        if not source.is_file() or count_rows(source) != 5000:
            continue
        key = (int(match[1]), match[2], float(match[3]), int(match[4]))
        stamp = (match[5], int(match[6]))
        if key not in selected or stamp > selected[key][0]:
            selected[key] = (stamp, directory)
    runs = {key: value[1] for key, value in selected.items()}
    if len(runs) != 48:
        raise RuntimeError(f"Expected 48 complete runs, found {len(runs)}")
    return runs


def completed_gb5_runs() -> dict[tuple[int, str, float, int], Path]:
    """Select the eight completed GB=5 runs from the main campaign."""
    selected: dict[tuple[int, str, float, int], tuple[tuple[str, int], Path]] = {}
    for directory in FINAL_OUTPUT.iterdir():
        match = FINAL_GB5_PATTERN.fullmatch(
            directory.name
        ) if directory.is_dir() else None
        if not match:
            continue
        source = directory / "interference_aware_handover_v2_snapshot.csv"
        if not source.is_file() or count_rows(source) != 5000:
            continue
        key = (int(match[1]), match[2], float(match[3]), 5)
        stamp = (match[4], int(match[5]))
        if key not in selected or stamp > selected[key][0]:
            selected[key] = (stamp, directory)
    runs = {key: value[1] for key, value in selected.items()}
    if len(runs) != 8:
        raise RuntimeError(f"Expected 8 complete GB=5 runs, found {len(runs)}")
    return runs


def load_figure_module(filename: str, module_name: str):
    path = FIGURE_SCRIPTS / filename
    spec = spec_from_file_location(module_name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def choose_operational_feature(risk, data: pd.DataFrame) -> str:
    stats = risk.feature_statistics(data)
    pooled = stats[stats.scope == "POOLED"].copy()
    pooled["score"] = (
        pooled.median_scenario_oriented_auc
        * pooled.scenario_direction_consistency
    )
    best = pooled.sort_values("score", ascending=False).iloc[0]
    rx = pooled[pooled.feature == "top1_rx_offaxis_deg"].iloc[0]
    return (
        "top1_rx_offaxis_deg"
        if rx.score >= best.score - 0.02
        else str(best.feature)
    )


def scenario_summary(
    runs: dict[tuple[int, str, float, int], Path],
    *, filename: str = "operational_risk_snapshot.csv",
    source_kind: str = "operational_diagnostics",
) -> pd.DataFrame:
    records = []
    columns = [
        "iagg_before_dbw_per_mhz", "iagg_after_dbw_per_mhz",
    ]
    for (altitude, eess, load, guard_band), directory in sorted(runs.items()):
        source = directory / filename
        frame = pd.read_csv(source, usecols=columns)
        before = frame.iagg_before_dbw_per_mhz.to_numpy(float) > THRESHOLD_DBW_PER_MHZ
        after = frame.iagg_after_dbw_per_mhz.to_numpy(float) > THRESHOLD_DBW_PER_MHZ
        total = len(frame)
        before_k, after_k = int(before.sum()), int(after.sum())
        before_low, before_high = clopper_pearson(before_k, total)
        after_low, after_high = clopper_pearson(after_k, total)
        records.append({
            "altitude_km": altitude,
            "eess_system": eess,
            "load_factor": load,
            "guard_band_mhz": guard_band,
            "snapshots": total,
            "threshold_dbw_per_mhz": THRESHOLD_DBW_PER_MHZ,
            "before_exceedances": before_k,
            "before_probability_pct": 100.0 * before_k / total,
            "before_cp95_low_pct": 100.0 * before_low,
            "before_cp95_high_pct": 100.0 * before_high,
            "after_exceedances": after_k,
            "after_probability_pct": 100.0 * after_k / total,
            "after_cp95_low_pct": 100.0 * after_low,
            "after_cp95_high_pct": 100.0 * after_high,
            "source_kind": source_kind,
            "source_path": str(directory.resolve()),
        })
    return pd.DataFrame(records)


def risk_bin_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use exactly the data selection and global quantile bins of Figure 8."""
    risk = load_figure_module("07_risk_features.py", "risk_features_cp")
    data, _ = risk.load_data()
    feature = choose_operational_feature(risk, data)
    finite = data[np.isfinite(data[feature])].copy()
    edges = np.unique(np.quantile(finite[feature], np.linspace(0.0, 1.0, 11)))
    if len(edges) < 7:
        raise RuntimeError("Insufficient unique feature values for risk bins")
    finite["bin"] = pd.cut(
        finite[feature], bins=edges, include_lowest=True, duplicates="drop"
    )

    scenario_records = []
    balanced_records = []
    for interval, group in finite.groupby("bin", observed=True, sort=True):
        bin_scenarios = []
        for scenario, scenario_group in group.groupby("scenario", sort=True):
            total = len(scenario_group)
            before_k = int(scenario_group.critical.sum())
            # Figure 8 currently uses GB=10 operational snapshots.  The
            # post-V2 state is retained in the source CSV identified per row.
            source = Path(str(scenario_group.source_path.iloc[0]))
            snapshot_after = pd.read_csv(
                source / "operational_risk_snapshot.csv",
                usecols=["snapshot_id", "iagg_after_dbw_per_mhz"],
            ).set_index("snapshot_id")
            snapshot_ids = scenario_group.snapshot_id.astype(int).to_numpy()
            after_values = snapshot_after.loc[
                snapshot_ids, "iagg_after_dbw_per_mhz"
            ].to_numpy(float)
            after_k = int((after_values > THRESHOLD_DBW_PER_MHZ).sum())
            before_low, before_high = clopper_pearson(before_k, total)
            after_low, after_high = clopper_pearson(after_k, total)
            record = {
                "feature": feature,
                "bin_left": float(interval.left),
                "bin_right": float(interval.right),
                "scenario": scenario,
                "snapshots": total,
                "before_exceedances": before_k,
                "before_probability_pct": 100.0 * before_k / total,
                "before_cp95_low_pct": 100.0 * before_low,
                "before_cp95_high_pct": 100.0 * before_high,
                "after_exceedances": after_k,
                "after_probability_pct": 100.0 * after_k / total,
                "after_cp95_low_pct": 100.0 * after_low,
                "after_cp95_high_pct": 100.0 * after_high,
            }
            scenario_records.append(record)
            bin_scenarios.append(record)

        scenario_count = len(bin_scenarios)
        if scenario_count != 8:
            raise RuntimeError(
                f"Expected 8 scenarios in bin {interval}, found {scenario_count}"
            )
        total = sum(row["snapshots"] for row in bin_scenarios)
        before_k = sum(row["before_exceedances"] for row in bin_scenarios)
        after_k = sum(row["after_exceedances"] for row in bin_scenarios)
        pooled_before = clopper_pearson(before_k, total)
        pooled_after = clopper_pearson(after_k, total)

        # CP applies exactly within each binomial scenario.  To form a 95%
        # simultaneous interval for the equally weighted mean of 8 different
        # scenario probabilities, use alpha/8 in each CP interval and average
        # the endpoints.  The union bound makes this conservative but valid.
        simultaneous_alpha = ALPHA / scenario_count
        before_sim = [
            clopper_pearson(
                row["before_exceedances"], row["snapshots"], simultaneous_alpha
            )
            for row in bin_scenarios
        ]
        after_sim = [
            clopper_pearson(
                row["after_exceedances"], row["snapshots"], simultaneous_alpha
            )
            for row in bin_scenarios
        ]
        balanced_records.append({
            "feature": feature,
            "bin_left": float(interval.left),
            "bin_right": float(interval.right),
            "feature_center": float(group[feature].median()),
            "scenario_count": scenario_count,
            "snapshots": total,
            "before_exceedances": before_k,
            "before_pooled_probability_pct": 100.0 * before_k / total,
            "before_pooled_cp95_low_pct": 100.0 * pooled_before[0],
            "before_pooled_cp95_high_pct": 100.0 * pooled_before[1],
            "before_balanced_probability_pct": float(np.mean([
                row["before_probability_pct"] for row in bin_scenarios
            ])),
            "before_balanced_simultaneous_cp95_low_pct": 100.0 * float(
                np.mean([bounds[0] for bounds in before_sim])
            ),
            "before_balanced_simultaneous_cp95_high_pct": 100.0 * float(
                np.mean([bounds[1] for bounds in before_sim])
            ),
            "after_exceedances": after_k,
            "after_pooled_probability_pct": 100.0 * after_k / total,
            "after_pooled_cp95_low_pct": 100.0 * pooled_after[0],
            "after_pooled_cp95_high_pct": 100.0 * pooled_after[1],
            "after_balanced_probability_pct": float(np.mean([
                row["after_probability_pct"] for row in bin_scenarios
            ])),
            "after_balanced_simultaneous_cp95_low_pct": 100.0 * float(
                np.mean([bounds[0] for bounds in after_sim])
            ),
            "after_balanced_simultaneous_cp95_high_pct": 100.0 * float(
                np.mean([bounds[1] for bounds in after_sim])
            ),
        })
    return pd.DataFrame(scenario_records), pd.DataFrame(balanced_records)


def validate_edge_cases() -> None:
    assert clopper_pearson(0, 5000)[0] == 0.0
    assert clopper_pearson(5000, 5000)[1] == 1.0
    assert clopper_pearson(0, 5000)[1] > 0.0
    assert clopper_pearson(5000, 5000)[0] < 1.0


def main() -> None:
    validate_edge_cases()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    runs = completed_runs()
    gb5_runs = completed_gb5_runs()
    summary = pd.concat([
        scenario_summary(runs),
        scenario_summary(
            gb5_runs,
            filename="interference_aware_handover_v2_snapshot.csv",
            source_kind="main_campaign_gb5",
        ),
    ], ignore_index=True).sort_values(
        ["altitude_km", "eess_system", "load_factor", "guard_band_mhz"],
        kind="stable",
    )
    by_scenario, balanced = risk_bin_tables()
    summary.to_csv(DESTINATION / "scenario_exceedance_cp95.csv", index=False)
    by_scenario.to_csv(
        DESTINATION / "risk_curve_bins_cp95_by_scenario.csv", index=False
    )
    balanced.to_csv(
        DESTINATION / "risk_curve_bins_cp95_balanced.csv", index=False
    )
    print(f"Complete runs: {len(runs)}")
    print(f"Complete GB=5 runs: {len(gb5_runs)}")
    print(f"Scenario rows: {len(summary)}")
    print(f"Risk-bin scenario rows: {len(by_scenario)}")
    print(f"Balanced risk bins: {len(balanced)}")
    print(f"Output: {DESTINATION.resolve()}")


if __name__ == "__main__":
    main()

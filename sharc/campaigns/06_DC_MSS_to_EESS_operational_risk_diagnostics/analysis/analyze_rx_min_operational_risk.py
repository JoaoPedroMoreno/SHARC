"""Analyze reconstructed psi_RX,min as an operational risk indicator.

All calculations are post-processing over completed GB=10 diagnostics and the
geometry-only cache produced by ``reconstruct_rx_offaxis_min.py``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy.stats import beta, binomtest, rankdata


CAMPAIGN = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
RX_MIN = CAMPAIGN / "analysis" / "operational_risk_rx_min.csv"
DESTINATION = CAMPAIGN / "analysis" / "rx_min_operational_risk"
FIGURE_SCRIPTS = (
    CAMPAIGN.parent / "04_DC_MSS_to_EESS" / "figures" / "scripts"
)
if str(FIGURE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(FIGURE_SCRIPTS))

from _common import operational_runs, scenario_label  # noqa: E402


THRESHOLD_DBW_PER_MHZ = -154.0
ALPHA = 0.05
N_BINS = 10


def cp(successes: int, total: int, alpha: float = ALPHA) -> tuple[float, float]:
    if total <= 0:
        return np.nan, np.nan
    low = 0.0 if successes == 0 else float(
        beta.ppf(alpha / 2.0, successes, total - successes + 1)
    )
    high = 1.0 if successes == total else float(
        beta.ppf(1.0 - alpha / 2.0, successes + 1, total - successes)
    )
    return low, high


def cp_array(successes: np.ndarray, total: int, alpha: float) -> tuple[np.ndarray, np.ndarray]:
    successes = np.asarray(successes, dtype=int)
    low = np.zeros(successes.shape, dtype=float)
    high = np.ones(successes.shape, dtype=float)
    lower_mask = successes > 0
    upper_mask = successes < total
    low[lower_mask] = beta.ppf(
        alpha / 2.0,
        successes[lower_mask],
        total - successes[lower_mask] + 1,
    )
    high[upper_mask] = beta.ppf(
        1.0 - alpha / 2.0,
        successes[upper_mask] + 1,
        total - successes[upper_mask],
    )
    return low, high


def validate_cp() -> float:
    k, n = 45, 5000
    expected = binomtest(k, n).proportion_ci(
        confidence_level=0.95, method="exact"
    )
    observed = cp(k, n)
    error = max(abs(expected.low - observed[0]), abs(expected.high - observed[1]))
    if error > 1e-12:
        raise RuntimeError(f"Clopper-Pearson validation failed: {error}")
    return error


def load_data() -> tuple[pd.DataFrame, list[str]]:
    geometry = pd.read_csv(RX_MIN)
    if len(geometry) != 10000:
        raise RuntimeError(f"Expected 10000 reconstructed geometries, got {len(geometry)}")
    geometry = geometry[[
        "altitude_km", "snapshot_id", "secondary_seed",
        "rx_visible_satellite_count", "rx_offaxis_min_satellite_idx",
        "rx_offaxis_min_deg", "rx_offaxis_rank2_satellite_idx",
        "rx_offaxis_rank2_deg", "rx_offaxis_rank3_satellite_idx",
        "rx_offaxis_rank3_deg",
    ]].copy()
    geometry = geometry.rename(columns={"snapshot_id": "geometry_snapshot_id"})

    pieces = []
    sources = []
    for (altitude, eess, load, gb), directory in sorted(operational_runs().items()):
        if gb != 10:
            continue
        source = directory / "operational_risk_snapshot.csv"
        frame = pd.read_csv(source, usecols=[
            "snapshot_id", "secondary_seed",
            "iagg_before_dbw_per_mhz", "iagg_after_dbw_per_mhz",
            "top1_joint_gain_suppression_db",
        ])
        frame["altitude_km"] = altitude
        frame["eess_system"] = eess
        frame["load_factor"] = load
        frame["guard_band_mhz"] = gb
        frame["scenario"] = scenario_label(altitude, eess, load)
        frame["source_path"] = str(directory.resolve())
        merged = frame.merge(
            geometry,
            on=["altitude_km", "secondary_seed"],
            how="left",
            validate="many_to_one",
        )
        if len(merged) != 5000 or merged.rx_offaxis_min_deg.isna().any():
            raise RuntimeError(f"Geometry merge failed for {source}")
        if not np.array_equal(
            merged.snapshot_id.to_numpy(int),
            merged.geometry_snapshot_id.to_numpy(int),
        ):
            raise RuntimeError(f"Snapshot identity mismatch for {source}")
        merged["critical_before"] = (
            merged.iagg_before_dbw_per_mhz > THRESHOLD_DBW_PER_MHZ
        )
        merged["critical_after"] = (
            merged.iagg_after_dbw_per_mhz > THRESHOLD_DBW_PER_MHZ
        )
        pieces.append(merged)
        sources.append(str(source.resolve()))
    data = pd.concat(pieces, ignore_index=True)
    if len(data) != 40000 or data.scenario.nunique() != 8:
        raise RuntimeError("Expected 40000 GB=10 rows from eight scenarios")
    return data, sources


def auc_higher(score: np.ndarray, positive: np.ndarray) -> float:
    score = np.asarray(score, dtype=float)
    positive = np.asarray(positive, dtype=bool)
    valid = np.isfinite(score)
    score, positive = score[valid], positive[valid]
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if not n1 or not n0:
        return np.nan
    ranks = rankdata(score, method="average")
    return float((ranks[positive].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def distribution_table(data: pd.DataFrame) -> pd.DataFrame:
    records = []
    groups = [("POOLED", data)] + list(data.groupby("scenario", sort=True))
    for scope, group in groups:
        for label, mask in (
            ("safe", ~group.critical_before),
            ("critical", group.critical_before),
        ):
            values = group.loc[mask, "rx_offaxis_min_deg"].to_numpy(float)
            records.append({
                "scope": scope,
                "class": label,
                "n": len(values),
                "min_deg": np.min(values),
                "p05_deg": np.quantile(values, 0.05),
                "q1_deg": np.quantile(values, 0.25),
                "median_deg": np.median(values),
                "q3_deg": np.quantile(values, 0.75),
                "p95_deg": np.quantile(values, 0.95),
                "max_deg": np.max(values),
                "mean_deg": np.mean(values),
            })
    return pd.DataFrame(records)


def auc_table(data: pd.DataFrame) -> pd.DataFrame:
    records = []
    groups = [("POOLED", data)] + list(data.groupby("scenario", sort=True))
    for scope, group in groups:
        higher = auc_higher(
            group.rx_offaxis_min_deg.to_numpy(float),
            group.critical_before.to_numpy(bool),
        )
        records.append({
            "scope": scope,
            "safe_n": int((~group.critical_before).sum()),
            "critical_n": int(group.critical_before.sum()),
            "auc_higher_psi_predicts_critical": higher,
            "auc_lower_psi_predicts_critical": 1.0 - higher,
        })
    return pd.DataFrame(records)


def risk_bins(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    values = data.rx_offaxis_min_deg.to_numpy(float)
    edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, N_BINS + 1)))
    if len(edges) != N_BINS + 1:
        raise RuntimeError("Quantile binning collapsed because of tied values")
    frame = data.copy()
    frame["bin"] = pd.cut(
        frame.rx_offaxis_min_deg,
        bins=edges,
        include_lowest=True,
        duplicates="raise",
    )
    scenario_records = []
    balanced_records = []
    for interval, group in frame.groupby("bin", observed=True, sort=True):
        per_scenario = []
        for scenario, scenario_group in group.groupby("scenario", sort=True):
            n = len(scenario_group)
            k = int(scenario_group.critical_before.sum())
            low, high = cp(k, n)
            record = {
                "bin_left_deg": float(interval.left),
                "bin_right_deg": float(interval.right),
                "scenario": scenario,
                "n": n,
                "critical_events_k": k,
                "p_hat": k / n,
                "cp95_low": low,
                "cp95_high": high,
            }
            scenario_records.append(record)
            per_scenario.append(record)
        if len(per_scenario) != 8:
            raise RuntimeError(f"Bin {interval} does not contain all eight scenarios")
        simultaneous = [
            cp(row["critical_events_k"], row["n"], ALPHA / len(per_scenario))
            for row in per_scenario
        ]
        risks = np.array([row["p_hat"] for row in per_scenario])
        balanced_records.append({
            "bin_left_deg": float(interval.left),
            "bin_right_deg": float(interval.right),
            "psi_rx_min_center_deg": float(group.rx_offaxis_min_deg.median()),
            "scenario_count": len(per_scenario),
            "n_total": len(group),
            "n_min_per_scenario": min(row["n"] for row in per_scenario),
            "n_max_per_scenario": max(row["n"] for row in per_scenario),
            "critical_events_total": int(group.critical_before.sum()),
            "balanced_p_hat": float(risks.mean()),
            "balanced_simultaneous_cp95_low": float(np.mean([
                bounds[0] for bounds in simultaneous
            ])),
            "balanced_simultaneous_cp95_high": float(np.mean([
                bounds[1] for bounds in simultaneous
            ])),
            "scenario_q25": float(np.quantile(risks, 0.25)),
            "scenario_q75": float(np.quantile(risks, 0.75)),
            "interval_method": (
                "CP per scenario with alpha/8 Bonferroni simultaneous bounds; "
                "equal-weight mean of endpoints"
            ),
        })
    return pd.DataFrame(scenario_records), pd.DataFrame(balanced_records)


def threshold_grid(data: pd.DataFrame) -> np.ndarray:
    unique = np.unique(data.rx_offaxis_min_deg.to_numpy(float))
    if len(unique) < 2:
        raise RuntimeError("Insufficient unique psi_RX,min values")
    midpoints = (unique[:-1] + unique[1:]) / 2.0
    return np.concatenate(([np.nextafter(unique[0], -np.inf)], midpoints,
                           [np.nextafter(unique[-1], np.inf)]))


def scenario_threshold_metrics(group: pd.DataFrame, thresholds: np.ndarray) -> pd.DataFrame:
    ordered = group.sort_values("rx_offaxis_min_deg", kind="stable")
    psi = ordered.rx_offaxis_min_deg.to_numpy(float)
    critical = ordered.critical_before.to_numpy(bool)
    cumulative_critical = np.concatenate(([0], np.cumsum(critical, dtype=int)))
    activated = np.searchsorted(psi, thresholds, side="left")
    tp = cumulative_critical[activated]
    fp = activated - tp
    total_critical = int(critical.sum())
    total_safe = int((~critical).sum())
    fn = total_critical - tp
    detection = tp / total_critical
    false_activation = fp / total_safe
    activation = activated / len(group)
    missed = fn / total_critical
    precision = np.divide(
        tp, activated, out=np.ones_like(tp, dtype=float), where=activated > 0
    )
    detection_cp = cp_array(tp, total_critical, ALPHA)
    false_activation_cp = cp_array(fp, total_safe, ALPHA)
    activation_cp = cp_array(activated, len(group), ALPHA)
    missed_cp = cp_array(fn, total_critical, ALPHA)
    return pd.DataFrame({
        "psi_threshold_deg": thresholds,
        "critical_n": total_critical,
        "safe_n": total_safe,
        "total_n": len(group),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "activated_n": activated,
        "critical_detection_rate": detection,
        "critical_detection_cp95_low": detection_cp[0],
        "critical_detection_cp95_high": detection_cp[1],
        "false_activation_rate_among_safe": false_activation,
        "false_activation_cp95_low": false_activation_cp[0],
        "false_activation_cp95_high": false_activation_cp[1],
        "total_activation_rate": activation,
        "total_activation_cp95_low": activation_cp[0],
        "total_activation_cp95_high": activation_cp[1],
        "missed_critical_rate": missed,
        "missed_critical_cp95_low": missed_cp[0],
        "missed_critical_cp95_high": missed_cp[1],
        "precision_among_activations": precision,
        "youden_j": detection - false_activation,
    })


def threshold_sweep(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    thresholds = threshold_grid(data)
    pieces = []
    scenario_arrays = {}
    for scenario, group in data.groupby("scenario", sort=True):
        metrics = scenario_threshold_metrics(group, thresholds)
        metrics.insert(0, "scenario", scenario)
        pieces.append(metrics)
        scenario_arrays[scenario] = metrics
    by_scenario = pd.concat(pieces, ignore_index=True)

    scenarios = sorted(scenario_arrays)
    balanced = pd.DataFrame({"psi_threshold_deg": thresholds})
    point_metrics = [
        "critical_detection_rate", "false_activation_rate_among_safe",
        "total_activation_rate", "missed_critical_rate",
        "precision_among_activations", "youden_j",
    ]
    for metric in point_metrics:
        balanced[metric] = np.mean([
            scenario_arrays[scenario][metric].to_numpy(float)
            for scenario in scenarios
        ], axis=0)

    simultaneous_alpha = ALPHA / len(scenarios)
    probability_specs = {
        "critical_detection": ("tp", "critical_n"),
        "false_activation_among_safe": ("fp", "safe_n"),
        "total_activation": ("activated_n", "total_n"),
        "missed_critical": ("fn", "critical_n"),
    }
    for label, (success_col, total_col) in probability_specs.items():
        lows, highs = [], []
        for scenario in scenarios:
            frame = scenario_arrays[scenario]
            total = int(frame[total_col].iloc[0])
            low, high = cp_array(
                frame[success_col].to_numpy(int), total, simultaneous_alpha
            )
            lows.append(low)
            highs.append(high)
        balanced[f"{label}_balanced_simultaneous_cp95_low"] = np.mean(
            lows, axis=0
        )
        balanced[f"{label}_balanced_simultaneous_cp95_high"] = np.mean(
            highs, axis=0
        )

    loso_records = []
    for held_out in scenarios:
        training = [scenario_arrays[s] for s in scenarios if s != held_out]
        training_j = np.mean([x.youden_j.to_numpy(float) for x in training], axis=0)
        best_index = int(np.flatnonzero(training_j == np.nanmax(training_j))[0])
        threshold = float(thresholds[best_index])
        test = scenario_arrays[held_out].iloc[best_index]
        loso_records.append({
            "held_out_scenario": held_out,
            "training_scenario_count": len(training),
            "selected_threshold_deg": threshold,
            "training_balanced_youden_j": float(training_j[best_index]),
            "held_out_detection_rate": float(test.critical_detection_rate),
            "held_out_false_activation_rate_among_safe": float(
                test.false_activation_rate_among_safe
            ),
            "held_out_total_activation_rate": float(test.total_activation_rate),
            "held_out_missed_critical_rate": float(test.missed_critical_rate),
            "held_out_precision": float(test.precision_among_activations),
        })

    metadata = data[["scenario", "altitude_km", "eess_system", "load_factor"]]
    metadata = metadata.drop_duplicates("scenario").set_index("scenario")
    group_holdout_records = []
    for axis in ("altitude_km", "eess_system", "load_factor"):
        for held_value in sorted(metadata[axis].unique()):
            held_scenarios = metadata.index[metadata[axis] == held_value].tolist()
            train_scenarios = [s for s in scenarios if s not in held_scenarios]
            training_j = np.mean([
                scenario_arrays[s].youden_j.to_numpy(float)
                for s in train_scenarios
            ], axis=0)
            best_index = int(np.flatnonzero(training_j == np.nanmax(training_j))[0])
            test_frames = [scenario_arrays[s].iloc[best_index] for s in held_scenarios]
            group_holdout_records.append({
                "holdout_axis": axis,
                "held_out_value": held_value,
                "training_scenario_count": len(train_scenarios),
                "held_out_scenario_count": len(held_scenarios),
                "selected_threshold_deg": float(thresholds[best_index]),
                "training_balanced_youden_j": float(training_j[best_index]),
                "held_out_detection_rate": float(np.mean([
                    row.critical_detection_rate for row in test_frames
                ])),
                "held_out_false_activation_rate_among_safe": float(np.mean([
                    row.false_activation_rate_among_safe for row in test_frames
                ])),
                "held_out_total_activation_rate": float(np.mean([
                    row.total_activation_rate for row in test_frames
                ])),
                "held_out_missed_critical_rate": float(np.mean([
                    row.missed_critical_rate for row in test_frames
                ])),
            })
    return (
        by_scenario, balanced, pd.DataFrame(loso_records),
        pd.DataFrame(group_holdout_records),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unavailable"


def main() -> None:
    cp_error = validate_cp()
    data, sources = load_data()
    distributions = distribution_table(data)
    aucs = auc_table(data)
    bins_by_scenario, bins_balanced = risk_bins(data)
    sweep_by_scenario, sweep_balanced, loso, group_holdout = threshold_sweep(data)
    DESTINATION.mkdir(parents=True, exist_ok=True)

    data_columns = [
        "snapshot_id", "secondary_seed", "altitude_km", "eess_system",
        "load_factor", "scenario", "critical_before", "critical_after",
        "iagg_before_dbw_per_mhz", "iagg_after_dbw_per_mhz",
        "top1_joint_gain_suppression_db", "rx_visible_satellite_count",
        "rx_offaxis_min_satellite_idx", "rx_offaxis_min_deg",
    ]
    data[data_columns].to_csv(DESTINATION / "rx_min_merged_gb10.csv", index=False)
    distributions.to_csv(DESTINATION / "rx_min_distributions.csv", index=False)
    aucs.to_csv(DESTINATION / "rx_min_auc.csv", index=False)
    bins_by_scenario.to_csv(
        DESTINATION / "rx_min_risk_bins_by_scenario.csv", index=False
    )
    bins_balanced.to_csv(
        DESTINATION / "rx_min_risk_bins_balanced.csv", index=False
    )
    sweep_by_scenario.to_csv(
        DESTINATION / "rx_min_threshold_sweep_by_scenario.csv", index=False
    )
    sweep_balanced.to_csv(
        DESTINATION / "rx_min_threshold_sweep_balanced.csv", index=False
    )
    loso.to_csv(DESTINATION / "rx_min_threshold_loso.csv", index=False)
    group_holdout.to_csv(
        DESTINATION / "rx_min_threshold_group_holdout.csv", index=False
    )

    pooled_auc = aucs.loc[
        aucs.scope == "POOLED", "auc_lower_psi_predicts_critical"
    ].iloc[0]
    best_index = int(sweep_balanced.youden_j.idxmax())
    best = sweep_balanced.loc[best_index]
    summary = {
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "git_commit": git_commit(),
        "analysis_script_sha256": file_sha256(Path(__file__)),
        "geometry_cache": str(RX_MIN.resolve()),
        "geometry_cache_sha256": file_sha256(RX_MIN),
        "input_snapshot_csvs": sources,
        "filters": {
            "guard_band_mhz": 10,
            "critical_event": "iagg_before_dbw_per_mhz > -154",
            "scenario_count": 8,
            "snapshots_per_scenario": 5000,
        },
        "auc_lower_psi_predicts_critical": float(pooled_auc),
        "risk_bins": {
            "method": "10 global empirical quantile bins",
            "minimum_n_per_scenario_bin": int(
                bins_balanced.n_min_per_scenario.min()
            ),
            "confidence_interval": (
                "Clopper-Pearson per scenario/bin; alpha/8 Bonferroni "
                "simultaneous bounds averaged with equal scenario weight"
            ),
        },
        "threshold_sweep": {
            "rule": "consider handover when psi_RX_min < psi_threshold",
            "threshold_count": len(sweep_balanced),
            "selection_diagnostic": (
                "empirical maximum of scenario-balanced Youden J; descriptive, "
                "not a definitive threshold"
            ),
            "empirical_max_youden_threshold_deg": float(best.psi_threshold_deg),
            "balanced_detection_rate": float(best.critical_detection_rate),
            "balanced_false_activation_rate_among_safe": float(
                best.false_activation_rate_among_safe
            ),
            "balanced_total_activation_rate": float(best.total_activation_rate),
            "balanced_missed_critical_rate": float(best.missed_critical_rate),
            "loso_threshold_min_deg": float(loso.selected_threshold_deg.min()),
            "loso_threshold_q1_deg": float(loso.selected_threshold_deg.quantile(.25)),
            "loso_threshold_median_deg": float(loso.selected_threshold_deg.median()),
            "loso_threshold_q3_deg": float(loso.selected_threshold_deg.quantile(.75)),
            "loso_threshold_max_deg": float(loso.selected_threshold_deg.max()),
            "scenario_specific_threshold_min_deg": float(
                sweep_by_scenario.loc[
                    sweep_by_scenario.groupby("scenario").youden_j.idxmax(),
                    "psi_threshold_deg",
                ].min()
            ),
            "scenario_specific_threshold_max_deg": float(
                sweep_by_scenario.loc[
                    sweep_by_scenario.groupby("scenario").youden_j.idxmax(),
                    "psi_threshold_deg",
                ].max()
            ),
            "group_holdout_results": group_holdout.to_dict("records"),
        },
        "clopper_pearson_validation_max_abs_error": cp_error,
        "bootstrap_used_for_binomial_intervals": False,
    }
    (DESTINATION / "rx_min_analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

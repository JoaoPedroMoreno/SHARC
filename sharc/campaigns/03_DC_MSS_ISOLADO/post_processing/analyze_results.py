#!/usr/bin/env python3
"""Post-process Campaign 03 without modifying or rerunning SHARC outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


REQUIRED_COLUMNS = [
    "snapshot_id",
    "ue_id",
    "beam_id",
    "beam_active",
    "beam_affected_by_pbo",
    "power_backoff_db",
    "tx_power_dbm",
    "sinr_db",
    "snr_db",
    "spectral_efficiency_proxy",
    "requested_affected_fraction",
    "realized_affected_fraction",
]
KEY_COLUMNS = ["snapshot_id", "ue_id", "beam_id"]
GROUP_LABELS = {
    "all": "Todos os usuários",
    "affected": "Feixes afetados",
    "unaffected": "Feixes não afetados",
}
OUTAGE_THRESHOLDS = {
    "m1": -1.0,
    "m6": -6.0,
    "m10": -10.0,
}
OUTAGE_METRICS = {
    key: f"outage_probability_{key}"
    for key in OUTAGE_THRESHOLDS
}
MAIN_OUTAGE_METRIC = OUTAGE_METRICS["m6"]
BOOTSTRAP_METRICS = [
    "sinr_mean_db",
    "sinr_p5_db",
    "spectral_efficiency_mean_bpshz",
    "spectral_efficiency_p5_bpshz",
    *OUTAGE_METRICS.values(),
]
METRIC_LABELS = {
    "sinr_mean_db": "SINR média (dB)",
    "sinr_p5_db": "SINR P5 (dB)",
    "spectral_efficiency_mean_bpshz":
        "Proxy de eficiência espectral média (bit/s/Hz)",
    "spectral_efficiency_p5_bpshz":
        "Proxy de eficiência espectral P5 (bit/s/Hz)",
    "outage_probability_m1": "Outage para SINR < -1 dB",
    "outage_probability_m6": "Outage para SINR < -6 dB",
    "outage_probability_m10": "Outage para SINR < -10 dB",
}
EXPECTED_LOAD_FACTORS = (0.2, 0.5)
EXPECTED_PBO_LEVELS = (5.0, 10.0, 15.0, 20.0)
EXPECTED_FRACTIONS = (0.05, 0.10, 0.15)
STATUS_ORDER = {"PASS": 0, "WARNING": 1, "FAIL": 2}


@dataclass
class Scenario:
    scenario_id: str
    output_path: str
    yaml_path: str
    metrics_csv_path: str
    load_factor: float
    pbo_db: float
    requested_fraction: float
    configured_snapshots: int
    actual_snapshots: int
    user_records: int
    unique_ue_ids: int
    nominal_tx_power_dbm: float
    attenuation_factor: float
    sinr_min_db: float
    sinr_max_db: float
    pbo_mode: str
    candidate_count: int = 1
    discarded_candidate_paths: str = ""


class QCRecorder:
    """Collect machine-readable quality-control findings."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(
        self,
        check: str,
        status: str,
        message: str,
        scenario_id: str = "campaign",
    ) -> None:
        if status not in STATUS_ORDER:
            raise ValueError(f"Unknown QC status: {status}")
        self.rows.append({
            "check": check,
            "status": status,
            "scenario_id": scenario_id,
            "message": message,
        })

    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.rows,
            columns=["check", "status", "scenario_id", "message"],
        )

    def has_failures(self) -> bool:
        return any(row["status"] == "FAIL" for row in self.rows)

    def warning_count(self) -> int:
        return sum(row["status"] == "WARNING" for row in self.rows)


def nested_get(mapping: dict, *keys: str, default=None):
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def scenario_id(load_factor: float, pbo_db: float, fraction: float) -> str:
    return (
        f"LF{int(round(100 * load_factor)):02d}_"
        f"PBO{int(round(pbo_db)):02d}_"
        f"F{int(round(100 * fraction)):02d}"
    )


def stable_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(label.encode("ascii")).digest()
    return (base_seed + int.from_bytes(digest[:4], "little")) % (2**32)


def csv_has_structured_schema(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            header = stream.readline().strip().split(",")
    except OSError:
        return False
    return set(REQUIRED_COLUMNS).issubset(header)


def find_structured_csv(directory: Path) -> Path | None:
    candidates = []
    for path in directory.glob("*.csv"):
        if csv_has_structured_schema(path):
            candidates.append(path)
    if not candidates:
        return None
    expected = [p for p in candidates if p.name == "imt_dl_selected_ue_metrics.csv"]
    return max(expected or candidates, key=lambda p: p.stat().st_size)


def inspect_csv_counts(path: Path | None) -> tuple[int, int, int]:
    if path is None or not path.exists():
        return 0, 0, 0
    snapshots: set[int] = set()
    ue_ids: set[int] = set()
    rows = 0
    for chunk in pd.read_csv(
        path,
        usecols=["snapshot_id", "ue_id"],
        chunksize=250_000,
    ):
        rows += len(chunk)
        snapshots.update(
            pd.to_numeric(chunk["snapshot_id"], errors="coerce")
            .dropna().astype(int).unique().tolist()
        )
        ue_ids.update(
            pd.to_numeric(chunk["ue_id"], errors="coerce")
            .dropna().astype(int).unique().tolist()
        )
    return len(snapshots), rows, len(ue_ids)


def parse_yaml_candidate(yaml_path: Path) -> dict:
    with yaml_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    power_control = nested_get(
        config,
        "imt",
        "topology",
        "mss_dc",
        "power_control_zones",
        default={},
    ) or {}
    return {
        "yaml_path": str(yaml_path.resolve()),
        "load_factor": float(nested_get(
            config, "imt", "bs", "load_probability", default=np.nan)),
        "pbo_db": float(power_control.get("power_backoff_db", 0.0) or 0.0),
        "requested_fraction": float(
            power_control.get("affected_fraction", 0.0) or 0.0),
        "configured_snapshots": int(
            nested_get(config, "general", "num_snapshots", default=0) or 0),
        "nominal_tx_power_dbm": float(
            nested_get(config, "imt", "bs", "conducted_power", default=np.nan)),
        "attenuation_factor": float(nested_get(
            config,
            "imt",
            "downlink",
            "attenuation_factor",
            default=np.nan,
        )),
        "sinr_min_db": float(nested_get(
            config, "imt", "downlink", "sinr_min", default=np.nan)),
        "sinr_max_db": float(nested_get(
            config, "imt", "downlink", "sinr_max", default=np.nan)),
        "pbo_mode": str(power_control.get("mode", "GEOGRAPHIC")),
    }


def discover_scenarios(
    campaign_dir: Path,
) -> tuple[list[Scenario], pd.DataFrame]:
    """Discover all output candidates and select the most complete per config."""
    output_root = campaign_dir / "output"
    yaml_paths = sorted(output_root.rglob("*.yaml"))
    candidates: list[dict] = []
    for yaml_path in yaml_paths:
        try:
            parsed = parse_yaml_candidate(yaml_path)
        except (OSError, ValueError, yaml.YAMLError, TypeError):
            continue
        load_factor = parsed["load_factor"]
        if not np.isfinite(load_factor):
            continue
        metrics_csv = find_structured_csv(yaml_path.parent)
        actual_snapshots, user_records, unique_ues = inspect_csv_counts(
            metrics_csv)
        pbo_db = parsed["pbo_db"]
        fraction = parsed["requested_fraction"] if pbo_db > 0 else 0.0
        parsed["requested_fraction"] = fraction
        sid = scenario_id(load_factor, pbo_db, fraction)
        candidates.append({
            **parsed,
            "scenario_id": sid,
            "output_path": str(yaml_path.parent.resolve()),
            "metrics_csv_path":
                str(metrics_csv.resolve()) if metrics_csv else "",
            "actual_snapshots": actual_snapshots,
            "user_records": user_records,
            "unique_ue_ids": unique_ues,
            "metrics_csv_bytes":
                metrics_csv.stat().st_size if metrics_csv else 0,
            "modified_ns": yaml_path.parent.stat().st_mtime_ns,
        })

    candidate_df = pd.DataFrame(candidates)
    selected: list[Scenario] = []
    if candidate_df.empty:
        return selected, candidate_df

    for sid, group in candidate_df.groupby("scenario_id", sort=True):
        ranked = group.sort_values(
            ["actual_snapshots", "user_records", "metrics_csv_bytes",
             "modified_ns"],
            ascending=False,
        )
        chosen = ranked.iloc[0].to_dict()
        discarded = ranked.iloc[1:]["output_path"].tolist()
        chosen["candidate_count"] = len(ranked)
        chosen["discarded_candidate_paths"] = " | ".join(discarded)
        selected.append(Scenario(**{
            key: chosen[key]
            for key in Scenario.__dataclass_fields__
        }))

    candidate_df["selected"] = False
    selected_paths = {scenario.output_path for scenario in selected}
    candidate_df.loc[
        candidate_df["output_path"].isin(selected_paths), "selected"
    ] = True
    candidate_df = candidate_df.sort_values([
        "load_factor", "pbo_db", "requested_fraction",
        "actual_snapshots", "output_path",
    ]).reset_index(drop=True)
    selected.sort(key=lambda item: (
        item.load_factor, item.pbo_db, item.requested_fraction))
    return selected, candidate_df


def normalize_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    mapping = {
        "true": True, "1": True, "yes": True,
        "false": False, "0": False, "no": False,
    }
    return normalized.map(mapping)


def load_scenario_dataframe(scenario: Scenario) -> pd.DataFrame:
    path = Path(scenario.metrics_csv_path)
    frame = pd.read_csv(path, usecols=REQUIRED_COLUMNS)
    for column in ["beam_active", "beam_affected_by_pbo"]:
        frame[column] = normalize_bool(frame[column])
    for column in set(REQUIRED_COLUMNS) - {
        "beam_active", "beam_affected_by_pbo",
    }:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(KEY_COLUMNS, kind="mergesort").reset_index(
        drop=True)
    return frame


def key_digest(frame: pd.DataFrame) -> str:
    values = frame[KEY_COLUMNS].to_numpy(dtype=np.int64, copy=False)
    return hashlib.sha256(values.tobytes()).hexdigest()


def sharc_spectral_efficiency_proxy(
    sinr_db: np.ndarray,
    sinr_min_db: float,
    sinr_max_db: float,
    attenuation_factor: float,
) -> np.ndarray:
    sinr = np.asarray(sinr_db, dtype=float)
    result = attenuation_factor * np.log2(
        1.0 + np.power(10.0, 0.1 * sinr))
    result = np.where(sinr < sinr_min_db, 0.0, result)
    maximum = attenuation_factor * math.log2(
        1.0 + math.pow(10.0, 0.1 * sinr_max_db))
    result = np.where(sinr > sinr_max_db, maximum, result)
    return result


def validate_dataframe(
    scenario: Scenario,
    frame: pd.DataFrame,
    qc: QCRecorder,
    tolerance: float = 1e-8,
) -> dict:
    sid = scenario.scenario_id
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    qc.add(
        "required_columns",
        "FAIL" if missing else "PASS",
        f"Colunas ausentes: {missing}" if missing
        else f"As {len(REQUIRED_COLUMNS)} colunas obrigatórias estão presentes.",
        sid,
    )
    if missing:
        return {}

    numeric_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in {"beam_active", "beam_affected_by_pbo"}
    ]
    missing_count = int(frame[REQUIRED_COLUMNS].isna().sum().sum())
    finite = np.isfinite(frame[numeric_columns].to_numpy(dtype=float)).all()
    qc.add(
        "finite_values",
        "FAIL" if missing_count or not finite else "PASS",
        f"NaN={missing_count}; todos finitos={finite}.",
        sid,
    )

    duplicate_count = int(frame.duplicated(KEY_COLUMNS, keep=False).sum())
    qc.add(
        "unique_snapshot_ue_beam",
        "FAIL" if duplicate_count else "PASS",
        f"Registros em chaves duplicadas: {duplicate_count}.",
        sid,
    )

    actual_snapshots = int(frame["snapshot_id"].nunique())
    expected = scenario.configured_snapshots
    qc.add(
        "snapshot_count",
        "PASS" if actual_snapshots == expected else "FAIL",
        f"Snapshots observados={actual_snapshots}; configurados={expected}.",
        sid,
    )

    inactive_records = int((~frame["beam_active"].fillna(False)).sum())
    qc.add(
        "selected_beams_active",
        "PASS" if inactive_records == 0 else "FAIL",
        f"Registros selecionados com beam_active=False: {inactive_records}.",
        sid,
    )

    affected = frame["beam_affected_by_pbo"].fillna(False).to_numpy(bool)
    pbo_values = frame["power_backoff_db"].to_numpy(float)
    tx_values = frame["tx_power_dbm"].to_numpy(float)
    expected_pbo = np.where(affected, scenario.pbo_db, 0.0)
    pbo_error = float(np.nanmax(np.abs(pbo_values - expected_pbo)))
    expected_tx = scenario.nominal_tx_power_dbm - expected_pbo
    tx_error = float(np.nanmax(np.abs(tx_values - expected_tx)))
    qc.add(
        "tx_power_consistency",
        "PASS" if pbo_error <= tolerance and tx_error <= tolerance else "FAIL",
        f"Erro máximo PBO={pbo_error:.3g} dB; "
        f"erro máximo de potência={tx_error:.3g} dB.",
        sid,
    )

    unaffected_error = float(np.nanmax(np.abs(
        tx_values[~affected] - scenario.nominal_tx_power_dbm
    ))) if np.any(~affected) else 0.0
    qc.add(
        "unaffected_nominal_power",
        "PASS" if unaffected_error <= tolerance else "FAIL",
        f"Erro máximo em feixes não afetados={unaffected_error:.3g} dB.",
        sid,
    )

    grouped = frame.groupby("snapshot_id", sort=False)
    observed_realized = grouped["beam_affected_by_pbo"].mean()
    stored_realized = grouped["realized_affected_fraction"].first()
    stored_spread = grouped["realized_affected_fraction"].nunique().max()
    stored_error = float(np.max(np.abs(
        observed_realized.to_numpy() - stored_realized.to_numpy()
    )))
    active_counts = grouped.size().to_numpy()
    expected_counts = np.floor(
        scenario.requested_fraction * active_counts + 0.5).astype(int)
    expected_realized = np.divide(
        expected_counts,
        active_counts,
        out=np.zeros_like(active_counts, dtype=float),
        where=active_counts > 0,
    )
    rounding_error = float(np.max(np.abs(
        observed_realized.to_numpy() - expected_realized
    )))
    fraction_ok = (
        stored_spread == 1
        and stored_error <= tolerance
        and rounding_error <= tolerance
    )
    qc.add(
        "realized_fraction",
        "PASS" if fraction_ok else "FAIL",
        f"Erro salvo/observado={stored_error:.3g}; "
        f"erro de arredondamento={rounding_error:.3g}; "
        f"máximo de valores distintos por snapshot={stored_spread}.",
        sid,
    )

    no_affected = int((grouped[
        "beam_affected_by_pbo"].sum() == 0).sum())
    if scenario.pbo_db > 0 and scenario.requested_fraction > 0:
        status = "WARNING" if no_affected else "PASS"
    else:
        status = "PASS"
    qc.add(
        "snapshots_without_affected_beams",
        status,
        f"Snapshots sem feixe afetado: {no_affected}.",
        sid,
    )

    proxy_expected = sharc_spectral_efficiency_proxy(
        frame["sinr_db"].to_numpy(float),
        scenario.sinr_min_db,
        scenario.sinr_max_db,
        scenario.attenuation_factor,
    )
    proxy_error = float(np.max(np.abs(
        proxy_expected
        - frame["spectral_efficiency_proxy"].to_numpy(float)
    )))
    qc.add(
        "spectral_efficiency_proxy_formula",
        "PASS" if proxy_error <= 1e-9 else "FAIL",
        f"Erro absoluto máximo contra a equação do SHARC={proxy_error:.3g}.",
        sid,
    )
    return {
        "key_digest": key_digest(frame),
        "mask": affected.copy(),
        "actual_snapshots": actual_snapshots,
        "user_records": len(frame),
        "no_affected_snapshots": no_affected,
        "realized_fraction_mean": float(observed_realized.mean()),
        "realized_fraction_std": float(observed_realized.std(ddof=1)),
    }


def masks_are_nested(smaller: np.ndarray, larger: np.ndarray) -> bool:
    smaller = np.asarray(smaller, dtype=bool)
    larger = np.asarray(larger, dtype=bool)
    return smaller.shape == larger.shape and not np.any(smaller & ~larger)


def validate_cross_scenario(
    scenarios: Sequence[Scenario],
    summaries: dict[str, dict],
    qc: QCRecorder,
) -> dict[tuple[float, float], bool]:
    by_key = {
        (item.load_factor, item.pbo_db, item.requested_fraction): item
        for item in scenarios
    }
    pairable: dict[tuple[float, float], bool] = {}

    for load_factor in EXPECTED_LOAD_FACTORS:
        baseline = by_key.get((load_factor, 0.0, 0.0))
        if baseline is None:
            continue
        baseline_summary = summaries.get(baseline.scenario_id, {})
        for fraction in EXPECTED_FRACTIONS:
            members = [
                by_key.get((load_factor, pbo, fraction))
                for pbo in EXPECTED_PBO_LEVELS
            ]
            complete = all(
                member is not None and member.scenario_id in summaries
                for member in members
            )
            masks_equal = complete
            geometry_equal = complete
            if complete:
                reference = summaries[members[0].scenario_id]
                for member in members[1:]:
                    current = summaries[member.scenario_id]
                    masks_equal &= (
                        current["key_digest"] == reference["key_digest"]
                        and np.array_equal(current["mask"], reference["mask"])
                    )
                geometry_equal &= all(
                    summaries[member.scenario_id]["key_digest"]
                    == baseline_summary.get("key_digest")
                    for member in members
                )
            label = (
                f"LF={load_factor:.1f}, fração={100 * fraction:.0f}%")
            qc.add(
                "identical_masks_across_pbo",
                "PASS" if masks_equal else "FAIL",
                f"{label}: máscaras de 5, 10, 15 e 20 dB "
                f"{'idênticas' if masks_equal else 'não idênticas'}.",
            )
            qc.add(
                "paired_geometry_and_users",
                "PASS" if geometry_equal else "FAIL",
                f"{label}: chaves snapshot_id+ue_id+beam_id "
                f"{'coincidem' if geometry_equal else 'não coincidem'} "
                "com o baseline.",
            )
            pairable[(load_factor, fraction)] = bool(
                masks_equal and geometry_equal)

        for pbo in EXPECTED_PBO_LEVELS:
            items = [
                by_key.get((load_factor, pbo, fraction))
                for fraction in EXPECTED_FRACTIONS
            ]
            nested = all(item is not None for item in items)
            if nested:
                masks = [summaries[item.scenario_id]["mask"] for item in items]
                digests = [
                    summaries[item.scenario_id]["key_digest"] for item in items
                ]
                nested = (
                    len(set(digests)) == 1
                    and masks_are_nested(masks[0], masks[1])
                    and masks_are_nested(masks[1], masks[2])
                )
            qc.add(
                "nested_fraction_masks",
                "PASS" if nested else "FAIL",
                f"LF={load_factor:.1f}, PBO={pbo:.0f} dB: "
                f"5% ⊆ 10% ⊆ 15% = {nested}.",
            )
    return pairable


def select_group(frame: pd.DataFrame, group: str) -> pd.DataFrame:
    if group == "all":
        return frame
    affected = frame["beam_affected_by_pbo"].to_numpy(bool)
    if group == "affected":
        return frame.loc[affected]
    if group == "unaffected":
        return frame.loc[~affected]
    raise ValueError(f"Unknown group: {group}")


def classify_baseline(
    baseline: pd.DataFrame,
    mask_source: pd.DataFrame,
) -> pd.DataFrame | None:
    baseline_sorted = baseline.sort_values(
        KEY_COLUMNS, kind="mergesort").reset_index(drop=True)
    source_sorted = mask_source.sort_values(
        KEY_COLUMNS, kind="mergesort").reset_index(drop=True)
    if len(baseline_sorted) != len(source_sorted):
        return None
    if not np.array_equal(
        baseline_sorted[KEY_COLUMNS].to_numpy(),
        source_sorted[KEY_COLUMNS].to_numpy(),
    ):
        return None
    result = baseline_sorted.copy()
    result["beam_affected_by_pbo"] = source_sorted[
        "beam_affected_by_pbo"].to_numpy(bool)
    return result


def linear_quantile(values: pd.Series | np.ndarray, quantile: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), quantile,
                             method="linear"))


def calculate_metrics(
    frame: pd.DataFrame,
    outage_threshold: float,
) -> dict:
    outage_fields = {
        metric: np.nan for metric in OUTAGE_METRICS.values()
    }
    if frame.empty:
        return {
            "n_snapshots": 0,
            "n_users": 0,
            "realized_affected_fraction_mean": np.nan,
            "realized_affected_fraction_std": np.nan,
            "sinr_mean_db": np.nan,
            "sinr_p5_db": np.nan,
            "sinr_median_db": np.nan,
            "spectral_efficiency_mean_bpshz": np.nan,
            "spectral_efficiency_p5_bpshz": np.nan,
            "spectral_efficiency_median_bpshz": np.nan,
            "outage_probability": np.nan,
            **outage_fields,
        }
    realized_by_snapshot = frame.groupby(
        "snapshot_id")["realized_affected_fraction"].first()
    sinr = frame["sinr_db"].to_numpy(float)
    efficiency = frame["spectral_efficiency_proxy"].to_numpy(float)
    outage_fields = {
        OUTAGE_METRICS[key]: float(np.mean(sinr < threshold))
        for key, threshold in OUTAGE_THRESHOLDS.items()
    }
    return {
        "n_snapshots": int(frame["snapshot_id"].nunique()),
        "n_users": int(len(frame)),
        "realized_affected_fraction_mean":
            float(realized_by_snapshot.mean()),
        "realized_affected_fraction_std":
            float(realized_by_snapshot.std(ddof=1)),
        "sinr_mean_db": float(np.mean(sinr)),
        "sinr_p5_db": linear_quantile(sinr, 0.05),
        "sinr_median_db": linear_quantile(sinr, 0.50),
        "spectral_efficiency_mean_bpshz": float(np.mean(efficiency)),
        "spectral_efficiency_p5_bpshz":
            linear_quantile(efficiency, 0.05),
        "spectral_efficiency_median_bpshz":
            linear_quantile(efficiency, 0.50),
        "outage_probability": float(np.mean(sinr < outage_threshold)),
        **outage_fields,
    }


def generate_bootstrap_counts(
    n_snapshots: int,
    repetitions: int,
    seed: int,
) -> np.ndarray:
    if n_snapshots <= 0 or repetitions <= 0:
        raise ValueError("n_snapshots and repetitions must be positive")
    rng = np.random.default_rng(seed)
    probabilities = np.full(n_snapshots, 1.0 / n_snapshots)
    counts = rng.multinomial(
        n_snapshots, probabilities, size=repetitions)
    maximum = int(counts.max())
    dtype = np.int16 if maximum <= np.iinfo(np.int16).max else np.int32
    return counts.astype(dtype, copy=False)


def _weighted_order_statistics(
    values: np.ndarray,
    companion: np.ndarray,
    snapshot_codes: np.ndarray,
    bootstrap_counts: np.ndarray,
    sample_sizes: np.ndarray,
    quantile: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact linear quantiles for snapshot-weighted bootstrap samples."""
    values = np.asarray(values, dtype=float)
    companion = np.asarray(companion, dtype=float)
    snapshot_codes = np.asarray(snapshot_codes, dtype=np.int32)
    repetitions, n_snapshots = bootstrap_counts.shape
    if values.size == 0:
        empty = np.full(repetitions, np.nan)
        return empty, empty.copy()

    order = np.argsort(values, kind="mergesort")
    global_values = values[order]
    global_companion = companion[order]
    per_snapshot = [
        np.sort(values[snapshot_codes == code])
        for code in range(n_snapshots)
    ]

    h = (sample_sizes.astype(float) - 1.0) * quantile
    lower_rank = np.floor(h).astype(np.int64)
    upper_rank = np.ceil(h).astype(np.int64)
    targets = np.concatenate([lower_rank, upper_rank])
    repeated_counts = np.concatenate(
        [bootstrap_counts, bootstrap_counts], axis=0)
    low = np.zeros(2 * repetitions, dtype=np.int64)
    high = np.full(2 * repetitions, values.size - 1, dtype=np.int64)

    while np.any(low < high):
        middle = (low + high) // 2
        thresholds = global_values[middle]
        cumulative = np.zeros(2 * repetitions, dtype=np.int64)
        for code, snapshot_values in enumerate(per_snapshot):
            if snapshot_values.size == 0:
                continue
            positions = np.searchsorted(
                snapshot_values, thresholds, side="right")
            cumulative += (
                repeated_counts[:, code].astype(np.int64) * positions)
        go_left = cumulative > targets
        high = np.where(go_left, middle, high)
        low = np.where(go_left, low, middle + 1)

    lower_indices = low[:repetitions]
    upper_indices = low[repetitions:]
    gamma = h - lower_rank
    value_result = (
        global_values[lower_indices] * (1.0 - gamma)
        + global_values[upper_indices] * gamma
    )
    companion_result = (
        global_companion[lower_indices] * (1.0 - gamma)
        + global_companion[upper_indices] * gamma
    )
    zero_samples = sample_sizes <= 0
    value_result[zero_samples] = np.nan
    companion_result[zero_samples] = np.nan
    return value_result, companion_result


def cluster_bootstrap_distribution(
    frame: pd.DataFrame,
    all_snapshot_ids: Sequence[int],
    bootstrap_counts: np.ndarray,
    outage_threshold: float,
) -> dict[str, np.ndarray]:
    """Bootstrap user-level estimands while resampling complete snapshots."""
    snapshot_ids = np.asarray(sorted(all_snapshot_ids), dtype=np.int64)
    snapshot_lookup = {value: idx for idx, value in enumerate(snapshot_ids)}
    codes = frame["snapshot_id"].map(snapshot_lookup)
    if codes.isna().any():
        raise ValueError("Frame contains snapshot IDs outside bootstrap domain")
    codes_array = codes.to_numpy(dtype=np.int32)
    n_snapshots = len(snapshot_ids)
    if bootstrap_counts.shape[1] != n_snapshots:
        raise ValueError("bootstrap_counts has incompatible snapshot dimension")

    sinr = frame["sinr_db"].to_numpy(float)
    efficiency = frame["spectral_efficiency_proxy"].to_numpy(float)
    row_counts = np.bincount(
        codes_array, minlength=n_snapshots).astype(np.int64)
    sinr_sums = np.bincount(
        codes_array, weights=sinr, minlength=n_snapshots)
    efficiency_sums = np.bincount(
        codes_array, weights=efficiency, minlength=n_snapshots)
    outage_sums = {
        key: np.bincount(
            codes_array,
            weights=(sinr < threshold).astype(float),
            minlength=n_snapshots,
        )
        for key, threshold in OUTAGE_THRESHOLDS.items()
    }
    counts_float = bootstrap_counts.astype(float, copy=False)
    sample_sizes = counts_float @ row_counts
    with np.errstate(divide="ignore", invalid="ignore"):
        sinr_mean = (counts_float @ sinr_sums) / sample_sizes
        efficiency_mean = (counts_float @ efficiency_sums) / sample_sizes
        outage = {
            key: (counts_float @ sums) / sample_sizes
            for key, sums in outage_sums.items()
        }
    sinr_p5, efficiency_p5 = _weighted_order_statistics(
        sinr,
        efficiency,
        codes_array,
        bootstrap_counts,
        sample_sizes,
        0.05,
    )
    return {
        "sinr_mean_db": sinr_mean,
        "sinr_p5_db": sinr_p5,
        "spectral_efficiency_mean_bpshz": efficiency_mean,
        "spectral_efficiency_p5_bpshz": efficiency_p5,
        "outage_probability": outage["m6"],
        **{
            OUTAGE_METRICS[key]: values
            for key, values in outage.items()
        },
    }


def percentile_interval(values: np.ndarray) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    lower, upper = np.quantile(
        finite, [0.025, 0.975], method="linear")
    return float(lower), float(upper)


def bootstrap_records(
    scenario: Scenario,
    group: str,
    analysis_fraction: float,
    point_metrics: dict,
    distributions: dict[str, np.ndarray],
    repetitions: int,
    seed: int,
) -> list[dict]:
    rows = []
    for metric in BOOTSTRAP_METRICS:
        lower, upper = percentile_interval(distributions[metric])
        rows.append({
            "scenario_id": scenario.scenario_id,
            "load_factor": scenario.load_factor,
            "pbo_db": scenario.pbo_db,
            "affected_fraction": analysis_fraction,
            "group": group,
            "metric": metric,
            "estimate": point_metrics[metric],
            "ci95_lower": lower,
            "ci95_upper": upper,
            "repetitions": repetitions,
            "seed": seed,
            "analysis_type": "absolute",
        })
    return rows


def paired_bootstrap_differences(
    scenario_distribution: dict[str, np.ndarray],
    baseline_distribution: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    return {
        metric: (
            np.asarray(scenario_distribution[metric])
            - np.asarray(baseline_distribution[metric])
        )
        for metric in BOOTSTRAP_METRICS
    }


def paired_difference_records(
    scenario: Scenario,
    group: str,
    analysis_fraction: float,
    scenario_points: dict,
    baseline_points: dict,
    differences: dict[str, np.ndarray],
    repetitions: int,
    seed: int,
) -> list[dict]:
    rows = []
    for metric in BOOTSTRAP_METRICS:
        lower, upper = percentile_interval(differences[metric])
        rows.append({
            "scenario_id": scenario.scenario_id,
            "load_factor": scenario.load_factor,
            "pbo_db": scenario.pbo_db,
            "affected_fraction": analysis_fraction,
            "group": group,
            "metric": metric,
            "estimate": scenario_points[metric] - baseline_points[metric],
            "ci95_lower": lower,
            "ci95_upper": upper,
            "repetitions": repetitions,
            "seed": seed,
            "analysis_type": "paired_delta_pbo_minus_baseline",
        })
    return rows


def ensure_generated_dirs(output_dir: Path) -> dict[str, Path]:
    paths = {
        "root": output_dir,
        "data": output_dir / "data",
        "figures": output_dir / "figures",
        "supplementary": output_dir / "figures" / "supplementary",
        "tables": output_dir / "tables",
        "reports": output_dir / "reports",
        "quality_control": output_dir / "quality_control",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_qc_outputs(
    qc: QCRecorder,
    paths: dict[str, Path],
) -> None:
    frame = qc.dataframe()
    frame.to_csv(
        paths["quality_control"] / "qc_summary.csv",
        index=False,
        encoding="utf-8",
    )
    counts = frame["status"].value_counts().to_dict() if not frame.empty else {}
    lines = [
        "# Relatório de controle de qualidade",
        "",
        "Este relatório foi produzido sem alterar os outputs brutos.",
        "",
        "## Resumo",
        "",
        f"- PASS: {counts.get('PASS', 0)}",
        f"- WARNING: {counts.get('WARNING', 0)}",
        f"- FAIL: {counts.get('FAIL', 0)}",
        "",
        "## Verificações",
        "",
        "| Status | Verificação | Cenário | Evidência |",
        "|---|---|---|---|",
    ]
    for row in frame.itertuples(index=False):
        message = str(row.message).replace("|", "\\|")
        lines.append(
            f"| {row.status} | `{row.check}` | `{row.scenario_id}` | "
            f"{message} |"
        )
    (paths["quality_control"] / "qc_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def validate_campaign_inventory(
    scenarios: Sequence[Scenario],
    candidate_df: pd.DataFrame,
    qc: QCRecorder,
) -> None:
    count = len(scenarios)
    qc.add(
        "selected_scenario_count",
        "PASS" if count == 26 else "FAIL",
        f"Cenários selecionados={count}; esperado=26.",
    )
    baselines = [item for item in scenarios if item.pbo_db == 0.0]
    baseline_loads = sorted(item.load_factor for item in baselines)
    qc.add(
        "baseline_count",
        "PASS" if baseline_loads == list(EXPECTED_LOAD_FACTORS) else "FAIL",
        f"Baselines por load factor={baseline_loads}.",
    )
    positive_counts = {
        load_factor: sum(
            item.load_factor == load_factor and item.pbo_db > 0
            for item in scenarios
        )
        for load_factor in EXPECTED_LOAD_FACTORS
    }
    qc.add(
        "positive_scenarios_per_load_factor",
        "PASS" if all(value == 12 for value in positive_counts.values())
        else "FAIL",
        f"Contagens={positive_counts}; esperado=12 por load factor.",
    )
    actual_loads = sorted({round(item.load_factor, 8) for item in scenarios})
    actual_pbo = sorted({round(item.pbo_db, 8) for item in scenarios})
    actual_fractions = sorted({
        round(item.requested_fraction, 8)
        for item in scenarios if item.pbo_db > 0
    })
    unique_ok = (
        actual_loads == list(EXPECTED_LOAD_FACTORS)
        and actual_pbo == [0.0, *EXPECTED_PBO_LEVELS]
        and actual_fractions == list(EXPECTED_FRACTIONS)
    )
    qc.add(
        "configured_parameter_levels",
        "PASS" if unique_ok else "FAIL",
        f"LF={actual_loads}; PBO={actual_pbo}; frações={actual_fractions}.",
    )
    superseded = int((~candidate_df["selected"]).sum()) \
        if not candidate_df.empty else 0
    qc.add(
        "superseded_output_candidates",
        "WARNING" if superseded else "PASS",
        f"Diretórios candidatos não selecionados por estarem menos completos: "
        f"{superseded}.",
    )


def scenario_row(
    scenario: Scenario,
    group: str,
    analysis_fraction: float,
    metrics: dict,
    baseline_mask_paired: bool,
) -> dict:
    return {
        "scenario_id": scenario.scenario_id,
        "load_factor": scenario.load_factor,
        "pbo_db": scenario.pbo_db,
        "affected_fraction": analysis_fraction,
        "group": group,
        "baseline_mask_paired": baseline_mask_paired,
        **metrics,
    }


def process_metrics_and_bootstrap(
    scenarios: Sequence[Scenario],
    summaries: dict[str, dict],
    pairable: dict[tuple[float, float], bool],
    outage_threshold: float,
    repetitions: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    by_key = {
        (item.load_factor, item.pbo_db, item.requested_fraction): item
        for item in scenarios
    }
    metric_rows: list[dict] = []
    bootstrap_rows: list[dict] = []
    paired_rows: list[dict] = []

    for load_factor in EXPECTED_LOAD_FACTORS:
        baseline = by_key[(load_factor, 0.0, 0.0)]
        baseline_frame = load_scenario_dataframe(baseline)
        snapshot_ids = sorted(
            baseline_frame["snapshot_id"].astype(int).unique().tolist())
        counts = generate_bootstrap_counts(
            len(snapshot_ids), repetitions, seed)

        baseline_points_all = calculate_metrics(
            baseline_frame, outage_threshold)
        baseline_dist_all = cluster_bootstrap_distribution(
            baseline_frame,
            snapshot_ids,
            counts,
            outage_threshold,
        )
        metric_rows.append(scenario_row(
            baseline, "all", 0.0, baseline_points_all, False))
        bootstrap_rows.extend(bootstrap_records(
            baseline,
            "all",
            0.0,
            baseline_points_all,
            baseline_dist_all,
            repetitions,
            seed,
        ))
        baseline_cache: dict[tuple[float, str], tuple[dict, dict]] = {
            (fraction, "all"): (
                baseline_points_all, baseline_dist_all)
            for fraction in EXPECTED_FRACTIONS
        }

        for fraction in EXPECTED_FRACTIONS:
            if not pairable.get((load_factor, fraction), False):
                continue
            source = by_key[(load_factor, 5.0, fraction)]
            classified = baseline_frame.copy()
            classified["beam_affected_by_pbo"] = summaries[
                source.scenario_id]["mask"]
            for group in ("affected", "unaffected"):
                group_frame = select_group(classified, group)
                points = calculate_metrics(group_frame, outage_threshold)
                distribution = cluster_bootstrap_distribution(
                    group_frame,
                    snapshot_ids,
                    counts,
                    outage_threshold,
                )
                baseline_cache[(fraction, group)] = (points, distribution)
                metric_rows.append(scenario_row(
                    baseline, group, fraction, points, True))
                bootstrap_rows.extend(bootstrap_records(
                    baseline,
                    group,
                    fraction,
                    points,
                    distribution,
                    repetitions,
                    seed,
                ))

        positives = sorted(
            (
                item for item in scenarios
                if item.load_factor == load_factor and item.pbo_db > 0
            ),
            key=lambda item: (item.requested_fraction, item.pbo_db),
        )
        for scenario in positives:
            frame = load_scenario_dataframe(scenario)
            for group in ("all", "affected", "unaffected"):
                group_frame = select_group(frame, group)
                points = calculate_metrics(group_frame, outage_threshold)
                distribution = cluster_bootstrap_distribution(
                    group_frame,
                    snapshot_ids,
                    counts,
                    outage_threshold,
                )
                metric_rows.append(scenario_row(
                    scenario,
                    group,
                    scenario.requested_fraction,
                    points,
                    False,
                ))
                bootstrap_rows.extend(bootstrap_records(
                    scenario,
                    group,
                    scenario.requested_fraction,
                    points,
                    distribution,
                    repetitions,
                    seed,
                ))
                baseline_values = baseline_cache.get(
                    (scenario.requested_fraction, group))
                if baseline_values is None:
                    continue
                baseline_points, baseline_distribution = baseline_values
                differences = paired_bootstrap_differences(
                    distribution, baseline_distribution)
                paired_rows.extend(paired_difference_records(
                    scenario,
                    group,
                    scenario.requested_fraction,
                    points,
                    baseline_points,
                    differences,
                    repetitions,
                    seed,
                ))

    metrics_df = pd.DataFrame(metric_rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db", "group",
    ]).reset_index(drop=True)
    bootstrap_df = pd.DataFrame(bootstrap_rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db", "group", "metric",
    ]).reset_index(drop=True)
    paired_df = pd.DataFrame(paired_rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db", "group", "metric",
    ]).reset_index(drop=True)
    return metrics_df, bootstrap_df, paired_df


def _single_row(frame: pd.DataFrame, **filters) -> pd.Series:
    selected = frame
    for column, value in filters.items():
        if isinstance(value, float):
            selected = selected[np.isclose(selected[column], value)]
        else:
            selected = selected[selected[column] == value]
    if len(selected) != 1:
        raise ValueError(
            f"Expected one row for {filters}, found {len(selected)}")
    return selected.iloc[0]


def _metric_ci(
    bootstrap_df: pd.DataFrame,
    load_factor: float,
    pbo_db: float,
    fraction: float,
    group: str,
    metric: str,
) -> tuple[float, float, float]:
    row = _single_row(
        bootstrap_df,
        load_factor=load_factor,
        pbo_db=pbo_db,
        affected_fraction=fraction,
        group=group,
        metric=metric,
    )
    return (
        float(row["estimate"]),
        float(row["ci95_lower"]),
        float(row["ci95_upper"]),
    )


def _paired_ci(
    paired_df: pd.DataFrame,
    load_factor: float,
    pbo_db: float,
    fraction: float,
    group: str,
    metric: str,
) -> tuple[float, float, float]:
    row = _single_row(
        paired_df,
        load_factor=load_factor,
        pbo_db=pbo_db,
        affected_fraction=fraction,
        group=group,
        metric=metric,
    )
    return (
        float(row["estimate"]),
        float(row["ci95_lower"]),
        float(row["ci95_upper"]),
    )


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "lines.linewidth": 1.2,
        "lines.markersize": 4,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linewidth": 0.5,
        "savefig.bbox": "tight",
    })


def save_figure(figure: plt.Figure, base_path: Path) -> None:
    figure.savefig(base_path.with_suffix(".pdf"))
    figure.savefig(base_path.with_suffix(".png"), dpi=350)
    plt.close(figure)


def add_sinr_reference_lines(axis: plt.Axes) -> None:
    references = [
        (-1.0, "−1 dB", ":", "#555555"),
        (-6.0, "−6 dB", "--", "#777777"),
        (-10.0, "−10 dB", "-.", "#999999"),
    ]
    for threshold, label, linestyle, color in references:
        axis.axhline(
            threshold,
            color=color,
            linestyle=linestyle,
            linewidth=0.75,
            zorder=0,
        )
        axis.text(
            0.015,
            threshold,
            label,
            transform=axis.get_yaxis_transform(),
            color=color,
            fontsize=6,
            va="bottom",
            ha="left",
        )


def build_operational_classification(
    bootstrap_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    sinr_rows = bootstrap_df[
        (bootstrap_df["metric"] == "sinr_p5_db")
        & (bootstrap_df["group"] == "all")
        & (bootstrap_df["pbo_db"] > 0)
    ]
    for row in sinr_rows.itertuples(index=False):
        outage = _metric_ci(
            bootstrap_df,
            row.load_factor,
            row.pbo_db,
            row.affected_fraction,
            "all",
            MAIN_OUTAGE_METRIC,
        )
        if row.ci95_lower >= OUTAGE_THRESHOLDS["m6"]:
            status = "acima_com_ic95"
        elif row.ci95_upper < OUTAGE_THRESHOLDS["m6"]:
            status = "abaixo_com_ic95"
        else:
            status = "limitrofe_ic95"
        rows.append({
            "scenario_id": row.scenario_id,
            "load_factor": row.load_factor,
            "affected_fraction": row.affected_fraction,
            "pbo_db": row.pbo_db,
            "sinr_p5_db": row.estimate,
            "sinr_p5_ci95_lower_db": row.ci95_lower,
            "sinr_p5_ci95_upper_db": row.ci95_upper,
            "outage_probability_m6": outage[0],
            "outage_m6_ci95_lower": outage[1],
            "outage_m6_ci95_upper": outage[2],
            "meets_sinr_p5_m6_point_criterion":
                row.estimate >= OUTAGE_THRESHOLDS["m6"],
            "operational_status_m6": status,
        })
    classification = pd.DataFrame(rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db",
    ]).reset_index(drop=True)

    frontier_rows = []
    for load_factor in EXPECTED_LOAD_FACTORS:
        for key, threshold in OUTAGE_THRESHOLDS.items():
            for fraction in EXPECTED_FRACTIONS:
                subset = classification[
                    np.isclose(classification["load_factor"], load_factor)
                    & np.isclose(
                        classification["affected_fraction"], fraction)
                    & (classification["sinr_p5_db"] >= threshold)
                ]
                frontier_rows.append({
                    "load_factor": load_factor,
                    "threshold_key": key,
                    "sinr_threshold_db": threshold,
                    "affected_fraction": fraction,
                    "maximum_simulated_pbo_above_threshold_db":
                        float(subset["pbo_db"].max())
                        if not subset.empty else np.nan,
                })
    frontiers = pd.DataFrame(frontier_rows)
    return classification, frontiers


def _outage_marker_size(probability: float) -> float:
    return 34.0 + 720.0 * max(0.0, float(probability))


def plot_operational_region(
    classification: pd.DataFrame,
    frontiers: pd.DataFrame,
    figures_dir: Path,
) -> None:
    status_style = {
        "acima_com_ic95": {
            "marker": "o", "color": "#009E73", "label": "IC95% acima de −6 dB",
        },
        "limitrofe_ic95": {
            "marker": "D", "color": "#E69F00", "label": "IC95% intercepta −6 dB",
        },
        "abaixo_com_ic95": {
            "marker": "x", "color": "#D55E00", "label": "IC95% abaixo de −6 dB",
        },
    }
    frontier_style = {
        "m1": ("#7B3294", ":", "Fronteira −1 dB"),
        "m6": ("#0072B2", "--", "Fronteira −6 dB"),
        "m10": ("#555555", "-.", "Fronteira −10 dB"),
    }

    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 3.2), constrained_layout=True,
        sharex=True, sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        subset = classification[
            np.isclose(classification["load_factor"], load_factor)]
        for status, style in status_style.items():
            points = subset[subset["operational_status_m6"] == status]
            if points.empty:
                continue
            axis.scatter(
                100 * points["affected_fraction"],
                points["pbo_db"],
                s=[
                    _outage_marker_size(value)
                    for value in points["outage_probability_m6"]
                ],
                marker=style["marker"],
                color=style["color"],
                linewidths=1.2,
                zorder=3,
                label=style["label"],
            )
        for key, (color, linestyle, label) in frontier_style.items():
            boundary = frontiers[
                np.isclose(frontiers["load_factor"], load_factor)
                & (frontiers["threshold_key"] == key)
            ].dropna(
                subset=["maximum_simulated_pbo_above_threshold_db"]
            ).sort_values("affected_fraction")
            if boundary.empty:
                continue
            axis.plot(
                100 * boundary["affected_fraction"],
                boundary["maximum_simulated_pbo_above_threshold_db"],
                color=color,
                linestyle=linestyle,
                marker=".",
                linewidth=0.9,
                zorder=2,
                label=label,
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Fração de feixes ativos afetados (%)")
        axis.set_ylabel("Power back-off (dB)")
        axis.set_xticks([5, 10, 15])
        axis.set_yticks([5, 10, 15, 20])
        axis.set_xlim(3.5, 16.5)
        axis.set_ylim(3.5, 21.5)

    handles, labels = axes[1].get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    shape_labels = [style["label"] for style in status_style.values()]
    frontier_labels = [style[2] for style in frontier_style.values()]
    ordered_labels = [
        label for label in [*shape_labels, *frontier_labels]
        if label in unique
    ]
    legend_shapes = axes[1].legend(
        [unique[label] for label in ordered_labels],
        ordered_labels,
        frameon=False,
        loc="upper right",
        fontsize=6.3,
    )
    axes[1].add_artist(legend_shapes)
    size_handles = [
        axes[1].scatter(
            [], [], s=_outage_marker_size(value), marker="o",
            facecolors="none", edgecolors="#555555")
        for value in (0.01, 0.05, 0.10)
    ]
    axes[1].legend(
        size_handles,
        ["1%", "5%", "10%"],
        title="Outage (SINR < −6 dB)",
        frameon=False,
        loc="lower right",
        fontsize=6.3,
        title_fontsize=6.3,
    )
    save_figure(figure, figures_dir / "fig_operational_region_pbo")

    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharex=True, sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for key, (color, linestyle, label) in frontier_style.items():
            boundary = frontiers[
                np.isclose(frontiers["load_factor"], load_factor)
                & (frontiers["threshold_key"] == key)
            ].dropna(
                subset=["maximum_simulated_pbo_above_threshold_db"]
            ).sort_values("affected_fraction")
            axis.plot(
                100 * boundary["affected_fraction"],
                boundary["maximum_simulated_pbo_above_threshold_db"],
                color=color,
                linestyle=linestyle,
                marker="o",
                linewidth=1.0,
                label=label,
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Fração de feixes ativos afetados (%)")
        axis.set_ylabel("Maior PBO simulado acima do limiar (dB)")
        axis.set_xticks([5, 10, 15])
        axis.set_yticks([5, 10, 15, 20])
    axes[1].legend(frameon=False, loc="best")
    save_figure(figure, figures_dir / "fig_operational_frontiers_pbo")


def plot_sinr_affected_unaffected(
    bootstrap_df: pd.DataFrame,
    figures_dir: Path,
    fraction: float,
    supplementary: bool = False,
) -> None:
    colors = {"all": "#1f77b4", "affected": "#d62728",
              "unaffected": "#2ca02c"}
    markers = {"all": "o", "affected": "s", "unaffected": "^"}
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for group in ("all", "affected", "unaffected"):
            xs = [0.0, *EXPECTED_PBO_LEVELS]
            ys, lower, upper = [], [], []
            for pbo in xs:
                baseline_fraction = (
                    0.0 if pbo == 0.0 and group == "all" else fraction)
                estimate, low, high = _metric_ci(
                    bootstrap_df,
                    load_factor,
                    pbo,
                    baseline_fraction,
                    group,
                    "sinr_p5_db",
                )
                ys.append(estimate)
                lower.append(max(0.0, estimate - low))
                upper.append(max(0.0, high - estimate))
            axis.errorbar(
                xs,
                ys,
                yerr=np.vstack([lower, upper]),
                color=colors[group],
                marker=markers[group],
                capsize=2,
                label=GROUP_LABELS[group],
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
        axis.set_ylabel("SINR P5 (dB)")
    axes[1].legend(frameon=False, loc="best")
    suffix = f"f{int(round(100 * fraction)):02d}"
    directory = figures_dir / "supplementary" if supplementary else figures_dir
    save_figure(
        figure,
        directory / f"fig_sinr_p5_affected_unaffected_{suffix}",
    )


def plot_outage(
    bootstrap_df: pd.DataFrame,
    figures_dir: Path,
) -> None:
    colors = ["#0072B2", "#D55E00", "#009E73"]
    markers = ["o", "s", "^"]
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        baseline = _metric_ci(
            bootstrap_df, load_factor, 0.0, 0.0, "all",
            "outage_probability")
        axis.errorbar(
            [0],
            [100 * baseline[0]],
            yerr=[[100 * max(0.0, baseline[0] - baseline[1])],
                  [100 * max(0.0, baseline[2] - baseline[0])]],
            color="#333333",
            marker="D",
            capsize=2,
            linestyle="none",
            label="Baseline",
        )
        for fraction, color, marker in zip(
            EXPECTED_FRACTIONS, colors, markers
        ):
            ys, lower, upper = [], [], []
            for pbo in EXPECTED_PBO_LEVELS:
                estimate, low, high = _metric_ci(
                    bootstrap_df,
                    load_factor,
                    pbo,
                    fraction,
                    "all",
                    "outage_probability",
                )
                ys.append(100 * estimate)
                lower.append(100 * max(0.0, estimate - low))
                upper.append(100 * max(0.0, high - estimate))
            axis.errorbar(
                EXPECTED_PBO_LEVELS,
                ys,
                yerr=np.vstack([lower, upper]),
                color=color,
                marker=marker,
                capsize=2,
                label=f"{100 * fraction:.0f}%",
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel("Probabilidade de outage (%)")
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
    axes[1].legend(frameon=False, title="Fração afetada")
    save_figure(figure, figures_dir / "fig_outage_vs_pbo")


def ecdf_xy(values: np.ndarray, maximum_points: int = 6000):
    ordered = np.sort(np.asarray(values, dtype=float))
    if ordered.size > maximum_points:
        indices = np.unique(np.linspace(
            0, ordered.size - 1, maximum_points).astype(int))
        x = ordered[indices]
        y = (indices + 1) / ordered.size
        return x, y
    return ordered, np.arange(1, ordered.size + 1) / ordered.size


def plot_representative_cdf(
    scenarios: Sequence[Scenario],
    summaries: dict[str, dict],
    figures_dir: Path,
) -> None:
    by_key = {
        (item.load_factor, item.pbo_db, item.requested_fraction): item
        for item in scenarios
    }
    load_factor = 0.5
    fraction = 0.10
    baseline = by_key[(load_factor, 0.0, 0.0)]
    baseline_frame = load_scenario_dataframe(baseline)
    source = by_key[(load_factor, 5.0, fraction)]
    baseline_frame["beam_affected_by_pbo"] = summaries[
        source.scenario_id]["mask"]
    frames = {0.0: baseline_frame}
    for pbo in (10.0, 20.0):
        frames[pbo] = load_scenario_dataframe(
            by_key[(load_factor, pbo, fraction)])

    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharex=True, sharey=True,
    )
    colors = {0.0: "#333333", 10.0: "#0072B2", 20.0: "#D55E00"}
    styles = {0.0: "--", 10.0: "-", 20.0: "-."}
    for axis, group, panel in zip(
        axes, ("affected", "unaffected"), ("(a)", "(b)")
    ):
        for pbo in (0.0, 10.0, 20.0):
            subset = select_group(frames[pbo], group)
            x, y = ecdf_xy(subset["sinr_db"].to_numpy(float))
            axis.plot(
                x,
                y,
                color=colors[pbo],
                linestyle=styles[pbo],
                label="Baseline" if pbo == 0 else f"PBO = {pbo:.0f} dB",
            )
        axis.set_title(f"{panel} {GROUP_LABELS[group]}")
        axis.set_xlabel("SINR (dB)")
        axis.set_ylabel("CDF empírica")
        axis.set_ylim(0, 1)
    axes[1].legend(frameon=False)
    save_figure(figure, figures_dir / "fig_cdf_representative")


def plot_metric_all_fractions(
    bootstrap_df: pd.DataFrame,
    supplementary_dir: Path,
    metric: str,
    filename: str,
) -> None:
    colors = ["#0072B2", "#D55E00", "#009E73"]
    markers = ["o", "s", "^"]
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        baseline = _metric_ci(
            bootstrap_df, load_factor, 0.0, 0.0, "all", metric)
        scale = 100.0 if metric == "outage_probability" else 1.0
        axis.errorbar(
            [0],
            [scale * baseline[0]],
            yerr=[[scale * max(0.0, baseline[0] - baseline[1])],
                  [scale * max(0.0, baseline[2] - baseline[0])]],
            color="#333333",
            marker="D",
            linestyle="none",
            capsize=2,
            label="Baseline",
        )
        for fraction, color, marker in zip(
            EXPECTED_FRACTIONS, colors, markers
        ):
            values, lower, upper = [], [], []
            for pbo in EXPECTED_PBO_LEVELS:
                estimate, low, high = _metric_ci(
                    bootstrap_df, load_factor, pbo, fraction, "all", metric)
                values.append(scale * estimate)
                lower.append(scale * max(0.0, estimate - low))
                upper.append(scale * max(0.0, high - estimate))
            axis.errorbar(
                EXPECTED_PBO_LEVELS,
                values,
                yerr=np.vstack([lower, upper]),
                color=color,
                marker=marker,
                capsize=2,
                label=f"{100 * fraction:.0f}%",
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel(
            "Probabilidade de outage (%)"
            if metric == "outage_probability" else METRIC_LABELS[metric]
        )
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
    axes[1].legend(frameon=False, title="Fração afetada")
    save_figure(figure, supplementary_dir / filename)


def plot_outage_by_group(
    bootstrap_df: pd.DataFrame,
    supplementary_dir: Path,
) -> None:
    colors = ["#0072B2", "#D55E00", "#009E73"]
    figure, axes = plt.subplots(
        3, 2, figsize=(7.16, 7.2), constrained_layout=True,
        sharex=True,
    )
    for row_idx, group in enumerate(("all", "affected", "unaffected")):
        for col_idx, load_factor in enumerate(EXPECTED_LOAD_FACTORS):
            axis = axes[row_idx, col_idx]
            for fraction, color in zip(EXPECTED_FRACTIONS, colors):
                xs = [0.0, *EXPECTED_PBO_LEVELS]
                values = []
                for pbo in xs:
                    baseline_fraction = (
                        0.0 if pbo == 0 and group == "all" else fraction)
                    estimate = _metric_ci(
                        bootstrap_df,
                        load_factor,
                        pbo,
                        baseline_fraction,
                        group,
                        "outage_probability",
                    )[0]
                    values.append(100 * estimate)
                axis.plot(
                    xs,
                    values,
                    marker="o",
                    color=color,
                    label=f"{100 * fraction:.0f}%",
                )
            axis.set_title(
                f"{GROUP_LABELS[group]}; LF = {100 * load_factor:.0f}%")
            axis.set_ylabel("Outage (%)")
            axis.set_xlabel("Power back-off (dB)")
            axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
    axes[0, 1].legend(frameon=False, title="Fração afetada")
    save_figure(figure, supplementary_dir / "fig_outage_by_group")


def plot_realized_fraction(
    metrics_df: pd.DataFrame,
    supplementary_dir: Path,
) -> None:
    figure, axis = plt.subplots(
        figsize=(3.5, 2.8), constrained_layout=True)
    colors = ["#0072B2", "#D55E00"]
    markers = ["o", "s"]
    for load_factor, color, marker in zip(
        EXPECTED_LOAD_FACTORS, colors, markers
    ):
        x, y, error = [], [], []
        for fraction in EXPECTED_FRACTIONS:
            row = _single_row(
                metrics_df,
                load_factor=load_factor,
                pbo_db=5.0,
                affected_fraction=fraction,
                group="all",
            )
            x.append(100 * fraction)
            y.append(100 * float(row[
                "realized_affected_fraction_mean"]))
            error.append(100 * float(row[
                "realized_affected_fraction_std"]))
        axis.errorbar(
            x,
            y,
            yerr=error,
            color=color,
            marker=marker,
            capsize=2,
            label=f"LF = {100 * load_factor:.0f}%",
        )
    axis.plot([4, 16], [4, 16], color="#555555", linestyle="--",
              label="Realizada = solicitada")
    axis.set_xlabel("Fração solicitada (%)")
    axis.set_ylabel("Fração realizada (%)")
    axis.set_xticks([5, 10, 15])
    axis.legend(frameon=False)
    save_figure(
        figure, supplementary_dir / "fig_realized_vs_requested_fraction")


def plot_affected_user_counts(
    metrics_df: pd.DataFrame,
    supplementary_dir: Path,
) -> None:
    positives = metrics_df[
        (metrics_df["pbo_db"] > 0)
        & (metrics_df["group"] == "affected")
    ].copy()
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.9), constrained_layout=True,
        sharey=False,
    )
    width = 0.22
    x = np.arange(len(EXPECTED_PBO_LEVELS))
    colors = ["#0072B2", "#D55E00", "#009E73"]
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for idx, (fraction, color) in enumerate(zip(
            EXPECTED_FRACTIONS, colors
        )):
            subset = positives[
                np.isclose(positives["load_factor"], load_factor)
                & np.isclose(positives["affected_fraction"], fraction)
            ].sort_values("pbo_db")
            axis.bar(
                x + (idx - 1) * width,
                subset["n_users"].to_numpy(),
                width=width,
                color=color,
                label=f"{100 * fraction:.0f}%",
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel("Registros de usuários afetados")
        axis.set_xticks(x)
        axis.set_xticklabels(
            [f"{pbo:.0f}" for pbo in EXPECTED_PBO_LEVELS])
    axes[1].legend(frameon=False, title="Fração afetada")
    save_figure(
        figure, supplementary_dir / "fig_affected_user_counts")


def read_active_beam_samples(scenario: Scenario) -> np.ndarray | None:
    path = Path(scenario.output_path) / "num_of_active_beams.csv"
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError):
        return None
    if frame.empty:
        return np.array([], dtype=float)
    values = pd.to_numeric(frame.iloc[:, 0], errors="coerce").dropna()
    return values.to_numpy(float)


def plot_active_beam_distribution(
    scenarios: Sequence[Scenario],
    supplementary_dir: Path,
) -> bool:
    baselines = sorted(
        [item for item in scenarios if item.pbo_db == 0],
        key=lambda item: item.load_factor,
    )
    samples = [read_active_beam_samples(item) for item in baselines]
    if any(item is None or item.size == 0 for item in samples):
        return False
    figure, axis = plt.subplots(
        figsize=(3.5, 2.8), constrained_layout=True)
    axis.boxplot(
        samples,
        tick_labels=[
            f"LF = {100 * item.load_factor:.0f}%" for item in baselines
        ],
        showfliers=False,
    )
    axis.set_ylabel("Feixes ativos por snapshot")
    axis.set_xlabel("Load factor")
    save_figure(
        figure, supplementary_dir / "fig_active_beams_per_snapshot")
    return True


def plot_paired_group_delta(
    paired_df: pd.DataFrame,
    supplementary_dir: Path,
    group: str,
) -> None:
    subset = paired_df[
        (paired_df["metric"] == "sinr_p5_db")
        & (paired_df["group"] == group)
    ]
    colors = ["#0072B2", "#D55E00", "#009E73"]
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.75), constrained_layout=True,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for fraction, color in zip(EXPECTED_FRACTIONS, colors):
            rows = subset[
                np.isclose(subset["load_factor"], load_factor)
                & np.isclose(subset["affected_fraction"], fraction)
            ].sort_values("pbo_db")
            estimates = rows["estimate"].to_numpy(float)
            axis.errorbar(
                rows["pbo_db"],
                estimates,
                yerr=np.vstack([
                    np.maximum(
                        0.0,
                        estimates - rows["ci95_lower"].to_numpy(float),
                    ),
                    np.maximum(
                        0.0,
                        rows["ci95_upper"].to_numpy(float) - estimates,
                    ),
                ]),
                color=color,
                marker="o",
                capsize=2,
                label=f"{100 * fraction:.0f}%",
            )
        axis.axhline(0, color="#555555", linewidth=0.8)
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel("Δ SINR P5 pareada (dB)")
    axes[1].legend(frameon=False, title="Fração afetada")
    save_figure(
        figure,
        supplementary_dir / f"fig_delta_sinr_p5_{group}",
    )


def generate_supplementary_figures(
    metrics_df: pd.DataFrame,
    bootstrap_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    scenarios: Sequence[Scenario],
    paths: dict[str, Path],
) -> None:
    supplementary = paths["supplementary"]
    plot_metric_all_fractions(
        bootstrap_df,
        supplementary,
        "sinr_mean_db",
        "fig_sinr_mean_all_fractions",
    )
    plot_metric_all_fractions(
        bootstrap_df,
        supplementary,
        "sinr_p5_db",
        "fig_sinr_p5_all_fractions",
    )
    plot_metric_all_fractions(
        bootstrap_df,
        supplementary,
        "spectral_efficiency_mean_bpshz",
        "fig_spectral_efficiency_mean_all_fractions",
    )
    plot_metric_all_fractions(
        bootstrap_df,
        supplementary,
        "spectral_efficiency_p5_bpshz",
        "fig_spectral_efficiency_p5_all_fractions",
    )
    plot_outage_by_group(bootstrap_df, supplementary)
    plot_realized_fraction(metrics_df, supplementary)
    plot_affected_user_counts(metrics_df, supplementary)
    plot_active_beam_distribution(scenarios, supplementary)
    plot_paired_group_delta(paired_df, supplementary, "unaffected")
    plot_paired_group_delta(paired_df, supplementary, "affected")


def latex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in text)


def write_latex_table(
    frame: pd.DataFrame,
    path: Path,
    column_format: str | None = None,
) -> None:
    columns = list(frame.columns)
    alignment = column_format or ("l" + "r" * (len(columns) - 1))
    lines = [
        r"\begin{tabular}{" + alignment + "}",
        r"\toprule",
        " & ".join(latex_escape(column) for column in columns) + r" \\",
        r"\midrule",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append(
            " & ".join(latex_escape(value) for value in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_tables(
    scenarios: Sequence[Scenario],
    metrics_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    tables_dir: Path,
) -> dict[str, pd.DataFrame]:
    count_rows = []
    for scenario in scenarios:
        all_row = _single_row(
            metrics_df,
            load_factor=scenario.load_factor,
            pbo_db=scenario.pbo_db,
            affected_fraction=scenario.requested_fraction,
            group="all",
        )
        if scenario.pbo_db == 0:
            affected_users = 0
            unaffected_users = int(all_row["n_users"])
        else:
            affected_users = int(_single_row(
                metrics_df,
                load_factor=scenario.load_factor,
                pbo_db=scenario.pbo_db,
                affected_fraction=scenario.requested_fraction,
                group="affected",
            )["n_users"])
            unaffected_users = int(_single_row(
                metrics_df,
                load_factor=scenario.load_factor,
                pbo_db=scenario.pbo_db,
                affected_fraction=scenario.requested_fraction,
                group="unaffected",
            )["n_users"])
        count_rows.append({
            "load_factor": scenario.load_factor,
            "pbo_db": scenario.pbo_db,
            "requested_fraction": scenario.requested_fraction,
            "realized_fraction_mean": all_row[
                "realized_affected_fraction_mean"],
            "snapshots": int(all_row["n_snapshots"]),
            "total_user_records": int(all_row["n_users"]),
            "affected_user_records": affected_users,
            "unaffected_user_records": unaffected_users,
        })
    counts = pd.DataFrame(count_rows)
    counts.to_csv(
        tables_dir / "table_scenario_counts.csv", index=False)
    counts_fmt = counts.copy()
    counts_fmt["load_factor"] = counts_fmt["load_factor"].map(
        lambda value: f"{100 * value:.0f}%")
    counts_fmt["pbo_db"] = counts_fmt["pbo_db"].map(
        lambda value: f"{value:.0f}")
    for column in ["requested_fraction", "realized_fraction_mean"]:
        counts_fmt[column] = counts[column].map(
            lambda value: f"{100 * value:.2f}%")
    write_latex_table(
        counts_fmt,
        tables_dir / "table_scenario_counts.tex",
    )

    main_rows = []
    for load_factor in EXPECTED_LOAD_FACTORS:
        baseline = _single_row(
            metrics_df,
            load_factor=load_factor,
            pbo_db=0.0,
            affected_fraction=0.0,
            group="all",
        )
        for fraction in EXPECTED_FRACTIONS:
            pbo10 = _single_row(
                metrics_df,
                load_factor=load_factor,
                pbo_db=10.0,
                affected_fraction=fraction,
                group="all",
            )
            pbo20 = _single_row(
                metrics_df,
                load_factor=load_factor,
                pbo_db=20.0,
                affected_fraction=fraction,
                group="all",
            )
            delta10 = _paired_ci(
                paired_df, load_factor, 10.0, fraction, "all",
                "sinr_p5_db")
            delta20 = _paired_ci(
                paired_df, load_factor, 20.0, fraction, "all",
                "sinr_p5_db")
            main_rows.append({
                "load_factor": load_factor,
                "requested_fraction": fraction,
                "baseline_sinr_p5_db": baseline["sinr_p5_db"],
                "pbo10_sinr_p5_db": pbo10["sinr_p5_db"],
                "pbo10_delta_sinr_p5_db": delta10[0],
                "pbo10_delta_ci95_lower_db": delta10[1],
                "pbo10_delta_ci95_upper_db": delta10[2],
                "pbo20_sinr_p5_db": pbo20["sinr_p5_db"],
                "pbo20_delta_sinr_p5_db": delta20[0],
                "pbo20_delta_ci95_lower_db": delta20[1],
                "pbo20_delta_ci95_upper_db": delta20[2],
                "pbo10_outage_probability":
                    pbo10["outage_probability"],
                "pbo20_outage_probability":
                    pbo20["outage_probability"],
            })
    main = pd.DataFrame(main_rows)
    main.to_csv(tables_dir / "table_main_results.csv", index=False)
    main_fmt = pd.DataFrame({
        "LF": main["load_factor"].map(lambda value: f"{100 * value:.0f}%"),
        "Fração": main["requested_fraction"].map(
            lambda value: f"{100 * value:.0f}%"),
        "P5 base": main["baseline_sinr_p5_db"].map(
            lambda value: f"{value:.2f}"),
        "P5 10 dB": main["pbo10_sinr_p5_db"].map(
            lambda value: f"{value:.2f}"),
        "Δ 10 dB [IC95%]": main.apply(
            lambda row: (
                f"{row['pbo10_delta_sinr_p5_db']:.2f} "
                f"[{row['pbo10_delta_ci95_lower_db']:.2f}, "
                f"{row['pbo10_delta_ci95_upper_db']:.2f}]"
            ),
            axis=1,
        ),
        "P5 20 dB": main["pbo20_sinr_p5_db"].map(
            lambda value: f"{value:.2f}"),
        "Δ 20 dB [IC95%]": main.apply(
            lambda row: (
                f"{row['pbo20_delta_sinr_p5_db']:.2f} "
                f"[{row['pbo20_delta_ci95_lower_db']:.2f}, "
                f"{row['pbo20_delta_ci95_upper_db']:.2f}]"
            ),
            axis=1,
        ),
        "Outage 10 dB": main["pbo10_outage_probability"].map(
            lambda value: f"{100 * value:.2f}%"),
        "Outage 20 dB": main["pbo20_outage_probability"].map(
            lambda value: f"{100 * value:.2f}%"),
    })
    write_latex_table(
        main_fmt,
        tables_dir / "table_main_results.tex",
    )

    comparison_rows = []
    fraction = 0.10
    for load_factor in EXPECTED_LOAD_FACTORS:
        for pbo in EXPECTED_PBO_LEVELS:
            affected = _single_row(
                metrics_df,
                load_factor=load_factor,
                pbo_db=pbo,
                affected_fraction=fraction,
                group="affected",
            )
            unaffected = _single_row(
                metrics_df,
                load_factor=load_factor,
                pbo_db=pbo,
                affected_fraction=fraction,
                group="unaffected",
            )
            delta_affected = _paired_ci(
                paired_df, load_factor, pbo, fraction, "affected",
                "sinr_p5_db")
            delta_unaffected = _paired_ci(
                paired_df, load_factor, pbo, fraction, "unaffected",
                "sinr_p5_db")
            comparison_rows.append({
                "load_factor": load_factor,
                "pbo_db": pbo,
                "affected_sinr_p5_db": affected["sinr_p5_db"],
                "affected_delta_db": delta_affected[0],
                "affected_delta_ci95_lower_db": delta_affected[1],
                "affected_delta_ci95_upper_db": delta_affected[2],
                "unaffected_sinr_p5_db": unaffected["sinr_p5_db"],
                "unaffected_delta_db": delta_unaffected[0],
                "unaffected_delta_ci95_lower_db": delta_unaffected[1],
                "unaffected_delta_ci95_upper_db": delta_unaffected[2],
            })
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(
        tables_dir / "table_affected_unaffected.csv", index=False)
    comparison_fmt = pd.DataFrame({
        "LF": comparison["load_factor"].map(
            lambda value: f"{100 * value:.0f}%"),
        "PBO": comparison["pbo_db"].map(lambda value: f"{value:.0f}"),
        "P5 afetados": comparison["affected_sinr_p5_db"].map(
            lambda value: f"{value:.2f}"),
        "Δ afetados [IC95%]": comparison.apply(
            lambda row: (
                f"{row['affected_delta_db']:.2f} "
                f"[{row['affected_delta_ci95_lower_db']:.2f}, "
                f"{row['affected_delta_ci95_upper_db']:.2f}]"
            ),
            axis=1,
        ),
        "P5 não afetados": comparison["unaffected_sinr_p5_db"].map(
            lambda value: f"{value:.2f}"),
        "Δ não afetados [IC95%]": comparison.apply(
            lambda row: (
                f"{row['unaffected_delta_db']:.2f} "
                f"[{row['unaffected_delta_ci95_lower_db']:.2f}, "
                f"{row['unaffected_delta_ci95_upper_db']:.2f}]"
            ),
            axis=1,
        ),
    })
    write_latex_table(
        comparison_fmt,
        tables_dir / "table_affected_unaffected.tex",
    )
    return {
        "scenario_counts": counts,
        "main_results": main,
        "affected_unaffected": comparison,
    }


def _scenario_description(row: pd.Series) -> str:
    return (
        f"LF={100 * float(row['load_factor']):.0f}%, "
        f"PBO={float(row['pbo_db']):.0f} dB e "
        f"fração={100 * float(row['affected_fraction']):.0f}%"
    )


def generate_results_report(
    metrics_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    qc: QCRecorder,
    outage_threshold: float,
    repetitions: int,
    reports_dir: Path,
) -> dict:
    baselines = metrics_df[
        (metrics_df["pbo_db"] == 0)
        & (metrics_df["group"] == "all")
        & (metrics_df["affected_fraction"] == 0)
    ].sort_values("load_factor")
    all_positive = metrics_df[
        (metrics_df["pbo_db"] > 0)
        & (metrics_df["group"] == "all")
    ]
    sinr_deltas = paired_df[
        (paired_df["metric"] == "sinr_p5_db")
        & (paired_df["group"] == "all")
    ]
    worst = sinr_deltas.loc[sinr_deltas["estimate"].idxmin()]
    greatest_outage = all_positive.loc[
        all_positive["outage_probability"].idxmax()]
    unaffected = paired_df[
        (paired_df["metric"] == "sinr_p5_db")
        & (paired_df["group"] == "unaffected")
    ].copy()
    improvements = unaffected[unaffected["ci95_lower"] > 0].sort_values(
        "estimate", ascending=False)
    differences = paired_df[
        (paired_df["ci95_lower"] > 0)
        | (paired_df["ci95_upper"] < 0)
    ]
    status_counts = qc.dataframe()["status"].value_counts().to_dict()

    lines = [
        "# Resultados da Campanha 03 — DC-MSS isolado",
        "",
        "## 1. Integridade dos dados",
        "",
        f"O controle de qualidade registrou {status_counts.get('PASS', 0)} "
        f"verificações PASS, {status_counts.get('WARNING', 0)} WARNING e "
        f"{status_counts.get('FAIL', 0)} FAIL. Foram processados 26 cenários "
        "selecionados, cada um com 1.000 snapshots.",
        "",
        "Os diretórios incompletos ou substituídos detectados durante a busca "
        "recursiva foram mantidos sem alteração e não foram combinados com os "
        "cenários completos.",
        "",
        "## 2. Baselines",
        "",
    ]
    for row in baselines.itertuples(index=False):
        lines.append(
            f"- LF = {100 * row.load_factor:.0f}%: SINR média "
            f"{row.sinr_mean_db:.2f} dB, SINR P5 {row.sinr_p5_db:.2f} dB, "
            f"proxy de eficiência espectral baseada em Shannon média "
            f"{row.spectral_efficiency_mean_bpshz:.3f} bit/s/Hz, P5 "
            f"{row.spectral_efficiency_p5_bpshz:.3f} bit/s/Hz e outage "
            f"{100 * row.outage_probability:.2f}%."
        )
    lines.extend([
        "",
        "## 3. Efeito do aumento do PBO",
        "",
        f"A maior redução da SINR P5 de todos os usuários foi "
        f"{float(worst['estimate']):.2f} dB em "
        f"{_scenario_description(worst)}, com IC95% pareado "
        f"[{float(worst['ci95_lower']):.2f}, "
        f"{float(worst['ci95_upper']):.2f}] dB.",
        "",
        "## 4. Efeito da fração afetada",
        "",
    ])
    for load_factor in EXPECTED_LOAD_FACTORS:
        for pbo in (10.0, 20.0):
            rows = sinr_deltas[
                np.isclose(sinr_deltas["load_factor"], load_factor)
                & np.isclose(sinr_deltas["pbo_db"], pbo)
            ].sort_values("affected_fraction")
            values = ", ".join(
                f"{100 * row.affected_fraction:.0f}%: "
                f"{row.estimate:.2f} dB"
                for row in rows.itertuples(index=False)
            )
            lines.append(
                f"- LF = {100 * load_factor:.0f}%, PBO = {pbo:.0f} dB — "
                f"Δ SINR P5 por fração: {values}."
            )
    lines.extend([
        "",
        "## 5. Comparação LF20 versus LF50",
        "",
    ])
    for fraction in EXPECTED_FRACTIONS:
        values = []
        for load_factor in EXPECTED_LOAD_FACTORS:
            row = _single_row(
                sinr_deltas,
                load_factor=load_factor,
                pbo_db=20.0,
                affected_fraction=fraction,
                group="all",
                metric="sinr_p5_db",
            )
            values.append(
                f"LF={100 * load_factor:.0f}%: "
                f"{float(row['estimate']):.2f} dB")
        lines.append(
            f"- Fração {100 * fraction:.0f}% em PBO = 20 dB — "
            + "; ".join(values) + "."
        )
    lines.extend([
        "",
        "## 6. Usuários afetados e não afetados",
        "",
        "Os grupos do baseline foram construídos por correspondência um a um "
        "de `snapshot_id`, `ue_id` e `beam_id`, usando a máscara validada do "
        "cenário de 5 dB da mesma fração.",
        "",
    ])
    representative = unaffected[
        np.isclose(unaffected["affected_fraction"], 0.10)
        & np.isclose(unaffected["pbo_db"], 20.0)
    ].sort_values("load_factor")
    for row in representative.itertuples(index=False):
        lines.append(
            f"- LF = {100 * row.load_factor:.0f}%, fração 10% e PBO 20 dB: "
            f"Δ SINR P5 dos usuários não afetados = {row.estimate:.2f} dB, "
            f"IC95% [{row.ci95_lower:.2f}, {row.ci95_upper:.2f}] dB."
        )
    lines.extend([
        "",
        "## 7. Outage",
        "",
        f"Outage foi calculado para o limiar operacional adotado para "
        f"comparação de SINR < {outage_threshold:.1f} dB. A maior "
        f"probabilidade observada foi "
        f"{100 * float(greatest_outage['outage_probability']):.2f}% em "
        f"{_scenario_description(greatest_outage)}.",
        "",
        "## 8. Proxy de eficiência espectral",
        "",
        "A coluna salva pelo SHARC foi usada diretamente. Ela representa a "
        "proxy de eficiência espectral baseada em Shannon, em bit/s/Hz, com "
        "fator de atenuação e limites de SINR da configuração. Ela não foi "
        "tratada como throughput.",
        "",
        "## 9. Maiores degradações observadas",
        "",
    ])
    for row in sinr_deltas.nsmallest(5, "estimate").itertuples(index=False):
        lines.append(
            f"- {_scenario_description(pd.Series(row._asdict()))}: "
            f"Δ SINR P5 = {row.estimate:.2f} dB, IC95% "
            f"[{row.ci95_lower:.2f}, {row.ci95_upper:.2f}] dB."
        )
    lines.extend([
        "",
        "## 10. Possíveis melhorias dos usuários não afetados",
        "",
    ])
    if improvements.empty:
        lines.append(
            "Nenhum IC95% pareado da variação de SINR P5 dos usuários não "
            "afetados ficou inteiramente acima de zero."
        )
    else:
        for row in improvements.itertuples(index=False):
            lines.append(
                f"- {_scenario_description(pd.Series(row._asdict()))}: "
                f"Δ SINR P5 = {row.estimate:.2f} dB, IC95% "
                f"[{row.ci95_lower:.2f}, {row.ci95_upper:.2f}] dB."
            )
    lines.extend([
        "",
        "## 11. Verificação pelos intervalos de confiança",
        "",
        f"Em {len(differences)} comparações pareadas de métricas, o IC95% da "
        "diferença não incluiu zero. Essa contagem usa exclusivamente o "
        "critério numérico IC95% inferior > 0 ou superior < 0.",
        "",
        "## 12. Limitações estatísticas",
        "",
        f"- Os IC95% são intervalos percentis de bootstrap agrupado por "
        f"snapshot com {repetitions} repetições.",
        "- Usuários do mesmo snapshot são reamostrados conjuntamente; não foi "
        "assumida independência entre usuários de um mesmo snapshot.",
        "- A campanha contém níveis discretos de PBO e fração; não foram "
        "interpolados cruzamentos entre níveis simulados.",
        "- A proxy de eficiência espectral não modela scheduler, MCS/BLER, "
        "HARQ, overhead ou entrega de bits na camada 3.",
        "",
        "## Valores sugeridos para citação no artigo",
        "",
    ])
    for load_factor in EXPECTED_LOAD_FACTORS:
        row = _single_row(
            sinr_deltas,
            load_factor=load_factor,
            pbo_db=10.0,
            affected_fraction=0.10,
            group="all",
            metric="sinr_p5_db",
        )
        lines.append(
            f"- Para LF = {100 * load_factor:.0f}% e fração de 10%, o PBO "
            f"de 10 dB alterou a SINR P5 em "
            f"{float(row['estimate']):.2f} dB em relação ao baseline, com "
            f"IC95% de [{float(row['ci95_lower']):.2f}, "
            f"{float(row['ci95_upper']):.2f}] dB."
        )
    lines.append(
        f"- A maior probabilidade de outage observada foi "
        f"{100 * float(greatest_outage['outage_probability']):.2f}% em "
        f"{_scenario_description(greatest_outage)}."
    )
    (reports_dir / "results_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {
        "worst_sinr_delta": worst.to_dict(),
        "greatest_outage": greatest_outage.to_dict(),
        "unaffected_improvement_count": int(len(improvements)),
        "largest_unaffected_improvement":
            improvements.iloc[0].to_dict() if not improvements.empty else None,
    }


def generate_figure_captions(
    outage_threshold: float,
    reports_dir: Path,
) -> None:
    captions = [
        r"% Legendas geradas a partir do mesmo conjunto de dados das figuras.",
        r"\newcommand{\CaptionHeatmapDeltaSinrPFive}{"
        r"Variação da SINR no percentil 5 em relação ao baseline agregado, "
        r"para (a) LF de 20\% e (b) LF de 50\%. Os valores nas células estão "
        r"em dB.}",
        r"\newcommand{\CaptionHeatmapAbsoluteSinrPFive}{"
        r"SINR absoluta no percentil 5 para as combinações simuladas de "
        r"power back-off e fração afetada, em dB.}",
        r"\newcommand{\CaptionAffectedUnaffected}{"
        r"SINR no percentil 5 para todos os usuários e para os grupos "
        r"atendidos por feixes afetados e não afetados. As barras indicam "
        r"IC95\% por bootstrap agrupado por snapshot; os grupos do baseline "
        r"foram pareados pela máscara de PBO.}",
        r"\newcommand{\CaptionOutagePbo}{"
        rf"Probabilidade de outage em função do power back-off. Outage "
        rf"calculado para o limiar operacional adotado de SINR < "
        rf"{outage_threshold:.1f} dB. As barras indicam IC95\% por bootstrap "
        r"agrupado por snapshot.}",
        r"\newcommand{\CaptionRepresentativeCdf}{"
        r"CDF empírica da SINR para LF de 50\%, fração afetada de 10\% e "
        r"PBO de 0, 10 e 20 dB: (a) usuários em feixes afetados e (b) "
        r"usuários em feixes não afetados. O baseline foi classificado com "
        r"a máscara pareada de 10\%.}",
        "",
    ]
    (reports_dir / "figure_captions.tex").write_text(
        "\n".join(captions),
        encoding="utf-8",
    )


def latex_command_name(
    metric_prefix: str,
    load_factor: float,
    pbo_db: float,
    fraction: float,
) -> str:
    number_names = {
        5: "Five", 10: "Ten", 15: "Fifteen", 20: "Twenty",
        50: "Fifty",
    }
    lf_value = int(round(100 * load_factor))
    pbo_value = int(round(pbo_db))
    fraction_value = int(round(100 * fraction))
    return (
        metric_prefix
        + "Lf" + number_names.get(lf_value, str(lf_value))
        + "Pbo" + number_names.get(pbo_value, str(pbo_value))
        + "Frac" + number_names.get(fraction_value, str(fraction_value))
    )


def generate_results_values(
    metrics_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    reports_dir: Path,
) -> None:
    lines = [
        r"% Valores gerados automaticamente; não editar manualmente.",
    ]
    for load_factor in EXPECTED_LOAD_FACTORS:
        baseline = _single_row(
            metrics_df,
            load_factor=load_factor,
            pbo_db=0.0,
            affected_fraction=0.0,
            group="all",
        )
        baseline_name = (
            "BaselineSinrPfiveLf"
            + ("Twenty" if np.isclose(load_factor, 0.2) else "Fifty")
        )
        lines.append(
            rf"\newcommand{{\{baseline_name}}}"
            rf"{{{float(baseline['sinr_p5_db']):.2f}\,\mathrm{{dB}}}}")
        for fraction in EXPECTED_FRACTIONS:
            for pbo in (10.0, 20.0):
                metric = _single_row(
                    metrics_df,
                    load_factor=load_factor,
                    pbo_db=pbo,
                    affected_fraction=fraction,
                    group="all",
                )
                delta = _paired_ci(
                    paired_df, load_factor, pbo, fraction, "all",
                    "sinr_p5_db")
                sinr_name = latex_command_name(
                    "SinrPfive", load_factor, pbo, fraction)
                delta_name = latex_command_name(
                    "DeltaSinrPfive", load_factor, pbo, fraction)
                outage_name = latex_command_name(
                    "Outage", load_factor, pbo, fraction)
                lines.extend([
                    rf"\newcommand{{\{sinr_name}}}"
                    rf"{{{float(metric['sinr_p5_db']):.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}}}"
                    rf"{{{delta[0]:.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}CiLow}}"
                    rf"{{{delta[1]:.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}CiHigh}}"
                    rf"{{{delta[2]:.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{outage_name}}}"
                    rf"{{{100 * float(metric['outage_probability']):.2f}\%}}",
                ])
    lines.append("")
    (reports_dir / "results_values.tex").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_all_figures(
    scenarios: Sequence[Scenario],
    summaries: dict[str, dict],
    metrics_df: pd.DataFrame,
    bootstrap_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    paths: dict[str, Path],
) -> None:
    configure_matplotlib()
    plot_heatmaps(metrics_df, paired_df, paths["figures"])
    plot_sinr_affected_unaffected(
        bootstrap_df, paths["figures"], 0.10, supplementary=False)
    plot_sinr_affected_unaffected(
        bootstrap_df, paths["figures"], 0.05, supplementary=True)
    plot_sinr_affected_unaffected(
        bootstrap_df, paths["figures"], 0.15, supplementary=True)
    plot_outage(bootstrap_df, paths["figures"])
    plot_representative_cdf(scenarios, summaries, paths["figures"])
    generate_supplementary_figures(
        metrics_df, bootstrap_df, paired_df, scenarios, paths)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_campaign = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Pós-processamento da Campanha 03 DC-MSS isolado.")
    parser.add_argument(
        "--campaign-dir",
        type=Path,
        default=default_campaign,
        help="Diretório da campanha que contém input/ e output/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Diretório de artefatos; padrão: post_processing/generated.",
    )
    parser.add_argument(
        "--outage-threshold",
        type=float,
        default=-10.0,
        help="Limiar operacional adotado para comparação, em dB.",
    )
    parser.add_argument(
        "--bootstrap-repetitions",
        type=int,
        default=2000,
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=838,
    )
    return parser.parse_args(argv)


def run_analysis(args: argparse.Namespace) -> dict:
    campaign_dir = args.campaign_dir.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else campaign_dir / "post_processing" / "generated"
    )
    paths = ensure_generated_dirs(output_dir)
    qc = QCRecorder()

    print(f"Campanha: {campaign_dir}")
    print("Descobrindo recursivamente os outputs...")
    scenarios, candidate_df = discover_scenarios(campaign_dir)
    print(f"Diretórios candidatos encontrados: {len(candidate_df)}")
    print(f"Cenários selecionados: {len(scenarios)}")
    validate_campaign_inventory(scenarios, candidate_df, qc)

    manifest = pd.DataFrame([asdict(item) for item in scenarios])
    manifest.to_csv(
        paths["data"] / "scenario_manifest.csv",
        index=False,
        encoding="utf-8",
    )
    candidate_df.to_csv(
        paths["data"] / "discovery_candidates.csv",
        index=False,
        encoding="utf-8",
    )

    summaries: dict[str, dict] = {}
    for index, scenario in enumerate(scenarios, start=1):
        print(
            f"QC {index:02d}/{len(scenarios):02d}: "
            f"{scenario.scenario_id}")
        if not scenario.metrics_csv_path:
            qc.add(
                "structured_csv_exists",
                "FAIL",
                "CSV estruturado não localizado.",
                scenario.scenario_id,
            )
            continue
        qc.add(
            "structured_csv_exists",
            "PASS",
            scenario.metrics_csv_path,
            scenario.scenario_id,
        )
        try:
            frame = load_scenario_dataframe(scenario)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            qc.add(
                "structured_csv_readable",
                "FAIL",
                f"Erro de leitura: {error}",
                scenario.scenario_id,
            )
            continue
        qc.add(
            "structured_csv_readable",
            "PASS",
            f"Registros lidos: {len(frame)}.",
            scenario.scenario_id,
        )
        summaries[scenario.scenario_id] = validate_dataframe(
            scenario, frame, qc)
        del frame

    pairable = validate_cross_scenario(scenarios, summaries, qc)
    masks_identical = all(pairable.values()) and len(pairable) == 6
    nested_rows = [
        row for row in qc.rows if row["check"] == "nested_fraction_masks"
    ]
    fractions_nested = bool(nested_rows) and all(
        row["status"] == "PASS" for row in nested_rows)
    write_qc_outputs(qc, paths)
    if qc.has_failures():
        raise RuntimeError(
            "O controle de qualidade encontrou falhas que impedem a análise. "
            "Consulte generated/quality_control/qc_report.md.")

    print(
        f"Iniciando métricas e bootstrap agrupado por snapshot "
        f"({args.bootstrap_repetitions} repetições)...")
    metrics_df, bootstrap_df, paired_df = process_metrics_and_bootstrap(
        scenarios,
        summaries,
        pairable,
        args.outage_threshold,
        args.bootstrap_repetitions,
        args.bootstrap_seed,
    )
    metrics_df.to_csv(
        paths["data"] / "scenario_metrics.csv", index=False)
    bootstrap_df.to_csv(
        paths["data"] / "bootstrap_metrics.csv", index=False)
    paired_df.to_csv(
        paths["data"] / "paired_baseline_differences.csv", index=False)

    print("Gerando figuras em PDF vetorial e PNG a 350 dpi...")
    generate_all_figures(
        scenarios,
        summaries,
        metrics_df,
        bootstrap_df,
        paired_df,
        paths,
    )
    print("Gerando tabelas e relatórios...")
    build_tables(scenarios, metrics_df, paired_df, paths["tables"])
    result_summary = generate_results_report(
        metrics_df,
        paired_df,
        qc,
        args.outage_threshold,
        args.bootstrap_repetitions,
        paths["reports"],
    )
    generate_figure_captions(
        args.outage_threshold, paths["reports"])
    generate_results_values(metrics_df, paired_df, paths["reports"])

    summary = {
        "campaign_dir": str(campaign_dir),
        "output_dir": str(output_dir),
        "candidate_directories": len(candidate_df),
        "scenarios_processed": len(scenarios),
        "warnings": qc.warning_count(),
        "masks_identical_across_pbo": masks_identical,
        "fractions_nested": fractions_nested,
        "paired_baselines_available": all(pairable.values()),
        "all_scenarios_have_1000_snapshots": all(
            item.actual_snapshots == 1000 for item in scenarios),
        "produced_file_count": 0,
        **result_summary,
    }
    summary_path = paths["reports"] / "analysis_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    produced_files = sorted(
        str(path.relative_to(output_dir))
        for path in output_dir.rglob("*") if path.is_file()
    )
    summary["produced_file_count"] = len(produced_files)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Warnings: {qc.warning_count()}")
    print(f"Arquivos produzidos: {len(produced_files)}")
    for filename in produced_files:
        print(f"  {filename}")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.bootstrap_repetitions <= 0:
        raise ValueError("--bootstrap-repetitions deve ser positivo")
    summary = run_analysis(args)
    print("Resumo final:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

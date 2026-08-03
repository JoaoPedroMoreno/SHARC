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
RETENTION_METRIC = "spectral_efficiency_p5_retention_percent"
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
    RETENTION_METRIC:
        "Retenção da proxy de eficiência espectral P5 (%)",
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


def read_flat_samples(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError):
        return None
    if frame.shape[1] != 1:
        return None
    return pd.to_numeric(
        frame.iloc[:, 0], errors="coerce").to_numpy(float)


def load_scenario_dataframe(
    scenario: Scenario,
    include_path_loss: bool = False,
) -> pd.DataFrame:
    path = Path(scenario.metrics_csv_path)
    frame = pd.read_csv(path, usecols=REQUIRED_COLUMNS)
    if include_path_loss:
        output_path = Path(scenario.output_path)
        path_loss = read_flat_samples(output_path / "imt_path_loss.csv")
        flat_snr = read_flat_samples(output_path / "imt_dl_snr.csv")
        count_matches = (
            path_loss is not None
            and flat_snr is not None
            and len(path_loss) == len(frame)
            and len(flat_snr) == len(frame)
        )
        frame.attrs["path_loss_count_matches"] = count_matches
        if count_matches:
            structured_snr = pd.to_numeric(
                frame["snr_db"], errors="coerce").to_numpy(float)
            frame.attrs["flat_snr_alignment_max_error_db"] = float(
                np.nanmax(np.abs(flat_snr - structured_snr)))
            frame["path_loss_db"] = path_loss
        else:
            frame.attrs["flat_snr_alignment_max_error_db"] = np.inf
            frame["path_loss_db"] = np.nan
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


def numeric_digest(values: pd.Series | np.ndarray) -> str:
    array = np.asarray(values, dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


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
    path_loss_available = (
        "path_loss_db" in frame
        and frame.attrs.get("path_loss_count_matches", False)
        and np.isfinite(frame["path_loss_db"].to_numpy(float)).all()
    )
    flat_snr_error = float(frame.attrs.get(
        "flat_snr_alignment_max_error_db", np.inf))
    path_loss_aligned = path_loss_available and flat_snr_error <= tolerance
    qc.add(
        "path_loss_row_alignment",
        "PASS" if path_loss_aligned else "FAIL",
        "Amostras de path loss e SNR achatada possuem a mesma quantidade e "
        f"ordem do CSV estruturado; erro máximo de SNR={flat_snr_error:.3g} dB."
        if path_loss_aligned else
        "Não foi possível confirmar quantidade e ordem entre path loss, SNR "
        f"achatada e CSV estruturado; erro máximo={flat_snr_error:.3g} dB.",
        sid,
    )
    return {
        "key_digest": key_digest(frame),
        "path_loss_digest": (
            numeric_digest(frame["path_loss_db"])
            if path_loss_available else None
        ),
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
            path_loss_equal = complete
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
                path_loss_equal &= all(
                    summaries[member.scenario_id].get("path_loss_digest")
                    == baseline_summary.get("path_loss_digest")
                    and summaries[member.scenario_id].get(
                        "path_loss_digest") is not None
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
            qc.add(
                "paired_path_loss_unchanged",
                "PASS" if path_loss_equal else "WARNING",
                f"{label}: path loss por chave "
                f"{'coincide' if path_loss_equal else 'não coincide'} "
                "com o baseline nos quatro níveis de PBO.",
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


def paired_bootstrap_ratio_percent(
    scenario_distribution: dict[str, np.ndarray],
    baseline_distribution: dict[str, np.ndarray],
    metric: str,
) -> np.ndarray:
    numerator = np.asarray(scenario_distribution[metric], dtype=float)
    denominator = np.asarray(baseline_distribution[metric], dtype=float)
    result = np.full(numerator.shape, np.nan, dtype=float)
    valid = np.isfinite(numerator) & np.isfinite(denominator) & (
        denominator > 0)
    result[valid] = 100.0 * numerator[valid] / denominator[valid]
    return result


def paired_retention_record(
    scenario: Scenario,
    group: str,
    analysis_fraction: float,
    scenario_points: dict,
    baseline_points: dict,
    scenario_distribution: dict[str, np.ndarray],
    baseline_distribution: dict[str, np.ndarray],
    repetitions: int,
    seed: int,
) -> dict:
    source_metric = "spectral_efficiency_p5_bpshz"
    denominator = float(baseline_points[source_metric])
    estimate = (
        100.0 * float(scenario_points[source_metric]) / denominator
        if denominator > 0 else np.nan
    )
    distribution = paired_bootstrap_ratio_percent(
        scenario_distribution,
        baseline_distribution,
        source_metric,
    )
    lower, upper = percentile_interval(distribution)
    return {
        "scenario_id": scenario.scenario_id,
        "load_factor": scenario.load_factor,
        "pbo_db": scenario.pbo_db,
        "affected_fraction": analysis_fraction,
        "group": group,
        "metric": RETENTION_METRIC,
        "estimate": estimate,
        "ci95_lower": lower,
        "ci95_upper": upper,
        "repetitions": repetitions,
        "seed": seed,
        "analysis_type": "paired_ratio_pbo_over_baseline",
    }


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
                if group == "all":
                    paired_rows.append(paired_retention_record(
                        scenario,
                        group,
                        scenario.requested_fraction,
                        points,
                        baseline_points,
                        distribution,
                        baseline_distribution,
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
    figure.savefig(base_path.with_suffix(".png"), dpi=300)
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


def build_system_performance_values(
    bootstrap_df: pd.DataFrame,
    paired_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for load_factor in EXPECTED_LOAD_FACTORS:
        outage = _metric_ci(
            bootstrap_df,
            load_factor,
            0.0,
            0.0,
            "all",
            MAIN_OUTAGE_METRIC,
        )
        rows.append({
            "scenario_id": scenario_id(load_factor, 0.0, 0.0),
            "load_factor": load_factor,
            "pbo_db": 0.0,
            "affected_fraction": 0.0,
            "is_baseline": True,
            "outage_probability_m6": outage[0],
            "outage_m6_ci95_lower": outage[1],
            "outage_m6_ci95_upper": outage[2],
            RETENTION_METRIC: 100.0,
            "retention_se_p5_ci95_lower_percent": 100.0,
            "retention_se_p5_ci95_upper_percent": 100.0,
        })
        for fraction in EXPECTED_FRACTIONS:
            for pbo in EXPECTED_PBO_LEVELS:
                outage = _metric_ci(
                    bootstrap_df,
                    load_factor,
                    pbo,
                    fraction,
                    "all",
                    MAIN_OUTAGE_METRIC,
                )
                retention = _paired_ci(
                    paired_df,
                    load_factor,
                    pbo,
                    fraction,
                    "all",
                    RETENTION_METRIC,
                )
                rows.append({
                    "scenario_id": scenario_id(
                        load_factor, pbo, fraction),
                    "load_factor": load_factor,
                    "pbo_db": pbo,
                    "affected_fraction": fraction,
                    "is_baseline": False,
                    "outage_probability_m6": outage[0],
                    "outage_m6_ci95_lower": outage[1],
                    "outage_m6_ci95_upper": outage[2],
                    RETENTION_METRIC: retention[0],
                    "retention_se_p5_ci95_lower_percent": retention[1],
                    "retention_se_p5_ci95_upper_percent": retention[2],
                })
    result = pd.DataFrame(rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db",
    ]).reset_index(drop=True)
    if len(result) != 26 or int((~result["is_baseline"]).sum()) != 24:
        raise ValueError(
            "A figura principal exige 24 cenários com PBO e dois baselines.")
    return result


def _asymmetric_errors(
    estimate: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    return np.vstack([
        np.maximum(0.0, estimate - lower),
        np.maximum(0.0, upper - estimate),
    ])


def plot_system_performance(
    values: pd.DataFrame,
    figures_dir: Path,
) -> None:
    colors = ["#0072B2", "#D55E00", "#009E73"]
    markers = ["o", "s", "^"]
    figure, axes = plt.subplots(
        2, 2, figsize=(7.16, 5.4), constrained_layout=False,
        sharex="col",
    )
    for col_idx, (load_factor, panel) in enumerate(zip(
        EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    )):
        top = axes[0, col_idx]
        bottom = axes[1, col_idx]
        baseline = values[
            np.isclose(values["load_factor"], load_factor)
            & values["is_baseline"]
        ].iloc[0]
        baseline_outage = 100.0 * float(
            baseline["outage_probability_m6"])
        top.errorbar(
            [0.0],
            [baseline_outage],
            yerr=_asymmetric_errors(
                np.array([baseline_outage]),
                np.array([100.0 * baseline["outage_m6_ci95_lower"]]),
                np.array([100.0 * baseline["outage_m6_ci95_upper"]]),
            ),
            color="#333333",
            marker="D",
            linestyle="none",
            capsize=2,
        )
        top.annotate(
            "Baseline",
            (0.0, baseline_outage),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=6.5,
        )
        bottom.plot(
            [0.0], [100.0], color="#333333", marker="D",
            linestyle="none",
        )
        bottom.annotate(
            "Baseline",
            (0.0, 100.0),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=6.5,
        )

        for fraction, color, marker in zip(
            EXPECTED_FRACTIONS, colors, markers
        ):
            subset = values[
                np.isclose(values["load_factor"], load_factor)
                & np.isclose(values["affected_fraction"], fraction)
                & (~values["is_baseline"])
            ].sort_values("pbo_db")
            outage_estimate = (
                100.0 * subset["outage_probability_m6"].to_numpy(float))
            top.errorbar(
                subset["pbo_db"],
                outage_estimate,
                yerr=_asymmetric_errors(
                    outage_estimate,
                    100.0 * subset[
                        "outage_m6_ci95_lower"].to_numpy(float),
                    100.0 * subset[
                        "outage_m6_ci95_upper"].to_numpy(float),
                ),
                color=color,
                marker=marker,
                capsize=2,
                label=f"{100 * fraction:.0f}%",
            )
            retention = subset[RETENTION_METRIC].to_numpy(float)
            bottom.errorbar(
                subset["pbo_db"],
                retention,
                yerr=_asymmetric_errors(
                    retention,
                    subset[
                        "retention_se_p5_ci95_lower_percent"].to_numpy(float),
                    subset[
                        "retention_se_p5_ci95_upper_percent"].to_numpy(float),
                ),
                color=color,
                marker=marker,
                capsize=2,
                label=f"{100 * fraction:.0f}%",
            )

        top.axhline(
            5.0, color="#555555", linestyle="--", linewidth=0.8)
        top.text(
            0.99, 5.0, "Outage = 5%",
            transform=top.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=6.5, color="#555555",
        )
        top.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        top.set_ylabel("Outage para SINR < −6 dB (%)")
        bottom.set_ylabel(
            "Retenção da proxy de eficiência\nespectral P5 (%)")
        bottom.set_xlabel("Power back-off (dB)")
        bottom.set_xticks([0, *EXPECTED_PBO_LEVELS])
        bottom.set_xlim(-0.8, 20.8)

    handles, labels = axes[0, 1].get_legend_handles_labels()
    figure.subplots_adjust(
        left=0.10, right=0.99, top=0.94, bottom=0.12,
        hspace=0.20, wspace=0.23,
    )
    figure.legend(
        handles,
        labels,
        title="Fração de feixes ativos afetados",
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=3,
        fontsize=7,
        title_fontsize=7,
    )
    save_figure(
        figure,
        figures_dir / "fig_system_performance_outage_se_p5",
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
        1, 2, figsize=(7.16, 4.0), constrained_layout=False,
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
    size_handles = [
        axes[1].scatter(
            [], [], s=_outage_marker_size(value), marker="o",
            facecolors="none", edgecolors="#555555")
        for value in (0.01, 0.05, 0.10)
    ]
    figure.subplots_adjust(
        left=0.08, right=0.99, top=0.91, bottom=0.31, wspace=0.20)
    figure.legend(
        [*[unique[label] for label in ordered_labels], *size_handles],
        [
            *ordered_labels,
            "Outage 1%",
            "Outage 5%",
            "Outage 10%",
        ],
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=3,
        fontsize=6.3,
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
        add_sinr_reference_lines(axis)
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
            MAIN_OUTAGE_METRIC)
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
                    MAIN_OUTAGE_METRIC,
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
        axis.axhline(
            5.0,
            color="#555555",
            linestyle="--",
            linewidth=0.8,
            label="Outage = 5%" if load_factor == EXPECTED_LOAD_FACTORS[1]
            else "_nolegend_",
        )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel("Outage para SINR < −6 dB (%)")
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
    axes[1].legend(frameon=False, title="Fração / critério")
    save_figure(
        figure, figures_dir / "fig_outage_vs_pbo_threshold_m6")


def plot_outage_threshold_sensitivity(
    bootstrap_df: pd.DataFrame,
    figures_dir: Path,
) -> None:
    threshold_styles = [
        (
            "m1", "#7B3294", "o", ":",
            "SINR < −1 dB (ref. NR-NTN restritiva)",
        ),
        ("m6", "#0072B2", "s", "--", "SINR < −6 dB (principal)"),
        ("m10", "#555555", "^", "-.", "SINR < −10 dB (degradação severa)"),
    ]
    fraction = 0.10
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 3.25), constrained_layout=False,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for key, color, marker, linestyle, label in threshold_styles:
            xs = [0.0, *EXPECTED_PBO_LEVELS]
            values, lower, upper = [], [], []
            metric = OUTAGE_METRICS[key]
            for pbo in xs:
                baseline_fraction = 0.0 if pbo == 0.0 else fraction
                estimate, low, high = _metric_ci(
                    bootstrap_df,
                    load_factor,
                    pbo,
                    baseline_fraction,
                    "all",
                    metric,
                )
                values.append(100 * estimate)
                lower.append(100 * max(0.0, estimate - low))
                upper.append(100 * max(0.0, high - estimate))
            axis.errorbar(
                xs,
                values,
                yerr=np.vstack([lower, upper]),
                color=color,
                marker=marker,
                linestyle=linestyle,
                capsize=2,
                label=label,
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel("Power back-off (dB)")
        axis.set_ylabel("Probabilidade de outage (%)")
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
    handles, labels = axes[1].get_legend_handles_labels()
    figure.subplots_adjust(
        left=0.08, right=0.99, top=0.89, bottom=0.27, wspace=0.18)
    figure.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=3,
        fontsize=6.5,
    )
    save_figure(
        figure, figures_dir / "fig_outage_threshold_sensitivity_f10")


def ecdf_xy(values: np.ndarray, maximum_points: int = 6000):
    ordered = np.sort(np.asarray(values, dtype=float))
    if ordered.size > maximum_points:
        indices = np.unique(np.linspace(
            0, ordered.size - 1, maximum_points).astype(int))
        x = ordered[indices]
        y = (indices + 1) / ordered.size
        return x, y
    return ordered, np.arange(1, ordered.size + 1) / ordered.size


def inr_db_from_snr_sinr(
    snr_db: pd.Series | np.ndarray,
    sinr_db: pd.Series | np.ndarray,
) -> tuple[np.ndarray, int]:
    snr_linear = np.power(10.0, np.asarray(snr_db, dtype=float) / 10.0)
    sinr_linear = np.power(10.0, np.asarray(sinr_db, dtype=float) / 10.0)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        inr_linear = snr_linear / sinr_linear - 1.0
    valid = np.isfinite(inr_linear) & (inr_linear > 0.0)
    result = np.full(inr_linear.shape, np.nan, dtype=float)
    result[valid] = 10.0 * np.log10(inr_linear[valid])
    return result, int((~valid).sum())


def distribution_statistics(
    values: np.ndarray,
    total_records: int | None = None,
) -> dict:
    array = np.asarray(values, dtype=float)
    finite = array[np.isfinite(array)]
    total = int(array.size if total_records is None else total_records)
    omitted = total - int(finite.size)
    if finite.size == 0:
        return {
            "total_records": total,
            "valid_records": 0,
            "omitted_records": omitted,
            "mean": np.nan,
            "median": np.nan,
            "p5": np.nan,
            "p95": np.nan,
        }
    return {
        "total_records": total,
        "valid_records": int(finite.size),
        "omitted_records": omitted,
        "mean": float(np.mean(finite)),
        "median": float(np.median(finite)),
        "p5": linear_quantile(finite, 0.05),
        "p95": linear_quantile(finite, 0.95),
    }


def _same_keys(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return len(left) == len(right) and np.array_equal(
        left[KEY_COLUMNS].to_numpy(dtype=np.int64, copy=False),
        right[KEY_COLUMNS].to_numpy(dtype=np.int64, copy=False),
    )


def _append_cdf_rows(
    rows: list[dict],
    values: np.ndarray,
    scenario: Scenario,
    analysis_fraction: float,
    metric: str,
    group: str,
) -> None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    x, y = ecdf_xy(finite)
    for index, (x_value, probability) in enumerate(zip(x, y)):
        rows.append({
            "scenario_id": scenario.scenario_id,
            "load_factor": scenario.load_factor,
            "pbo_db": scenario.pbo_db,
            "affected_fraction": analysis_fraction,
            "metric": metric,
            "group": group,
            "cdf_point_index": index,
            "x_value": x_value,
            "cdf_probability": probability,
        })


def build_mechanism_analysis(
    scenarios: Sequence[Scenario],
    summaries: dict[str, dict],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    by_key = {
        (item.load_factor, item.pbo_db, item.requested_fraction): item
        for item in scenarios
    }
    cdf_rows: list[dict] = []
    summary_rows: list[dict] = []
    control_rows: list[dict] = []

    for load_factor in EXPECTED_LOAD_FACTORS:
        baseline_scenario = by_key[(load_factor, 0.0, 0.0)]
        baseline_raw = load_scenario_dataframe(
            baseline_scenario, include_path_loss=True)
        for fraction in EXPECTED_FRACTIONS:
            mask_source = by_key[(load_factor, 5.0, fraction)]
            baseline = baseline_raw.copy()
            baseline["beam_affected_by_pbo"] = summaries[
                mask_source.scenario_id]["mask"]
            scenario_frames = {
                pbo: load_scenario_dataframe(
                    by_key[(load_factor, pbo, fraction)],
                    include_path_loss=True,
                )
                for pbo in EXPECTED_PBO_LEVELS
            }

            for pbo, frame in scenario_frames.items():
                if not _same_keys(baseline, frame):
                    raise ValueError(
                        f"Chaves não pareadas em LF={load_factor}, "
                        f"fração={fraction}, PBO={pbo}.")
                baseline_affected = select_group(baseline, "affected")
                scenario_affected = select_group(frame, "affected")
                baseline_unaffected = select_group(baseline, "unaffected")
                scenario_unaffected = select_group(frame, "unaffected")
                if (
                    not _same_keys(baseline_affected, scenario_affected)
                    or not _same_keys(
                        baseline_unaffected, scenario_unaffected)
                ):
                    raise ValueError(
                        f"Grupos não pareados em LF={load_factor}, "
                        f"fração={fraction}, PBO={pbo}.")

                snr_affected_delta = (
                    scenario_affected["snr_db"].to_numpy(float)
                    - baseline_affected["snr_db"].to_numpy(float)
                )
                snr_unaffected_delta = (
                    scenario_unaffected["snr_db"].to_numpy(float)
                    - baseline_unaffected["snr_db"].to_numpy(float)
                )
                baseline_inr, baseline_inr_omitted = inr_db_from_snr_sinr(
                    baseline_unaffected["snr_db"],
                    baseline_unaffected["sinr_db"],
                )
                scenario_inr, scenario_inr_omitted = inr_db_from_snr_sinr(
                    scenario_unaffected["snr_db"],
                    scenario_unaffected["sinr_db"],
                )
                paired_inr_valid = (
                    np.isfinite(baseline_inr) & np.isfinite(scenario_inr))
                inr_delta = (
                    scenario_inr[paired_inr_valid]
                    - baseline_inr[paired_inr_valid]
                )
                path_loss_delta = (
                    frame["path_loss_db"].to_numpy(float)
                    - baseline["path_loss_db"].to_numpy(float)
                )
                snr_affected_median = float(
                    np.median(snr_affected_delta))
                inr_unaffected_median = (
                    float(np.median(inr_delta))
                    if inr_delta.size else np.nan
                )
                control_rows.append({
                    "scenario_id": by_key[(
                        load_factor, pbo, fraction)].scenario_id,
                    "load_factor": load_factor,
                    "pbo_db": pbo,
                    "affected_fraction": fraction,
                    "paired_user_records": len(frame),
                    "snr_affected_mean_delta_db":
                        float(np.mean(snr_affected_delta)),
                    "snr_affected_median_delta_db":
                        snr_affected_median,
                    "snr_unaffected_mean_delta_db":
                        float(np.mean(snr_unaffected_delta)),
                    "snr_unaffected_median_delta_db":
                        float(np.median(snr_unaffected_delta)),
                    "snr_unaffected_max_abs_delta_db":
                        float(np.max(np.abs(snr_unaffected_delta))),
                    "inr_unaffected_valid_pairs": int(inr_delta.size),
                    "inr_unaffected_mean_delta_db": (
                        float(np.mean(inr_delta))
                        if inr_delta.size else np.nan
                    ),
                    "inr_unaffected_median_delta_db":
                        inr_unaffected_median,
                    "inr_baseline_omitted_records":
                        baseline_inr_omitted,
                    "inr_pbo_omitted_records":
                        scenario_inr_omitted,
                    "path_loss_mean_delta_db":
                        float(np.mean(path_loss_delta)),
                    "path_loss_max_abs_delta_db":
                        float(np.max(np.abs(path_loss_delta))),
                    "snr_unaffected_practically_constant": bool(
                        np.max(np.abs(snr_unaffected_delta)) <= 1e-9),
                    "path_loss_overlaid": bool(
                        np.max(np.abs(path_loss_delta)) <= 1e-9),
                    "inr_unaffected_decreased": bool(
                        np.isfinite(inr_unaffected_median)
                        and inr_unaffected_median < 0.0),
                    "snr_reduction_dominates_inr_benefit": bool(
                        np.isfinite(inr_unaffected_median)
                        and abs(snr_affected_median)
                        > abs(inr_unaffected_median)
                    ),
                })

            plotted_frames = {
                0.0: (baseline_scenario, baseline),
                10.0: (
                    by_key[(load_factor, 10.0, fraction)],
                    scenario_frames[10.0],
                ),
                20.0: (
                    by_key[(load_factor, 20.0, fraction)],
                    scenario_frames[20.0],
                ),
            }
            for pbo, (scenario, frame) in plotted_frames.items():
                affected = select_group(frame, "affected")
                unaffected = select_group(frame, "unaffected")
                inr_db, inr_omitted = inr_db_from_snr_sinr(
                    unaffected["snr_db"], unaffected["sinr_db"])
                curve_specs = [
                    (
                        "snr_affected_db",
                        "affected",
                        affected["snr_db"].to_numpy(float),
                        len(affected),
                    ),
                    (
                        "inr_unaffected_db",
                        "unaffected",
                        inr_db,
                        len(unaffected),
                    ),
                    (
                        "path_loss_db",
                        "all",
                        frame["path_loss_db"].to_numpy(float),
                        len(frame),
                    ),
                ]
                if np.isclose(fraction, 0.10):
                    curve_specs.extend([
                        (
                            "sinr_all_db",
                            "all",
                            frame["sinr_db"].to_numpy(float),
                            len(frame),
                        ),
                        (
                            "spectral_efficiency_proxy_all_bpshz",
                            "all",
                            frame[
                                "spectral_efficiency_proxy"].to_numpy(float),
                            len(frame),
                        ),
                    ])
                for metric, group, values, total_records in curve_specs:
                    _append_cdf_rows(
                        cdf_rows,
                        values,
                        scenario,
                        fraction,
                        metric,
                        group,
                    )
                    statistics = distribution_statistics(
                        values, total_records=total_records)
                    summary_rows.append({
                        "scenario_id": scenario.scenario_id,
                        "load_factor": load_factor,
                        "pbo_db": pbo,
                        "affected_fraction": fraction,
                        "metric": metric,
                        "group": group,
                        **statistics,
                    })
                    if metric == "inr_unaffected_db":
                        summary_rows[-1]["omitted_records"] = inr_omitted

    cdf_values = pd.DataFrame(cdf_rows).sort_values([
        "metric", "affected_fraction", "load_factor", "pbo_db",
        "cdf_point_index",
    ]).reset_index(drop=True)
    distribution_summary = pd.DataFrame(summary_rows).sort_values([
        "metric", "affected_fraction", "load_factor", "pbo_db",
    ]).reset_index(drop=True)
    paired_controls = pd.DataFrame(control_rows).sort_values([
        "load_factor", "affected_fraction", "pbo_db",
    ]).reset_index(drop=True)
    return cdf_values, distribution_summary, paired_controls


def _cdf_curve(
    cdf_values: pd.DataFrame,
    load_factor: float,
    pbo_db: float,
    fraction: float,
    metric: str,
) -> pd.DataFrame:
    return cdf_values[
        np.isclose(cdf_values["load_factor"], load_factor)
        & np.isclose(cdf_values["pbo_db"], pbo_db)
        & np.isclose(cdf_values["affected_fraction"], fraction)
        & (cdf_values["metric"] == metric)
    ].sort_values("cdf_point_index")


def plot_mechanism_cdf(
    cdf_values: pd.DataFrame,
    figures_dir: Path,
    fraction: float,
    supplementary: bool = False,
) -> None:
    styles = [
        (0.0, "#333333", "--", "Baseline pareado"),
        (10.0, "#0072B2", "-", "PBO = 10 dB"),
        (20.0, "#D55E00", "-.", "PBO = 20 dB"),
    ]
    figure, axes = plt.subplots(
        2, 2, figsize=(7.16, 5.0), constrained_layout=False,
        sharey=True,
    )
    for col_idx, (load_factor, panel) in enumerate(zip(
        EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    )):
        for row_idx, (metric, x_label) in enumerate([
            ("snr_affected_db", "SNR dos usuários afetados (dB)"),
            ("inr_unaffected_db", "I/N dos usuários não afetados (dB)"),
        ]):
            axis = axes[row_idx, col_idx]
            for pbo, color, linestyle, label in styles:
                curve = _cdf_curve(
                    cdf_values, load_factor, pbo, fraction, metric)
                axis.plot(
                    curve["x_value"],
                    curve["cdf_probability"],
                    color=color,
                    linestyle=linestyle,
                    label=label,
                )
            axis.set_xlabel(x_label)
            axis.set_ylabel("CDF empírica")
            axis.set_ylim(0.0, 1.0)
        axes[0, col_idx].set_title(
            f"{panel} LF = {100 * load_factor:.0f}%")

    handles, labels = axes[0, 1].get_legend_handles_labels()
    figure.subplots_adjust(
        left=0.09, right=0.99, top=0.94, bottom=0.12,
        hspace=0.25, wspace=0.20,
    )
    figure.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=3,
        fontsize=7,
    )
    destination = (
        figures_dir
        / f"fig_cdf_snr_inr_mechanism_f{int(round(100 * fraction)):02d}"
    )
    save_figure(figure, destination)


def plot_path_loss_control_cdf(
    cdf_values: pd.DataFrame,
    supplementary_dir: Path,
) -> None:
    styles = [
        (0.0, "#333333", "--", "Baseline pareado"),
        (10.0, "#0072B2", "-", "PBO = 10 dB"),
        (20.0, "#D55E00", "-.", "PBO = 20 dB"),
    ]
    figure, axes = plt.subplots(
        2, 3, figsize=(7.16, 4.6), constrained_layout=False,
        sharex=True, sharey=True,
    )
    for row_idx, load_factor in enumerate(EXPECTED_LOAD_FACTORS):
        for col_idx, fraction in enumerate(EXPECTED_FRACTIONS):
            axis = axes[row_idx, col_idx]
            for pbo, color, linestyle, label in styles:
                curve = _cdf_curve(
                    cdf_values,
                    load_factor,
                    pbo,
                    fraction,
                    "path_loss_db",
                )
                axis.plot(
                    curve["x_value"],
                    curve["cdf_probability"],
                    color=color,
                    linestyle=linestyle,
                    label=label,
                )
            if row_idx == 0:
                axis.set_title(
                    f"Fração = {100 * fraction:.0f}%")
            if col_idx == 0:
                axis.set_ylabel(
                    f"CDF empírica\nLF = {100 * load_factor:.0f}%")
            if row_idx == 1:
                axis.set_xlabel("Path loss (dB)")
            axis.set_ylim(0.0, 1.0)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.subplots_adjust(
        left=0.10, right=0.99, top=0.93, bottom=0.14,
        hspace=0.15, wspace=0.13,
    )
    figure.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=3,
        fontsize=7,
    )
    save_figure(
        figure,
        supplementary_dir / "fig_cdf_path_loss_paired_control",
    )


def plot_supplementary_cdf_metric(
    cdf_values: pd.DataFrame,
    supplementary_dir: Path,
    metric: str,
    x_label: str,
    filename: str,
) -> None:
    fraction = 0.10
    styles = [
        (0.0, "#333333", "--", "Baseline pareado"),
        (10.0, "#0072B2", "-", "PBO = 10 dB"),
        (20.0, "#D55E00", "-.", "PBO = 20 dB"),
    ]
    figure, axes = plt.subplots(
        1, 2, figsize=(7.16, 2.9), constrained_layout=False,
        sharey=True,
    )
    for axis, load_factor, panel in zip(
        axes, EXPECTED_LOAD_FACTORS, ("(a)", "(b)")
    ):
        for pbo, color, linestyle, label in styles:
            curve = _cdf_curve(
                cdf_values, load_factor, pbo, fraction, metric)
            axis.plot(
                curve["x_value"],
                curve["cdf_probability"],
                color=color,
                linestyle=linestyle,
                label=label,
            )
        axis.set_title(f"{panel} LF = {100 * load_factor:.0f}%")
        axis.set_xlabel(x_label)
        axis.set_ylabel("CDF empírica")
        axis.set_ylim(0.0, 1.0)
    handles, labels = axes[1].get_legend_handles_labels()
    figure.subplots_adjust(
        left=0.09, right=0.99, top=0.90, bottom=0.23, wspace=0.18)
    figure.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=3,
        fontsize=7,
    )
    save_figure(figure, supplementary_dir / filename)


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
        is_outage = metric.startswith("outage_probability")
        scale = 100.0 if is_outage else 1.0
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
            if is_outage else METRIC_LABELS[metric]
        )
        axis.set_xticks([0, *EXPECTED_PBO_LEVELS])
        if metric.startswith("sinr_"):
            add_sinr_reference_lines(axis)
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
                        MAIN_OUTAGE_METRIC,
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
            axis.set_ylabel("Outage para SINR < −6 dB (%)")
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
    scenarios: Sequence[Scenario],
    cdf_values: pd.DataFrame,
    paths: dict[str, Path],
) -> None:
    supplementary = paths["supplementary"]
    plot_mechanism_cdf(
        cdf_values, supplementary, 0.05, supplementary=True)
    plot_mechanism_cdf(
        cdf_values, supplementary, 0.15, supplementary=True)
    plot_path_loss_control_cdf(cdf_values, supplementary)
    plot_supplementary_cdf_metric(
        cdf_values,
        supplementary,
        "sinr_all_db",
        "SINR (dB)",
        "fig_cdf_sinr_supplementary_f10",
    )
    plot_supplementary_cdf_metric(
        cdf_values,
        supplementary,
        "spectral_efficiency_proxy_all_bpshz",
        "Proxy de eficiência espectral (bit/s/Hz)",
        "fig_cdf_spectral_efficiency_proxy_f10",
    )
    plot_realized_fraction(metrics_df, supplementary)
    plot_affected_user_counts(metrics_df, supplementary)
    plot_active_beam_distribution(scenarios, supplementary)


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
    performance_values: pd.DataFrame,
    distribution_summary: pd.DataFrame,
    paired_controls: pd.DataFrame,
    tables_dir: Path,
) -> dict[str, pd.DataFrame]:
    for obsolete_stem in [
        "table_main_results",
        "table_affected_unaffected",
        "table_operational_region",
    ]:
        for extension in (".csv", ".tex"):
            obsolete = tables_dir / f"{obsolete_stem}{extension}"
            if obsolete.exists():
                obsolete.unlink()

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

    performance_values.to_csv(
        tables_dir / "table_system_performance.csv", index=False)
    performance_fmt = pd.DataFrame({
        "LF": performance_values["load_factor"].map(
            lambda value: f"{100 * value:.0f}%"),
        "Fração": performance_values.apply(
            lambda row: (
                "Baseline" if row["is_baseline"]
                else f"{100 * row['affected_fraction']:.0f}%"
            ),
            axis=1,
        ),
        "PBO (dB)": performance_values["pbo_db"].map(
            lambda value: f"{value:.0f}"),
        "Outage SINR < -6 dB [IC95%]": performance_values.apply(
            lambda row: (
                f"{100 * row['outage_probability_m6']:.2f}% "
                f"[{100 * row['outage_m6_ci95_lower']:.2f}%, "
                f"{100 * row['outage_m6_ci95_upper']:.2f}%]"
            ),
            axis=1,
        ),
        "Retenção SE P5 [IC95%]": performance_values.apply(
            lambda row: (
                f"{row[RETENTION_METRIC]:.2f}% "
                f"[{row['retention_se_p5_ci95_lower_percent']:.2f}%, "
                f"{row['retention_se_p5_ci95_upper_percent']:.2f}%]"
            ),
            axis=1,
        ),
    })
    write_latex_table(
        performance_fmt,
        tables_dir / "table_system_performance.tex",
    )

    mechanism = distribution_summary[
        distribution_summary["metric"].isin(
            ["snr_affected_db", "inr_unaffected_db"])
    ].copy()
    mechanism.to_csv(
        tables_dir / "table_mechanism_summary.csv", index=False)
    mechanism_fmt = pd.DataFrame({
        "LF": mechanism["load_factor"].map(
            lambda value: f"{100 * value:.0f}%"),
        "Fração": mechanism["affected_fraction"].map(
            lambda value: f"{100 * value:.0f}%"),
        "PBO": mechanism["pbo_db"].map(
            lambda value: "Base" if value == 0 else f"{value:.0f} dB"),
        "Métrica": mechanism["metric"].replace({
            "snr_affected_db": "SNR afetados (dB)",
            "inr_unaffected_db": "I/N não afetados (dB)",
        }),
        "Média": mechanism["mean"].map(lambda value: f"{value:.2f}"),
        "Mediana": mechanism["median"].map(lambda value: f"{value:.2f}"),
        "P5": mechanism["p5"].map(lambda value: f"{value:.2f}"),
        "P95": mechanism["p95"].map(lambda value: f"{value:.2f}"),
        "Omitidos": mechanism["omitted_records"].map(
            lambda value: f"{int(value)}"),
    })
    write_latex_table(
        mechanism_fmt,
        tables_dir / "table_mechanism_summary.tex",
    )

    paired_controls.to_csv(
        tables_dir / "table_paired_controls.csv", index=False)
    controls_fmt = pd.DataFrame({
        "LF": paired_controls["load_factor"].map(
            lambda value: f"{100 * value:.0f}%"),
        "Fração": paired_controls["affected_fraction"].map(
            lambda value: f"{100 * value:.0f}%"),
        "PBO": paired_controls["pbo_db"].map(
            lambda value: f"{value:.0f} dB"),
        "Δ SNR afetados": paired_controls[
            "snr_affected_median_delta_db"].map(
                lambda value: f"{value:.2f} dB"),
        "Δ I/N não afetados": paired_controls[
            "inr_unaffected_median_delta_db"].map(
                lambda value: f"{value:.2f} dB"),
        "Máx. |Δ SNR não afetados|": paired_controls[
            "snr_unaffected_max_abs_delta_db"].map(
                lambda value: f"{value:.3g} dB"),
        "Máx. |Δ path loss|": paired_controls[
            "path_loss_max_abs_delta_db"].map(
                lambda value: f"{value:.3g} dB"),
        "SNR domina": paired_controls[
            "snr_reduction_dominates_inr_benefit"].map(
                lambda value: "Sim" if value else "Não"),
    })
    write_latex_table(
        controls_fmt,
        tables_dir / "table_paired_controls.tex",
    )

    return {
        "scenario_counts": counts,
        "system_performance": performance_values,
        "mechanism_summary": mechanism,
        "paired_controls": paired_controls,
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
    operational_classification: pd.DataFrame,
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
    greatest_outages = {
        key: all_positive.loc[
            all_positive[metric].idxmax()]
        for key, metric in OUTAGE_METRICS.items()
    }
    greatest_outage = greatest_outages["m6"]
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
    point_meets = operational_classification[
        operational_classification[
            "meets_sinr_p5_m6_point_criterion"]
    ]
    robust_meets = operational_classification[
        operational_classification[
            "operational_status_m6"] == "acima_com_ic95"
    ]
    borderline = operational_classification[
        operational_classification[
            "operational_status_m6"] == "limitrofe_ic95"
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
            f"{row.spectral_efficiency_p5_bpshz:.3f} bit/s/Hz. Outage: "
            f"{100 * row.outage_probability_m1:.2f}% para −1 dB, "
            f"{100 * row.outage_probability_m6:.2f}% para −6 dB e "
            f"{100 * row.outage_probability_m10:.2f}% para −10 dB."
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
        "Foram calculados três indicadores diretamente da SINR de cada "
        "registro: −1 dB como referência NR-NTN mais restritiva, −6 dB como "
        "limiar "
        "operacional principal adotado no artigo e −10 dB como indicador "
        "complementar de degradação severa.",
        "",
        "Nenhum desses valores é apresentado como limiar universal de "
        "conformidade NR-NTN.",
        "",
        f"Para o critério principal SINR < {outage_threshold:.1f} dB, a maior "
        f"probabilidade de outage foi "
        f"{100 * float(greatest_outage[MAIN_OUTAGE_METRIC]):.2f}% em "
        f"{_scenario_description(greatest_outage)}. A linha de 5% nas figuras "
        "representa o critério de comparação de pelo menos 95% dos usuários "
        "acima do limiar principal.",
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
        "- As fronteiras operacionais conectam somente o maior nível de PBO "
        "simulado que permaneceu acima de cada limiar para cada fração.",
        "- Os limiares de −1, −6 e −10 dB são referências analíticas desta "
        "avaliação, não critérios universais de conformidade NR-NTN.",
        "- A proxy de eficiência espectral não modela scheduler, MCS/BLER, "
        "HARQ, overhead ou entrega de bits na camada 3.",
        "",
        "## 13. Região operacional para SINR P5 ≥ −6 dB",
        "",
    ])
    lines.append(
        f"{len(point_meets)} das 24 combinações possuem estimativa pontual de "
        "SINR P5 ≥ −6 dB. Destas, "
        f"{len(robust_meets)} têm IC95% inteiramente acima de −6 dB e "
        f"{len(borderline)} são limítrofes porque o IC95% intercepta −6 dB."
    )
    lines.extend(["", "Combinações com estimativa pontual SINR P5 ≥ −6 dB:", ""])
    for row in point_meets.itertuples(index=False):
        suffix = " — limítrofe pelo IC95%" \
            if row.operational_status_m6 == "limitrofe_ic95" else ""
        lines.append(
            f"- LF={100 * row.load_factor:.0f}%, fração="
            f"{100 * row.affected_fraction:.0f}%, PBO={row.pbo_db:.0f} dB: "
            f"SINR P5={row.sinr_p5_db:.2f} dB, IC95% "
            f"[{row.sinr_p5_ci95_lower_db:.2f}, "
            f"{row.sinr_p5_ci95_upper_db:.2f}] dB{suffix}."
        )
    lines.extend(["", "Combinações limítrofes pelo IC95%:", ""])
    if borderline.empty:
        lines.append("- Nenhuma.")
    else:
        for row in borderline.itertuples(index=False):
            lines.append(
                f"- LF={100 * row.load_factor:.0f}%, fração="
                f"{100 * row.affected_fraction:.0f}%, "
                f"PBO={row.pbo_db:.0f} dB: SINR P5="
                f"{row.sinr_p5_db:.2f} dB, IC95% "
                f"[{row.sinr_p5_ci95_lower_db:.2f}, "
                f"{row.sinr_p5_ci95_upper_db:.2f}] dB."
            )
    lines.extend(["", "## Valores sugeridos para citação no artigo", ""])
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
        f"- Para o limiar operacional principal de −6 dB, a maior "
        f"probabilidade de outage observada foi "
        f"{100 * float(greatest_outage[MAIN_OUTAGE_METRIC]):.2f}% em "
        f"{_scenario_description(greatest_outage)}."
    )
    (reports_dir / "results_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {
        "worst_sinr_delta": worst.to_dict(),
        "greatest_outage_m6": greatest_outage.to_dict(),
        "greatest_outage_by_threshold": {
            key: row.to_dict() for key, row in greatest_outages.items()
        },
        "sinr_p5_m6_point_criterion_scenarios":
            point_meets["scenario_id"].tolist(),
        "sinr_p5_m6_robust_scenarios":
            robust_meets["scenario_id"].tolist(),
        "sinr_p5_m6_borderline_scenarios":
            borderline["scenario_id"].tolist(),
        "unaffected_improvement_count": int(len(improvements)),
        "largest_unaffected_improvement":
            improvements.iloc[0].to_dict() if not improvements.empty else None,
    }


def generate_performance_report(
    performance_values: pd.DataFrame,
    distribution_summary: pd.DataFrame,
    paired_controls: pd.DataFrame,
    qc: QCRecorder,
    repetitions: int,
    reports_dir: Path,
) -> dict:
    positives = performance_values[~performance_values["is_baseline"]]
    baselines = performance_values[
        performance_values["is_baseline"]].sort_values("load_factor")
    greatest_outage = positives.loc[
        positives["outage_probability_m6"].idxmax()]
    minimum_retention = positives.loc[
        positives[RETENTION_METRIC].idxmin()]
    availability_pass = positives[
        positives["outage_probability_m6"] <= 0.05]
    main_controls = paired_controls[
        np.isclose(paired_controls["affected_fraction"], 0.10)
        & paired_controls["pbo_db"].isin([10.0, 20.0])
    ].sort_values(["load_factor", "pbo_db"])
    main_inr = distribution_summary[
        (distribution_summary["metric"] == "inr_unaffected_db")
        & np.isclose(distribution_summary["affected_fraction"], 0.10)
        & distribution_summary["pbo_db"].isin([0.0, 10.0, 20.0])
    ].sort_values(["load_factor", "pbo_db"])
    status_counts = qc.dataframe()["status"].value_counts().to_dict()
    snr_constant_count = int(
        paired_controls["snr_unaffected_practically_constant"].sum())
    path_loss_count = int(paired_controls["path_loss_overlaid"].sum())
    inr_decreased_count = int(
        paired_controls["inr_unaffected_decreased"].sum())
    dominance_count = int(
        paired_controls["snr_reduction_dominates_inr_benefit"].sum())

    lines = [
        "# Resultados da Campanha 03 — disponibilidade, qualidade e mecanismo",
        "",
        "## Escopo e integridade",
        "",
        f"O controle de qualidade registrou {status_counts.get('PASS', 0)} "
        f"verificações PASS, {status_counts.get('WARNING', 0)} WARNING e "
        f"{status_counts.get('FAIL', 0)} FAIL. Foram processados 26 cenários "
        "selecionados, cada um com 1.000 snapshots.",
        "",
        "O pós-processamento leu os CSVs existentes sem executar novamente o "
        "simulador ou modificar os dados brutos.",
        "",
        "A disponibilidade e a qualidade são apresentadas conjuntamente. "
        "Outage ≤ 5% para SINR < −6 dB e SINR P5 ≥ −6 dB expressam "
        "essencialmente o mesmo corte estatístico e não são tratados como "
        "análises independentes.",
        "",
        "O limiar de −6 dB é o critério operacional principal desta análise; "
        "não é apresentado como limiar universal de conformidade NR-NTN.",
        "",
        "## 1. Disponibilidade: qual é a probabilidade de SINR < −6 dB?",
        "",
    ]
    for row in baselines.itertuples(index=False):
        lines.append(
            f"- Baseline LF = {100 * row.load_factor:.0f}%: outage "
            f"{100 * row.outage_probability_m6:.2f}%, IC95% "
            f"[{100 * row.outage_m6_ci95_lower:.2f}%, "
            f"{100 * row.outage_m6_ci95_upper:.2f}%]."
        )
    lines.extend([
        "",
        f"{len(availability_pass)} dos 24 cenários com PBO possuem outage "
        "pontual ≤ 5%. O maior outage foi "
        f"{100 * greatest_outage['outage_probability_m6']:.2f}% em "
        f"{_scenario_description(greatest_outage)}.",
        "",
        "Os IC95% foram obtidos por bootstrap agrupado por snapshot. A figura "
        "principal contém os 24 cenários com PBO e os dois baselines.",
        "",
        "## 2. Qualidade: quanto da proxy de eficiência espectral P5 é preservado?",
        "",
        "A retenção foi calculada diretamente da proxy salva pelo SHARC como "
        "100 × SE P5 do cenário / SE P5 do baseline. O IC95% usa a razão "
        "repetição a repetição do bootstrap pareado por snapshot.",
        "",
        f"A menor retenção pontual foi "
        f"{minimum_retention[RETENTION_METRIC]:.2f}% em "
        f"{_scenario_description(minimum_retention)}. Não foi aplicado limiar "
        "arbitrário à retenção.",
        "",
        "A grandeza permanece identificada como proxy de eficiência espectral; "
        "não é chamada de throughput.",
        "",
        "## 3. Mecanismo: redução de SNR e benefício de interferência",
        "",
        "As comparações usam as mesmas chaves `snapshot_id`, `ue_id` e "
        "`beam_id`. O baseline recebe a mesma máscara da fração analisada.",
        "",
    ])
    for row in main_controls.itertuples(index=False):
        lines.append(
            f"- LF={100 * row.load_factor:.0f}%, fração=10% e "
            f"PBO={row.pbo_db:.0f} dB: mediana da ΔSNR dos usuários afetados "
            f"= {row.snr_affected_median_delta_db:.2f} dB; mediana da ΔI/N "
            f"dos usuários não afetados = "
            f"{row.inr_unaffected_median_delta_db:.2f} dB."
        )
    lines.extend([
        "",
        "O I/N foi derivado registro a registro por "
        "`SNR_linear / SINR_linear - 1`. Valores não positivos ou não finitos "
        "foram omitidos, sem substituição artificial.",
        "",
    ])
    for row in main_inr.itertuples(index=False):
        label = "baseline" if row.pbo_db == 0 else f"PBO={row.pbo_db:.0f} dB"
        lines.append(
            f"- LF={100 * row.load_factor:.0f}%, {label}: "
            f"{row.omitted_records} de {row.total_records} registros de I/N "
            "omitidos por precisão numérica."
        )
    lines.extend([
        "",
        "## Controles pareados",
        "",
        f"- SNR dos usuários não afetados praticamente constante: "
        f"{snr_constant_count}/24 cenários.",
        f"- Path loss sobreposto ao baseline por chave: "
        f"{path_loss_count}/24 cenários.",
        f"- Mediana de I/N dos usuários não afetados reduzida: "
        f"{inr_decreased_count}/24 cenários.",
        f"- Redução de SNR dos afetados dominante sobre a redução de I/N: "
        f"{dominance_count}/24 cenários.",
        "",
        "A CDF de path loss é usada apenas como controle de qualidade, pois o "
        "PBO não deve alterar a perda de propagação.",
        "",
        "## Método estatístico e limitações",
        "",
        f"- Os IC95% usam bootstrap agrupado por snapshot com {repetitions} "
        "repetições.",
        "- A retenção usa bootstrap pareado; os mesmos snapshots são "
        "reamostrados no cenário e no baseline.",
        "- As CDFs não recebem bandas de confiança para preservar a "
        "legibilidade.",
        "- A proxy de eficiência espectral não modela scheduler, MCS/BLER, "
        "HARQ, overhead ou entrega de bits na camada 3.",
        "",
        "## Valores sugeridos para citação no artigo",
        "",
        f"- O maior outage para SINR < −6 dB foi "
        f"{100 * greatest_outage['outage_probability_m6']:.2f}% em "
        f"{_scenario_description(greatest_outage)}.",
        f"- A menor retenção da proxy de eficiência espectral P5 foi "
        f"{minimum_retention[RETENTION_METRIC]:.2f}% em "
        f"{_scenario_description(minimum_retention)}.",
    ])
    (reports_dir / "results_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {
        "greatest_outage_m6": greatest_outage.to_dict(),
        "minimum_spectral_efficiency_p5_retention":
            minimum_retention.to_dict(),
        "availability_scenarios_outage_le_5_percent":
            int(len(availability_pass)),
        "snr_unaffected_constant_scenarios": snr_constant_count,
        "path_loss_overlaid_scenarios": path_loss_count,
        "inr_unaffected_decreased_scenarios": inr_decreased_count,
        "snr_reduction_dominant_scenarios": dominance_count,
        "main_inr_omitted_records": int(main_inr[
            "omitted_records"].sum()),
    }


def generate_figure_captions(
    outage_threshold: float,
    reports_dir: Path,
) -> None:
    captions = [
        r"% Legendas geradas a partir do mesmo conjunto de dados das figuras.",
        r"\newcommand{\CaptionSystemPerformance}{"
        rf"Disponibilidade e qualidade do sistema para LF de 20\% e 50\%. "
        rf"A linha superior mostra outage para SINR $< "
        rf"{outage_threshold:.0f}$ dB, com IC95\% por bootstrap agrupado por "
        r"snapshot e referência horizontal de 5\%. A linha inferior mostra "
        r"a retenção da proxy de eficiência espectral P5 em relação ao "
        r"baseline, com IC95\% por bootstrap pareado por snapshot.}",
        r"\newcommand{\CaptionMechanismFten}{"
        r"Mecanismo físico para fração afetada de 10\%: CDF da SNR dos "
        r"usuários em feixes afetados e CDF de I/N dos usuários em feixes "
        r"não afetados. Baseline, PBO de 10 dB e PBO de 20 dB usam as mesmas "
        r"chaves de snapshot, usuário e feixe.}",
        r"\newcommand{\CaptionPathLossControl}{"
        r"Controle pareado da CDF de path loss. A sobreposição entre baseline "
        r"e cenários com PBO confirma que a perda de propagação não foi "
        r"alterada pelo controle de potência.}",
        r"\newcommand{\CaptionSupplementarySinrCdf}{"
        r"CDF suplementar da SINR de todos os usuários para fração afetada "
        r"de 10\%, apresentada apenas como apoio à análise conjunta de "
        r"disponibilidade e qualidade.}",
        r"\newcommand{\CaptionSupplementarySpectralEfficiencyCdf}{"
        r"CDF suplementar da proxy de eficiência espectral salva pelo SHARC "
        r"para fração afetada de 10\%. A grandeza não representa throughput.}",
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
                outage_names = {
                    key: latex_command_name(
                        f"Outage{key.upper()}",
                        load_factor,
                        pbo,
                        fraction,
                    )
                    for key in OUTAGE_THRESHOLDS
                }
                lines.extend([
                    rf"\newcommand{{\{sinr_name}}}"
                    rf"{{{float(metric['sinr_p5_db']):.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}}}"
                    rf"{{{delta[0]:.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}CiLow}}"
                    rf"{{{delta[1]:.2f}\,\mathrm{{dB}}}}",
                    rf"\newcommand{{\{delta_name}CiHigh}}"
                    rf"{{{delta[2]:.2f}\,\mathrm{{dB}}}}",
                ])
                for key, outage_name in outage_names.items():
                    lines.append(
                        rf"\newcommand{{\{outage_name}}}"
                        rf"{{{100 * float(metric[OUTAGE_METRICS[key]]):.2f}\%}}"
                    )
    lines.append("")
    (reports_dir / "results_values.tex").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_performance_results_values(
    performance_values: pd.DataFrame,
    paired_controls: pd.DataFrame,
    reports_dir: Path,
) -> None:
    lines = [
        r"% Valores gerados automaticamente; não editar manualmente.",
    ]
    for row in performance_values.itertuples(index=False):
        if row.is_baseline:
            prefix = (
                "BaselinePerformanceLf"
                + ("Twenty" if np.isclose(row.load_factor, 0.2) else "Fifty")
            )
        else:
            prefix = latex_command_name(
                "Performance",
                row.load_factor,
                row.pbo_db,
                row.affected_fraction,
            )
        lines.extend([
            rf"\newcommand{{\{prefix}OutageM6}}"
            rf"{{{100 * row.outage_probability_m6:.2f}\%}}",
            rf"\newcommand{{\{prefix}OutageM6CiLow}}"
            rf"{{{100 * row.outage_m6_ci95_lower:.2f}\%}}",
            rf"\newcommand{{\{prefix}OutageM6CiHigh}}"
            rf"{{{100 * row.outage_m6_ci95_upper:.2f}\%}}",
            rf"\newcommand{{\{prefix}SePfiveRetention}}"
            rf"{{{getattr(row, RETENTION_METRIC):.2f}\%}}",
            rf"\newcommand{{\{prefix}SePfiveRetentionCiLow}}"
            rf"{{{row.retention_se_p5_ci95_lower_percent:.2f}\%}}",
            rf"\newcommand{{\{prefix}SePfiveRetentionCiHigh}}"
            rf"{{{row.retention_se_p5_ci95_upper_percent:.2f}\%}}",
        ])
    controls = paired_controls[
        np.isclose(paired_controls["affected_fraction"], 0.10)
        & paired_controls["pbo_db"].isin([10.0, 20.0])
    ]
    for row in controls.itertuples(index=False):
        prefix = latex_command_name(
            "Mechanism",
            row.load_factor,
            row.pbo_db,
            row.affected_fraction,
        )
        lines.extend([
            rf"\newcommand{{\{prefix}SnrAffectedDeltaMedian}}"
            rf"{{{row.snr_affected_median_delta_db:.2f}\,\mathrm{{dB}}}}",
            rf"\newcommand{{\{prefix}InrUnaffectedDeltaMedian}}"
            rf"{{{row.inr_unaffected_median_delta_db:.2f}\,\mathrm{{dB}}}}",
        ])
    lines.append("")
    (reports_dir / "results_values.tex").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_all_figures(
    scenarios: Sequence[Scenario],
    metrics_df: pd.DataFrame,
    performance_values: pd.DataFrame,
    cdf_values: pd.DataFrame,
    paths: dict[str, Path],
) -> None:
    configure_matplotlib()
    for obsolete_stem in [
        "fig_heatmap_delta_sinr_p5",
        "fig_heatmap_absolute_sinr_p5",
        "fig_outage_vs_pbo",
        "fig_operational_region_pbo",
        "fig_operational_frontiers_pbo",
        "fig_outage_threshold_sensitivity_f10",
        "fig_outage_vs_pbo_threshold_m6",
        "fig_sinr_p5_affected_unaffected_f10",
        "fig_cdf_representative",
    ]:
        for extension in (".pdf", ".png"):
            obsolete = paths["figures"] / f"{obsolete_stem}{extension}"
            if obsolete.exists():
                obsolete.unlink()
    for obsolete_stem in [
        "fig_sinr_mean_all_fractions",
        "fig_sinr_p5_all_fractions",
        "fig_spectral_efficiency_mean_all_fractions",
        "fig_spectral_efficiency_p5_all_fractions",
        "fig_outage_by_group",
        "fig_delta_sinr_p5_unaffected",
        "fig_delta_sinr_p5_affected",
        "fig_sinr_p5_affected_unaffected_f05",
        "fig_sinr_p5_affected_unaffected_f15",
    ]:
        for extension in (".pdf", ".png"):
            obsolete = paths["supplementary"] / f"{obsolete_stem}{extension}"
            if obsolete.exists():
                obsolete.unlink()
    plot_system_performance(performance_values, paths["figures"])
    plot_mechanism_cdf(
        cdf_values, paths["figures"], 0.10, supplementary=False)
    generate_supplementary_figures(
        metrics_df, scenarios, cdf_values, paths)


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
        default=-6.0,
        help="Limiar operacional principal adotado para comparação, em dB.",
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
            frame = load_scenario_dataframe(
                scenario, include_path_loss=True)
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
    performance_values = build_system_performance_values(
        bootstrap_df, paired_df)
    performance_values.to_csv(
        paths["data"] / "system_performance_figure_values.csv",
        index=False,
    )
    print("Construindo CDFs pareadas e controles do mecanismo físico...")
    cdf_values, distribution_summary, paired_controls = (
        build_mechanism_analysis(scenarios, summaries)
    )
    cdf_values.to_csv(
        paths["data"] / "cdf_figure_values.csv", index=False)
    distribution_summary.to_csv(
        paths["data"] / "distribution_summary.csv", index=False)
    paired_controls.to_csv(
        paths["data"] / "paired_control_checks.csv", index=False)
    for obsolete_name in [
        "operational_region_classification.csv",
        "operational_frontiers.csv",
    ]:
        obsolete = paths["data"] / obsolete_name
        if obsolete.exists():
            obsolete.unlink()

    qc.add(
        "main_figure_inventory",
        "PASS" if (
            len(performance_values) == 26
            and int((~performance_values["is_baseline"]).sum()) == 24
            and int(performance_values["is_baseline"].sum()) == 2
        ) else "FAIL",
        f"Linhas={len(performance_values)}; cenários com PBO="
        f"{int((~performance_values['is_baseline']).sum())}; baselines="
        f"{int(performance_values['is_baseline'].sum())}.",
    )
    paired_checks = [
        (
            "snr_unaffected_constant",
            "snr_unaffected_practically_constant",
            "SNR dos usuários não afetados constante",
        ),
        (
            "path_loss_control",
            "path_loss_overlaid",
            "path loss sobreposto",
        ),
        (
            "inr_unaffected_decreases",
            "inr_unaffected_decreased",
            "I/N dos usuários não afetados reduzido",
        ),
        (
            "snr_reduction_dominates",
            "snr_reduction_dominates_inr_benefit",
            "redução de SNR dominante",
        ),
    ]
    for check, column, label in paired_checks:
        passed = int(paired_controls[column].sum())
        qc.add(
            check,
            "PASS" if passed == 24 else "WARNING",
            f"{label}: {passed}/24 cenários pareados.",
        )
    total_inr_omitted = int(distribution_summary.loc[
        distribution_summary["metric"] == "inr_unaffected_db",
        "omitted_records",
    ].sum())
    total_inr_records = int(distribution_summary.loc[
        distribution_summary["metric"] == "inr_unaffected_db",
        "total_records",
    ].sum())
    qc.add(
        "inr_numerical_omissions",
        "PASS",
        f"Registros de I/N omitidos por resultado linear não positivo ou "
        f"não finito: {total_inr_omitted}/{total_inr_records}.",
    )
    write_qc_outputs(qc, paths)
    if qc.has_failures():
        raise RuntimeError(
            "O controle de qualidade pós-bootstrap encontrou falhas. "
            "Consulte generated/quality_control/qc_report.md.")

    print("Gerando figuras em PDF vetorial e PNG a 300 dpi...")
    generate_all_figures(
        scenarios,
        metrics_df,
        performance_values,
        cdf_values,
        paths,
    )
    print("Gerando tabelas e relatórios...")
    build_tables(
        scenarios,
        metrics_df,
        performance_values,
        distribution_summary,
        paired_controls,
        paths["tables"],
    )
    result_summary = generate_performance_report(
        performance_values,
        distribution_summary,
        paired_controls,
        qc,
        args.bootstrap_repetitions,
        paths["reports"],
    )
    generate_figure_captions(
        args.outage_threshold, paths["reports"])
    generate_performance_results_values(
        performance_values, paired_controls, paths["reports"])

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
    if not np.isclose(args.outage_threshold, OUTAGE_THRESHOLDS["m6"]):
        raise ValueError(
            "A Campanha 03 usa -6 dB como limiar operacional principal; "
            "--outage-threshold deve permanecer em -6.")
    summary = run_analysis(args)
    print("Resumo final:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

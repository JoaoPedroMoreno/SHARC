"""Snapshot-based interference-aware inter-satellite handover (V2).

The module deliberately separates *which links are examined* (trigger) from
*which eligible satellite is selected* (target selection).  It contains no
random operation and works exclusively in linear power for aggregate updates.
"""
from dataclasses import dataclass, asdict
from typing import Callable, Iterable

import numpy as np


@dataclass(frozen=True)
class CandidateEvaluation:
    satellite_idx: int
    service_elevation_deg: float
    i_link_linear_mw: float
    eess_elevation_deg: float = np.nan
    tx_offaxis_deg: float = np.nan
    rx_offaxis_deg: float = np.nan
    g_tx_dbi: float = np.nan
    g_rx_dbi: float = np.nan
    tx_gain_drop_db: float = np.nan
    rx_gain_drop_db: float = np.nan
    joint_gain_suppression_db: float = np.nan
    path_loss_db: float = np.nan
    spectral_coupling_db: float = np.nan
    coupling_loss_db: float = np.nan
    tx_peak_gain_dbi: float = np.nan
    rx_peak_gain_dbi: float = np.nan
    tx_conducted_power_dbm: float = np.nan
    tx_spectral_power_dbm: float = np.nan
    interferer_azimuth_from_eess_deg: float = np.nan
    satellite_enu_x_m: float = np.nan
    satellite_enu_y_m: float = np.nan
    satellite_enu_z_m: float = np.nan
    satellite_latitude_deg: float = np.nan
    satellite_longitude_deg: float = np.nan
    satellite_altitude_m: float = np.nan
    tx_boresight_azimuth_deg: float = np.nan
    tx_boresight_elevation_deg: float = np.nan


@dataclass(frozen=True)
class TargetDecision:
    beam_row_idx: int
    current_satellite_idx: int
    selected_satellite_idx: int
    current_i_linear_mw: float
    selected_i_linear_mw: float
    predicted_reduction_db: float
    accepted: bool
    reason: str
    candidates: tuple[CandidateEvaluation, ...]

    def as_dict(self):
        value = asdict(self)
        value["candidates"] = [asdict(c) for c in self.candidates]
        return value


def select_triggered_links(
    link_powers_linear_mw: dict[int, float], top_k: int, trigger_mode: str,
    geometric_rule: Callable[[int], bool] | None = None,
) -> list[int]:
    """Return stable link order selected by the configured research trigger."""
    ranked = sorted(link_powers_linear_mw, key=lambda i: (-link_powers_linear_mw[i], i))
    mode = trigger_mode.upper()
    if mode == "ORACLE_TOP_K":
        return ranked[:top_k]
    if mode == "GEOMETRIC_RULE":
        if geometric_rule is None:
            raise ValueError("GEOMETRIC_RULE requires an explicitly supplied rule")
        return [idx for idx in ranked if geometric_rule(idx)][:top_k]
    raise ValueError(f"Unsupported V2 trigger mode: {trigger_mode}")


def should_enter_risk_gate(
    trigger_mode: str, iagg_dbw_per_mhz: float, threshold_dbw_per_mhz: float,
) -> bool:
    """Separate snapshot mitigation need from dominant-link ranking."""
    mode = trigger_mode.upper()
    if mode == "ORACLE_TOP_K":
        return True
    if mode == "RISK_GATED_TOP_K":
        return iagg_dbw_per_mhz > threshold_dbw_per_mhz
    if mode == "GEOMETRIC_RULE":
        return True
    raise ValueError(f"Unsupported V2 trigger mode: {trigger_mode}")


def choose_minimum_interference_target(
    *, beam_row_idx: int, current_satellite_idx: int,
    current_service_elevation_deg: float, current_i_linear_mw: float,
    candidates: Iterable[CandidateEvaluation], min_reduction_db: float,
    max_service_elevation_loss_deg: float,
) -> TargetDecision:
    """Choose the eligible candidate with minimum exact predicted I_link."""
    evaluated = tuple(candidates)
    eligible = [c for c in evaluated if (
        current_service_elevation_deg - c.service_elevation_deg
        <= max_service_elevation_loss_deg
        and c.satellite_idx != current_satellite_idx
        and c.i_link_linear_mw >= 0.0
    )]
    if not eligible:
        return TargetDecision(beam_row_idx, current_satellite_idx,
                              current_satellite_idx, current_i_linear_mw,
                              current_i_linear_mw, 0.0, False,
                              "NO_ELIGIBLE_TARGET", evaluated)
    target = min(eligible, key=lambda c: (c.i_link_linear_mw, c.satellite_idx))
    if current_i_linear_mw <= 0.0:
        reduction = 0.0
    elif target.i_link_linear_mw == 0.0:
        reduction = np.inf
    else:
        reduction = 10.0 * np.log10(current_i_linear_mw / target.i_link_linear_mw)
    accepted = reduction >= min_reduction_db
    return TargetDecision(
        beam_row_idx, current_satellite_idx,
        target.satellite_idx if accepted else current_satellite_idx,
        current_i_linear_mw,
        target.i_link_linear_mw if accepted else current_i_linear_mw,
        float(reduction), bool(accepted),
        "ACCEPTED" if accepted else "BELOW_MIN_REDUCTION", evaluated)


def replace_link_power_linear(
    aggregate_linear_mw: float, current_linear_mw: float,
    candidate_linear_mw: float,
) -> float:
    """Apply one replacement without ever subtracting logarithmic values."""
    updated = aggregate_linear_mw - current_linear_mw + candidate_linear_mw
    return float(max(updated, 0.0))

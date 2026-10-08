"""Snapshot-based Interference-Aware Inter-Satellite Handover.

This module contains only deterministic geometry and selection logic.  It does
not keep state between Monte Carlo snapshots and does not consume random
numbers.
"""

from dataclasses import dataclass

import numpy as np

from sharc.support.sharc_geom import polar_to_cartesian


@dataclass(frozen=True)
class InterferenceAwareHandoverEvent:
    """Details of one primary main-main trigger within a snapshot."""

    beam_row_idx: int
    beam_grid_idx: int
    primary_satellite_idx: int
    target_satellite_idx: int
    final_satellite_idx: int
    primary_elevation_deg: float
    target_elevation_deg: float
    delta_elevation_deg: float
    primary_dc_off_axis_deg: float
    primary_eess_off_axis_deg: float
    target_dc_off_axis_deg: float
    target_eess_off_axis_deg: float
    eess_phi_min_deg: float
    eess_system: str
    outcome: str

    def as_dict(self) -> dict:
        """Return a serialization-friendly event record."""
        return {
            "beam_row_idx": self.beam_row_idx,
            "beam_grid_idx": self.beam_grid_idx,
            "primary_satellite_idx": self.primary_satellite_idx,
            "target_satellite_idx": self.target_satellite_idx,
            "final_satellite_idx": self.final_satellite_idx,
            "primary_elevation_deg": self.primary_elevation_deg,
            "target_elevation_deg": self.target_elevation_deg,
            "delta_elevation_deg": self.delta_elevation_deg,
            "primary_dc_off_axis_deg": self.primary_dc_off_axis_deg,
            "primary_eess_off_axis_deg": self.primary_eess_off_axis_deg,
            "target_dc_off_axis_deg": self.target_dc_off_axis_deg,
            "target_eess_off_axis_deg": self.target_eess_off_axis_deg,
            "eess_phi_min_deg": self.eess_phi_min_deg,
            "eess_system": self.eess_system,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class InterferenceAwareHandoverOutcome:
    """Final serving association and instrumentation for one snapshot."""

    serving_satellite_indices: np.ndarray
    triggered_mask: np.ndarray
    successful_mask: np.ndarray
    unresolved_mask: np.ndarray
    metrics: dict
    events: tuple[InterferenceAwareHandoverEvent, ...]


def angle_between_vectors_deg(vector_a: np.ndarray,
                              vector_b: np.ndarray) -> np.ndarray:
    """Return the smaller angle between vectors in degrees."""
    vector_a = np.asarray(vector_a, dtype=float)
    vector_b = np.asarray(vector_b, dtype=float)
    norm_a = np.linalg.norm(vector_a, axis=-1)
    norm_b = np.linalg.norm(vector_b, axis=-1)
    if np.any(norm_a == 0.0) or np.any(norm_b == 0.0):
        raise ValueError("Off-axis vectors must have non-zero length")
    cosine = np.sum(vector_a * vector_b, axis=-1) / (norm_a * norm_b)
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))


def calculate_dc_mss_off_axis_deg(
    satellite_position: np.ndarray,
    cell_position: np.ndarray,
    eess_position: np.ndarray,
) -> np.ndarray:
    """Angle between a cell-centred DC-MSS beam and the EESS direction."""
    satellite_position = np.asarray(satellite_position, dtype=float)
    return angle_between_vectors_deg(
        np.asarray(cell_position, dtype=float) - satellite_position,
        np.asarray(eess_position, dtype=float) - satellite_position,
    )


def calculate_eess_off_axis_deg(
    eess_position: np.ndarray,
    eess_boresight_azimuth_deg: float,
    eess_boresight_elevation_deg: float,
    satellite_positions: np.ndarray,
) -> np.ndarray:
    """Angle from the realized EESS boresight to candidate satellites."""
    bx, by, bz = polar_to_cartesian(
        1.0,
        eess_boresight_azimuth_deg,
        eess_boresight_elevation_deg,
    )
    boresight = np.asarray([bx, by, bz], dtype=float).reshape(3)
    directions = (
        np.asarray(satellite_positions, dtype=float)
        - np.asarray(eess_position, dtype=float)
    )
    return angle_between_vectors_deg(
        np.broadcast_to(boresight, directions.shape),
        directions,
    )


def is_main_beam_to_main_beam(
    dc_mss_off_axis_deg: np.ndarray | float,
    eess_off_axis_deg: np.ndarray | float,
    dc_mss_off_axis_limit_deg: float,
    eess_phi_min_deg: float,
) -> np.ndarray:
    """Apply the campaign's operational main-main definition.

    ``eess_phi_min_deg`` is the limit of the maximum-gain region of the
    implemented S.465 pattern.  It is not treated as a physical HPBW.
    """
    return (
        np.asarray(dc_mss_off_axis_deg) <= dc_mss_off_axis_limit_deg
    ) & (
        np.asarray(eess_off_axis_deg) < eess_phi_min_deg
    )


def select_interference_aware_serving_satellites(
    *,
    primary_satellite_indices: np.ndarray,
    beam_grid_indices: np.ndarray,
    active_mask: np.ndarray,
    candidate_satellite_indices: np.ndarray,
    candidate_elevations_deg: np.ndarray,
    candidate_satellite_positions: np.ndarray,
    cell_positions: np.ndarray,
    eess_position: np.ndarray,
    eess_boresight_azimuth_deg: float,
    eess_boresight_elevation_deg: float,
    dc_mss_off_axis_limit_deg: float,
    eess_phi_min_deg: float,
    minimum_service_angle_deg: float,
    eess_system: str = "",
) -> InterferenceAwareHandoverOutcome:
    """Select a safe serving satellite without changing cell identity.

    Candidate ordering is descending elevation with a stable tie break.  All
    inputs describe one Monte Carlo snapshot; no previous serving association
    is accepted or retained.
    """
    primary_satellite_indices = np.asarray(
        primary_satellite_indices, dtype=int)
    beam_grid_indices = np.asarray(beam_grid_indices, dtype=int)
    active_mask = np.asarray(active_mask, dtype=bool)
    candidate_satellite_indices = np.asarray(
        candidate_satellite_indices, dtype=int)
    candidate_elevations_deg = np.asarray(
        candidate_elevations_deg, dtype=float)
    candidate_satellite_positions = np.asarray(
        candidate_satellite_positions, dtype=float)
    cell_positions = np.asarray(cell_positions, dtype=float)
    eess_position = np.asarray(eess_position, dtype=float).reshape(3)

    num_beams = primary_satellite_indices.size
    if beam_grid_indices.shape != (num_beams,):
        raise ValueError("beam_grid_indices must match the number of beams")
    if active_mask.shape != (num_beams,):
        raise ValueError("active_mask must match the number of beams")
    num_candidates = candidate_satellite_indices.size
    if candidate_satellite_positions.shape != (num_candidates, 3):
        raise ValueError(
            "candidate_satellite_positions must have shape (candidates, 3)")
    if candidate_elevations_deg.ndim != 2:
        raise ValueError("candidate_elevations_deg must be a 2-D matrix")
    if candidate_elevations_deg.shape[1] != num_candidates:
        raise ValueError(
            "candidate elevation columns must match candidate satellites")
    if cell_positions.shape != (candidate_elevations_deg.shape[0], 3):
        raise ValueError(
            "cell_positions must match candidate elevation grid rows")
    if np.any(beam_grid_indices < 0) or np.any(
            beam_grid_indices >= cell_positions.shape[0]):
        raise ValueError("beam_grid_indices contain an invalid cell index")
    if np.unique(candidate_satellite_indices).size != num_candidates:
        raise ValueError("candidate satellite indices must be unique")

    candidate_column = {
        int(satellite_idx): column
        for column, satellite_idx in enumerate(candidate_satellite_indices)
    }
    missing_primary = set(primary_satellite_indices.tolist()) - set(
        candidate_column)
    if missing_primary:
        raise ValueError(
            "Primary satellites are absent from the available candidate set: "
            f"{sorted(missing_primary)}")

    eess_off_axis_by_candidate = calculate_eess_off_axis_deg(
        eess_position,
        eess_boresight_azimuth_deg,
        eess_boresight_elevation_deg,
        candidate_satellite_positions,
    )

    final_satellite_indices = primary_satellite_indices.copy()
    triggered_mask = np.zeros(num_beams, dtype=bool)
    successful_mask = np.zeros(num_beams, dtype=bool)
    unresolved_mask = np.zeros(num_beams, dtype=bool)
    events = []

    for beam_row_idx in np.flatnonzero(active_mask):
        grid_idx = int(beam_grid_indices[beam_row_idx])
        primary_idx = int(primary_satellite_indices[beam_row_idx])
        primary_col = candidate_column[primary_idx]
        primary_position = candidate_satellite_positions[primary_col]
        cell_position = cell_positions[grid_idx]
        primary_dc_off_axis = float(calculate_dc_mss_off_axis_deg(
            primary_position, cell_position, eess_position))
        primary_eess_off_axis = float(
            eess_off_axis_by_candidate[primary_col])

        if not bool(is_main_beam_to_main_beam(
            primary_dc_off_axis,
            primary_eess_off_axis,
            dc_mss_off_axis_limit_deg,
            eess_phi_min_deg,
        )):
            continue

        triggered_mask[beam_row_idx] = True
        elevations = candidate_elevations_deg[grid_idx]
        ordered_columns = np.argsort(-elevations, kind="stable")

        target_idx = -1
        target_elevation = np.nan
        target_dc_off_axis = np.nan
        target_eess_off_axis = np.nan
        for candidate_col in ordered_columns:
            candidate_idx = int(candidate_satellite_indices[candidate_col])
            if candidate_idx == primary_idx:
                continue
            candidate_elevation = float(elevations[candidate_col])
            if candidate_elevation < minimum_service_angle_deg:
                continue
            candidate_dc_off_axis = float(calculate_dc_mss_off_axis_deg(
                candidate_satellite_positions[candidate_col],
                cell_position,
                eess_position,
            ))
            candidate_eess_off_axis = float(
                eess_off_axis_by_candidate[candidate_col])
            if bool(is_main_beam_to_main_beam(
                candidate_dc_off_axis,
                candidate_eess_off_axis,
                dc_mss_off_axis_limit_deg,
                eess_phi_min_deg,
            )):
                continue

            target_idx = candidate_idx
            target_elevation = candidate_elevation
            target_dc_off_axis = candidate_dc_off_axis
            target_eess_off_axis = candidate_eess_off_axis
            break

        primary_elevation = float(elevations[primary_col])
        if target_idx >= 0:
            final_satellite_indices[beam_row_idx] = target_idx
            successful_mask[beam_row_idx] = True
            delta_elevation = primary_elevation - target_elevation
            final_idx = target_idx
            outcome = "HANDOVER"
        else:
            unresolved_mask[beam_row_idx] = True
            delta_elevation = np.nan
            final_idx = primary_idx
            outcome = "UNRESOLVED_KEEP_PRIMARY"

        events.append(InterferenceAwareHandoverEvent(
            beam_row_idx=int(beam_row_idx),
            beam_grid_idx=grid_idx,
            primary_satellite_idx=primary_idx,
            target_satellite_idx=target_idx,
            final_satellite_idx=final_idx,
            primary_elevation_deg=primary_elevation,
            target_elevation_deg=target_elevation,
            delta_elevation_deg=delta_elevation,
            primary_dc_off_axis_deg=primary_dc_off_axis,
            primary_eess_off_axis_deg=primary_eess_off_axis,
            target_dc_off_axis_deg=target_dc_off_axis,
            target_eess_off_axis_deg=target_eess_off_axis,
            eess_phi_min_deg=float(eess_phi_min_deg),
            eess_system=eess_system,
            outcome=outcome,
        ))

    active_beams_evaluated = int(np.count_nonzero(active_mask))
    handover_trigger_count = int(np.count_nonzero(triggered_mask))
    successful_handover_count = int(np.count_nonzero(successful_mask))
    unresolved_count = int(np.count_nonzero(unresolved_mask))
    metrics = {
        "active_beams_evaluated": active_beams_evaluated,
        "primary_main_main_count": handover_trigger_count,
        "handover_trigger_count": handover_trigger_count,
        "successful_handover_count": successful_handover_count,
        "unresolved_count": unresolved_count,
        "reassigned_fraction": (
            successful_handover_count / active_beams_evaluated
            if active_beams_evaluated else 0.0
        ),
        "unresolved_trigger_fraction": (
            unresolved_count / handover_trigger_count
            if handover_trigger_count else 0.0
        ),
    }

    return InterferenceAwareHandoverOutcome(
        serving_satellite_indices=final_satellite_indices,
        triggered_mask=triggered_mask,
        successful_mask=successful_mask,
        unresolved_mask=unresolved_mask,
        metrics=metrics,
        events=tuple(events),
    )

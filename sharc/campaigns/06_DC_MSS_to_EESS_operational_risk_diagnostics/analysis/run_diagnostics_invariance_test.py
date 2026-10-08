"""Run and compare the paired 200-snapshot diagnostics OFF/ON realizations."""

from __future__ import annotations

import asyncio  # Load stdlib logging dependencies before the legacy venv path.
import csv
import json
import logging
import random
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[4]
SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(SITE_PACKAGES))

import numpy as np
import pandas as pd

from sharc.parameters.parameters import Parameters
from sharc.simulation_downlink import SimulationDownlink
from sharc.support.sharc_logger import SimulationLogger


CAMPAIGN = Path(__file__).resolve().parents[1]
INPUT = CAMPAIGN / "input"
OFF = INPUT / "invariance_340km_EESS_B_LF0.5_GB10_DIAGNOSTICS_OFF.yaml"
ON = INPUT / "invariance_340km_EESS_B_LF0.5_GB10_DIAGNOSTICS_ON.yaml"


class TraceSimulationDownlink(SimulationDownlink):
    """Test-only observer around the unchanged V2 application point."""

    def _apply_interference_aware_handover_v2(
        self, link_powers, aggregate_linear_mw, tx_oob_dbm,
    ):
        active = np.flatnonzero(self.bs.active).astype(np.int64)
        serving = np.asarray(
            self.topology.serving_satellite_idx[active], dtype=np.int64).copy()
        beam_grid = np.asarray(
            self.topology.beam_grid_idx[active], dtype=np.int64).copy()
        before = float(aggregate_linear_mw)
        after = super()._apply_interference_aware_handover_v2(
            link_powers, aggregate_linear_mw, tx_oob_dbm)
        record = dict(self._v2_last_snapshot_record)
        accepted = [decision for decision in self.interference_aware_handover_v2_decisions
                    if decision.accepted]
        self._invariance_current = {
            "snapshot_id": int(self._v2_snapshot_id),
            "active_rows": active.tolist(),
            "serving_before": serving.tolist(),
            "beam_grid_before": beam_grid.tolist(),
            "iagg_before_linear_mw": before,
            "iagg_after_linear_mw": float(after),
            "iagg_before_dbw_per_mhz": record["iagg_before_dbw_per_mhz"],
            "iagg_after_dbw_per_mhz": record["iagg_after_dbw_per_mhz"],
            "critical_before": bool(record["critical_before"]),
            "critical_after": bool(record["critical_after"]),
            "gate_entered": bool(record["gate_entered"]),
            "handover_count": int(record["reassigned_beams"]),
            "accepted_beam_cells": [
                [int(d.beam_row_idx), int(self.topology.beam_grid_idx[d.beam_row_idx])]
                for d in accepted
            ],
            "targets": [int(d.selected_satellite_idx) for d in accepted],
        }
        return after


def load_parameters(path: Path) -> Parameters:
    parameters = Parameters()
    parameters.set_file_name(str(path))
    parameters.read_params()
    return parameters


def run(path: Path) -> list[dict]:
    parameters = load_parameters(path)
    SimulationLogger._global_output_dir = None
    simulation = TraceSimulationDownlink(parameters, str(path))
    simulation.initialize()
    generator = random.Random(parameters.general.seed)
    seeds = [generator.randint(1, 2**32 - 1)
             for _ in range(parameters.general.num_snapshots)]
    trace = []
    for snapshot_id, seed in enumerate(seeds, 1):
        simulation.snapshot(
            write_to_file=(snapshot_id % 10 == 0),
            snapshot_number=snapshot_id,
            seed=seed,
        )
        row = dict(simulation._invariance_current)
        row["secondary_seed"] = seed
        row["final_interference_dbm"] = float(
            np.asarray(simulation.system.rx_interference).reshape(-1)[0])
        trace.append(row)
    simulation.finalize(snapshot_number=parameters.general.num_snapshots)
    return trace


def compare(off: list[dict], on: list[dict]) -> pd.DataFrame:
    rows = []
    for left, right in zip(off, on, strict=True):
        active_equal = left["active_rows"] == right["active_rows"]
        serving_equal = left["serving_before"] == right["serving_before"]
        cells_equal = left["beam_grid_before"] == right["beam_grid_before"]
        decisions_equal = (
            left["handover_count"] == right["handover_count"]
            and left["accepted_beam_cells"] == right["accepted_beam_cells"])
        targets_equal = left["targets"] == right["targets"]
        rows.append({
            "snapshot_id": left["snapshot_id"],
            "secondary_seed_off": left["secondary_seed"],
            "secondary_seed_on": right["secondary_seed"],
            "active_beam_count_off": len(left["active_rows"]),
            "active_beam_count_on": len(right["active_rows"]),
            "active_beams_equal": active_equal,
            "serving_satellite_ids_before_equal": serving_equal,
            "beam_grid_ids_before_equal": cells_equal,
            "iagg_before_linear_off": left["iagg_before_linear_mw"],
            "iagg_before_linear_on": right["iagg_before_linear_mw"],
            "abs_diff_iagg_before_linear": abs(
                left["iagg_before_linear_mw"] - right["iagg_before_linear_mw"]),
            "iagg_after_linear_off": left["iagg_after_linear_mw"],
            "iagg_after_linear_on": right["iagg_after_linear_mw"],
            "abs_diff_iagg_after_linear": abs(
                left["iagg_after_linear_mw"] - right["iagg_after_linear_mw"]),
            "iagg_before_dbw_per_mhz_off": left["iagg_before_dbw_per_mhz"],
            "iagg_before_dbw_per_mhz_on": right["iagg_before_dbw_per_mhz"],
            "abs_diff_iagg_before_db": abs(
                left["iagg_before_dbw_per_mhz"]
                - right["iagg_before_dbw_per_mhz"]),
            "iagg_after_dbw_per_mhz_off": left["iagg_after_dbw_per_mhz"],
            "iagg_after_dbw_per_mhz_on": right["iagg_after_dbw_per_mhz"],
            "abs_diff_iagg_after_db": abs(
                left["iagg_after_dbw_per_mhz"]
                - right["iagg_after_dbw_per_mhz"]),
            "critical_before_equal": (
                left["critical_before"] == right["critical_before"]),
            "critical_after_equal": (
                left["critical_after"] == right["critical_after"]),
            "gate_flag_equal": left["gate_entered"] == right["gate_entered"],
            "handover_decisions_equal": decisions_equal,
            "targets_equal": targets_equal,
            "accepted_beam_cells_off": json.dumps(left["accepted_beam_cells"]),
            "accepted_beam_cells_on": json.dumps(right["accepted_beam_cells"]),
            "targets_off": json.dumps(left["targets"]),
            "targets_on": json.dumps(right["targets"]),
            "final_interference_dbm_off": left["final_interference_dbm"],
            "final_interference_dbm_on": right["final_interference_dbm"],
            "abs_diff_final_interference_db": abs(
                left["final_interference_dbm"]
                - right["final_interference_dbm"]),
        })
    return pd.DataFrame(rows)


def validate_reconstruction() -> dict:
    output = CAMPAIGN / "output" / "diagnostics_on"
    snapshot = pd.read_csv(output / "operational_risk_snapshot.csv")
    topk = pd.read_csv(output / "operational_risk_topk.csv")
    events_path = output / "operational_risk_handover_events.csv"
    events = pd.read_csv(events_path) if events_path.exists() else pd.DataFrame()
    required_snapshot = [
        "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
        "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
        "eess_latitude_deg", "eess_longitude_deg", "eess_altitude_m",
        "iagg_before_linear_mw", "critical_before_flag",
    ]
    required_topk = [
        "satellite_enu_x_m", "satellite_enu_y_m", "satellite_enu_z_m",
        "satellite_latitude_deg", "satellite_longitude_deg",
        "satellite_altitude_m", "service_cell_latitude_deg",
        "service_cell_longitude_deg", "tx_offaxis_to_eess_deg",
        "rx_offaxis_from_eess_boresight_deg", "tx_gain_toward_eess_dbi",
        "rx_gain_from_interferer_dbi", "joint_gain_suppression_db",
        "individual_i_linear_mw",
    ]
    if snapshot[required_snapshot].isna().any().any():
        raise AssertionError("Snapshot reconstruction fields contain NaN")
    if topk[required_topk].isna().any().any():
        raise AssertionError("Top-k reconstruction fields contain NaN")
    accepted = events[events["accepted"] == True] if not events.empty else events
    if not accepted.empty:
        required_event = [
            "current_satellite_enu_x_m", "current_satellite_enu_y_m",
            "current_satellite_enu_z_m", "target_satellite_enu_x_m",
            "target_satellite_enu_y_m", "target_satellite_enu_z_m",
            "current_tx_offaxis_deg", "target_tx_offaxis_deg",
            "current_rx_offaxis_deg", "target_rx_offaxis_deg",
        ]
        if accepted[required_event].isna().any().any():
            raise AssertionError("Accepted-event reconstruction fields contain NaN")
    return {
        "snapshot_rows": len(snapshot),
        "topk_rows": len(topk),
        "event_rows": len(events),
        "accepted_event_rows": len(accepted),
        "geometry_reconstructible": True,
    }


def main() -> None:
    off = run(OFF)
    on = run(ON)
    comparison = compare(off, on)
    comparison_path = CAMPAIGN / "analysis" / "diagnostics_invariance_test.csv"
    comparison.to_csv(comparison_path, index=False)
    reconstruction = validate_reconstruction()
    summary = {
        "max_abs_diff_Iagg_before": comparison[
            "abs_diff_iagg_before_linear"].max(),
        "max_abs_diff_Iagg_after": comparison[
            "abs_diff_iagg_after_linear"].max(),
        "max_abs_diff_Iagg_before_db": comparison[
            "abs_diff_iagg_before_db"].max(),
        "max_abs_diff_Iagg_after_db": comparison[
            "abs_diff_iagg_after_db"].max(),
        "number_of_changed_handover_decisions": int((
            ~comparison["handover_decisions_equal"]).sum()),
        "number_of_changed_targets": int((
            ~comparison["targets_equal"]).sum()),
        "number_of_changed_active_beams": int((
            ~comparison["active_beams_equal"]).sum()),
        "number_of_changed_serving_satellite_sets_before_v2": int((
            ~comparison["serving_satellite_ids_before_equal"]).sum()),
        "number_of_changed_final_interference_values": int((
            comparison["abs_diff_final_interference_db"] != 0.0).sum()),
        **reconstruction,
    }
    pd.DataFrame([summary]).to_csv(
        CAMPAIGN / "analysis" / "diagnostics_invariance_summary.csv",
        index=False,
    )
    print(json.dumps(summary, indent=2))
    if any(summary[key] != 0 for key in (
        "number_of_changed_handover_decisions", "number_of_changed_targets",
        "number_of_changed_active_beams",
        "number_of_changed_serving_satellite_sets_before_v2",
        "number_of_changed_final_interference_values",
    )):
        raise AssertionError("Operational diagnostics changed simulation state")


if __name__ == "__main__":
    main()

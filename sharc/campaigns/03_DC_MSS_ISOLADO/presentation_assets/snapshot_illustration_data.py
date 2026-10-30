"""Recover only the geometry/load draws of one existing snapshot, never its RF run."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = HERE.parent / "output" / "output_dc_mss_isolado_Sys3_340km_LF50_PBO10dB_F10pct_2026-07-28_02"
CACHE = HERE / "v4" / "snapshot_1_geometry.json"


def first_snapshot_rows():
    rows = []
    with (SOURCE / "imt_dl_selected_ue_metrics.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if int(row["snapshot_id"]) != 1:
                break
            rows.append(row)
    return rows


def read_counts(name, count):
    with (SOURCE / name).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return [int(next(reader)["samples"]) for _ in range(count)]


def reconstruct():
    sys.path.insert(0, str(ROOT))
    from sharc.parameters.parameters import Parameters
    from sharc.support.sharc_geom import CoordinateSystem
    from sharc.support.sharc_logger import SimulationLogger
    from sharc.topology.topology_factory import TopologyFactory
    from sharc.station_factory import StationFactory
    from sharc.simulation_downlink import SimulationDownlink

    assert SimulationLogger.get_output_dir() is None
    config = next(SOURCE.glob("*.yaml"))
    params = Parameters()
    params.set_file_name(str(config))
    params.read_params()
    coordinate_system = CoordinateSystem()
    coordinate_system.set_reference(params.imt.topology.central_latitude,
                                    params.imt.topology.central_longitude,
                                    params.imt.topology.central_altitude)
    topology = TopologyFactory.createTopology(params, coordinate_system)
    seed = random.Random(params.general.seed).randint(1, 2**32 - 1)
    rng = np.random.RandomState(seed)
    topology.calculate_coordinates(rng)
    bs = StationFactory.generate_imt_base_stations(
        params.imt, params.imt.bs.antenna.array, topology, rng)
    affected, realized = SimulationDownlink.select_active_beams_for_pbo(
        bs.active, params.imt.topology.mss_dc.power_control_zones.affected_fraction, seed)
    # Preserve the original RNG call order before sampling the UE locations.
    StationFactory.generate_system(params, topology, rng, coordinate_system=coordinate_system)
    ue = StationFactory.generate_imt_ue(params.imt, params.imt.ue.antenna.array, topology, rng)
    rows = first_snapshot_rows()
    active_ids = np.array([int(row["beam_id"]) for row in rows])
    affected_ids = np.array([int(row["beam_id"]) for row in rows
                             if row["beam_affected_by_pbo"] == "True"])
    assert params.imt.ue.k == params.imt.ue.k_m == 1
    assert np.array_equal(np.flatnonzero(bs.active), active_ids), "Activity no longer reproduces the saved snapshot"
    assert np.array_equal(np.flatnonzero(affected), affected_ids), "PBO mask does not match saved data"
    assert all(int(row["ue_id"]) == int(row["beam_id"]) for row in rows)
    sat_count = read_counts("num_of_sat.csv", 1)[0]
    beam_counts = read_counts("num_of_beams_per_sat.csv", sat_count)
    assert sum(beam_counts) == topology.num_base_stations
    sat_ids, counts = np.unique(topology.serving_satellite_idx, return_counts=True)
    assert len(sat_ids) == sat_count
    assert sorted(counts.tolist()) == sorted(beam_counts)
    assert read_counts("num_of_active_beams.csv", 1)[0] == len(rows)
    candidate_count = read_counts("num_of_candidate_sats.csv", 1)[0]

    def ecef(obj):
        return np.column_stack(coordinate_system.enu2ecef(
            obj.x_global, obj.y_global, obj.z_global))

    state = {
        "source_folder": str(SOURCE), "source_config": str(config),
        "snapshot_id": 1, "seed": seed, "load_probability": params.imt.bs.load_probability,
        "pbo_db": params.imt.topology.mss_dc.power_control_zones.power_backoff_db,
        "requested_fraction": 0.1, "realized_fraction": realized,
        "total_constellation_satellites": sum(o.n_planes * o.sats_per_plane for o in params.imt.topology.mss_dc.orbits),
        "eligible_satellites": candidate_count, "associated_satellites": sat_count,
        "cells": int(topology.num_base_stations), "ues_generated": int(ue.num_stations),
        "active_beams": int(bs.active.sum()), "pbo_beams": int(affected.sum()),
        "beam_radius_m": params.imt.topology.mss_dc.beam_radius,
        "active": bs.active.tolist(), "affected": affected.tolist(),
        "serving_satellite_ids": topology.serving_satellite_idx.tolist(),
        "grid_ecef_m": topology.beam_grid_center_ecef.tolist(),
        "ue_ecef_m": ecef(ue.geom).tolist(),
        "satellite_ecef_m_per_beam": ecef(bs.geom).tolist(),
        "ue_metrics": rows,
        "checks": {"active_ids_match_saved_csv": True, "pbo_ids_match_saved_csv": True,
                   "satellite_beam_counts_match_saved_logs": True,
                   "no_rf_calculation": True, "no_simulation_output_writes": True},
    }
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def load_snapshot():
    state = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else reconstruct()
    ids = np.array([int(row["ue_id"]) for row in state["ue_metrics"]])
    ue = np.asarray(state["ue_ecef_m"])
    sat = np.asarray(state["satellite_ecef_m_per_beam"])
    cell = np.asarray(state["grid_ecef_m"])
    distance = np.linalg.norm(sat[ids] - ue[ids], axis=1)
    expected_fspl = 20 * np.log10(distance) + 20 * np.log10(2155.0) - 27.55
    with (SOURCE / "imt_path_loss.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        observed = np.array([float(next(reader)["samples"]) for _ in ids])
    error = float(np.max(np.abs(expected_fspl - observed)))
    assert error < 1e-8, f"Reconstructed UE geometry does not match saved path losses: {error}"
    state["checks"]["saved_pathloss_max_difference_db"] = error
    state["geometry_caution"] = {
        "ue_to_assigned_grid_center_distance_km_p0_p50_p100":
            np.percentile(np.linalg.norm(ue-cell, axis=1)/1000, [0, 50, 100]).tolist(),
        "actual_ue_locations_not_inside_assigned_grid_cells": True,
        "reason": "SERVICE_GRID returns sectors_x=sectors_y=0; UNIFORM_IN_CELL uses those anchors",
    }
    CACHE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    state = load_snapshot()
    print(json.dumps({k: v for k, v in state.items() if not isinstance(v, list)}, indent=2))

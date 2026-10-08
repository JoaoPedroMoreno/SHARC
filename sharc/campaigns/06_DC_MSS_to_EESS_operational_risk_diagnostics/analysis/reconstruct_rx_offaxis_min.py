"""Reconstruct the minimum EESS RX off-axis angle without interference data.

The reconstruction replays only ``topology.calculate_coordinates()`` from the
saved YAML and snapshot ``secondary_seed``.  It uses the realized EESS position
and pointing already stored in ``operational_risk_snapshot.csv`` and calls the
same ``GlobalGeometry.get_off_axis_angle()`` routine used by SHARC.

No propagation, antenna gain, spectral mask, I_link, I_agg, or Monte Carlo
snapshot is evaluated.  Existing campaign CSV files are read-only.
"""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd


CAMPAIGN = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
OUTPUT = CAMPAIGN / "output"
ANALYSIS = CAMPAIGN / "analysis"
DESTINATION = ANALYSIS / "operational_risk_rx_min.csv"
VALIDATION = ANALYSIS / "operational_risk_rx_min_validation.json"

RUN_PATTERN = re.compile(
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(10|60|65|70|75|80)MHz_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)


@dataclass(frozen=True)
class GeometrySource:
    altitude_km: int
    directory: Path
    yaml_path: Path
    snapshot_path: Path
    topk_path: Path


def count_rows(path: Path) -> int:
    with path.open("rb") as stream:
        return max(sum(1 for _ in stream) - 1, 0)


def geometry_sources() -> list[GeometrySource]:
    """Choose one complete canonical GB=10 run per altitude."""
    selected: dict[int, tuple[tuple[str, int], Path]] = {}
    for directory in OUTPUT.iterdir():
        match = RUN_PATTERN.fullmatch(directory.name) if directory.is_dir() else None
        if not match:
            continue
        altitude, eess, load, gb = (
            int(match[1]), match[2], float(match[3]), int(match[4])
        )
        if eess != "B" or load != 0.2 or gb != 10:
            continue
        snapshot = directory / "operational_risk_snapshot.csv"
        topk = directory / "operational_risk_topk.csv"
        if not snapshot.is_file() or not topk.is_file():
            continue
        if count_rows(snapshot) != 5000 or count_rows(topk) != 15000:
            continue
        stamp = (match[5], int(match[6]))
        if altitude not in selected or stamp > selected[altitude][0]:
            selected[altitude] = (stamp, directory)
    if set(selected) != {340, 525}:
        raise RuntimeError(f"Expected canonical sources for 340/525 km, got {selected}")

    result = []
    for altitude, (_, directory) in sorted(selected.items()):
        yamls = sorted(directory.glob("*.yaml"))
        if len(yamls) != 1:
            raise RuntimeError(f"Expected one YAML in {directory}, found {len(yamls)}")
        result.append(GeometrySource(
            altitude_km=altitude,
            directory=directory,
            yaml_path=yamls[0],
            snapshot_path=directory / "operational_risk_snapshot.csv",
            topk_path=directory / "operational_risk_topk.csv",
        ))
    return result


def load_tasks(source: GeometrySource) -> list[dict]:
    columns = [
        "snapshot_id", "secondary_seed",
        "eess_enu_x_m", "eess_enu_y_m", "eess_enu_z_m",
        "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
    ]
    frame = pd.read_csv(source.snapshot_path, usecols=columns)
    if len(frame) != 5000 or frame.secondary_seed.nunique() != 5000:
        raise RuntimeError(f"Unexpected snapshot/seed count in {source.snapshot_path}")
    frame["altitude_km"] = source.altitude_km
    return frame.to_dict("records")


def load_validation(source: GeometrySource) -> dict[int, list[dict]]:
    columns = [
        "snapshot_id", "serving_satellite_idx",
        "satellite_enu_x_m", "satellite_enu_y_m", "satellite_enu_z_m",
        "rx_offaxis_from_eess_boresight_deg",
    ]
    frame = pd.read_csv(source.topk_path, usecols=columns)
    return {
        int(snapshot): group.to_dict("records")
        for snapshot, group in frame.groupby("snapshot_id", sort=False)
    }


def chunks(values: list[dict], size: int) -> list[list[dict]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def reconstruct_chunk(
    yaml_path: str,
    tasks: list[dict],
    validation_rows: dict[int, list[dict]],
) -> tuple[list[dict], dict]:
    """Worker function; one SHARC topology instance is reused per chunk."""
    # Imports stay inside the worker to support Windows spawn safely.
    from sharc.parameters.parameters import Parameters
    from sharc.simulation_downlink import SimulationDownlink
    from sharc.support.geometry import SimulatorGeometry
    from sharc.support.sharc_logger import SimulationLogger

    # Topology contains optional analysis logging.  Disable only those writes;
    # this does not participate in geometry or RNG state.
    SimulationLogger.log_to_csv = staticmethod(lambda *args, **kwargs: None)

    parameters = Parameters()
    parameters.set_file_name(yaml_path)
    parameters.read_params()
    simulation = SimulationDownlink(parameters, yaml_path)

    records = []
    max_position_error_m = 0.0
    max_angle_error_deg = 0.0
    validated_links = 0
    active_candidate_mismatches = 0

    # Capture the pre-SERVICE_GRID active/visible IDs to validate that the
    # persisted candidate population is the requested population.
    topology_class = type(simulation.topology)
    original_pointing = topology_class.get_satellite_pointing
    captured: dict[str, np.ndarray] = {}

    def capture_pointing(*args, **kwargs):
        captured["active_ids"] = np.asarray(args[-1], dtype=int).copy()
        return original_pointing(*args, **kwargs)

    topology_class.get_satellite_pointing = staticmethod(capture_pointing)
    try:
        for task in tasks:
            seed = int(task["secondary_seed"])
            simulation.topology.calculate_coordinates(np.random.RandomState(seed))
            state = simulation.topology._service_grid_snapshot
            satellite_ids = np.asarray(
                state["candidate_satellite_indices"], dtype=int
            )
            satellite_positions = np.asarray(
                state["candidate_positions_enu"], dtype=float
            )
            active_ids = captured.get("active_ids", np.empty(0, dtype=int))
            if not np.array_equal(active_ids, satellite_ids):
                active_candidate_mismatches += 1

            eess = SimulatorGeometry(1)
            eess.set_global_coords(
                x=np.array([float(task["eess_enu_x_m"])]),
                y=np.array([float(task["eess_enu_y_m"])]),
                z=np.array([float(task["eess_enu_z_m"])]),
                azim=np.array([float(task["eess_pointing_azimuth_deg"])]),
                elev=np.array([float(task["eess_pointing_elevation_deg"])]),
            )
            satellites = SimulatorGeometry(len(satellite_ids))
            satellites.set_global_coords(
                x=satellite_positions[:, 0],
                y=satellite_positions[:, 1],
                z=satellite_positions[:, 2],
                # Pointing of the destination geometry is irrelevant when
                # EESS is the receiver/self in get_off_axis_angle().
                azim=np.zeros(len(satellite_ids)),
                elev=np.zeros(len(satellite_ids)),
            )
            psi_rx = eess.get_off_axis_angle(satellites)[0]
            order = np.argsort(psi_rx, kind="stable")[:3]
            if len(order) < 3:
                raise RuntimeError("Fewer than three active/visible satellites")

            snapshot_id = int(task["snapshot_id"])
            for expected in validation_rows.get(snapshot_id, []):
                matches = np.flatnonzero(
                    satellite_ids == int(expected["serving_satellite_idx"])
                )
                if matches.size != 1:
                    raise RuntimeError(
                        "Stored top-K satellite is absent or duplicated in replay: "
                        f"snapshot={snapshot_id}, satellite="
                        f"{expected['serving_satellite_idx']}"
                    )
                column = int(matches[0])
                expected_position = np.array([
                    expected["satellite_enu_x_m"],
                    expected["satellite_enu_y_m"],
                    expected["satellite_enu_z_m"],
                ], dtype=float)
                max_position_error_m = max(
                    max_position_error_m,
                    float(np.max(np.abs(
                        satellite_positions[column] - expected_position
                    ))),
                )
                max_angle_error_deg = max(
                    max_angle_error_deg,
                    abs(float(psi_rx[column]) - float(
                        expected["rx_offaxis_from_eess_boresight_deg"]
                    )),
                )
                validated_links += 1

            records.append({
                "altitude_km": int(task["altitude_km"]),
                "snapshot_id": snapshot_id,
                "secondary_seed": seed,
                "eess_enu_x_m": float(task["eess_enu_x_m"]),
                "eess_enu_y_m": float(task["eess_enu_y_m"]),
                "eess_enu_z_m": float(task["eess_enu_z_m"]),
                "eess_pointing_azimuth_deg": float(
                    task["eess_pointing_azimuth_deg"]
                ),
                "eess_pointing_elevation_deg": float(
                    task["eess_pointing_elevation_deg"]
                ),
                "rx_visible_satellite_count": int(len(satellite_ids)),
                "rx_offaxis_min_satellite_idx": int(satellite_ids[order[0]]),
                "rx_offaxis_min_deg": float(psi_rx[order[0]]),
                "rx_offaxis_rank1_satellite_idx": int(satellite_ids[order[0]]),
                "rx_offaxis_rank1_deg": float(psi_rx[order[0]]),
                "rx_offaxis_rank2_satellite_idx": int(satellite_ids[order[1]]),
                "rx_offaxis_rank2_deg": float(psi_rx[order[1]]),
                "rx_offaxis_rank3_satellite_idx": int(satellite_ids[order[2]]),
                "rx_offaxis_rank3_deg": float(psi_rx[order[2]]),
            })
    finally:
        topology_class.get_satellite_pointing = staticmethod(original_pointing)

    return records, {
        "max_position_error_m": max_position_error_m,
        "max_angle_error_deg": max_angle_error_deg,
        "validated_links": validated_links,
        "active_candidate_mismatches": active_candidate_mismatches,
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unavailable"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workers", type=int,
        default=max(1, min(6, (os.cpu_count() or 2) - 1)),
    )
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()
    sources = geometry_sources()
    jobs = []
    source_manifest = []
    for source in sources:
        tasks = load_tasks(source)
        validation = load_validation(source)
        for task_chunk in chunks(tasks, args.chunk_size):
            chunk_validation = {
                int(task["snapshot_id"]): validation[int(task["snapshot_id"])]
                for task in task_chunk
            }
            jobs.append((str(source.yaml_path), task_chunk, chunk_validation))
        source_manifest.append({
            "altitude_km": source.altitude_km,
            "yaml": str(source.yaml_path.resolve()),
            "snapshot_csv": str(source.snapshot_path.resolve()),
            "topk_validation_csv": str(source.topk_path.resolve()),
        })

    started = time.perf_counter()
    all_records = []
    validations = []
    completed_snapshots = 0
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(reconstruct_chunk, *job) for job in jobs]
        for future in as_completed(futures):
            records, validation = future.result()
            all_records.extend(records)
            validations.append(validation)
            completed_snapshots += len(records)
            elapsed = time.perf_counter() - started
            print(
                f"Reconstructed {completed_snapshots}/10000 geometries "
                f"({elapsed / 60.0:.1f} min)",
                flush=True,
            )

    frame = pd.DataFrame(all_records).sort_values(
        ["altitude_km", "snapshot_id"], kind="stable"
    )
    if len(frame) != 10000:
        raise RuntimeError(f"Expected 10000 unique geometries, got {len(frame)}")
    if frame.duplicated(["altitude_km", "secondary_seed"]).any():
        raise RuntimeError("Duplicate geometry cache keys")

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    frame.to_csv(DESTINATION, index=False)
    summary = {
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "git_commit": git_commit(),
        "analysis_script_sha256": file_sha256(Path(__file__)),
        "output_sha256": file_sha256(DESTINATION),
        "unique_geometries": len(frame),
        "altitudes_km": sorted(frame.altitude_km.unique().tolist()),
        "workers": args.workers,
        "chunk_size": args.chunk_size,
        "elapsed_seconds": time.perf_counter() - started,
        "validated_topk_links": sum(v["validated_links"] for v in validations),
        "max_position_error_m": max(v["max_position_error_m"] for v in validations),
        "max_angle_error_deg": max(v["max_angle_error_deg"] for v in validations),
        "active_candidate_mismatches": sum(
            v["active_candidate_mismatches"] for v in validations
        ),
        "propagation_calls": 0,
        "interference_values_used": False,
        "geometry_method": "GlobalGeometry.get_off_axis_angle",
        "population": (
            "candidate_satellite_indices: active/visible satellites intersected "
            "with SERVICE_GRID eligibility"
        ),
        "sources": source_manifest,
    }
    VALIDATION.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

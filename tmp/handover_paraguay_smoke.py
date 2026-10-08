"""Temporary multi-snapshot smoke test for Paraguay handover.

This script never edits campaign YAML files. It loads one original campaign,
overrides only runtime/output/handover controls in memory, and copies the
historical 2117 MHz P.619 lookup table under tmp for this diagnostic run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(VENV_SITE_PACKAGES))

from sharc.parameters.parameters import Parameters
from sharc.simulation_downlink import SimulationDownlink
from sharc.support.sharc_logger import SimulationLogger


SOURCE = (
    REPO
    / "sharc"
    / "campaigns"
    / "04_DC_MSS_to_EESS"
    / "input"
    / "system_340km_EESS_D_SA_P_Spu_OM_0_lf_0.5.yaml"
)
DC_LIMIT_DEG = 4.322755
MIN_SNAPSHOTS = 10
MAX_SNAPSHOTS = 10
TARGET_TRIGGER_COUNT = 2
LOOKUP_SOURCE = (
    REPO / "sharc" / "propagation" / "Dataset" / "FOZ_2117_200m.csv"
)
EXPECTED_LOOKUP_GIT_BLOB = "88c97d4b2688f20eafee08ce7d14911906b0476c"


def build_lookup_table(output_path: Path) -> None:
    """Copy the exact restored historical FOZ_2117 table into tmp."""
    shutil.copyfile(LOOKUP_SOURCE, output_path)


def git_blob_hash(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def load_parameters(enabled: bool, output_dir: Path) -> Parameters:
    params = Parameters()
    params.set_file_name(str(SOURCE))
    params.read_params()

    # Runtime/output controls only. All physical and spectral values remain
    # exactly as loaded from SOURCE.
    params.general.num_snapshots = MAX_SNAPSHOTS
    params.general.overwrite_output = True
    params.general.output_dir = str(output_dir)
    params.general.output_dir_prefix = output_dir.name

    config = params.imt.topology.mss_dc.interference_aware_handover
    config.enabled = enabled
    config.dc_mss_off_axis_limit_deg = DC_LIMIT_DEG
    config.eess_boundary = "S465_MAX_GAIN_REGION"
    config.unresolved_policy = "KEEP_PRIMARY_AND_FLAG"
    config.record_event_details = enabled
    params.single_earth_station.system_label = "EESS_D"
    config.validate("smoke.interference_aware_handover")
    return params


def exact_seed_sequence(count: int) -> list[int]:
    generator = random.Random(157)
    return [generator.randint(1, 2**32 - 1) for _ in range(count)]


def snapshot_record(simulation: SimulationDownlink, snapshot_id: int) -> dict:
    topology = simulation.topology
    outcome = simulation.interference_aware_handover_outcome
    events = [] if outcome is None else [event.as_dict() for event in outcome.events]
    metrics = None if outcome is None else dict(outcome.metrics)
    links = {
        int(key): np.asarray(value, dtype=int).copy()
        for key, value in simulation.link.items()
    }
    tx_power = simulation.bs.tx_power
    if isinstance(tx_power, dict):
        tx_power = np.concatenate([
            np.asarray(tx_power[key], dtype=float)
            for key in sorted(tx_power)
        ])
    return {
        "snapshot_id": snapshot_id,
        "active": simulation.bs.active.copy(),
        "active_count": int(np.count_nonzero(simulation.bs.active)),
        "beam_grid_idx": topology.beam_grid_idx.copy(),
        "beam_grid_center_enu": topology.beam_grid_center_enu.copy(),
        "primary": topology.primary_satellite_idx.copy(),
        "serving": topology.serving_satellite_idx.copy(),
        "power_backoff": topology.power_backoff.copy(),
        "bs_tx_power": np.asarray(tx_power, dtype=float).copy(),
        "bs_frequency": np.asarray(simulation.bs.center_freq).copy(),
        "bs_bandwidth": np.asarray(simulation.bs.bandwidth).copy(),
        "bs_xyz": np.column_stack((
            simulation.bs.geom.x_global,
            simulation.bs.geom.y_global,
            simulation.bs.geom.z_global,
        )),
        "bs_pointing": np.column_stack((
            simulation.bs.geom.pointn_azim_global,
            simulation.bs.geom.pointn_elev_global,
        )),
        "ue_indoor": simulation.ue.indoor.copy(),
        "ue_active": simulation.ue.active.copy(),
        "links": links,
        "eess_position": np.array([
            simulation.system.geom.x_global[0],
            simulation.system.geom.y_global[0],
            simulation.system.geom.z_global[0],
        ]),
        "eess_pointing": np.array([
            simulation.system.geom.pointn_azim_global[0],
            simulation.system.geom.pointn_elev_global[0],
        ]),
        "system_inr": np.asarray(simulation.system.inr).copy(),
        "metrics": metrics,
        "events": events,
    }


def run_mode(enabled: bool, output_dir: Path, lookup_path: Path,
             seeds: list[int], stop_on_triggers: bool) -> tuple[SimulationDownlink, list[dict]]:
    params = load_parameters(enabled, output_dir)
    # Avoid cross-run contamination from the logger's process-global path.
    SimulationLogger._global_output_dir = None
    simulation = SimulationDownlink(params, str(SOURCE))
    simulation.initialize()

    propagation = simulation.propagation_system
    propagation._get_lookup_table_file = lambda _frequency: str(lookup_path)

    records = []
    cumulative_triggers = 0
    for index, seed in enumerate(seeds, start=1):
        print(
            f"{'ON' if enabled else 'OFF'} snapshot {index}/{len(seeds)} "
            f"seed={seed}",
            flush=True,
        )
        simulation.snapshot(
            write_to_file=False,
            snapshot_number=index,
            seed=seed,
        )
        record = snapshot_record(simulation, index)
        records.append(record)
        if record["metrics"] is not None:
            cumulative_triggers += record["metrics"]["handover_trigger_count"]
        if (
            stop_on_triggers
            and index >= MIN_SNAPSHOTS
            and cumulative_triggers >= TARGET_TRIGGER_COUNT
        ):
            break

    simulation.results.write_files(len(records))
    return simulation, records


def assert_array_exact(left, right, label: str, snapshot_id: int) -> None:
    if not np.array_equal(left, right, equal_nan=True):
        raise AssertionError(f"{label} differs at snapshot {snapshot_id}")


def assert_rng_observables_equal(off_records: list[dict],
                                 on_records: list[dict]) -> None:
    if len(off_records) != len(on_records):
        raise AssertionError("OFF/ON snapshot counts differ")
    for off, on in zip(off_records, on_records):
        snapshot_id = off["snapshot_id"]
        for key in [
            "active",
            "beam_grid_idx",
            "beam_grid_center_enu",
            "primary",
            "power_backoff",
            "bs_tx_power",
            "bs_frequency",
            "bs_bandwidth",
            "ue_indoor",
            "ue_active",
            "eess_position",
            "eess_pointing",
        ]:
            assert_array_exact(off[key], on[key], key, snapshot_id)
        if off["links"].keys() != on["links"].keys():
            raise AssertionError(f"link keys differ at snapshot {snapshot_id}")
        for beam_id in off["links"]:
            assert_array_exact(
                off["links"][beam_id],
                on["links"][beam_id],
                f"link[{beam_id}]",
                snapshot_id,
            )


def validate_finiteness(records: list[dict]) -> dict:
    unexpected_nonfinite = []
    expected_unresolved_nan = 0
    for record in records:
        snapshot_id = record["snapshot_id"]
        for key in [
            "beam_grid_center_enu",
            "power_backoff",
            "bs_tx_power",
            "bs_frequency",
            "bs_bandwidth",
            "bs_xyz",
            "bs_pointing",
            "eess_position",
            "eess_pointing",
            "system_inr",
        ]:
            values = np.asarray(record[key], dtype=float)
            if not np.all(np.isfinite(values)):
                unexpected_nonfinite.append((snapshot_id, key))
        metrics = record["metrics"]
        if metrics is not None and not all(
            math.isfinite(float(value)) for value in metrics.values()
        ):
            unexpected_nonfinite.append((snapshot_id, "metrics"))
        for event in record["events"]:
            primary_fields = [
                "primary_elevation_deg",
                "primary_dc_off_axis_deg",
                "primary_eess_off_axis_deg",
                "eess_phi_min_deg",
            ]
            if not all(math.isfinite(float(event[field])) for field in primary_fields):
                unexpected_nonfinite.append((snapshot_id, "event_primary"))
            target_fields = [
                "target_elevation_deg",
                "delta_elevation_deg",
                "target_dc_off_axis_deg",
                "target_eess_off_axis_deg",
            ]
            target_finite = [math.isfinite(float(event[field])) for field in target_fields]
            if event["outcome"] == "HANDOVER":
                if not all(target_finite):
                    unexpected_nonfinite.append((snapshot_id, "event_handover"))
            else:
                expected_unresolved_nan += sum(not value for value in target_finite)
                if any(target_finite):
                    unexpected_nonfinite.append((snapshot_id, "event_unresolved"))
    if unexpected_nonfinite:
        raise AssertionError(f"Unexpected non-finite values: {unexpected_nonfinite}")
    return {"expected_unresolved_nan_fields": expected_unresolved_nan}


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def validate_csvs(output_dir: Path, records: list[dict]) -> dict:
    metrics_path = output_dir / "interference_aware_handover_snapshot_metrics.csv"
    events_path = output_dir / "interference_aware_handover_events.csv"
    metrics_rows = read_csv_rows(metrics_path)
    events_rows = read_csv_rows(events_path) if events_path.exists() else []
    if len(metrics_rows) != len(records):
        raise AssertionError("Snapshot metrics CSV row count mismatch")
    expected_events = sum(len(record["events"]) for record in records)
    if len(events_rows) != expected_events:
        raise AssertionError("Event CSV row count mismatch")
    for row in metrics_rows:
        for key, value in row.items():
            if key == "snapshot_id":
                continue
            if not math.isfinite(float(value)):
                raise AssertionError(f"Non-finite metric CSV value: {key}={value}")
    outcomes = {}
    for row in events_rows:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
        if row["beam_grid_idx"] == "":
            raise AssertionError("Missing beam_grid_idx in event CSV")
    return {
        "metrics_csv": str(metrics_path),
        "metrics_rows": len(metrics_rows),
        "events_csv": str(events_path),
        "event_rows": len(events_rows),
        "event_outcomes": outcomes,
    }


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = REPO / "tmp" / f"handover_paraguay_smoke_{stamp}"
    off_dir = run_root / "off"
    on_dir = run_root / "on"
    off_dir.mkdir(parents=True)
    on_dir.mkdir(parents=True)
    lookup_path = run_root / "FOZ_2117_200m.csv"
    build_lookup_table(lookup_path)
    source_lookup_blob = git_blob_hash(LOOKUP_SOURCE)
    copied_lookup_blob = git_blob_hash(lookup_path)
    if source_lookup_blob != EXPECTED_LOOKUP_GIT_BLOB:
        raise AssertionError(
            f"Unexpected source lookup blob: {source_lookup_blob}"
        )
    if copied_lookup_blob != source_lookup_blob:
        raise AssertionError("Temporary lookup copy differs from source")

    seeds = exact_seed_sequence(MAX_SNAPSHOTS)
    _, on_records = run_mode(
        True, on_dir, lookup_path, seeds, stop_on_triggers=True)
    used_seeds = seeds[:len(on_records)]
    _, off_records = run_mode(
        False, off_dir, lookup_path, used_seeds, stop_on_triggers=False)

    assert_rng_observables_equal(off_records, on_records)
    finite_summary = validate_finiteness(on_records)
    csv_summary = validate_csvs(on_dir, on_records)

    trigger_count = sum(
        record["metrics"]["handover_trigger_count"] for record in on_records)
    handover_count = sum(
        record["metrics"]["successful_handover_count"] for record in on_records)
    unresolved_count = sum(
        record["metrics"]["unresolved_count"] for record in on_records)
    changed_rows = sum(
        int(np.count_nonzero(record["serving"] != record["primary"]))
        for record in on_records
    )
    unique_cells_ok = all(
        len(np.unique(record["beam_grid_idx"])) == len(record["beam_grid_idx"])
        for record in on_records
    )
    event_grid_indices_valid = all(
        int(event["beam_grid_idx"]) in set(record["beam_grid_idx"].tolist())
        for record in on_records
        for event in record["events"]
    )

    if changed_rows != handover_count:
        raise AssertionError("Changed serving rows do not match successful handovers")
    if not unique_cells_ok or not event_grid_indices_valid:
        raise AssertionError("beam_grid_idx identity validation failed")

    summary = {
        "source_yaml": str(SOURCE),
        "run_root": str(run_root),
        "lookup_table": str(lookup_path),
        "lookup_table_source": str(LOOKUP_SOURCE),
        "lookup_table_source_git_blob": source_lookup_blob,
        "lookup_table_copy_git_blob": copied_lookup_blob,
        "configured_propagation_frequency_mhz": 2117.5,
        "snapshots": len(on_records),
        "seeds": used_seeds,
        "active_counts": [record["active_count"] for record in on_records],
        "trigger_count": trigger_count,
        "successful_handover_count": handover_count,
        "unresolved_count": unresolved_count,
        "changed_rows": changed_rows,
        "unique_beam_grid_idx_per_snapshot": unique_cells_ok,
        "event_grid_indices_valid": event_grid_indices_valid,
        "rng_observables_off_on_exact": True,
        "natural_trigger_observation": (
            "observed" if trigger_count else "none_in_smoke_window"
        ),
        "physical_spectral_values_loaded_unchanged": {
            "imt_frequency_mhz": 2117.5,
            "imt_bandwidth_mhz": 5.0,
            "eess_frequency_mhz": 2203.0,
            "eess_bandwidth_mhz": 6.0,
            "load_probability": 0.5,
        },
        "nonfinite": finite_summary,
        "csv": csv_summary,
    }
    summary_path = run_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

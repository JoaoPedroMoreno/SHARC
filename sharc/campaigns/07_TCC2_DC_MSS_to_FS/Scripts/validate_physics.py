"""Small real-physics audit, not a campaign run. Writes only a fresh test folder."""
import argparse
import csv
import gc
import gzip
import json
from contextlib import ExitStack
from itertools import zip_longest
from time import perf_counter
from pathlib import Path
from unittest.mock import patch

import numpy as np

from generate import CAMPAIGN, HANDOVER_LIMIT, HANDOVER_MODE, ROOT, build, load, name
import yaml
from sharc.cochannel_handover import CochannelHandover, xyz
from sharc.simulation_downlink import SimulationDownlink
from sharc.support.sharc_logger import SimulationLogger

# Tiny angle rounding is amplified near deep Taylor-pattern nulls. Service
# SINR and victim INR are checked separately, much more tightly.
LINK_TOLERANCE_DB = 1e-6
SINR_TOLERANCE_DB = 1e-10


def validate_comparison_report(report):
    assert len(report) == 6
    assert all(r["exact_csv_equality_except_ue_performance"] and r["rng_equal"] for r in report)
    # Later snapshots may already be protected; count changes across the run.
    assert any(r["compared_rows"]["steps"] > r["snapshots"] for r in report), "Audit must exercise accepted handovers"


def compare_victim_only(output):
    """Compare two sequential snapshots per profile, without production outputs."""
    output.mkdir(parents=True)
    profiles = [(340, 20, .2, "BASELINE"), (340, 40, .5, HANDOVER_MODE),
                (340, 20, .5, "PBO100km"), (525, 40, .2, "BASELINE"),
                (525, 20, .5, HANDOVER_MODE), (525, 40, .5, "PBO100km")]
    performance_fields = {
        "ue_performance_calculated", "initial_performance_sha256", "served", "sinr_outage",
        "service_lost", "sinr_db", "snr_db", "rx_power_dbm", "interference_dbm",
        "desired_tx_gain_dbi", "desired_rx_gain_dbi", "desired_path_loss_db",
        "desired_coupling_loss_db", "noise_dbm", "served_users", "lost_users", "sinr_outage_users"}
    report = []
    for altitude, height, lf, mode in profiles:
        case = name(altitude, height, lf, mode)
        runs = {}
        for disabled in (False, True):
            label = "victim_only" if disabled else "full"
            folder = output / case / label
            folder.mkdir(parents=True)
            cfg = build(altitude, height, lf, mode)
            cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]["record_detailed_links_and_users"] = True
            cfg["imt"]["imt_dl_intra_sinr_calculation_disabled"] = disabled
            cfg["general"].update(num_snapshots=2, output_dir=str(folder), overwrite_output=True)
            source = folder / "input.yaml"
            source.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            params = load(source)
            with patch.object(SimulationLogger, "_global_output_dir", None):
                sim = SimulationDownlink(params, str(source))
                sim.initialize()
                started = perf_counter()
                with ExitStack() as stack:
                    if disabled:
                        for method in ("calculate_intra_imt_coupling_loss", "calculate_sinr"):
                            stack.enter_context(patch.object(sim, method, side_effect=AssertionError(
                                "Victim-only mode must not calculate UE performance")))
                    for number, seed in enumerate((2182114437, 293847123), 1):
                        sim.snapshot(write_to_file=number == 2, snapshot_number=number, seed=seed)
                elapsed = perf_counter() - started
                rng = sim.propagation_system.random_number_gen.get_state()
                runs[label] = dict(folder=Path(sim.results.output_directory), seconds=elapsed,
                                   rng=(rng[0], rng[1].tolist(), *rng[2:]),
                                   last=dict(sim.tcc2_last_snapshot))
                if disabled:
                    assert not sim.results.imt_dl_sinr
                    assert not sim.results.imt_dl_tput
                    assert not sim.results.imt_dl_selected_ue_metrics
                del sim
                gc.collect()
        assert runs["full"]["rng"] == runs["victim_only"]["rng"], case
        counts = {}
        for dataset in ("snapshots", "steps", "users", "links", "events", "candidates"):
            files = [runs[label]["folder"] / f"tcc2_{dataset}.csv.gz" for label in runs]
            assert files[0].exists() == files[1].exists(), (case, dataset)
            if not files[0].exists():
                continue
            # Noise is still evaluated for the FS; only UE noise is omitted.
            excluded = performance_fields - ({"noise_dbm"} if dataset != "users" else set())
            count = 0
            with gzip.open(files[0], "rt", newline="") as a, gzip.open(files[1], "rt", newline="") as b:
                for left, right in zip_longest(csv.DictReader(a), csv.DictReader(b)):
                    assert left is not None and right is not None, (case, dataset, count)
                    assert {k: v for k, v in left.items() if k not in excluded} == {
                        k: v for k, v in right.items() if k not in excluded}, (case, dataset, count)
                    if dataset == "users":
                        assert right["ue_performance_calculated"] == "False"
                        assert right["served"] == right["sinr_outage"] == right["service_lost"] == ""
                        assert np.isnan(float(right["sinr_db"]))
                    if dataset == "steps":
                        assert right["served_users"] == right["lost_users"] == right["sinr_outage_users"] == ""
                    count += 1
            counts[dataset] = count
        result = dict(case=case, snapshots=2, exact_csv_equality_except_ue_performance=True,
                      rng_equal=True, compared_rows=counts,
                      full_seconds=runs["full"]["seconds"], victim_only_seconds=runs["victim_only"]["seconds"],
                      speedup=runs["full"]["seconds"] / runs["victim_only"]["seconds"],
                      last_snapshot=runs["victim_only"]["last"])
        report.append(result)
        (output / "victim_only_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    validate_comparison_report(report)


def compare_recording(output):
    """Verify export-only changes with paired real snapshots, outside the campaign."""
    output.mkdir(parents=True)
    report = []
    profiles = [(340, 20, .2, "BASELINE"), (340, 40, .5, "HO5"),
                (525, 40, .5, "PBO100km"), (525, 20, .5, "HO5")]
    for altitude, height, lf, mode in profiles:
        case = name(altitude, height, lf, mode)
        runs = []
        for detailed in (True, False):
            folder = output / case / ("detailed" if detailed else "compact")
            folder.mkdir(parents=True)
            cfg = build(altitude, height, lf, mode)
            cfg["imt"]["imt_dl_intra_sinr_calculation_disabled"] = True
            cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]["record_detailed_links_and_users"] = detailed
            cfg["general"].update(num_snapshots=2, output_dir=str(folder), overwrite_output=True)
            source = folder / "input.yaml"
            source.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            params = load(source)
            with patch.object(SimulationLogger, "_global_output_dir", None):
                sim = SimulationDownlink(params, str(source))
                sim.initialize()
                snapshots = []
                with ExitStack() as stack:
                    if not detailed:
                        stack.enter_context(patch.object(CochannelHandover, "border_distances",
                            side_effect=AssertionError("Export-only border distance must not be calculated")))
                        stack.enter_context(patch.object(CochannelHandover, "record_links",
                            side_effect=AssertionError("Detailed links must not be assembled")))
                    for number, seed in enumerate((2182114437, 293847123), 1):
                        sim.snapshot(write_to_file=number == 2, snapshot_number=number, seed=seed)
                        snapshots.append(dict(sim.tcc2_last_snapshot))
                rng = sim.propagation_system.random_number_gen.get_state()
                runs.append(dict(folder=Path(sim.results.output_directory), snapshots=snapshots,
                                 rng=(rng[0], rng[1].tolist(), *rng[2:])))
                del sim
                gc.collect()
        left, right = runs
        assert left["snapshots"] == right["snapshots"], case
        assert left["rng"] == right["rng"], case
        compared = []
        for dataset in ("snapshots", "steps", "events", "candidates"):
            paths = [r["folder"] / f"tcc2_{dataset}.csv.gz" for r in runs]
            assert paths[0].exists() == paths[1].exists(), (case, dataset)
            if paths[0].exists():
                with gzip.open(paths[0], "rb") as a, gzip.open(paths[1], "rb") as b:
                    assert a.read() == b.read(), (case, dataset)
                compared.append(dataset)
        assert (left["folder"] / "system_inr.csv").read_bytes() == (right["folder"] / "system_inr.csv").read_bytes()
        for dataset in ("links", "users"):
            assert (left["folder"] / f"tcc2_{dataset}.csv.gz").is_file()
            assert not (right["folder"] / f"tcc2_{dataset}.csv.gz").exists()
        report.append(dict(case=case, snapshots=2, exact_inr_decisions_and_rng=True,
                           compared_datasets=compared, detailed_files_absent=True,
                           accepted_changes=sum(s["accepted_changes"] for s in right["snapshots"])))
        (output / "recording_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report[-1]), flush=True)
    assert any(r["accepted_changes"] > 0 for r in report), "Must exercise accepted handovers"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-handovers", type=int, default=HANDOVER_LIMIT)
    parser.add_argument("--compare-victim-only", action="store_true",
                        help="Compare full/victim-only physics, decisions, CSVs and RNG on six profiles")
    parser.add_argument("--compare-recording", action="store_true",
                        help="Compare detailed/compact exports on four profiles without changing physics")
    parser.add_argument("--check-incremental", action="store_true",
                        help="Compare the first optimized row update with the full link calculation")
    args = parser.parse_args()
    if args.max_handovers < 1:
        parser.error("--max-handovers must be positive")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if args.compare_recording:
        compare_recording(output)
        return
    if args.compare_victim_only:
        compare_victim_only(output)
        return
    # A completed baseline is no longer kept in the pending input queue.
    output.mkdir(parents=True)
    path = output / "input.yaml"
    cfg = build(340, 40, .5, "BASELINE")
    cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]["record_detailed_links_and_users"] = True
    cfg["imt"]["imt_dl_intra_sinr_calculation_disabled"] = False
    cfg["general"]["output_dir"] = str(output)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    params = load(path)
    # This reference audit explicitly evaluates user performance, even when
    # the campaign base is configured for victim-only production runs.
    params.imt.imt_dl_intra_sinr_calculation_disabled = False
    params.general.output_dir = str(output)
    SimulationLogger._global_output_dir = None
    sim = SimulationDownlink(params, str(path))
    sim.initialize()
    captured = []
    original = CochannelHandover.run

    def capture(adapter):
        captured.append(adapter)
        return original(adapter)

    with patch.object(CochannelHandover, "run", capture):
        sim.snapshot(write_to_file=False, snapshot_number=1, seed=2182114437)
    baseline = dict(sim.tcc2_last_snapshot)
    adapter = captured[0]
    rng = sim.propagation_system.random_number_gen
    consumed = rng.get_state()
    config = params.imt.topology.mss_dc.interference_aware_handover_v2
    rng.set_state(adapter.random_state)
    config.evaluation_mode = "ADJACENT_LEGACY"
    sim.calculate_external_interference()
    ordinary_inr = float(np.ravel(sim.system.inr)[0])
    np.testing.assert_allclose(ordinary_inr, baseline["inr_before_db"], rtol=0, atol=1e-10)
    config.evaluation_mode = "COCHANNEL_INR"
    rng.set_state(consumed)
    positions = xyz(sim.ue).copy()
    cells = sim.topology.beam_grid_idx.copy()
    config.enabled = True
    config.top_k = args.max_handovers
    config.max_handovers_per_snapshot = args.max_handovers
    # Only the audit may lower the gate when its one sampled state is protected.
    controlled_gate = baseline["inr_before_db"] <= -6
    if controlled_gate:
        config.inr_threshold_db = -100
    sim.results.output_directory = str(output / "handover_physics")
    Path(sim.results.output_directory).mkdir(parents=True)
    trial = CochannelHandover(sim)
    trial.random_state = adapter.random_state
    timings = []
    ordinary_performance = trial.performance
    def checked_performance(row=None):
        start = perf_counter()
        ordinary_performance(row)
        elapsed = perf_counter() - start
        if row is None or timings:
            return
        fields = ("coupling_loss_imt", "path_loss_imt", "imt_bs_antenna_gain", "imt_ue_antenna_gain")
        expected = {field: getattr(sim, field) for field in fields}
        sinr = sim.ue.sinr[sim.ue.active].copy()
        mask = sim.intra_imt_paths.mask
        start = perf_counter()
        ordinary_performance()
        full_elapsed = perf_counter() - start
        max_error = 0.
        for field in fields:
            actual, reference = getattr(sim, field), expected[field]
            for offset in range(0, sim.bs.num_stations, 128):
                a, b = actual[offset:offset + 128], reference[offset:offset + 128]
                np.testing.assert_array_equal(np.isfinite(a), np.isfinite(b))
                np.testing.assert_array_equal(np.isnan(a), np.isnan(b))
                np.testing.assert_array_equal(np.isposinf(a), np.isposinf(b))
                np.testing.assert_array_equal(np.isneginf(a), np.isneginf(b))
                finite = np.isfinite(a) & np.isfinite(b)
                max_error = max(max_error, float(np.max(np.abs(a[finite] - b[finite]), initial=0)))
        np.testing.assert_array_equal(mask, sim.intra_imt_paths.mask)
        np.testing.assert_allclose(sinr, sim.ue.sinr[sim.ue.active], rtol=0, atol=SINR_TOLERANCE_DB)
        timings.append(dict(beam=row, incremental_seconds=elapsed, full_seconds=full_elapsed,
                            max_link_error_db=max_error, max_sinr_error_db=float(
                                np.max(np.abs(sinr - sim.ue.sinr[sim.ue.active]), initial=0))))
    if args.check_incremental:
        trial.performance = checked_performance
    started = perf_counter()
    trial.run()
    handover_seconds = perf_counter() - started
    after = dict(sim.tcc2_last_snapshot)
    np.testing.assert_array_equal(xyz(sim.ue), positions)
    np.testing.assert_array_equal(sim.topology.beam_grid_idx, cells)
    assert after["accepted_changes"] > 0, "This audit must actually exercise physical handover"
    assert after["inr_after_db"] < baseline["inr_before_db"]
    assert after["max_prediction_error_db"] < 1e-9
    report = dict(baseline=baseline, handover=after, ordinary_sharc_inr_db=ordinary_inr,
                  controlled_gate=controlled_gate, audit_gate_db=config.inr_threshold_db,
                  users_and_cells_preserved=True, legacy_baseline_agrees=True,
                  max_user_cell_distance_m=float(sim._tcc2_ue_cell_distance_m.max()),
                  source_input=str(path), campaign_yaml_modified=False)
    report.update(handover_seconds=handover_seconds, incremental_checks=timings,
                  timing_includes_full_reference=args.check_incremental,
                  link_tolerance_db=LINK_TOLERANCE_DB, sinr_tolerance_db=SINR_TOLERANCE_DB)
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    assert all(t["max_link_error_db"] <= LINK_TOLERANCE_DB for t in timings), report


if __name__ == "__main__":
    main()

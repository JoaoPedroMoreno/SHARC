"""Campaign layout and launcher checks; these never start a campaign."""
import importlib.util
import csv
import gzip
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml
import numpy as np
import shapely

from sharc.cochannel_handover import CochannelHandover
from sharc.support.sharc_logger import SimulationLogger

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts"
spec = importlib.util.spec_from_file_location("tcc2_generate", SCRIPTS / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class TestTcc2Campaign(unittest.TestCase):
    @staticmethod
    def result_fixture(root, cfg, count, complete):
        scenario = cfg["general"]["output_dir_prefix"].removeprefix("output_")
        folder = root / ("output_" + scenario + "_2026-10-26_01")
        folder.mkdir(parents=True)
        (folder / "tcc2_manifest.json").write_text(json.dumps(dict(
            scenario=scenario, snapshots=cfg["general"]["num_snapshots"],
            completed_snapshots=count, complete=complete)))
        (folder / "tcc2_executed_config.yaml").write_text(yaml.safe_dump(cfg))
        with gzip.open(folder / "tcc2_snapshots.csv.gz", "wt", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["snapshot_id", "inr_after_db"])
            writer.writeheader()
            writer.writerows(dict(snapshot_id=i, inr_after_db=-7) for i in range(1, count + 1))
        return folder

    def test_reuse_requires_matching_config_and_actual_completed_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = generate.build(340, 20, .2, "BASELINE")
            cfg["general"]["num_snapshots"] = 2
            folder = self.result_fixture(root, cfg, 2, True)
            inventory = generate.result_inventory(root)
            self.assertEqual(generate.reusable_result(cfg, "BASELINE", inventory)["status"], "completed")
            changed = generate.deepcopy(cfg)
            changed["general"]["seed"] += 1
            self.assertIsNone(generate.reusable_result(changed, "BASELINE", inventory))
            with gzip.open(folder / "tcc2_snapshots.csv.gz", "wt") as f:
                f.write("snapshot_id,inr_after_db\n1,-7\n")
            self.assertIsNone(generate.reusable_result(cfg, "BASELINE", inventory))

    def test_export_options_do_not_invalidate_existing_inr(self):
        cfg = generate.build(340, 20, .2, "BASELINE")
        cfg["general"]["num_snapshots"] = 2
        old = generate.deepcopy(cfg)
        old["general"]["output_dir"] = "old_output"
        old["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"].pop(
            "record_detailed_links_and_users")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.result_fixture(root, old, 2, True)
            self.assertEqual(generate.reusable_result(cfg, "BASELINE", generate.result_inventory(root))[
                "status"], "completed")

    def test_compact_records_keep_step_inr_without_detailed_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = CochannelHandover.__new__(CochannelHandover)
            adapter.output = Path(directory)
            adapter.snapshot, adapter.seed, adapter.noise = 1, 123, -100.
            adapter.cfg = SimpleNamespace(record_detailed_links_and_users=False)
            adapter.s = SimpleNamespace(parameters=SimpleNamespace(imt=SimpleNamespace(
                imt_dl_intra_sinr_calculation_disabled=True)), ue=SimpleNamespace(active=np.array([True, False])))
            adapter.t = SimpleNamespace()
            adapter.record_step(0, {0: 1e-11})
            adapter.write("users", [{"unused": 1}])
            adapter.write("links", [{"unused": 1}])
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["tcc2_steps.csv.gz"])
            with gzip.open(Path(directory) / "tcc2_steps.csv.gz", "rt") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(float(row["inr_db"]), -10.)
            self.assertEqual(row["served_users"], "")

    def test_recording_option_defaults_to_legacy_exports_and_rejects_strings(self):
        from sharc.parameters.imt.parameters_imt_mss_dc import ParametersInterferenceAwareHandoverV2
        cfg = ParametersInterferenceAwareHandoverV2()
        self.assertTrue(cfg.record_detailed_links_and_users)
        cfg.record_detailed_links_and_users = "false"
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            cfg.validate("test")

    def test_ccdf_discovers_old_and_new_output_roots(self):
        module = runpy.run_path(str(SCRIPTS / "plot_system_inr_ccdf.py"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roots = [root / "old", root / "new"]
            for location, mode in zip(roots, ("BASELINE", "HO5")):
                cfg = generate.build(340, 20, .2, mode)
                cfg["general"]["num_snapshots"] = 2
                self.result_fixture(location, cfg, 2, True)
            found = module["discover"](roots)
            self.assertEqual({key[-1] for key in found}, {"BASELINE", "HO5"})
            self.assertEqual(len(module["discover"]([*roots, roots[0]])), 2)

    def test_pending_queue_removes_only_skipped_inputs_and_preserves_outputs(self):
        base = generate.load_base()
        base["general"]["num_snapshots"] = 2
        modes = ["BASELINE", "HO5", "HO30", "PBO100km"]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(generate, "load_base", return_value=base), \
                patch.object(generate, "SYSTEMS", {340: generate.SYSTEMS[340]}), \
                patch.object(generate, "FS_HEIGHTS", {20: generate.FS_HEIGHTS[20]}), \
                patch.object(generate, "LOAD_FACTORS", [.2]), patch.object(generate, "MODES", modes):
            root = Path(directory)
            inputs, results = root / "input", root / "output"
            inputs.mkdir()
            for mode in modes:
                cfg = generate.build(340, 20, .2, mode)
                finished = not mode.startswith("HO")
                self.result_fixture(results, cfg, 2 if finished else 1, finished)
                (inputs / (generate.name(340, 20, .2, mode) + ".yaml")).write_text(yaml.safe_dump(cfg))
            (inputs / "unrelated.yaml").write_text("untouched")
            before = {str(p): p.read_bytes() for p in results.rglob("*") if p.is_file()}
            generate.main(["--input-dir", str(inputs), "--results-dir", str(results)])
            expected = {generate.name(340, 20, .2, mode) + ".yaml" for mode in ("HO5", "HO30")}
            expected.add("unrelated.yaml")
            self.assertEqual({p.name for p in inputs.glob("*.yaml")}, expected)
            self.assertEqual(before, {str(p): p.read_bytes() for p in results.rglob("*") if p.is_file()})
            report = json.loads((inputs / "generation_report.json").read_text())
            self.assertEqual(sorted(r["status"] for r in report["skipped"]),
                             ["completed", "completed"])
            # Repeating generate is idempotent; both unfinished HO stay pending.
            generate.main(["--input-dir", str(inputs), "--results-dir", str(results)])
            self.assertEqual({p.name for p in inputs.glob("*.yaml")}, expected)

    def test_preserve_only_pbo_strictly_above_9000(self):
        for mode, count, preserve in (("PBO50km", 9000, False),
                                      ("PBO50km", 9001, True),
                                      ("HO30", 9001, False)):
            with self.subTest(mode=mode, count=count), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cfg = generate.build(340, 40, .2, mode)
                self.result_fixture(root, cfg, count, False)
                result = generate.reusable_result(cfg, mode, generate.result_inventory(root))
                if preserve:
                    self.assertEqual(result["status"], "preserved_partial_by_request")
                    self.assertEqual(result["snapshots"], count)
                else:
                    self.assertIsNone(result)

    def test_physics_audit_counts_changes_before_protected_final_snapshot(self):
        with patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
            audit = runpy.run_path(str(SCRIPTS / "validate_physics.py"))
        report = [dict(exact_csv_equality_except_ue_performance=True, rng_equal=True,
                       snapshots=2, compared_rows={"steps": 2},
                       last_snapshot={"accepted_changes": 0}) for _ in range(6)]
        with self.assertRaises(AssertionError):
            audit["validate_comparison_report"](report)
        report[0]["compared_rows"]["steps"] = 28
        audit["validate_comparison_report"](report)

    def test_generator_validates_all_inputs_without_touching_active_queue(self):
        active = {p.name: p.read_bytes() for p in (SCRIPTS.parent / "input").glob("*.yaml")}
        with tempfile.TemporaryDirectory() as directory:
            generate.main(["--input-dir", directory, "--results-dir", str(Path(directory) / "absent_results")])
            for altitude in generate.SYSTEMS:
                for height in generate.FS_HEIGHTS:
                    for lf in generate.LOAD_FACTORS:
                        for mode in generate.MODES:
                            path = Path(directory) / (generate.name(altitude, height, lf, mode) + ".yaml")
                            self.assertEqual(generate.build(altitude, height, lf, mode),
                                             yaml.safe_load(path.read_text(encoding="utf-8")))
                            self.assertTrue(yaml.safe_load(path.read_text())["imt"]["imt_dl_intra_sinr_calculation_disabled"])
                            self.assertEqual(yaml.safe_load(path.read_text())["imt"]["topology"]["mss_dc"][
                                "interference_aware_handover_v2"]["record_detailed_links_and_users"],
                                mode.startswith("HO"))
                            if mode.startswith("HO"):
                                ho = yaml.safe_load(path.read_text())["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]
                                self.assertTrue(ho["enabled"])
                                limit = int(mode[2:])
                                self.assertEqual((ho["top_k"], ho["max_handovers_per_snapshot"]), (limit, limit))
            self.assertEqual(len(list(Path(directory).glob("*.yaml"))), 136)
        self.assertEqual(active, {p.name: p.read_bytes() for p in (SCRIPTS.parent / "input").glob("*.yaml")})

    def test_common_parameters_come_from_local_base(self):
        base = generate.load_base()
        base["general"]["seed"] = 987
        base["general"]["num_snapshots"] = 12
        base["general"]["output_dir"] = "D:/custom_results"
        base["imt"]["bs"]["conducted_power"] = 41.5
        base["imt"]["imt_dl_intra_sinr_calculation_disabled"] = False
        with patch.object(generate, "load_base", return_value=base):
            cfg = generate.build(525, 40, .5, generate.HANDOVER_MODE)
        self.assertEqual(cfg["general"]["seed"], 987)
        self.assertEqual(cfg["general"]["num_snapshots"], 12)
        self.assertEqual(cfg["general"]["output_dir"], "D:/custom_results")
        self.assertEqual(cfg["imt"]["bs"]["conducted_power"], 41.5)
        self.assertFalse(cfg["imt"]["imt_dl_intra_sinr_calculation_disabled"])
        self.assertEqual(cfg["imt"]["topology"]["mss_dc"]["beam_radius"], 39844)

    def test_simple_launcher_selects_only_requested_treatments(self):
        with patch("sharc.run_multiple_campaigns_mut_thread.run_campaign") as launch:
            runpy.run_path(str(SCRIPTS / "run_multiple_campaigns_mut_thread.py"), run_name="__main__")
        launch.assert_called_once()
        campaign, = launch.call_args.args
        self.assertEqual(campaign, SCRIPTS.parent.name)

    def test_treatments_are_separate_and_service_area_unchanged(self):
        configs = {mode: generate.build(340, 20, .2, mode) for mode in generate.MODES}
        for mode, cfg in configs.items():
            mss = cfg["imt"]["topology"]["mss_dc"]
            self.assertEqual(mss["interference_aware_handover_v2"]["enabled"], mode.startswith("HO"))
            self.assertEqual(bool(mss["power_control_zones"]["zones"]), mode.startswith("PBO"))
            if mode.startswith("PBO"):
                zones = mss["power_control_zones"]["zones"]
                self.assertEqual(zones[0]["geometry"]["from_countries"]["margin_from_border"], 0)
                self.assertEqual(zones[0]["power_backoff_db"], 0)
                self.assertEqual(zones[1]["geometry"]["from_countries"]["margin_from_border"], -int(mode[3:-2]))
                self.assertEqual(zones[1]["geometry"]["from_countries"]["country_names"], ["Paraguay"])
                self.assertEqual(zones[1]["power_backoff_db"], 10)
            self.assertEqual(mss["beam_positioning"], configs["BASELINE"]["imt"]["topology"]["mss_dc"]["beam_positioning"])
            self.assertEqual(mss["sat_is_active_if"], configs["BASELINE"]["imt"]["topology"]["mss_dc"]["sat_is_active_if"])

    def test_real_topology_pbo_is_only_outside_paraguay(self):
        from sharc.simulation_downlink import SimulationDownlink
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pbo.yaml"
            path.write_text(yaml.safe_dump(generate.build(525, 40, .5, "PBO100km")))
            params = generate.load(path)
        sim = SimulationDownlink(params, str(path))
        with patch.object(SimulationLogger, "_global_output_dir", None):
            sim.topology.calculate_coordinates(np.random.RandomState(2182114437))
        t = sim.topology
        zones = params.imt.topology.mss_dc.power_control_zones.zones
        inside, expanded = (z.geometry._polygon for z in zones)
        points = shapely.points(t.beam_grid_center_lon, t.beam_grid_center_lat)
        expected = shapely.within(points, expanded) & ~shapely.within(points, inside)
        self.assertTrue(expected.any())
        self.assertTrue((~expected).any())
        np.testing.assert_array_equal(t.power_backoff, np.where(expected, 10., 0.))
        self.assertFalse(shapely.within(points, inside).any())
        self.assertEqual(zones[1].geometry.from_countries.margin_from_border, -100)

    def test_ccdf_uses_gui_empirical_rule(self):
        module = runpy.run_path(str(SCRIPTS / "plot_system_inr_ccdf.py"))
        x, y = module["compute_ccdf"]([3, 1, float("nan"), 2, 2])
        np.testing.assert_array_equal(x, [1, 2, 2, 3])
        np.testing.assert_array_equal(y, [.75, .5, .25, 0])

    def test_preview_pairs_common_snapshots_and_checks_realizations(self):
        module = runpy.run_path(str(SCRIPTS / "plot_system_inr_ccdf.py"))
        with tempfile.TemporaryDirectory() as directory:
            folders = {}
            for mode, count in (("BASELINE", 3), ("HO5", 2), ("HO30", 2), ("PBO100km", 3)):
                folder = Path(directory) / mode
                folder.mkdir()
                folders[mode] = folder
                rows = [dict(snapshot_id=i, secondary_seed=100 + i, inr_after_db=i - 7,
                             realization_sha256="paired", initial_performance_sha256="paired",
                             baseline_links_sha256="paired") for i in range(1, count + 1)]
                with gzip.open(folder / "tcc2_snapshots.csv.gz", "wt", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                (folder / "tcc2_manifest.json").write_text(json.dumps({"completed_snapshots": count}))
            samples, ids = module["paired_samples"](folders)
            self.assertEqual(ids, [1, 2])
            for sample in samples.values():
                np.testing.assert_array_equal(sample, [-6, -5])
            # An unfinished gzip member must not invalidate the committed prefix.
            with (folders["HO5"] / "tcc2_snapshots.csv.gz").open("ab") as stream:
                stream.write(gzip.compress(b"unfinished")[:12])
            self.assertEqual(len(module["read_snapshot_records"](folders["HO5"])), 2)
            records = {mode: module["read_snapshot_records"](folder) for mode, folder in folders.items()}
            records["HO5"][1]["realization_sha256"] = "different geometry"
            with patch.dict(module["paired_samples"].__globals__,
                            read_snapshot_records=lambda folder: records[folder.name]):
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    module["paired_samples"](folders)
                records["HO5"][1]["realization_sha256"] = "paired"
                records["HO30"][1]["initial_performance_sha256"] = "different performance"
                with self.assertRaisesRegex(ValueError, "Baseline/HO30 mismatch"):
                    module["paired_samples"](folders)
                records["HO30"][1]["ue_performance_calculated"] = "False"
                records["HO30"][1]["initial_performance_sha256"] = ""
                module["paired_samples"](folders)
                records["HO30"][1]["baseline_links_sha256"] = "different links"
                with self.assertRaisesRegex(ValueError, "baseline_links_sha256"):
                    module["paired_samples"](folders)

    def test_handover_preview_uses_fs_empirical_quantile(self):
        module = runpy.run_path(str(SCRIPTS / "plot_system_inr_ccdf.py"))
        metrics = module["handover_metrics"]([-10, -9, -8, -5, 2], [-10, -9, -8, -6, 0])
        self.assertEqual(metrics["inr20_baseline_db"], -5)
        self.assertEqual(metrics["inr20_handover_db"], -6)
        self.assertEqual(metrics["gain_at_20pct_db"], 1)
        self.assertEqual(metrics["margin20_handover_db"], 0)
        self.assertEqual(metrics["exceedance_baseline_pct"], 40)
        self.assertEqual(metrics["exceedance_handover_pct"], 20)
        for before, after in (([], []), ([1], [1, 2]), ([float("nan")], [1])):
            with self.assertRaises(ValueError):
                module["handover_metrics"](before, after)

    def test_standalone_manifest_records_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = CochannelHandover.__new__(CochannelHandover)
            adapter.output = Path(directory)
            adapter.snapshot, adapter.seed = 1, 123
            adapter.cfg = SimpleNamespace(enabled=True, max_handovers_per_snapshot=5,
                                           max_active_beams_per_satellite=None)
            adapter.s = SimpleNamespace(parameters_filename=str(generate.BASE_FILE),
                                         parameters=SimpleNamespace(imt=SimpleNamespace(
                                             imt_dl_intra_sinr_calculation_disabled=True), general=SimpleNamespace(
                                             num_snapshots=2, seed=838, output_dir=directory)))
            adapter.record_standalone_manifest()
            path = Path(directory) / "tcc2_manifest.json"
            first = json.loads(path.read_text())
            self.assertFalse(first["complete"])
            self.assertEqual(first["mode"], 5)
            self.assertFalse(first["ue_performance_calculated"])
            executed = yaml.safe_load((Path(directory) / "tcc2_executed_config.yaml").read_text())
            self.assertTrue(executed["imt"]["imt_dl_intra_sinr_calculation_disabled"])
            adapter.snapshot, adapter.seed = 2, 456
            adapter.record_standalone_manifest()
            final = json.loads(path.read_text())
            self.assertTrue(final["complete"])
            self.assertEqual(final["secondary_seeds"], [123, 456])
            self.assertNotIn("paired_snapshots", final)

    def test_existing_manifest_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tcc2_manifest.json"
            path.write_text('{"owned_by": "paired_runner"}')
            adapter = CochannelHandover.__new__(CochannelHandover)
            adapter.s, adapter.output = SimpleNamespace(), Path(directory)
            adapter.record_standalone_manifest()
            self.assertEqual(json.loads(path.read_text()), {"owned_by": "paired_runner"})

    def test_standard_cli_logger_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = SimulationLogger.__new__(SimulationLogger)
            logger.start_time = None
            logger.data = {"run": {}}
            logger.param_name = "test"
            logger.timestamp = "2026-10-25"
            logger.log_base = "simulation_log"
            logger.log_path = None
            with patch.object(SimulationLogger, "get_output_dir", return_value=Path(directory)):
                logger.end()
            self.assertTrue(logger.log_path.is_file())
            self.assertIn("ended_at", yaml.safe_load(logger.log_path.read_text())["run"])


if __name__ == "__main__":
    unittest.main()

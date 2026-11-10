"""Lightweight campaign-08 export/config checks; no production snapshots."""
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from sharc.cochannel_handover import CochannelHandover, validate_configuration
from sharc.parameters.imt.parameters_imt_mss_dc import ParametersInterferenceAwareHandoverV2
from sharc.simulation import Simulation
from sharc.simulation_downlink import SimulationDownlink

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


generate = module(SCRIPTS / "generate.py", "performance_generate")
with patch.dict(sys.modules, generate=generate):
    validation = module(SCRIPTS / "validate_physics.py", "performance_validation")


class PerformanceCampaignTest(unittest.TestCase):
    def test_full_matrix_preserves_all_physical_parameters(self):
        report = validation.check_inputs()
        self.assertEqual(report["scenarios"], 136)
        self.assertEqual(len(generate.MODES), 17)
        cfg = generate.build(525, 40, .5, "HO30")
        self.assertEqual(cfg["general"]["num_snapshots"], 1000)
        self.assertIn("08_TCC2_DC_MSS_performance", cfg["general"]["output_dir"])
        self.assertEqual(cfg["imt"]["bs"]["antenna"]["itu_r_s_1528"]["frequency"], 2000)

    def test_opt_in_is_disabled_for_campaign07_and_existing_configs(self):
        cfg = ParametersInterferenceAwareHandoverV2()
        cfg.validate("test")
        self.assertFalse(cfg.performance_only_output)
        paths = list((validation.SOURCE / "input").glob("*.yaml"))
        paths.append(validation.SOURCE / "Scripts/base_input.yaml")
        for path in paths:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertFalse(raw["imt"]["topology"]["mss_dc"][
                "interference_aware_handover_v2"].get("performance_only_output", False))

    def test_reject_invalid_export_modes(self):
        for bad in ("true", 1, None):
            cfg = ParametersInterferenceAwareHandoverV2(performance_only_output=bad)
            with self.assertRaises(ValueError):
                cfg.validate("test")
        cfg = ParametersInterferenceAwareHandoverV2(performance_only_output=True)
        with self.assertRaisesRegex(ValueError, "COCHANNEL_INR"):
            cfg.validate("test")
        cfg.evaluation_mode = "COCHANNEL_INR"
        cfg.validate("test")
        params = NS(general=None, imt=NS(imt_dl_intra_sinr_calculation_disabled=True,
                    topology=NS(mss_dc=NS(interference_aware_handover_v2=cfg))))
        with self.assertRaisesRegex(ValueError, "requires UE performance"):
            validate_configuration(params)

    def adapter(self, directory):
        obj = CochannelHandover.__new__(CochannelHandover)
        obj.output = Path(directory)
        obj.snapshot, obj.seed, obj.noise = 1, 123, -100.
        obj.cfg = NS(performance_only_output=True, record_detailed_links_and_users=False)
        obj.initial_served = None
        ue_geom = NS(x_global=np.zeros(3), y_global=np.zeros(3), z_global=np.zeros(3))
        bs_geom = NS(x_global=np.array([0., 10., 0.]), y_global=np.zeros(3),
                     z_global=np.array([10., 0., 10.]))
        obj.s = NS(
            parameters=NS(imt=NS(imt_dl_intra_sinr_calculation_disabled=False,
                downlink=NS(sinr_min=-10, sinr_max=30, attenuation_factor=.8))),
            ue=NS(num_stations=3, geom=ue_geom, active=np.array([True, True, False]),
                  sinr=np.array([10., 0., np.nan]), snr=np.array([20., 10., np.nan]),
                  rx_power=np.array([-80., -90., np.nan]), rx_interference=np.array([-90., -90., np.nan]),
                  bandwidth=np.full(3, 4.5), thermal_noise=np.full(3, -100.)),
            bs=NS(geom=bs_geom, tx_power={0: np.array([42.8]), 1: np.array([32.8])}),
            _tcc2_ue_up=np.tile([0., 0., 1.], (3, 1)), _tcc2_ue_cell_distance_m=np.arange(3.),
            imt_bs_antenna_gain=np.full((3, 3), 34.1), imt_ue_antenna_gain=np.full((3, 3), -3.),
            path_loss_imt=np.full((3, 3), 150.), coupling_loss_imt=np.full((3, 3), 120.),
            calculate_imt_tput=lambda *args: Simulation.calculate_imt_tput(None, *args))
        obj.t = NS(beam_grid_idx=np.arange(3), serving_satellite_idx=np.array([2, 1, 0]),
                   primary_satellite_idx=np.array([1, 1, 0]), power_backoff=np.array([0., 10., 0.]),
                   orbit_params=NS(beam_positioning=NS(service_grid=NS(minimum_service_angle=32))))
        return obj

    def test_final_export_keeps_unserved_inactive_and_ids_without_intermediate_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = self.adapter(directory)
            obj.record_step(0, {0: 1e-11, 1: 1e-12})
            obj.s.bs.geom.x_global[0] = 10.
            obj.s.bs.geom.z_global[0] = 0.
            obj.record_step(1, {0: 1e-12, 1: 1e-12})
            obj.record_final_performance()
            for dataset in ("links", "users", "events", "candidates"):
                obj.write(dataset, [{"ignored": 1}])
            self.assertEqual({p.name for p in Path(directory).iterdir()},
                             {"tcc2_steps.csv.gz", "tcc2_performance_users.csv.gz"})
            with gzip.open(Path(directory) / "tcc2_performance_users.csv.gz", "rt") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["step"] for r in rows], ["1"] * 3)
            self.assertEqual(rows[0]["service_lost"], "True")
            self.assertEqual(rows[0]["reassigned"], "True")
            self.assertEqual(rows[0]["served"], "False")
            self.assertEqual(float(rows[0]["served_rate_proxy_mbps"]), 0.)
            self.assertGreater(float(rows[0]["spectral_efficiency_proxy_bps_hz"]), 0.)
            self.assertEqual(float(rows[1]["power_backoff_db"]), 10.)
            self.assertEqual(float(rows[1]["intra_inr_db"]), 10.)
            self.assertEqual(rows[2]["active"], "False")
            self.assertTrue(np.isnan(float(rows[2]["spectral_efficiency_proxy_bps_hz"])))

    def test_legacy_writes_unchanged_when_option_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = self.adapter(directory)
            obj.cfg = NS(record_detailed_links_and_users=True, detailed_record_format="FULL")
            self.assertFalse(obj.performance_only_output)
            for dataset in ("links", "users", "events", "candidates"):
                obj.write(dataset, [{"snapshot_id": 1, "value": 2}])
                with gzip.open(Path(directory) / f"tcc2_{dataset}.csv.gz", "rt", newline="") as f:
                    self.assertEqual(f.read(), "snapshot_id,value\r\n1,2\r\n")

    def test_collector_does_not_accumulate_duplicate_raw_samples(self):
        sim = NS(parameters=NS(imt=NS(topology=NS(type="MSS_DC", mss_dc=NS(
            interference_aware_handover_v2=NS(performance_only_output=True))))),
            results=NS(write_files=lambda n: None), notify_observers=lambda **kwargs: None)
        # No victim arrays or UE metrics exist in this stub: they must not be accessed.
        SimulationDownlink.collect_results(sim, True, 1)

    def test_launcher_keeps_standard_campaign_pattern(self):
        with patch("sharc.run_multiple_campaigns_mut_thread.run_campaign") as launch:
            runpy.run_path(str(SCRIPTS / "run_multiple_campaigns_mut_thread.py"), run_name="__main__")
        launch.assert_called_once_with("08_TCC2_DC_MSS_performance")

    def test_pairing_checks_more_than_the_seed(self):
        row = dict(snapshot_id="1", secondary_seed="123", realization_sha256="same",
                   baseline_links_sha256="same", initial_top_k="[1]", examined_beams="1", attempts="1",
                   evaluated_candidates="1", accepted_changes="1", stop_reason="LIMIT",
                   active_pbo_beams="0", inr_before_db="0", inr_after_db="-1")
        validation.compare_records(row, row.copy())
        for key, value in (("realization_sha256", "different"), ("accepted_changes", "0")):
            with self.assertRaises(ValueError):
                validation.compare_records(row, {**row, key: value})
        with self.assertRaises(AssertionError):
            validation.compare_records(row, {**row, "inr_after_db": "-2"})


if __name__ == "__main__":
    unittest.main()

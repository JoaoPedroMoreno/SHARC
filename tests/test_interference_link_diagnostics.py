"""Tests for optional top-contributor interference diagnostics."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import numpy.testing as npt

from sharc.interference_link_diagnostics import select_diagnostic_links
from sharc.parameters.imt.parameters_imt_mss_dc import ParametersImtMssDc
from sharc.results import Results
from sharc.simulation_downlink import SimulationDownlink
from sharc.station_manager import StationManager


class TestDiagnosticSelection(unittest.TestCase):
    def test_defaults_are_disabled_and_nested_loading_works(self):
        params = ParametersImtMssDc()
        config = params.interference_link_diagnostics
        self.assertFalse(config.enabled)
        self.assertEqual(config.top_n, 10)
        self.assertEqual(config.eess_position_label, "")

        params.load_subparameters("imt.topology.mss_dc", {
            "interference_link_diagnostics": {
                "enabled": True,
                "top_n": 7,
                "eess_position_label": "Paraguay",
            },
        })
        config.validate("imt.topology.mss_dc.interference_link_diagnostics")
        self.assertTrue(config.enabled)
        self.assertEqual(config.top_n, 7)
        self.assertEqual(config.eess_position_label, "Paraguay")

    def test_top_ten_plus_affected_and_exact_aggregate_reconstruction(self):
        records = [
            {
                "beam_row_idx": index,
                "i_link_linear_mw": float(index + 1),
                "trigger_flag": index == 0,
                "handover_flag": index == 0,
                "unresolved_flag": False,
            }
            for index in range(12)
        ]
        aggregate = sum(row["i_link_linear_mw"] for row in records)
        selected, summary = select_diagnostic_links(records, aggregate, 10)

        self.assertEqual(len(selected), 11)
        self.assertEqual(selected[0]["beam_row_idx"], 11)
        self.assertIn(0, [row["beam_row_idx"] for row in selected])
        affected = next(row for row in selected if row["beam_row_idx"] == 0)
        self.assertEqual(affected["rank_in_snapshot"], 12)
        self.assertAlmostEqual(summary["sum_i_link_linear_mw"], aggregate)
        self.assertEqual(summary["sum_error_linear_mw"], 0.0)
        self.assertAlmostEqual(summary["fraction_top1"], 12 / aggregate)
        self.assertAlmostEqual(summary["fraction_top3"], (12 + 11 + 10) / aggregate)
        self.assertAlmostEqual(summary["fraction_top10"], sum(range(3, 13)) / aggregate)

    def test_selection_consumes_no_rng(self):
        records = [{"i_link_linear_mw": 1.0}]
        state_before = np.random.get_state()
        with patch("numpy.random.random", side_effect=AssertionError("RNG used")):
            select_diagnostic_links(records, 1.0, 10)
        state_after = np.random.get_state()
        self.assertEqual(state_before[0], state_after[0])
        npt.assert_array_equal(state_before[1], state_after[1])
        self.assertEqual(state_before[2:], state_after[2:])


class TestDiagnosticGeometryAndOutput(unittest.TestCase):
    @staticmethod
    def make_simulation():
        elevation = 30.0
        radius = 100.0
        satellite = np.array([
            radius * np.cos(np.radians(elevation)),
            0.0,
            radius * np.sin(np.radians(elevation)),
        ])
        bs = StationManager(1)
        bs.geom.set_global_coords(
            np.array([satellite[0]]), np.array([satellite[1]]),
            np.array([satellite[2]]), azim=np.array([180.0]),
            elev=np.array([-elevation]))
        bs.tx_power = np.array([20.0])
        bs.antenna = np.array([SimpleNamespace(peak_gain=34.1)], dtype=object)

        eess = StationManager(1)
        eess.geom.set_global_coords(
            np.array([0.0]), np.array([0.0]), np.array([0.0]),
            azim=np.array([0.0]), elev=np.array([elevation]))
        eess.antenna = np.array(
            [SimpleNamespace(peak_gain=45.8)], dtype=object)

        simulation = SimulationDownlink.__new__(SimulationDownlink)
        diagnostic_config = SimpleNamespace(
            enabled=True, top_n=10, eess_position_label="Paraguay")
        simulation.parameters = SimpleNamespace(
            imt=SimpleNamespace(
                frequency=2187.5, bandwidth=5.0,
                adjacent_ch_emissions="SPECTRAL_MASK",
                bs=SimpleNamespace(load_probability=0.5, ohmic_loss=0.0),
                ue=SimpleNamespace(k=1),
                topology=SimpleNamespace(
                    type="MSS_DC",
                    central_longitude=-54.5746686,
                    mss_dc=SimpleNamespace(
                        interference_link_diagnostics=diagnostic_config)),
            ),
            single_earth_station=SimpleNamespace(
                system_label="EESS_B",
                param_p619=SimpleNamespace(
                    earth_station_lat_deg=-25.5549751,
                    earth_station_alt_m=200.0)),
        )
        simulation.param_system = SimpleNamespace(
            frequency=2202.0, bandwidth=4.0,
            adjacent_ch_reception="OFF")
        simulation.polarization_loss = 3.0
        simulation.bs = bs
        simulation.system = eess
        simulation.system.bandwidth = np.array([4.0])
        simulation.system.noise_temperature = np.array([190.0])
        simulation.results = Results()
        simulation._diagnostic_snapshot_id = 3151
        simulation._diagnostic_secondary_seed = 123456
        simulation.imt_system_path_loss = np.array([[200.0]])
        simulation.system_imt_antenna_gain = np.array([[45.8]])
        simulation.imt_system_antenna_gain_adjacent = np.array([[34.1]])
        simulation.topology = SimpleNamespace(
            beam_grid_idx=np.array([7]),
            primary_satellite_idx=np.array([10]),
            serving_satellite_idx=np.array([11]),
            height=np.array([340000.0]),
            beam_grid_center_lat=np.array([-24.0]),
            beam_grid_center_lon=np.array([-55.0]),
            beam_ground_elev_angles=np.array([62.0]),
            interference_aware_handover_events=[{
                "beam_row_idx": 0, "target_satellite_idx": 11}],
            interference_aware_handover_triggered=np.array([True]),
            interference_aware_handover_successful=np.array([True]),
            interference_aware_handover_unresolved=np.array([False]),
        )
        return simulation

    def test_instrumentation_reconstructs_exact_physical_sum_and_does_not_change_it(self):
        outputs = []
        for enabled in (False, True):
            simulation = self.make_simulation()
            simulation.parameters.imt.topology.mss_dc.interference_link_diagnostics.enabled = enabled
            simulation.co_channel = False
            simulation.adjacent_channel = True
            simulation.bs.active = np.array([True])
            simulation.bs.spectral_mask = SimpleNamespace(
                power_calc=lambda *_: -60.0)
            simulation.paths_between_imt_and_sys = SimpleNamespace(
                mask=np.array([[True]]))

            def coupling_loss(*_args, **_kwargs):
                simulation.imt_system_path_loss = np.array([[200.0]])
                simulation.system_imt_antenna_gain = np.array([[45.8]])
                simulation.imt_system_antenna_gain_adjacent = np.array([[34.1]])
                return np.array([[100.0]])

            simulation.calculate_coupling_loss_system_imt = coupling_loss
            simulation.calculate_external_interference()
            outputs.append(float(simulation.system.rx_interference))
            if enabled:
                summary = simulation.results.interference_link_snapshot_summaries[0]
                self.assertEqual(summary["sum_error_linear_mw"], 0.0)
                self.assertEqual(
                    summary["sum_i_link_linear_mw"],
                    summary["i_agg_linear_mw"])

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], -160.0)

    def test_tx_rx_geometry_and_gain_suppression_are_consistent(self):
        simulation = self.make_simulation()
        link_power = 1e-15
        simulation._collect_interference_link_diagnostics(
            bs_active=np.array([0]),
            link_interference_linear_mw={0: link_power},
            aggregate_linear_mw=link_power,
            tx_spectral_power_dbm=-60.0,
        )
        row = simulation.results.interference_link_diagnostics[0]
        self.assertAlmostEqual(row["tx_offaxis_to_eess_deg"], 0.0, places=10)
        self.assertAlmostEqual(
            row["rx_offaxis_from_eess_boresight_deg"], 0.0, places=10)
        self.assertAlmostEqual(row["interferer_elevation_from_eess_deg"], 30.0)
        self.assertAlmostEqual(row["tx_gain_drop_from_peak_db"], 0.0)
        self.assertAlmostEqual(row["rx_gain_drop_from_peak_db"], 0.0)
        self.assertAlmostEqual(row["joint_gain_suppression_db"], 0.0)
        self.assertEqual(row["beam_grid_idx"], 7)
        self.assertEqual(row["service_cell_id"], 7)
        self.assertEqual(row["primary_satellite_idx"], 10)
        self.assertEqual(row["serving_satellite_idx"], 11)
        self.assertEqual(row["target_satellite_idx"], 11)
        self.assertTrue(row["handover_flag"])
        self.assertAlmostEqual(row["fraction_of_iagg_linear"], 1.0)

    def test_structured_csvs_have_complete_schema(self):
        simulation = self.make_simulation()
        simulation._collect_interference_link_diagnostics(
            bs_active=np.array([0]),
            link_interference_linear_mw={0: 1e-15},
            aggregate_linear_mw=1e-15,
            tx_spectral_power_dbm=-60.0,
        )
        with TemporaryDirectory() as temporary_directory:
            simulation.results.output_directory = Path(temporary_directory)
            simulation.results.write_files(snapshot_number=3151)
            link_path = Path(temporary_directory) / "interference_link_diagnostics.csv"
            summary_path = Path(temporary_directory) / "interference_link_snapshot_summary.csv"
            with link_path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
            self.assertEqual(reader.fieldnames, Results.interference_link_diagnostic_columns)
            self.assertEqual(len(rows), 1)
            with summary_path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
            self.assertEqual(
                reader.fieldnames,
                Results.interference_link_snapshot_summary_columns)
            self.assertEqual(len(rows), 1)

    def test_disabled_empty_results_create_no_diagnostic_files(self):
        with TemporaryDirectory() as temporary_directory:
            results = Results()
            results.output_directory = Path(temporary_directory)
            results.write_files(snapshot_number=1)
            self.assertFalse((Path(temporary_directory) /
                              "interference_link_diagnostics.csv").exists())
            self.assertFalse((Path(temporary_directory) /
                              "interference_link_snapshot_summary.csv").exists())


if __name__ == "__main__":
    unittest.main()

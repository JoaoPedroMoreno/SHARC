import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

import numpy as np
import numpy.testing as npt

from sharc.results import Results
from sharc.simulation_downlink import SimulationDownlink


class TestActiveFractionPowerBackoff(unittest.TestCase):
    @staticmethod
    def make_simulation(
        active,
        *,
        mode="ACTIVE_FRACTION",
        power_backoff_db=10.0,
        affected_fraction=0.25,
        conducted_power=42.8,
        geographic_backoff=None,
    ):
        active = np.asarray(active, dtype=bool)
        if geographic_backoff is None:
            geographic_backoff = np.zeros(active.size)
        geographic_backoff = np.asarray(geographic_backoff, dtype=float)

        power_control = SimpleNamespace(
            mode=mode,
            power_backoff_db=power_backoff_db,
            affected_fraction=affected_fraction,
        )
        simulation = SimulationDownlink.__new__(SimulationDownlink)
        simulation.parameters = SimpleNamespace(
            imt=SimpleNamespace(
                topology=SimpleNamespace(
                    type="MSS_DC",
                    mss_dc=SimpleNamespace(
                        power_control_zones=power_control,
                    ),
                ),
                bs=SimpleNamespace(conducted_power=conducted_power),
            ),
        )
        simulation.bs = SimpleNamespace(
            active=active,
            num_stations=active.size,
            tx_power=conducted_power - geographic_backoff,
        )
        simulation.topology = SimpleNamespace(
            power_backoff=geographic_backoff.copy(),
            power_backoff_affected=geographic_backoff != 0.0,
            requested_affected_fraction=np.nan,
            realized_affected_fraction=np.nan,
        )
        return simulation

    def test_only_active_beams_are_selected_with_correct_count(self):
        active = np.array(([True, False] * 20), dtype=bool)

        mask, realized = SimulationDownlink.select_active_beams_for_pbo(
            active,
            affected_fraction=0.25,
            snapshot_seed=1234,
        )

        self.assertEqual(np.count_nonzero(mask), 5)
        self.assertTrue(np.all(~mask | active))
        self.assertEqual(realized, 0.25)

    def test_fractions_are_nested(self):
        active = np.ones(100, dtype=bool)
        fractions = [0.05, 0.10, 0.15, 0.20, 0.25]
        masks = [
            SimulationDownlink.select_active_beams_for_pbo(
                active,
                fraction,
                snapshot_seed=4321,
            )[0]
            for fraction in fractions
        ]

        for smaller, larger in zip(masks, masks[1:]):
            self.assertTrue(np.all(~smaller | larger))
        self.assertEqual(
            [np.count_nonzero(mask) for mask in masks],
            [5, 10, 15, 20, 25],
        )

    def test_mask_is_the_same_for_all_positive_pbo_levels(self):
        active = np.ones(40, dtype=bool)
        masks = []

        for power_backoff_db in [5.0, 10.0, 15.0, 20.0]:
            simulation = self.make_simulation(
                active,
                power_backoff_db=power_backoff_db,
                affected_fraction=0.20,
            )
            simulation.apply_mss_dc_power_backoff(snapshot_seed=99)
            masks.append(simulation.topology.power_backoff_affected.copy())

        for mask in masks[1:]:
            npt.assert_array_equal(mask, masks[0])

    def test_power_is_reduced_only_on_selected_active_beams(self):
        active = np.array([True, False, True, True, False, True])
        simulation = self.make_simulation(
            active,
            power_backoff_db=10.0,
            affected_fraction=0.50,
        )

        simulation.apply_mss_dc_power_backoff(snapshot_seed=17)

        affected = simulation.topology.power_backoff_affected
        self.assertEqual(np.count_nonzero(affected), 2)
        self.assertTrue(np.all(~affected | active))
        npt.assert_allclose(simulation.bs.tx_power[affected], 32.8)
        npt.assert_allclose(simulation.bs.tx_power[~affected], 42.8)
        npt.assert_allclose(
            simulation.topology.power_backoff[affected],
            10.0,
        )

    def test_geographic_mode_keeps_existing_power_backoff(self):
        active = np.array([True, False, True, True])
        geographic_backoff = np.array([5.0, 0.0, 10.0, 0.0])
        simulation = self.make_simulation(
            active,
            mode="GEOGRAPHIC",
            geographic_backoff=geographic_backoff,
        )
        original_tx_power = simulation.bs.tx_power.copy()
        original_mask = simulation.topology.power_backoff_affected.copy()

        simulation.apply_mss_dc_power_backoff(snapshot_seed=55)

        npt.assert_array_equal(
            simulation.topology.power_backoff_affected,
            original_mask,
        )
        npt.assert_allclose(simulation.bs.tx_power, original_tx_power)
        npt.assert_allclose(
            simulation.topology.power_backoff,
            geographic_backoff,
        )

    def test_structured_csv_schema_contains_fraction_fields(self):
        self.assertEqual(
            Results.imt_dl_selected_ue_metrics_columns,
            [
                "snapshot_id",
                "ue_id",
                "beam_id",
                "beam_active",
                "beam_affected_by_pbo",
                "power_backoff_db",
                "tx_power_dbm",
                "sinr_db",
                "snr_db",
                "spectral_efficiency_proxy",
                "requested_affected_fraction",
                "realized_affected_fraction",
            ],
        )

    def test_structured_csv_writer_preserves_row_fields(self):
        row = {
            "snapshot_id": 1,
            "ue_id": 12,
            "beam_id": 7,
            "beam_active": True,
            "beam_affected_by_pbo": True,
            "power_backoff_db": 10.0,
            "tx_power_dbm": 32.8,
            "sinr_db": 4.5,
            "snr_db": 6.0,
            "spectral_efficiency_proxy": 1.2,
            "requested_affected_fraction": 0.25,
            "realized_affected_fraction": 0.24,
        }

        with TemporaryDirectory() as temporary_directory:
            results = Results()
            results.output_directory = Path(temporary_directory)
            results.overwrite_sample_files = True
            results.imt_dl_selected_ue_metrics.append(row)
            results.write_files(snapshot_number=1)

            csv_path = (
                Path(temporary_directory)
                / "imt_dl_selected_ue_metrics.csv"
            )
            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                written_rows = list(reader)

            self.assertEqual(
                reader.fieldnames,
                Results.imt_dl_selected_ue_metrics_columns,
            )
            self.assertEqual(len(written_rows), 1)
            self.assertEqual(written_rows[0]["snapshot_id"], "1")
            self.assertEqual(
                written_rows[0]["requested_affected_fraction"],
                "0.25",
            )
            self.assertEqual(
                written_rows[0]["realized_affected_fraction"],
                "0.24",
            )


if __name__ == "__main__":
    unittest.main()

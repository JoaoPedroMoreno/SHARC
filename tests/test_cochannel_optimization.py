"""Small physical checks of row updates against the full SHARC calculation."""
from pathlib import Path
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from sharc.antenna.antenna_factory import AntennaFactory
from sharc.cochannel_handover import CochannelHandover, update_service_links
from sharc.parameters.parameters import Parameters
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.propagation.propagation_path import PropagationPath
from sharc.simulation_downlink import SimulationDownlink
from sharc.station_manager import StationManager
from sharc.support.enumerations import StationType
from sharc.support.geometry import SimulatorGeometry


class TestServiceLinkUpdate(unittest.TestCase):
    def test_victim_only_does_not_calculate_service_performance(self):
        adapter = CochannelHandover.__new__(CochannelHandover)
        adapter.s = SimpleNamespace(parameters=SimpleNamespace(imt=SimpleNamespace(
            imt_dl_intra_sinr_calculation_disabled=True)))
        with patch("sharc.cochannel_handover.update_service_links") as update:
            adapter.performance()
            adapter.performance(2)
        update.assert_not_called()

    @classmethod
    def setUpClass(cls):
        cls.params = Parameters()
        cls.params.set_file_name(str(Path(__file__).resolve().parents[1] /
                                    "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml"))
        cls.params.read_params()

    def simulation(self, all_active):
        s = SimulationDownlink.__new__(SimulationDownlink)
        s.parameters = self.params
        n = 6
        s.bs, s.ue = StationManager(n), StationManager(n)
        s.bs.station_type, s.ue.station_type = StationType.IMT_BS, StationType.IMT_UE
        s.bs.is_space_station = True
        s.bs.active = np.ones(n, dtype=bool) if all_active else np.array([True, True, False, True, False, True])
        s.ue.active = s.bs.active.copy()
        s.bs.geom.set_global_coords(np.arange(n) * 15000., np.arange(n) * -9000.,
                                   np.full(n, 340000.), np.linspace(0, 30, n), np.full(n, -85.))
        s.ue.geom = SimulatorGeometry(n, uses_local_coords=True, global_cs=(-25., -54., 200.))
        s.ue.geom.set_local_coord_sys(np.full(n, -25.), np.full(n, -54.), np.zeros(n))
        s.ue.geom.set_local_coords(x=np.arange(n) * 16000., y=np.arange(n) * -8000.,
                                  z=np.full(n, 1.5), azim=np.zeros(n), elev=np.full(n, 90.))
        s.bs.antenna = AntennaFactory.create_n_antennas(
            self.params.imt.bs.antenna, s.bs.geom.pointn_azim_global, s.bs.geom.pointn_elev_global, n)
        s.ue.antenna = AntennaFactory.create_n_antennas(
            self.params.imt.ue.antenna, s.ue.geom.pointn_azim_global, s.ue.geom.pointn_elev_global, n)
        for antenna in s.ue.antenna:
            antenna.add_beam(0., 0.)
        s.bs_to_ue_beam_rbs = np.zeros(n, dtype=int)
        s.bs.tx_power = {int(row): np.array([42.8]) for row in np.flatnonzero(s.bs.active)}
        s.link = {int(row): [int(row)] for row in np.flatnonzero(s.bs.active)}
        s.ue.bandwidth = np.full(n, 4.5)
        s.ue.noise_figure = np.full(n, self.params.imt.ue.noise_figure)
        s.ue.rx_power = np.full(n, -500.)
        s.ue.rx_interference = np.full(n, -500.)
        s.propagation_imt = PropagationFreeSpace(np.random.RandomState(838))
        self.full(s)
        return s

    @staticmethod
    def full(s):
        s.bs_to_ue_phi, s.bs_to_ue_theta = s.bs.geom.get_global_pointing_vector_to(s.ue.geom)
        s.intra_imt_paths = PropagationPath.create_default(s.ue, s.bs)
        s.coupling_loss_imt = s.calculate_intra_imt_coupling_loss(s.ue, s.bs)
        s.calculate_sinr()

    def test_row_updates_match_full_for_multiple_moves_and_masks(self):
        for all_active in (True, False):
            s = self.simulation(all_active)
            for row, z in ((1, 525000.), (3, -1000.), (0, 400000.)):
                s.bs.geom.x_global[row] += 43000.
                s.bs.geom.z_global[row] = z
                s.bs.geom.pointn_elev_global[row] -= 5.
                untouched = s.coupling_loss_imt[np.arange(6) != row].copy()
                update_service_links(s, row)
                np.testing.assert_array_equal(s.coupling_loss_imt[np.arange(6) != row], untouched)
                fields = ("coupling_loss_imt", "path_loss_imt", "imt_bs_antenna_gain",
                          "imt_ue_antenna_gain", "bs_to_ue_phi", "bs_to_ue_theta")
                expected = {field: getattr(s, field).copy() for field in fields}
                mask = s.intra_imt_paths.mask.copy()
                sinr = s.ue.sinr.copy()
                self.full(s)
                for field in fields:
                    np.testing.assert_allclose(getattr(s, field), expected[field], rtol=0, atol=1e-10,
                                               equal_nan=True, err_msg=field)
                np.testing.assert_array_equal(s.intra_imt_paths.mask, mask)
                np.testing.assert_allclose(s.ue.sinr, sinr, rtol=0, atol=1e-10, equal_nan=True)

    def test_baseline_consumes_one_draw_and_candidates_replay_it(self):
        s = self.simulation(False)
        s.system = StationManager(1)
        s.system.geom.set_global_coords(np.zeros(1), np.zeros(1), np.array([20.]),
                                        np.array([90.]), np.zeros(1))
        s.param_system = self.params.single_earth_station
        s.ue.center_freq = np.full(6, 2155.)
        s.propagation_system = SimpleNamespace(random_number_gen=np.random.RandomState(91))
        s.paths_between_imt_and_sys = SimpleNamespace(mask=s.bs.active[None, :].copy())
        rng = s.propagation_system.random_number_gen
        s.calculate_coupling_loss_system_imt = lambda *args: 100 + rng.uniform(size=(6, 1))
        adapter = CochannelHandover.__new__(CochannelHandover)
        adapter.s, adapter.active = s, np.flatnonzero(s.bs.active)
        adapter.random_state, adapter.initial_mask = rng.get_state(), None
        powers = adapter.physical(advance_rng=True)
        expected = np.random.RandomState(91)
        expected.uniform(size=(6, 1))
        for _ in range(3):
            self.assertEqual(adapter.physical(), powers)
        np.testing.assert_array_equal(rng.random_sample(10), expected.random_sample(10))

    def test_row_update_preserves_main_beam_diagnostic_override(self):
        with patch.dict(os.environ, SHARC_FORCE_IMT_BS_TO_UE_MAIN_BEAM="1"):
            s = self.simulation(False)
            s.bs.geom.x_global[3] += 35000.
            update_service_links(s, 3)
            coupling = s.coupling_loss_imt.copy()
            self.full(s)
            np.testing.assert_allclose(s.coupling_loss_imt, coupling, rtol=0, atol=1e-10,
                                       equal_nan=True)


if __name__ == "__main__":
    unittest.main()

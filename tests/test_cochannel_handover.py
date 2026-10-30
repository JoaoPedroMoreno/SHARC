"""Deterministic controller tests; physical integration is exercised separately."""
import unittest
from types import SimpleNamespace
import numpy as np

from sharc.interference_aware_handover_v2 import CandidateEvaluation, run_inr_handover
from sharc.cochannel_handover import CochannelHandover


class TestCochannelController(unittest.TestCase):
    def execute(self, limit=5, enabled=True, candidates=True, threshold=-6, powers=None, top_k=5):
        config = SimpleNamespace(enabled=enabled, top_k=top_k, inr_threshold_db=threshold,
                                 max_handovers_per_snapshot=limit, min_reduction_db=0,
                                 max_service_elevation_loss_deg=90)
        powers = dict(powers or {i: 10.0 + i for i in range(6)})
        current = dict(powers)
        changes = []
        steps = []

        def apply(row, decision):
            self.assertNotIn(row, changes)
            changes.append(row)
            current[row] = decision.selected_i_linear_mw
            return dict(current)

        result = run_inr_handover(
            config=config, link_powers=powers, noise_dbm=0,
            cell_ids=np.arange(max(powers)+1), current_satellite=lambda row: row,
            current_elevation=lambda row: 70,
            evaluate=lambda row: [CandidateEvaluation(row + 10, 50, 0.01)] if candidates else [],
            apply=apply, record_step=lambda step, p: steps.append((step, dict(p))))
        return result, changes, steps

    def test_baseline(self):
        result, changes, _ = self.execute(enabled=False)
        self.assertEqual(result["stop_reason"], "BASELINE")
        self.assertEqual(changes, [])

    def test_no_candidate(self):
        result, changes, _ = self.execute(candidates=False)
        self.assertEqual(result["examined_beams"], 5)
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(result["stop_reason"], "SEARCH_EXHAUSTED")
        self.assertEqual(changes, [])

    def test_five_effective_changes(self):
        result, changes, steps = self.execute()
        self.assertEqual(result["accepted_changes"], 5)
        self.assertEqual(changes, [5, 4, 3, 2, 1])
        self.assertEqual(len(steps), 5)
        self.assertEqual(result["stop_reason"], "ACCEPTED_LIMIT")

    def test_protection_stops_before_limit(self):
        result, changes, _ = self.execute(powers={0: 10, 1: 0.01})
        self.assertEqual(len(changes), 1)
        self.assertEqual(result["stop_reason"], "PROTECTION_REACHED")

    def test_thirty_effective_changes_and_early_stops(self):
        powers = {i: 10. + i for i in range(31)}
        result, changes, steps = self.execute(limit=30, top_k=30, powers=powers)
        self.assertEqual(result["accepted_changes"], 30)
        self.assertEqual(result["examined_beams"], 30)
        self.assertEqual(changes, list(range(30, 0, -1)))
        self.assertEqual(len(steps), 30)
        self.assertEqual(result["stop_reason"], "ACCEPTED_LIMIT")
        result, changes, _ = self.execute(limit=30, top_k=30, powers=powers, candidates=False)
        self.assertEqual(result["stop_reason"], "SEARCH_EXHAUSTED")
        self.assertEqual(changes, [])
        result, changes, _ = self.execute(limit=30, top_k=30, powers={0: 10, 1: .01})
        self.assertEqual(result["stop_reason"], "PROTECTION_REACHED")
        self.assertEqual(changes, [0])

    def test_limits_count_accepted_changes(self):
        for limit in range(1, 6):
            result, changes, _ = self.execute(limit=limit)
            self.assertEqual(len(changes), limit)
            self.assertEqual(result["accepted_changes"], limit)

    def test_dynamic_ranking_and_no_repeated_cell(self):
        cfg = SimpleNamespace(enabled=True, top_k=5, inr_threshold_db=-100,
                              max_handovers_per_snapshot=5, min_reduction_db=0,
                              max_service_elevation_loss_deg=90)
        current = {0: 10., 1: 9., 2: 8., 3: 7., 4: 6.}
        order = []

        def apply(row, decision):
            order.append(row)
            current[row] = 0.01
            if row == 0:
                current[4] = 9.5
            return dict(current)

        result = run_inr_handover(
            config=cfg, link_powers=current, noise_dbm=0,
            cell_ids=[10, 11, 12, 13, 10], current_satellite=lambda row: 0,
            current_elevation=lambda row: 60,
            evaluate=lambda row: [CandidateEvaluation(1, 60, .01)],
            apply=apply, record_step=lambda *args: None)
        self.assertEqual(order, [0, 1, 2, 3])
        self.assertEqual(result["accepted_changes"], 4)

    def test_initial_top_k_remains_fixed_but_order_changes(self):
        cfg = SimpleNamespace(enabled=True, top_k=5, inr_threshold_db=-100,
                              max_handovers_per_snapshot=5, min_reduction_db=0,
                              max_service_elevation_loss_deg=90)
        current = {i: 10. - i for i in range(6)}
        order = []

        def apply(row, decision):
            order.append(row)
            current[row] = .01
            if row == 0:
                current[4], current[5] = 9.5, 100.
            return dict(current)

        run_inr_handover(config=cfg, link_powers=current, noise_dbm=0,
                         cell_ids=list(range(6)), current_satellite=lambda row: 0,
                         current_elevation=lambda row: 60,
                         evaluate=lambda row: [CandidateEvaluation(1, 60, .01)],
                         apply=apply, record_step=lambda *args: None)
        self.assertEqual(order, [0, 4, 1, 2, 3])

    def test_equal_power_not_accepted(self):
        cfg = SimpleNamespace(enabled=True, top_k=5, inr_threshold_db=-6,
                              max_handovers_per_snapshot=5, min_reduction_db=0,
                              max_service_elevation_loss_deg=90)
        result = run_inr_handover(config=cfg, link_powers={0: 10.}, noise_dbm=0,
                                 cell_ids=[0], current_satellite=lambda row: 0,
                                 current_elevation=lambda row: 60,
                                 evaluate=lambda row: [CandidateEvaluation(1, 60, 10.)],
                                 apply=lambda *args: self.fail("Equal power must not be applied"),
                                 record_step=lambda *args: None)
        self.assertEqual(result["accepted_changes"], 0)
        self.assertEqual(result["decisions"][0]["reason"], "NO_STRICT_REDUCTION")

    def test_full_target_satellite_is_not_physically_evaluated(self):
        adapter = CochannelHandover.__new__(CochannelHandover)
        adapter.snapshot, adapter.seed = 1, 123
        adapter.active = np.array([0, 1])
        adapter.candidate_rows = []
        adapter.cfg = SimpleNamespace(max_active_beams_per_satellite=1,
                                      max_service_elevation_loss_deg=90)
        grid = SimpleNamespace(minimum_service_angle=32)
        adapter.t = SimpleNamespace(
            beam_grid_idx=np.array([0, 1]), serving_satellite_idx=np.array([0, 1]),
            beam_ground_elev_angles=np.array([70, 70]),
            orbit_params=SimpleNamespace(beam_positioning=SimpleNamespace(service_grid=grid)),
            _service_grid_snapshot={"candidate_satellite_indices": [0, 1],
                                    "candidate_elevations_deg": np.full((2, 2), 70.),
                                    "candidate_positions_enu": np.array([[0, 0, 100], [0, 0, 100]])})
        geometry = SimpleNamespace(x_global=np.zeros(2), y_global=np.zeros(2), z_global=np.zeros(2))
        adapter.s = SimpleNamespace(ue=SimpleNamespace(geom=geometry),
                                    bs=SimpleNamespace(tx_power={0: [42.8]}),
                                    _tcc2_ue_up=np.array([[0, 0, 1], [0, 0, 1]]))
        self.assertEqual(adapter.evaluate(0), [])
        self.assertEqual(adapter.candidate_rows[0]["reason"], "SATELLITE_CAPACITY")


if __name__ == "__main__":
    unittest.main()

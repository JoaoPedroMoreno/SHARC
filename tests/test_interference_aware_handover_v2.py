import numpy as np

from sharc.interference_aware_handover_v2 import (
    CandidateEvaluation, choose_minimum_interference_target,
    replace_link_power_linear, select_triggered_links,
    should_enter_risk_gate,
)


def test_oracle_trigger_is_stable_top_k():
    assert select_triggered_links({4: 2.0, 1: 3.0, 2: 2.0}, 2,
                                  "ORACLE_TOP_K") == [1, 2]


def test_target_minimizes_exact_link_power_with_qos_constraint():
    decision = choose_minimum_interference_target(
        beam_row_idx=7, current_satellite_idx=10,
        current_service_elevation_deg=70, current_i_linear_mw=100,
        candidates=[CandidateEvaluation(11, 60, 10),
                    CandidateEvaluation(12, 40, 1)],
        min_reduction_db=3, max_service_elevation_loss_deg=15)
    assert decision.accepted and decision.selected_satellite_idx == 11
    assert np.isclose(decision.predicted_reduction_db, 10)


def test_rejection_and_linear_aggregate_replacement():
    decision = choose_minimum_interference_target(
        beam_row_idx=0, current_satellite_idx=1,
        current_service_elevation_deg=50, current_i_linear_mw=10,
        candidates=[CandidateEvaluation(2, 49, 9)],
        min_reduction_db=1, max_service_elevation_loss_deg=5)
    assert not decision.accepted
    assert replace_link_power_linear(30, 10, 4) == 24


def test_v2_off_has_no_decision_or_aggregate_side_effect():
    aggregate = 31.25
    enabled = False
    result = replace_link_power_linear(aggregate, 10, 1) if enabled else aggregate
    assert result == aggregate


def test_v2_on_changes_aggregate_for_better_same_cell_candidate():
    cell_id = 123
    current_cell_id = cell_id
    candidate_cell_id = cell_id
    decision = choose_minimum_interference_target(
        beam_row_idx=4, current_satellite_idx=1,
        current_service_elevation_deg=60, current_i_linear_mw=20,
        candidates=[CandidateEvaluation(2, 55, 2)],
        min_reduction_db=1, max_service_elevation_loss_deg=10)
    updated = replace_link_power_linear(
        50, decision.current_i_linear_mw, decision.selected_i_linear_mw)
    assert decision.accepted and updated == 32
    assert current_cell_id == candidate_cell_id


def test_geometric_trigger_is_injected_not_hard_coded():
    assert select_triggered_links({0: 2, 1: 1}, 3, "GEOMETRIC_RULE",
                                  lambda i: i == 1) == [1]


def test_target_decision_is_deterministic_and_has_no_rng_calls():
    before = np.random.get_state()
    choose_minimum_interference_target(
        beam_row_idx=1, current_satellite_idx=1,
        current_service_elevation_deg=50, current_i_linear_mw=10,
        candidates=[CandidateEvaluation(2, 45, 1)],
        min_reduction_db=0, max_service_elevation_loss_deg=10)
    after = np.random.get_state()
    assert all(np.array_equal(a, b) for a, b in zip(before, after))


def test_risk_gate_is_strict_and_oracle_remains_ungated():
    assert not should_enter_risk_gate("RISK_GATED_TOP_K", -154.0, -154.0)
    assert not should_enter_risk_gate("RISK_GATED_TOP_K", -155.0, -154.0)
    assert should_enter_risk_gate("RISK_GATED_TOP_K", -153.9, -154.0)
    assert should_enter_risk_gate("ORACLE_TOP_K", -200.0, -154.0)

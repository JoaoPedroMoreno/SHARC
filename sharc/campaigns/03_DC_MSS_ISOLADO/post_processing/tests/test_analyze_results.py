"""Unit tests for Campaign 03 post-processing."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


MODULE_PATH = Path(__file__).resolve().parents[1] / "analyze_results.py"
SPEC = importlib.util.spec_from_file_location("campaign03_analysis", MODULE_PATH)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = analysis
SPEC.loader.exec_module(analysis)


def make_scenario(
    load_factor=0.2,
    pbo_db=0.0,
    fraction=0.0,
    csv_path="",
    output_path=".",
):
    return analysis.Scenario(
        scenario_id=analysis.scenario_id(load_factor, pbo_db, fraction),
        output_path=output_path,
        yaml_path="input.yaml",
        metrics_csv_path=csv_path,
        load_factor=load_factor,
        pbo_db=pbo_db,
        requested_fraction=fraction,
        configured_snapshots=2,
        actual_snapshots=2,
        user_records=4,
        unique_ue_ids=4,
        nominal_tx_power_dbm=42.8,
        attenuation_factor=0.8,
        sinr_min_db=-10.0,
        sinr_max_db=30.0,
        pbo_mode="ACTIVE_FRACTION",
    )


def artificial_frame():
    sinr = np.array([-12.0, -8.0, 2.0, 12.0])
    return pd.DataFrame({
        "snapshot_id": [1, 1, 2, 2],
        "ue_id": [1, 2, 3, 4],
        "beam_id": [1, 2, 3, 4],
        "beam_active": [True] * 4,
        "beam_affected_by_pbo": [True, False, True, False],
        "power_backoff_db": [5.0, 0.0, 5.0, 0.0],
        "tx_power_dbm": [37.8, 42.8, 37.8, 42.8],
        "sinr_db": sinr,
        "snr_db": sinr + 1.0,
        "spectral_efficiency_proxy":
            analysis.sharc_spectral_efficiency_proxy(
                sinr, -10.0, 30.0, 0.8),
        "requested_affected_fraction": [0.5] * 4,
        "realized_affected_fraction": [0.5] * 4,
    })


class DiscoveryTests(unittest.TestCase):
    def test_discovers_26_scenarios_and_one_baseline_per_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            campaign = Path(temporary)
            output = campaign / "output"
            combinations = []
            for load_factor in analysis.EXPECTED_LOAD_FACTORS:
                combinations.append((load_factor, 0.0, 0.0))
                for pbo in analysis.EXPECTED_PBO_LEVELS:
                    for fraction in analysis.EXPECTED_FRACTIONS:
                        combinations.append((load_factor, pbo, fraction))
            for index, (load_factor, pbo, fraction) in enumerate(combinations):
                directory = output / f"case_{index:02d}"
                directory.mkdir(parents=True)
                config = {
                    "general": {"num_snapshots": 1},
                    "imt": {
                        "bs": {
                            "load_probability": load_factor,
                            "conducted_power": 42.8,
                        },
                        "downlink": {
                            "attenuation_factor": 0.8,
                            "sinr_min": -10,
                            "sinr_max": 30,
                        },
                        "topology": {
                            "mss_dc": {
                                "power_control_zones": {
                                    "mode": "ACTIVE_FRACTION",
                                    "power_backoff_db": pbo,
                                    "affected_fraction": fraction,
                                },
                            },
                        },
                    },
                }
                (directory / "config.yaml").write_text(
                    yaml.safe_dump(config), encoding="utf-8")
                frame = artificial_frame().iloc[:1].copy()
                frame["snapshot_id"] = 1
                frame.to_csv(
                    directory / "metrics_any_name.csv", index=False)

            scenarios, candidates = analysis.discover_scenarios(campaign)
            self.assertEqual(len(scenarios), 26)
            self.assertEqual(len(candidates), 26)
            for load_factor in analysis.EXPECTED_LOAD_FACTORS:
                baselines = [
                    item for item in scenarios
                    if item.load_factor == load_factor and item.pbo_db == 0
                ]
                self.assertEqual(len(baselines), 1)


class MetricTests(unittest.TestCase):
    def test_mean_linear_p5_and_outage(self):
        frame = artificial_frame()
        metrics = analysis.calculate_metrics(frame, -10.0)
        self.assertAlmostEqual(metrics["sinr_mean_db"], -1.5)
        self.assertAlmostEqual(
            metrics["sinr_p5_db"],
            np.quantile(frame["sinr_db"], 0.05, method="linear"),
        )
        self.assertAlmostEqual(metrics["outage_probability"], 0.25)
        self.assertAlmostEqual(metrics["outage_probability_m1"], 0.50)
        self.assertAlmostEqual(metrics["outage_probability_m6"], 0.50)
        self.assertAlmostEqual(metrics["outage_probability_m10"], 0.25)

    def test_affected_and_unaffected_groups(self):
        frame = artificial_frame()
        affected = analysis.select_group(frame, "affected")
        unaffected = analysis.select_group(frame, "unaffected")
        self.assertEqual(affected["ue_id"].tolist(), [1, 3])
        self.assertEqual(unaffected["ue_id"].tolist(), [2, 4])

    def test_missing_columns_are_reported_as_failure(self):
        qc = analysis.QCRecorder()
        scenario = make_scenario()
        analysis.validate_dataframe(
            scenario,
            artificial_frame().drop(columns=["sinr_db"]),
            qc,
        )
        self.assertTrue(qc.has_failures())
        row = qc.dataframe().query("check == 'required_columns'").iloc[0]
        self.assertEqual(row["status"], "FAIL")

    def test_inr_omits_nonpositive_linear_values(self):
        sinr_for_unit_inr = 10.0 * np.log10(5.0)
        values, omitted = analysis.inr_db_from_snr_sinr(
            [10.0, 3.0],
            [sinr_for_unit_inr, 3.0],
        )
        self.assertAlmostEqual(values[0], 0.0, places=12)
        self.assertTrue(np.isnan(values[1]))
        self.assertEqual(omitted, 1)

    def test_path_loss_is_aligned_before_key_sorting(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            frame = artificial_frame().iloc[[1, 0, 3, 2]].copy()
            metrics_path = output / "imt_dl_selected_ue_metrics.csv"
            frame.to_csv(metrics_path, index=False)
            pd.DataFrame({"samples": frame["snr_db"]}).to_csv(
                output / "imt_dl_snr.csv", index=False)
            path_loss = np.array([101.0, 102.0, 103.0, 104.0])
            pd.DataFrame({"samples": path_loss}).to_csv(
                output / "imt_path_loss.csv", index=False)
            scenario = make_scenario(
                csv_path=str(metrics_path), output_path=str(output))
            loaded = analysis.load_scenario_dataframe(
                scenario, include_path_loss=True)
            expected = pd.DataFrame({
                "snapshot_id": frame["snapshot_id"],
                "ue_id": frame["ue_id"],
                "beam_id": frame["beam_id"],
                "path_loss_db": path_loss,
            }).sort_values(analysis.KEY_COLUMNS)
            np.testing.assert_allclose(
                loaded["path_loss_db"], expected["path_loss_db"])
            self.assertEqual(
                loaded.attrs["flat_snr_alignment_max_error_db"], 0.0)


class BootstrapTests(unittest.TestCase):
    def test_cluster_bootstrap_keeps_snapshot_users_together(self):
        frame = pd.DataFrame({
            "snapshot_id": [1, 1, 2, 2],
            "sinr_db": [0.0, 0.0, 10.0, 10.0],
            "spectral_efficiency_proxy": [1.0, 1.0, 2.0, 2.0],
        })
        counts = np.array([[2, 0], [0, 2], [1, 1]], dtype=np.int16)
        result = analysis.cluster_bootstrap_distribution(
            frame, [1, 2], counts, -10.0)
        np.testing.assert_allclose(
            result["sinr_mean_db"], [0.0, 10.0, 5.0])
        np.testing.assert_allclose(
            result["sinr_p5_db"], [0.0, 10.0, 0.0])

    def test_paired_bootstrap_uses_repetition_wise_difference(self):
        scenario = {
            metric: np.array([2.0, 4.0])
            for metric in analysis.BOOTSTRAP_METRICS
        }
        baseline = {
            metric: np.array([1.0, 3.5])
            for metric in analysis.BOOTSTRAP_METRICS
        }
        result = analysis.paired_bootstrap_differences(
            scenario, baseline)
        for metric in analysis.BOOTSTRAP_METRICS:
            np.testing.assert_allclose(result[metric], [1.0, 0.5])

    def test_paired_retention_uses_repetition_wise_ratio(self):
        scenario = {
            "spectral_efficiency_p5_bpshz": np.array([2.0, 3.0, 0.0])
        }
        baseline = {
            "spectral_efficiency_p5_bpshz": np.array([1.0, 2.0, 0.0])
        }
        result = analysis.paired_bootstrap_ratio_percent(
            scenario,
            baseline,
            "spectral_efficiency_p5_bpshz",
        )
        np.testing.assert_allclose(result[:2], [200.0, 150.0])
        self.assertTrue(np.isnan(result[2]))


class PairingTests(unittest.TestCase):
    def test_baseline_classification_is_key_paired(self):
        baseline = artificial_frame().copy()
        baseline["beam_affected_by_pbo"] = False
        source = artificial_frame().sample(frac=1.0, random_state=3)
        result = analysis.classify_baseline(baseline, source)
        self.assertIsNotNone(result)
        expected = artificial_frame().sort_values(
            analysis.KEY_COLUMNS)["beam_affected_by_pbo"].tolist()
        self.assertEqual(
            result["beam_affected_by_pbo"].tolist(), expected)

    def test_nested_masks(self):
        five = np.array([True, False, False, False])
        ten = np.array([True, True, False, False])
        fifteen = np.array([True, True, True, False])
        self.assertTrue(analysis.masks_are_nested(five, ten))
        self.assertTrue(analysis.masks_are_nested(ten, fifteen))
        self.assertFalse(analysis.masks_are_nested(ten, five))


class OperationalRegionTests(unittest.TestCase):
    def test_classifies_above_borderline_and_below_m6(self):
        rows = []
        values = [
            (5.0, -5.0, -5.5, -4.5),
            (10.0, -5.9, -6.2, -5.6),
            (15.0, -7.0, -7.2, -6.8),
        ]
        for pbo, estimate, lower, upper in values:
            common = {
                "scenario_id": f"case_{int(pbo)}",
                "load_factor": 0.2,
                "pbo_db": pbo,
                "affected_fraction": 0.1,
                "group": "all",
                "repetitions": 20,
                "seed": 838,
                "analysis_type": "absolute",
            }
            rows.append({
                **common,
                "metric": "sinr_p5_db",
                "estimate": estimate,
                "ci95_lower": lower,
                "ci95_upper": upper,
            })
            rows.append({
                **common,
                "metric": analysis.MAIN_OUTAGE_METRIC,
                "estimate": 0.03,
                "ci95_lower": 0.02,
                "ci95_upper": 0.04,
            })
        classification, frontiers = (
            analysis.build_operational_classification(pd.DataFrame(rows))
        )
        self.assertEqual(
            classification["operational_status_m6"].tolist(),
            ["acima_com_ic95", "limitrofe_ic95", "abaixo_com_ic95"],
        )
        frontier = frontiers[
            np.isclose(frontiers["load_factor"], 0.2)
            & np.isclose(frontiers["affected_fraction"], 0.1)
            & (frontiers["threshold_key"] == "m6")
        ].iloc[0]
        self.assertEqual(
            frontier["maximum_simulated_pbo_above_threshold_db"], 10.0)


class PerformanceFigureTests(unittest.TestCase):
    def test_contains_24_pbo_scenarios_and_two_baselines(self):
        bootstrap_rows = []
        paired_rows = []
        for load_factor in analysis.EXPECTED_LOAD_FACTORS:
            bootstrap_rows.append({
                "scenario_id": analysis.scenario_id(
                    load_factor, 0.0, 0.0),
                "load_factor": load_factor,
                "pbo_db": 0.0,
                "affected_fraction": 0.0,
                "group": "all",
                "metric": analysis.MAIN_OUTAGE_METRIC,
                "estimate": 0.01,
                "ci95_lower": 0.009,
                "ci95_upper": 0.011,
            })
            for pbo in analysis.EXPECTED_PBO_LEVELS:
                for fraction in analysis.EXPECTED_FRACTIONS:
                    bootstrap_rows.append({
                        "scenario_id": analysis.scenario_id(
                            load_factor, pbo, fraction),
                        "load_factor": load_factor,
                        "pbo_db": pbo,
                        "affected_fraction": fraction,
                        "group": "all",
                        "metric": analysis.MAIN_OUTAGE_METRIC,
                        "estimate": 0.02,
                        "ci95_lower": 0.019,
                        "ci95_upper": 0.021,
                    })
                    paired_rows.append({
                        "scenario_id": analysis.scenario_id(
                            load_factor, pbo, fraction),
                        "load_factor": load_factor,
                        "pbo_db": pbo,
                        "affected_fraction": fraction,
                        "group": "all",
                        "metric": analysis.RETENTION_METRIC,
                        "estimate": 80.0,
                        "ci95_lower": 78.0,
                        "ci95_upper": 82.0,
                    })
        result = analysis.build_system_performance_values(
            pd.DataFrame(bootstrap_rows),
            pd.DataFrame(paired_rows),
        )
        self.assertEqual(len(result), 26)
        self.assertEqual(int(result["is_baseline"].sum()), 2)
        self.assertEqual(int((~result["is_baseline"]).sum()), 24)


class TableTests(unittest.TestCase):
    def test_generates_all_csv_and_latex_tables(self):
        scenarios = []
        metric_rows = []
        paired_rows = []
        for load_factor in analysis.EXPECTED_LOAD_FACTORS:
            baseline = make_scenario(load_factor, 0.0, 0.0)
            scenarios.append(baseline)
            base_metrics = {
                "scenario_id": baseline.scenario_id,
                "load_factor": load_factor,
                "pbo_db": 0.0,
                "affected_fraction": 0.0,
                "group": "all",
                "n_snapshots": 1000,
                "n_users": 10000,
                "realized_affected_fraction_mean": 0.0,
                "realized_affected_fraction_std": 0.0,
                "sinr_p5_db": -2.0,
                "outage_probability": 0.01,
                "outage_probability_m1": 0.02,
                "outage_probability_m6": 0.01,
                "outage_probability_m10": 0.005,
            }
            metric_rows.append(base_metrics)
            for pbo in analysis.EXPECTED_PBO_LEVELS:
                for fraction in analysis.EXPECTED_FRACTIONS:
                    scenario = make_scenario(
                        load_factor, pbo, fraction)
                    scenarios.append(scenario)
                    for group, users in [
                        ("all", 10000),
                        ("affected", int(10000 * fraction)),
                        ("unaffected", int(10000 * (1 - fraction))),
                    ]:
                        metric_rows.append({
                            "scenario_id": scenario.scenario_id,
                            "load_factor": load_factor,
                            "pbo_db": pbo,
                            "affected_fraction": fraction,
                            "group": group,
                            "n_snapshots": 1000,
                            "n_users": users,
                            "realized_affected_fraction_mean": fraction,
                            "realized_affected_fraction_std": 0.001,
                            "sinr_p5_db": -2.0 - pbo * fraction,
                            "outage_probability": 0.01 + pbo * fraction / 100,
                            "outage_probability_m1":
                                0.02 + pbo * fraction / 100,
                            "outage_probability_m6":
                                0.01 + pbo * fraction / 100,
                            "outage_probability_m10":
                                0.005 + pbo * fraction / 100,
                        })
                        paired_rows.append({
                            "scenario_id": scenario.scenario_id,
                            "load_factor": load_factor,
                            "pbo_db": pbo,
                            "affected_fraction": fraction,
                            "group": group,
                            "metric": "sinr_p5_db",
                            "estimate": -pbo * fraction,
                            "ci95_lower": -pbo * fraction - 0.1,
                            "ci95_upper": -pbo * fraction + 0.1,
                        })
        metrics = pd.DataFrame(metric_rows)
        performance_rows = []
        mechanism_rows = []
        control_rows = []
        for load_factor in analysis.EXPECTED_LOAD_FACTORS:
            performance_rows.append({
                "scenario_id": analysis.scenario_id(
                    load_factor, 0.0, 0.0),
                "load_factor": load_factor,
                "pbo_db": 0.0,
                "affected_fraction": 0.0,
                "is_baseline": True,
                "outage_probability_m6": 0.01,
                "outage_m6_ci95_lower": 0.009,
                "outage_m6_ci95_upper": 0.011,
                analysis.RETENTION_METRIC: 100.0,
                "retention_se_p5_ci95_lower_percent": 100.0,
                "retention_se_p5_ci95_upper_percent": 100.0,
            })
            for fraction in analysis.EXPECTED_FRACTIONS:
                for pbo in analysis.EXPECTED_PBO_LEVELS:
                    performance_rows.append({
                        "scenario_id": analysis.scenario_id(
                            load_factor, pbo, fraction),
                        "load_factor": load_factor,
                        "pbo_db": pbo,
                        "affected_fraction": fraction,
                        "is_baseline": False,
                        "outage_probability_m6": 0.02,
                        "outage_m6_ci95_lower": 0.019,
                        "outage_m6_ci95_upper": 0.021,
                        analysis.RETENTION_METRIC: 80.0,
                        "retention_se_p5_ci95_lower_percent": 78.0,
                        "retention_se_p5_ci95_upper_percent": 82.0,
                    })
                    control_rows.append({
                        "scenario_id": analysis.scenario_id(
                            load_factor, pbo, fraction),
                        "load_factor": load_factor,
                        "pbo_db": pbo,
                        "affected_fraction": fraction,
                        "snr_affected_median_delta_db": -pbo,
                        "inr_unaffected_median_delta_db": -1.0,
                        "snr_unaffected_max_abs_delta_db": 0.0,
                        "path_loss_max_abs_delta_db": 0.0,
                        "snr_reduction_dominates_inr_benefit": True,
                    })
                for pbo in [0.0, 10.0, 20.0]:
                    for metric in [
                        "snr_affected_db", "inr_unaffected_db",
                    ]:
                        mechanism_rows.append({
                            "scenario_id": analysis.scenario_id(
                                load_factor,
                                pbo,
                                0.0 if pbo == 0 else fraction,
                            ),
                            "load_factor": load_factor,
                            "pbo_db": pbo,
                            "affected_fraction": fraction,
                            "metric": metric,
                            "group": (
                                "affected"
                                if metric == "snr_affected_db"
                                else "unaffected"
                            ),
                            "total_records": 100,
                            "valid_records": 100,
                            "omitted_records": 0,
                            "mean": 1.0,
                            "median": 1.0,
                            "p5": 0.0,
                            "p95": 2.0,
                        })
        performance = pd.DataFrame(performance_rows)
        mechanism = pd.DataFrame(mechanism_rows)
        controls = pd.DataFrame(control_rows)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            analysis.build_tables(
                scenarios,
                metrics,
                performance,
                mechanism,
                controls,
                output,
            )
            for stem in [
                "table_scenario_counts",
                "table_system_performance",
                "table_mechanism_summary",
                "table_paired_controls",
            ]:
                self.assertTrue((output / f"{stem}.csv").exists())
                self.assertTrue((output / f"{stem}.tex").exists())


if __name__ == "__main__":
    unittest.main()

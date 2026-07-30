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
):
    return analysis.Scenario(
        scenario_id=analysis.scenario_id(load_factor, pbo_db, fraction),
        output_path=".",
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
        paired = pd.DataFrame(paired_rows)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            analysis.build_tables(scenarios, metrics, paired, output)
            for stem in [
                "table_scenario_counts",
                "table_main_results",
                "table_affected_unaffected",
            ]:
                self.assertTrue((output / f"{stem}.csv").exists())
                self.assertTrue((output / f"{stem}.tex").exists())


if __name__ == "__main__":
    unittest.main()

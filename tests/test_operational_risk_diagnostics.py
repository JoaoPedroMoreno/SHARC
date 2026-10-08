"""Tests for passive operational-risk diagnostic configuration and output."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from sharc.parameters.imt.parameters_imt_mss_dc import (
    ParametersOperationalRiskDiagnostics,
)
from sharc.results import Results


class TestOperationalRiskDiagnostics(unittest.TestCase):
    def test_defaults_are_passive(self):
        config = ParametersOperationalRiskDiagnostics()
        self.assertFalse(config.enabled)
        self.assertTrue(config.record_snapshot_summary)
        self.assertEqual(config.record_top_k, 3)
        self.assertTrue(config.record_handover_events)
        self.assertFalse(config.record_candidate_details)

    def test_validation_rejects_invalid_top_k(self):
        config = ParametersOperationalRiskDiagnostics(record_top_k=0)
        with self.assertRaises(ValueError):
            config.validate("operational_risk_diagnostics")

    def test_three_structured_csv_schemas(self):
        results = Results()
        with tempfile.TemporaryDirectory() as temporary:
            results.output_directory = Path(temporary)
            results.operational_risk_snapshots.append({
                column: 0 for column in results.operational_risk_snapshot_columns
            })
            results.operational_risk_topk.append({
                column: 0 for column in results.operational_risk_topk_columns
            })
            results.operational_risk_handover_events.append({
                column: 0
                for column in results.operational_risk_handover_event_columns
            })
            results.write_files(1)
            expected = {
                "operational_risk_snapshot.csv": (
                    results.operational_risk_snapshot_columns),
                "operational_risk_topk.csv": results.operational_risk_topk_columns,
                "operational_risk_handover_events.csv": (
                    results.operational_risk_handover_event_columns),
            }
            for filename, columns in expected.items():
                frame = pd.read_csv(Path(temporary) / filename)
                self.assertEqual(list(frame.columns), columns)


if __name__ == "__main__":
    unittest.main()

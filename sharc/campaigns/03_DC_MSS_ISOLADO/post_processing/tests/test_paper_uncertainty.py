import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_paper_uncertainty import paper_outage_intervals


class PaperUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.values = pd.DataFrame({
            "scenario_id": ["test"], "outage_probability_m6": [0.0469093538879743],
            "outage_m6_ci95_lower": [0.04654179541554455],
            "outage_m6_ci95_upper": [0.04733124396298632],
            "spectral_efficiency_p5_retention_percent": [23.984],
            "retention_se_p5_ci95_lower_percent": [22.646],
            "retention_se_p5_ci95_upper_percent": [25.335],
        })
        self.metrics = pd.DataFrame({
            "scenario_id": ["test"], "group": ["all"],
            "affected_fraction": [0.05], "pbo_db": [20], "n_snapshots": [1000],
        })

    def test_published_interval_and_retention_preserved(self):
        original = self.values.copy(deep=True)
        result = paper_outage_intervals(self.values, self.metrics)
        np.testing.assert_allclose(
            result[["outage_m6_ci95_lower", "outage_m6_ci95_upper"]].iloc[0],
            [0.0338038748358957, 0.0600148329400529],
        )
        for column in self.values.columns:
            if column.startswith("outage_m6_ci95"):
                self.assertEqual(result[column.replace("ci95", "bootstrap_ci95")][0], original[column][0])
            else:
                pd.testing.assert_series_equal(result[column], original[column])
        pd.testing.assert_frame_equal(self.values, original)

    def test_bounds_and_low_probability(self):
        for p in [0, 0.0001, 0.9999, 1]:
            self.values["outage_probability_m6"] = p
            result = paper_outage_intervals(self.values, self.metrics)
            self.assertGreaterEqual(result.outage_m6_ci95_lower[0], 0)
            self.assertLessEqual(result.outage_m6_ci95_upper[0], 1)

    def test_missing_snapshot_count_rejected(self):
        self.metrics["n_snapshots"] = np.nan
        with self.assertRaises(ValueError):
            paper_outage_intervals(self.values, self.metrics)


if __name__ == "__main__":
    unittest.main()

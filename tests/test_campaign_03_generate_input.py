import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "sharc"
    / "campaigns"
    / "03_DC_MSS_ISOLADO"
    / "Script"
    / "generate_input.py"
)
SPEC = importlib.util.spec_from_file_location(
    "campaign_03_generate_input",
    SCRIPT_PATH,
)
GENERATE_INPUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATE_INPUT)


class TestCampaign03GenerateInput(unittest.TestCase):
    def test_generates_full_requested_matrix(self):
        with TemporaryDirectory() as temporary_directory:
            generated_paths = GENERATE_INPUT.generate_inputs(
                output_dir=Path(temporary_directory),
            )

            self.assertEqual(len(generated_paths), 26)
            self.assertEqual(len(set(generated_paths)), 26)
            self.assertTrue(all("FS" not in path.name for path in generated_paths))

            scenarios = []
            for path in generated_paths:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                general = data["general"]
                imt = data["imt"]
                mss_dc = imt["topology"]["mss_dc"]
                power_control = mss_dc["power_control_zones"]

                self.assertNotIn("FS", general["output_dir_prefix"])
                self.assertEqual(general["num_snapshots"], 1000)
                self.assertEqual(imt["frequency"], 2155.0)
                self.assertEqual(mss_dc["orbits"][0]["perigee_alt_km"], 340.0)
                self.assertEqual(mss_dc["orbits"][0]["apogee_alt_km"], 340.0)
                self.assertEqual(mss_dc["beam_radius"], 25803)
                self.assertEqual(power_control["mode"], "ACTIVE_FRACTION")
                self.assertTrue(all(
                    zone["power_backoff_db"] == 0.0
                    for zone in power_control["zones"]
                ))

                scenarios.append((
                    imt["bs"]["load_probability"],
                    power_control["power_backoff_db"],
                    power_control["affected_fraction"],
                ))

            baseline = [
                scenario for scenario in scenarios if scenario[1] == 0.0
            ]
            self.assertEqual(
                baseline,
                [(0.2, 0.0, 0.0), (0.5, 0.0, 0.0)],
            )

            positive = {
                scenario for scenario in scenarios if scenario[1] > 0.0
            }
            expected_positive = {
                (load_factor, power_backoff_db, affected_fraction)
                for load_factor in [0.2, 0.5]
                for power_backoff_db in [5.0, 10.0, 15.0, 20.0]
                for affected_fraction in [0.05, 0.10, 0.15]
            }
            self.assertEqual(positive, expected_positive)


if __name__ == "__main__":
    unittest.main()

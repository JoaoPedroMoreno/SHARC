"""Real-scenario non-regression check for diagnostic instrumentation.

Runs only snapshot 3151 of the completed 340 km / EESS B / LF 0.5 /
GB 10 MHz / HO OFF scenario, once with diagnostics OFF and once ON.  Outputs
are temporary and no campaign YAML is modified.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from sharc.parameters.parameters import Parameters
from sharc.simulation_downlink import SimulationDownlink
from sharc.support.sharc_logger import SimulationLogger


CAMPAIGN = Path(__file__).resolve().parents[1]
SOURCE = CAMPAIGN / "input" / (
    "system_340km_EESS_B_SA_P_OM_0_lf_0.5_GB_10MHz_HO_OFF.yaml")
SNAPSHOT_ID = 3151


def secondary_seed(snapshot_id: int) -> int:
    generator = random.Random(157)
    value = 0
    for _ in range(snapshot_id):
        value = generator.randint(1, 2**32 - 1)
    return value


def run_snapshot(enabled: bool, output_dir: Path) -> tuple[float, dict | None]:
    parameters = Parameters()
    parameters.set_file_name(str(SOURCE))
    parameters.read_params()
    parameters.general.overwrite_output = True
    parameters.general.output_dir = str(output_dir)
    parameters.imt.topology.mss_dc.interference_link_diagnostics.enabled = enabled
    parameters.imt.topology.mss_dc.interference_link_diagnostics.top_n = 10
    parameters.imt.topology.mss_dc.interference_link_diagnostics.eess_position_label = "Paraguay"
    SimulationLogger._global_output_dir = None
    simulation = SimulationDownlink(parameters, str(SOURCE))
    simulation.initialize()
    simulation.snapshot(
        write_to_file=False,
        snapshot_number=SNAPSHOT_ID,
        seed=secondary_seed(SNAPSHOT_ID),
    )
    aggregate_dbw_mhz = float(
        np.asarray(simulation.system.rx_interference).reshape(-1)[0]
        - 30.0 - 10.0 * math.log10(
            float(np.asarray(simulation.system.bandwidth).reshape(-1)[0])))
    summary = (
        simulation.results.interference_link_snapshot_summaries[0]
        if enabled else None)
    return aggregate_dbw_mhz, summary


def completed_baseline_value() -> float:
    pattern = SOURCE.stem + "_*"
    for directory in sorted((CAMPAIGN / "output").glob(pattern), reverse=True):
        path = directory / "system_dl_interf_power_per_mhz.csv"
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        if len(rows) == 10_001:
            return float(rows[SNAPSHOT_ID][0]) - 30.0
    raise RuntimeError("Completed baseline output was not found")


def main() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        disabled, _ = run_snapshot(False, root / "disabled")
        enabled, summary = run_snapshot(True, root / "enabled")
    historical = completed_baseline_value()
    if disabled != enabled:
        raise AssertionError(
            f"Instrumentation changed I_agg: OFF={disabled}, ON={enabled}")
    assert summary is not None
    tolerance = max(abs(summary["i_agg_linear_mw"]) * 1e-12, 1e-300)
    if abs(summary["sum_error_linear_mw"]) > tolerance:
        raise AssertionError(
            f"Per-link reconstruction error {summary['sum_error_linear_mw']}")
    print(f"snapshot_id={SNAPSHOT_ID}")
    print(f"secondary_seed={secondary_seed(SNAPSHOT_ID)}")
    print(f"I_agg_OFF={disabled:.15f} dBW/MHz")
    print(f"I_agg_ON={enabled:.15f} dBW/MHz")
    print(f"historical={historical:.15f} dBW/MHz")
    print(f"current_minus_historical={disabled - historical:.15f} dB")
    print(f"sum_error_linear_mw={summary['sum_error_linear_mw']:.3e}")
    print(f"recorded_links={summary['recorded_links']}")


if __name__ == "__main__":
    main()

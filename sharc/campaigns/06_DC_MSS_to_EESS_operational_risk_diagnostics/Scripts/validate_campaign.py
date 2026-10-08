"""Validate every generated input through the real SHARC parameter loader."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / ".venv" / "Lib" / "site-packages"))

from sharc.parameters.parameters import Parameters


CAMPAIGN = Path(__file__).resolve().parents[1]
PATTERN = re.compile(
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_"
    r"lf_(0\.2|0\.5)_GB_(80|75|70|65|60|10)MHz_V2_RISK_GATE\.yaml$"
)


def main() -> None:
    paths = sorted((CAMPAIGN / "input").glob("*.yaml"))
    if len(paths) != 48:
        raise AssertionError(f"Expected 48 YAMLs, found {len(paths)}")
    combinations = set()
    for path in paths:
        match = PATTERN.fullmatch(path.name)
        if match is None:
            raise AssertionError(f"Unexpected input name: {path.name}")
        parameters = Parameters()
        parameters.set_file_name(str(path))
        parameters.read_params()
        altitude, eess, load, gb = match.groups()
        combinations.add((int(altitude), eess, float(load), int(gb)))
        mss = parameters.imt.topology.mss_dc
        diagnostics = mss.operational_risk_diagnostics
        v2 = mss.interference_aware_handover_v2
        assert parameters.general.seed == 157
        assert parameters.general.num_snapshots == 5000
        assert parameters.imt.bandwidth == 5.0
        assert parameters.imt.frequency == 2197.5 - int(gb)
        assert mss.interference_aware_handover.enabled is False
        assert v2.enabled is True
        assert v2.trigger_mode == "RISK_GATED_TOP_K"
        assert v2.risk_gate_dbw_per_mhz == -154.0
        assert v2.top_k == 3
        assert v2.min_reduction_db == 0.0
        assert v2.max_service_elevation_loss_deg == 90.0
        assert v2.max_handovers_per_snapshot == 1
        assert diagnostics.enabled is True
        assert diagnostics.record_snapshot_summary is True
        assert diagnostics.record_top_k == 3
        assert diagnostics.record_handover_events is True
        assert diagnostics.record_candidate_details is False
    if len(combinations) != 48:
        raise AssertionError("Generated Cartesian product is incomplete")
    print(json.dumps({
        "validated_inputs": len(paths),
        "unique_combinations": len(combinations),
        "altitudes_km": sorted({case[0] for case in combinations}),
        "eess_systems": sorted({case[1] for case in combinations}),
        "load_factors": sorted({case[2] for case in combinations}),
        "guard_bands_mhz": sorted(
            {case[3] for case in combinations}, reverse=True),
        "simulations_started": 0,
    }, indent=2))


if __name__ == "__main__":
    main()

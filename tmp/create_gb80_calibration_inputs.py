from copy import deepcopy
import importlib.util
from pathlib import Path

import yaml


generator_path = Path(
    "sharc/campaigns/04_DC_MSS_to_EESS/Scripts/generate.py")
spec = importlib.util.spec_from_file_location("campaign04_generate", generator_path)
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)

common = generate.load_base()
common["general"]["seed"] = 157
common["general"]["num_snapshots"] = 1000
generate.apply_altitude(common, 340)
generate.apply_eess(common, "EESS_B")
generate.apply_position(common, "P")
generate.apply_coverage(common, "SA")
generate.apply_operational_margin(common, 0)
common["imt"]["bs"]["load_probability"] = 0.5
generate.apply_guard_band(common, 80)
generate.apply_handover(common, "V2")

cases = [
    ("CAL_GB80_A_ORACLE_UPPER_BOUND", {
        "trigger_mode": "ORACLE_TOP_K",
        "min_reduction_db": 0.0,
        "max_service_elevation_loss_deg": 90.0,
    }, False),
    ("CAL_GB80_B_RISK_GATE", {
        "trigger_mode": "RISK_GATED_TOP_K",
        "risk_gate_dbw_per_mhz": -154.0,
        "min_reduction_db": 0.0,
        "max_service_elevation_loss_deg": 90.0,
    }, True),
    ("CAL_GB80_C_RISK_GATE_SERVICE", {
        "trigger_mode": "RISK_GATED_TOP_K",
        "risk_gate_dbw_per_mhz": -154.0,
        "min_reduction_db": 3.0,
        "max_service_elevation_loss_deg": 10.0,
    }, False),
]

output_dir = generate.CAMPAIGN_DIR / "input"
output_dir.mkdir(parents=True, exist_ok=True)
for name, overrides, diagnostics_enabled in cases:
    config = deepcopy(common)
    mss = config["imt"]["topology"]["mss_dc"]
    mss["interference_aware_handover_v2"].update(overrides)
    mss["interference_link_diagnostics"]["enabled"] = diagnostics_enabled
    config["general"]["output_dir_prefix"] = name
    generate.validate_generated_config(config, 80, "V2", "EESS_B")
    output_path = output_dir / f"{name}.yaml"
    output_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(output_path.resolve())

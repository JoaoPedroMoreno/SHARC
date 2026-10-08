from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import math
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
BASE_FILE = SCRIPT_DIR / "base_input.yaml"
INPUT_DIR = CAMPAIGN_DIR / "input"
OUTPUT_DIR = CAMPAIGN_DIR / "output"
P619_DATASET_DIR = CAMPAIGN_DIR.parents[1] / "propagation" / "Dataset"

# Eixo experimental preparado para o estudo futuro de qualidade de serviço.
MAX_SERVICE_ELEVATION_LOSS_DEG = [10, 20, 30, 45]

# Os demais eixos ficam deliberadamente fixos até a definição do experimento.
ALTITUDE_KM = 340
EESS_SYSTEM = "EESS_B"
LOAD_FACTOR = 0.5
GUARD_BAND_MHZ = 80
DC_MSS_FREQUENCY_MHZ = 2197.5 - GUARD_BAND_MHZ
DC_MSS_BANDWIDTH_MHZ = 5.0
NUM_SNAPSHOTS = 5000
SEED = 157


def expected_lookup_path() -> Path:
    # PropagationP619 usa int(frequency) na convenção atual do dataset.
    return P619_DATASET_DIR / f"FOZ_{int(DC_MSS_FREQUENCY_MHZ)}_200m.csv"


def validate_lookup() -> None:
    path = expected_lookup_path()
    if not path.is_file():
        raise FileNotFoundError(
            "Campanha QoS não gerada: lookup P.619 ausente: " + str(path)
        )


def load_base() -> dict:
    with BASE_FILE.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def configure(limit_deg: float) -> dict:
    cfg = deepcopy(load_base())
    cfg["general"]["seed"] = SEED
    cfg["general"]["num_snapshots"] = NUM_SNAPSHOTS
    cfg["general"]["output_dir"] = str(OUTPUT_DIR)
    cfg["imt"]["frequency"] = DC_MSS_FREQUENCY_MHZ
    cfg["imt"]["bandwidth"] = DC_MSS_BANDWIDTH_MHZ
    cfg["imt"]["bs"]["load_probability"] = LOAD_FACTOR

    mss = cfg["imt"]["topology"]["mss_dc"]
    legacy = mss.setdefault("interference_aware_handover", {})
    legacy["enabled"] = False

    v2 = mss.setdefault("interference_aware_handover_v2", {})
    v2.update({
        "enabled": True,
        "top_k": 3,
        "trigger_mode": "RISK_GATED_TOP_K",
        "risk_gate_dbw_per_mhz": -154.0,
        "min_reduction_db": 3.0,
        "max_service_elevation_loss_deg": float(limit_deg),
        "max_handovers_per_snapshot": 1,
        "record_candidate_details": False,
    })

    diagnostics = mss.setdefault("interference_link_diagnostics", {})
    diagnostics.update({
        "enabled": False,
        "top_n": 10,
        "eess_position_label": "Paraguay",
    })

    name = (
        "QOS_340km_EESS_B_SA_P_OM_0_lf_0.5_GB_80MHz"
        f"_MAX_ELEV_LOSS_{int(limit_deg)}deg"
    )
    cfg["general"]["output_dir_prefix"] = name
    return cfg


def validate_config(cfg: dict, limit_deg: float) -> None:
    assert cfg["general"]["seed"] == 157
    assert cfg["general"]["num_snapshots"] == 5000
    assert math.isclose(float(cfg["imt"]["frequency"]), 2117.5)
    assert math.isclose(float(cfg["imt"]["bandwidth"]), 5.0)
    mss = cfg["imt"]["topology"]["mss_dc"]
    assert mss["interference_aware_handover"]["enabled"] is False
    v2 = mss["interference_aware_handover_v2"]
    assert v2["enabled"] is True
    assert v2["trigger_mode"] == "RISK_GATED_TOP_K"
    assert math.isclose(float(v2["risk_gate_dbw_per_mhz"]), -154.0)
    assert math.isclose(float(v2["min_reduction_db"]), 3.0)
    assert math.isclose(float(v2["max_service_elevation_loss_deg"]), limit_deg)
    assert int(v2["max_handovers_per_snapshot"]) == 1
    assert mss["interference_link_diagnostics"]["enabled"] is False


def main() -> None:
    # A validação ocorre antes de criar diretórios ou escrever YAMLs.
    validate_lookup()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for limit_deg in MAX_SERVICE_ELEVATION_LOSS_DEG:
        cfg = configure(limit_deg)
        validate_config(cfg, limit_deg)
        name = cfg["general"]["output_dir_prefix"] + ".yaml"
        path = INPUT_DIR / name
        if path.exists():
            raise FileExistsError(f"Nada sobrescrito: {path}")
        with path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(cfg, stream, sort_keys=False, allow_unicode=True)
        generated.append(path)
    print(f"Gerados {len(generated)} inputs QoS: {MAX_SERVICE_ELEVATION_LOSS_DEG}")


if __name__ == "__main__":
    main()

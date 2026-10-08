"""Generate the 48-run operational-risk diagnostics campaign.

This campaign deliberately excludes GB=5 MHz because that point is in the
variable region of SpectralMaskMSS.  GB=80..10 MHz remain in the flat
spurious-emission regime used to study geometry-conditioned risk.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from itertools import product
from pathlib import Path
import shutil
import sys


REPO = Path(__file__).resolve().parents[4]
SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
sys.path.insert(0, str(SITE_PACKAGES))

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
INPUT_DIR = CAMPAIGN_DIR / "input"
OUTPUT_DIR = CAMPAIGN_DIR / "output"
ANALYSIS_DIR = CAMPAIGN_DIR / "analysis"
BASE_FILE = SCRIPT_DIR / "base_input.yaml"
REFERENCE_BASE = (
    REPO / "sharc" / "campaigns" / "04_DC_MSS_to_EESS"
    / "Scripts" / "base_input.yaml"
)
P619_DATASET_DIR = REPO / "sharc" / "propagation" / "Dataset"


ALTITUDES_KM = [340, 525]
EESS_SYSTEMS = ["EESS_B", "EESS_D"]
LOAD_FACTORS = [0.2, 0.5]
GUARD_BANDS_MHZ = [80, 75, 70, 65, 60, 10]
NUM_SNAPSHOTS = 5000
MASTER_SEED = 157
DC_MSS_BANDWIDTH_MHZ = 5.0


ALTITUDE_CONFIG = {
    340: {
        "n_planes": 48, "sats_per_plane": 110, "phasing_deg": 1.636,
        "beam_radius": 26195, "N_max_beam": 105, "bs_height_m": 340000,
    },
    525: {
        "n_planes": 28, "sats_per_plane": 120, "phasing_deg": 1.5,
        "beam_radius": 40448, "N_max_beam": 90, "bs_height_m": 525000,
    },
}

EESS_CONFIG = {
    "EESS_B": {
        "frequency": 2202.0, "bandwidth": 4.0,
        "noise_temperature": 190, "gain": 45.8, "diameter": 8.91,
    },
    "EESS_D": {
        "frequency": 2203.0, "bandwidth": 6.0,
        "noise_temperature": 120, "gain": 39.0, "diameter": 4.07,
    },
}

SA_COUNTRIES = [
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
    "Paraguay", "Peru", "Uruguay", "Venezuela", "Guyana", "Suriname",
]


def load_base() -> dict:
    source = BASE_FILE if BASE_FILE.is_file() else REFERENCE_BASE
    if not source.is_file():
        raise FileNotFoundError(f"Base input not found: {source}")
    with source.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def expected_lookup(frequency_mhz: float) -> Path:
    # Exact convention used by the audited P.619 lookup loader.
    return P619_DATASET_DIR / f"FOZ_{int(frequency_mhz)}_200m.csv"


def validate_lookups() -> dict[float, Path]:
    required = {
        2197.5 - float(gb): expected_lookup(2197.5 - float(gb))
        for gb in GUARD_BANDS_MHZ
    }
    missing = {frequency: path for frequency, path in required.items()
               if not path.is_file()}
    if missing:
        details = "\n".join(
            f"  {frequency:.1f} MHz -> {path.name}"
            for frequency, path in missing.items())
        raise FileNotFoundError(
            "Missing P.619 lookup tables; no YAML was written:\n" + details)
    return required


def apply_altitude(data: dict, altitude_km: int) -> None:
    values = ALTITUDE_CONFIG[altitude_km]
    mss = data["imt"]["topology"]["mss_dc"]
    orbit = mss["orbits"][0]
    orbit.update({
        "n_planes": values["n_planes"],
        "perigee_alt_km": altitude_km,
        "apogee_alt_km": altitude_km,
        "sats_per_plane": values["sats_per_plane"],
        "phasing_deg": values["phasing_deg"],
    })
    mss["beam_radius"] = values["beam_radius"]
    mss["N_max_beam"] = values["N_max_beam"]
    data["imt"]["bs"]["height"] = values["bs_height_m"]


def apply_eess(data: dict, system: str) -> None:
    values = EESS_CONFIG[system]
    eess = data["single_earth_station"]
    eess.update({
        "system_label": system,
        "frequency": values["frequency"],
        "bandwidth": values["bandwidth"],
        "noise_temperature": values["noise_temperature"],
    })
    eess["antenna"]["gain"] = values["gain"]
    s465 = eess["antenna"]["itu_r_s_465"]
    s465["antenna_gain"] = values["gain"]
    s465["diameter"] = values["diameter"]


def apply_paraguay_sa(data: dict) -> None:
    topology = data["imt"]["topology"]
    topology.update({
        "central_latitude": -25.5549751,
        "central_longitude": -54.5746686,
        "central_altitude": 200,
    })
    p619 = data["single_earth_station"]["param_p619"]
    p619["earth_station_lat_deg"] = -25.5549751
    p619["earth_station_alt_m"] = 200
    mss = topology["mss_dc"]
    mss["sat_is_active_if"]["lat_long_inside_country"][
        "country_names"] = list(SA_COUNTRIES)
    grid = mss["beam_positioning"]["service_grid"]["grid_in_zone"]
    grid["from_countries"]["country_names"] = list(SA_COUNTRIES)
    grid["from_countries"]["margin_from_border"] = 0


def build_case(base: dict, altitude: int, eess: str, load: float,
               guard_band: int) -> tuple[str, dict]:
    data = deepcopy(base)
    apply_altitude(data, altitude)
    apply_eess(data, eess)
    apply_paraguay_sa(data)

    frequency = 2197.5 - float(guard_band)
    data["general"].update({
        "seed": MASTER_SEED,
        "num_snapshots": NUM_SNAPSHOTS,
        "overwrite_output": False,
        "output_dir": str(OUTPUT_DIR),
    })
    data["imt"]["frequency"] = frequency
    data["imt"]["bandwidth"] = DC_MSS_BANDWIDTH_MHZ
    data["imt"]["bs"]["load_probability"] = load

    mss = data["imt"]["topology"]["mss_dc"]
    mss.setdefault("interference_aware_handover", {})["enabled"] = False
    mss["interference_aware_handover_v2"] = {
        "enabled": True,
        "top_k": 3,
        "min_reduction_db": 0.0,
        "max_service_elevation_loss_deg": 90.0,
        "max_handovers_per_snapshot": 1,
        "trigger_mode": "RISK_GATED_TOP_K",
        "risk_gate_dbw_per_mhz": -154.0,
        "record_candidate_details": False,
    }
    mss["interference_link_diagnostics"] = {
        "enabled": False, "top_n": 10, "eess_position_label": "Paraguay",
    }
    mss["operational_risk_diagnostics"] = {
        "enabled": True,
        "record_snapshot_summary": True,
        "record_top_k": 3,
        "record_handover_events": True,
        "record_candidate_details": False,
    }

    system_letter = eess.removeprefix("EESS_")
    prefix = (
        f"operational_risk_{altitude}km_EESS_{system_letter}_SA_P_OM_0_"
        f"lf_{load}_GB_{guard_band}MHz_V2_RISK_GATE"
    )
    data["general"]["output_dir_prefix"] = prefix
    return prefix + ".yaml", data


def build_matrix() -> list[tuple[str, dict]]:
    base = load_base()
    cases = [
        build_case(base, altitude, eess, load, guard_band)
        for altitude, eess, load, guard_band in product(
            ALTITUDES_KM, EESS_SYSTEMS, LOAD_FACTORS, GUARD_BANDS_MHZ)
    ]
    if len(cases) != 48 or len({name for name, _ in cases}) != 48:
        raise AssertionError("Operational-risk campaign must contain 48 unique cases")
    for name, data in cases:
        assert data["general"]["num_snapshots"] == 5000
        assert data["general"]["seed"] == 157
        assert data["imt"]["bandwidth"] == 5.0
        assert data["imt"]["topology"]["mss_dc"][
            "interference_aware_handover"]["enabled"] is False
        assert data["imt"]["topology"]["mss_dc"][
            "interference_aware_handover_v2"]["enabled"] is True
        assert data["imt"]["topology"]["mss_dc"][
            "operational_risk_diagnostics"]["enabled"] is True
    return cases


def write_matrix(cases: list[tuple[str, dict]]) -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve the approved invariance inputs outside the runnable input set.
    invariant_archive = ANALYSIS_DIR / "invariance_inputs"
    invariant_archive.mkdir(parents=True, exist_ok=True)
    for path in INPUT_DIR.glob("invariance_*.yaml"):
        shutil.move(str(path), invariant_archive / path.name)

    expected_names = {name for name, _ in cases}
    for path in INPUT_DIR.glob("operational_risk_*.yaml"):
        if path.name not in expected_names:
            path.unlink()
    for name, data in cases:
        with (INPUT_DIR / name).open(
            "w", encoding="utf-8", newline="\n",
        ) as stream:
            yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=True)

    if not BASE_FILE.exists():
        with REFERENCE_BASE.open(encoding="utf-8") as stream:
            reference = yaml.safe_load(stream)
        with BASE_FILE.open("w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(reference, stream, sort_keys=False, allow_unicode=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="write the validated 48 YAML files")
    args = parser.parse_args()
    lookups = validate_lookups()
    cases = build_matrix()
    print("Matrix: 2 altitudes x 2 EESS x 2 loads x 6 GB = 48 inputs")
    print("Guard bands:", GUARD_BANDS_MHZ)
    print("Frequencies:", [2197.5 - gb for gb in GUARD_BANDS_MHZ])
    print("Lookups:", ", ".join(path.name for path in lookups.values()))
    print("First five inputs:")
    for name, _ in cases[:5]:
        print("  ", name)
    if args.write:
        write_matrix(cases)
        print(f"Wrote {len(cases)} inputs to {INPUT_DIR}")
    else:
        print("Dry run only; use --write to replace the runnable input set.")


if __name__ == "__main__":
    main()

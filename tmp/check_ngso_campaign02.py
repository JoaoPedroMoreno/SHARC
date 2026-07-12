from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[1] / ".venv" / "Lib" / "site-packages"))

import sharc.satellite.ngso.backend.orbit_backend_service as ngso_backend
from sharc.satellite.ngso.backend.orbit_backend_service import SimulationProfile, build_simulation


ngso_backend.PROFILES["smoke"] = SimulationProfile(
    "smoke",
    interval_secs=900,
    grid_size=10,
    footprint_points=24,
)


PARAM_FILES = [
    Path("sharc/campaigns/02_DC_MSS_to_FS 2/input/dc_mss_to_fs_SouthAmerica_Sys3_340km_FS20m_LF20_EZ0km_Azi90deg.yaml"),
    Path("sharc/campaigns/02_DC_MSS_to_FS 2/output/output_dc_mss_to_fs_BR_AR_Paraguay_Sys3_340km_FS20m_LF20_M0km_Azi90deg_2026-07-02_01/dc_mss_to_fs_BR_AR_Paraguay_Sys3_340km_FS20m_LF20_M0km_Azi90deg.yaml"),
]


for param_file in PARAM_FILES:
    print(f"FILE {param_file}")
    data = build_simulation(profile="smoke", param_file=param_file)
    meta = data["meta"]
    keys = [
        "paramFile",
        "frameCount",
        "satelliteCount",
        "beamRadiuskm",
        "minimumServiceAngleDeg",
        "guardbandHexCount",
        "powerBackoffDb",
        "imtFrequencyMHz",
        "imtBandwidthMHz",
        "singleEarthStationBandwidthMHz",
        "serviceAreaCountryNames",
        "serviceAreaLabel",
    ]
    print(json.dumps({key: meta.get(key) for key in keys}, indent=2))
    print(f"station {data['station']}")
    first = data["frames"][0]
    print(
        "first_frame "
        f"coverage={first['coveragePercent']} "
        f"active_sats={first['activeSatelliteCount']} "
        f"footprints={len(first['footprints'])}"
    )

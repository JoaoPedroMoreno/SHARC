"""Backend utilities for the NGSO satellite map frontend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
from cartopy.io import shapereader
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import unary_union

from sharc.parameters.parameters import Parameters
from sharc.satellite.utils.sat_utils import calc_elevation
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM
from sharc.satellite.ngso.orbit_model import OrbitModel


@dataclass(frozen=True)
class SimulationProfile:
    name: str
    interval_secs: int
    grid_size: int
    footprint_points: int
    n_periods: int = 1


PROFILES = {
    "fast": SimulationProfile("fast", interval_secs=30, grid_size=28, footprint_points=48),
    "high_quality": SimulationProfile("high_quality", interval_secs=10, grid_size=52, footprint_points=96),
    "presentation": SimulationProfile("presentation", interval_secs=300, grid_size=72, footprint_points=180),
}


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_param_file() -> Path:
    return (
        _package_root()
        / "campaigns"
        / "02_DC_MSS_to_FS 2"
        / "input"
        / "dc_mss_to_fs_SouthAmerica_Sys3_340km_FS20m_LF20_EZ0km_Azi90deg.yaml"
    )


def resolve_param_file(param_file: str | Path | None) -> Path:
    """Resolve arquivos de parametros enviados pela URL do frontend.

    O servidor pode ser iniciado a partir da raiz do repositorio ou da pasta do
    simulador. Por isso, caminhos relativos sao testados contra os locais mais
    provaveis antes de serem entregues ao leitor de parametros do SHARC.
    """
    if not param_file:
        return default_param_file()

    candidate = Path(param_file)
    if candidate.is_absolute() or candidate.exists():
        return candidate

    package_root = _package_root()
    for base_path in (Path.cwd(), package_root, package_root.parent):
        resolved = base_path / candidate
        if resolved.exists():
            return resolved

    return candidate


def _latlon_to_ecef(lat_deg: float, lon_deg: float, radius_km: float = EARTH_RADIUS_KM) -> np.ndarray:
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    x = radius_km * np.cos(lat) * np.cos(lon)
    y = radius_km * np.cos(lat) * np.sin(lon)
    z = radius_km * np.sin(lat)
    return np.array([x, y, z], dtype=float)


def _ecef_to_latlon(vector: np.ndarray) -> tuple[float, float]:
    x, y, z = vector
    radius = np.linalg.norm(vector)
    lat = np.degrees(np.arcsin(z / radius))
    lon = np.degrees(np.arctan2(y, x))
    return float(lat), float(lon)


def _orthonormal_basis(unit_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    reference = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(unit_vector, reference)) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])

    tangent_1 = np.cross(unit_vector, reference)
    tangent_1 /= np.linalg.norm(tangent_1)
    tangent_2 = np.cross(unit_vector, tangent_1)
    tangent_2 /= np.linalg.norm(tangent_2)
    return tangent_1, tangent_2


def _footprint_ring(sat_xyz: np.ndarray, central_angle_rad: float, n_points: int) -> list[list[float]]:
    nadir = sat_xyz / np.linalg.norm(sat_xyz)
    tangent_1, tangent_2 = _orthonormal_basis(nadir)
    angles = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=True)

    ring_xyz = EARTH_RADIUS_KM * (
        np.cos(central_angle_rad) * nadir[None, :]
        + np.sin(central_angle_rad)
        * (
            np.cos(angles)[:, None] * tangent_1[None, :]
            + np.sin(angles)[:, None] * tangent_2[None, :]
        )
    )

    ring_lonlat = []
    for point_xyz in ring_xyz:
        lat_deg, lon_deg = _ecef_to_latlon(point_xyz)
        ring_lonlat.append([round(lon_deg, 6), round(lat_deg, 6), 0.0])

    return ring_lonlat


def _service_central_angle_rad(altitude_km: float, minimum_elevation_deg: float) -> float:
    """Return the ground central angle visible above a minimum elevation."""
    satellite_radius = EARTH_RADIUS_KM + altitude_km
    horizon_angle = np.arccos(EARTH_RADIUS_KM / satellite_radius)
    min_elevation_rad = np.radians(minimum_elevation_deg)
    low = 0.0
    high = float(horizon_angle)

    for _ in range(48):
        mid = 0.5 * (low + high)
        slant = np.sqrt(
            satellite_radius**2
            + EARTH_RADIUS_KM**2
            - 2.0 * satellite_radius * EARTH_RADIUS_KM * np.cos(mid)
        )
        elevation = np.arccos(
            np.clip(
                (slant**2 + EARTH_RADIUS_KM**2 - satellite_radius**2)
                / (2.0 * slant * EARTH_RADIUS_KM),
                -1.0,
                1.0,
            )
        ) - (np.pi / 2.0)

        if elevation >= min_elevation_rad:
            low = mid
        else:
            high = mid

    return low


def _s1528_relative_gain_angle_deg(*, antenna_3db_bw_deg: float, loss_db: float) -> float:
    """Return the off-axis angle where S.1528 section 1.2 reaches ``loss_db``."""
    psi_b = antenna_3db_bw_deg / 2.0
    return psi_b * (loss_db / 3.0) ** (1.0 / 1.5)


def _hex_ring_count(num_beams: int) -> int:
    ring_count = 0
    beams_in_cluster = 1
    while beams_in_cluster < num_beams:
        ring_count += 1
        beams_in_cluster = 1 + 3 * ring_count * (ring_count + 1)

    return ring_count


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _load_country_geometry(country_names: list[str]):
    try:
        shp_path = shapereader.natural_earth(
            resolution="110m",
            category="cultural",
            name="admin_0_countries",
        )
        countries = gpd.read_file(shp_path)
        selected = countries[countries["ADMIN"].isin(country_names)].geometry
        if not selected.empty:
            return unary_union(selected.tolist())
    except Exception:
        pass

    # Fallback simplificado para ambientes sem cache/gravaÃ§Ã£o do Natural Earth.
    return Polygon(
        [
            (-73.99, -7.6),
            (-70.2, 1.2),
            (-60.5, 5.2),
            (-50.8, 4.6),
            (-44.2, 1.2),
            (-35.0, -7.5),
            (-34.8, -16.0),
            (-38.8, -25.0),
            (-48.0, -33.5),
            (-53.5, -31.3),
            (-57.8, -33.7),
            (-62.5, -30.0),
            (-67.8, -21.5),
            (-70.3, -11.0),
            (-73.99, -7.6),
        ]
    )


class OrbitSimulationBackend:
    """Runs the orbit simulation and serializes it for the Cesium frontend."""

    def __init__(self, profile: str = "fast", param_file: str | Path | None = None):
        if profile not in PROFILES:
            raise ValueError(f"Perfil invalido: {profile}. Use um destes: {', '.join(PROFILES)}")

        self.profile = PROFILES[profile]
        self.param_file = resolve_param_file(param_file)
        self.parameters = self._load_parameters()
        self.topology = self.parameters.imt.topology
        self.mss_dc = self.topology.mss_dc
        self.country_names = self._load_service_country_names()
        self.brazil_geometry = _load_country_geometry(self.country_names)

    def _load_service_country_names(self) -> list[str]:
        service_grid = self.mss_dc.beam_positioning.service_grid
        country_names = []
        try:
            country_names = list(service_grid.grid_in_zone.from_countries.country_names)
        except Exception:
            pass
        if not country_names:
            try:
                country_names = list(self.mss_dc.sat_is_active_if.lat_long_inside_country.country_names)
            except Exception:
                pass
        return country_names or ["Brazil"]

    def _load_parameters(self) -> Parameters:
        parameters = Parameters()
        parameters.set_file_name(str(self.param_file))
        parameters.read_params()
        return parameters

    def _build_orbit_model(self) -> OrbitModel:
        orbit_params = self.mss_dc.orbits[0]
        return OrbitModel(
            Nsp=orbit_params.sats_per_plane,
            Np=orbit_params.n_planes,
            phasing=orbit_params.phasing_deg,
            long_asc=orbit_params.long_asc_deg,
            omega=orbit_params.omega_deg,
            delta=orbit_params.inclination_deg,
            hp=orbit_params.perigee_alt_km,
            ha=orbit_params.apogee_alt_km,
            Mo=orbit_params.initial_mean_anomaly,
            model_time_as_random_variable=orbit_params.model_time_as_random_variable,
            t_min=orbit_params.t_min,
            t_max=orbit_params.t_max,
        )

    def _build_grid(self):
        min_lon, min_lat, max_lon, max_lat = self.brazil_geometry.bounds
        lon_pad = max(2.0, 0.05 * (max_lon - min_lon))
        lat_pad = max(2.0, 0.05 * (max_lat - min_lat))
        grid_lat = np.linspace(min_lat - lat_pad, max_lat + lat_pad, self.profile.grid_size)
        grid_lon = np.linspace(min_lon - lon_pad, max_lon + lon_pad, self.profile.grid_size)
        grid_points = [(lon, lat) for lat in grid_lat for lon in grid_lon]
        grid_xyz = np.array(
            [_latlon_to_ecef(lat_deg=lat, lon_deg=lon) for lon, lat in grid_points],
            dtype=float,
        )
        grid_norm = grid_xyz / np.linalg.norm(grid_xyz, axis=1)[:, None]
        brazil_mask = np.array(
            [self.brazil_geometry.contains(Point(lon, lat)) for lon, lat in grid_points],
            dtype=bool,
        )
        return grid_points, grid_norm, brazil_mask

    def build_simulation(self) -> dict:
        orbit_model = self._build_orbit_model()
        positions = orbit_model.get_satellite_positions_time_interval(
            interval_secs=self.profile.interval_secs,
            n_periods=self.profile.n_periods,
        )

        topology = self.parameters.imt.topology
        system = self.parameters.single_earth_station
        minimum_service_angle_deg = float(
            topology.mss_dc.beam_positioning.service_grid.minimum_service_angle
        )

        grid_points, _, brazil_mask = self._build_grid()
        brazil_indices = np.flatnonzero(brazil_mask)
        grid_lon = np.array([point[0] for point in grid_points], dtype=float)
        grid_lat = np.array([point[1] for point in grid_points], dtype=float)
        times = np.arange(positions["sx"].shape[1], dtype=float) * self.profile.interval_secs
        satellite_ids = [f"SAT-{index + 1:03d}" for index in range(positions["sx"].shape[0])]

        frames = []
        for frame_index, time_seconds in enumerate(times):
            sx = positions["sx"][:, frame_index]
            sy = positions["sy"][:, frame_index]
            sz = positions["sz"][:, frame_index]
            latitudes = positions["lat"][:, frame_index]
            longitudes = positions["lon"][:, frame_index]
            altitudes = positions["alt"][:, frame_index]

            elevations = calc_elevation(
                grid_lat[:, np.newaxis],
                latitudes[np.newaxis, :],
                grid_lon[:, np.newaxis],
                longitudes[np.newaxis, :],
                sat_height=altitudes[np.newaxis, :] * 1000.0,
                es_height=0.0,
            )
            best_satellite_index = np.argmax(elevations, axis=1)
            best_elevation = elevations[np.arange(len(grid_points)), best_satellite_index]
            grid_active = brazil_mask & (best_elevation >= minimum_service_angle_deg)
            satellite_cell_counts = np.bincount(
                best_satellite_index[grid_active],
                minlength=len(satellite_ids),
            )

            active_satellite_ids = []
            footprints = []
            satellites = []

            for sat_index, sat_id in enumerate(satellite_ids):
                assigned_mask = grid_active & (best_satellite_index == sat_index)
                covered_points = [
                    grid_points[i]
                    for i in range(len(grid_points))
                    if assigned_mask[i]
                ]

                covers_brazil = bool(satellite_cell_counts[sat_index] > 0)
                satellites.append(
                    {
                        "id": sat_id,
                        "lat": round(float(latitudes[sat_index]), 6),
                        "lon": round(float(longitudes[sat_index]), 6),
                        "altKm": round(float(altitudes[sat_index]), 3),
                        "active": covers_brazil,
                    }
                )

                if covers_brazil:
                    active_satellite_ids.append(sat_id)
                    sat_xyz = np.array([sx[sat_index], sy[sat_index], sz[sat_index]], dtype=float)
                    theta_service_raw = _service_central_angle_rad(
                        float(altitudes[sat_index]),
                        minimum_service_angle_deg,
                    )
                    footprints.append(
                        {
                            "satelliteId": sat_id,
                            "cellCount": int(satellite_cell_counts[sat_index]),
                            "grid": covered_points,
                        }
                    )
                    continue

                    sat_norm = np.linalg.norm(sat_xyz)

                    # Ã¢ngulo mÃ¡ximo visÃ­vel da Terra (horizonte)
                    theta_horizon = np.arccos(EARTH_RADIUS_KM / sat_norm)

                    # usa o menor entre serviÃ§o e horizonte
                    theta_service = min(theta_service_raw, theta_horizon)

                    ring = _footprint_ring(
                        sat_xyz,
                        central_angle_rad=theta_service,
                        n_points=self.profile.footprint_points,
                    )
                    try:
                        coords = [(lon, lat) for lon, lat, _ in ring]
                        poly = Polygon(coords)

                        if not poly.is_valid:
                            poly = poly.buffer(0)

                        clipped = poly.intersection(self.brazil_geometry)

                        rings = []

                        # âœ… CASO NORMAL
                        if not clipped.is_empty:
                            if clipped.geom_type == "Polygon":
                                rings.append([
                                    [round(lon, 6), round(lat, 6), 0.0]
                                    for lon, lat in clipped.exterior.coords
                                ])

                            elif clipped.geom_type == "MultiPolygon":
                                for p in clipped.geoms:
                                    rings.append([
                                        [round(lon, 6), round(lat, 6), 0.0]
                                        for lon, lat in p.exterior.coords
                                    ])

                        # FALLBACK INTELIGENTE
                        else:
                            inside_points = [
                                (lon, lat)
                                for lon, lat, _ in ring
                                if self.brazil_geometry.contains(Point(lon, lat))
                            ]

                            if inside_points:
                                rings.append([
                                    [round(lon, 6), round(lat, 6), 0.0]
                                    for lon, lat in inside_points
                                ])

                        if rings:
                            footprints.append(
                                {
                                    "satelliteId": sat_id,
                                    "rings": rings,
                                    "grid": covered_points,
                                }
                            )

                    except Exception:
                        # fallback (se der qualquer erro, usa footprint original)
                        footprints.append(
                            {
                                "satelliteId": sat_id,
                                "rings": [ring]
                            }
                        )


            active_weights = 0.0
            total_weights = 0.0
            for brazil_idx in brazil_indices:
                lat_rad = np.radians(grid_points[brazil_idx][1])
                weight = float(np.cos(lat_rad))
                total_weights += weight
                if grid_active[brazil_idx]:
                    active_weights += weight

            coverage_percent = 100.0 * active_weights / total_weights if total_weights else 0.0
            frames.append(
                {
                    "timeSeconds": round(float(time_seconds), 3),
                    "coveragePercent": round(float(coverage_percent), 3),
                    "activeSatelliteIds": active_satellite_ids,
                    "activeSatelliteCount": len(active_satellite_ids),
                    "satellites": satellites,
                    "footprints": footprints,
                }
            )

        station = {
            "lat": float(topology.central_latitude),
            "lon": float(topology.central_longitude),
            "altKm": float(topology.central_altitude) / 1000.0,
        }

        reference_altitude_km = float(np.mean(positions["alt"]))
        footprint_diameter_km = (
            2.0
            * EARTH_RADIUS_KM
            * _service_central_angle_rad(reference_altitude_km, minimum_service_angle_deg)
        )
        interference_active_min_elevation_deg = float(
            topology.mss_dc.sat_is_active_if.minimum_elevation_from_es
        )
        interference_active_footprint_diameter_km = (
            2.0
            * EARTH_RADIUS_KM
            * _service_central_angle_rad(
                reference_altitude_km,
                interference_active_min_elevation_deg,
            )
        )
        interference_path_footprint_diameter_km = (
            2.0
            * EARTH_RADIUS_KM
            * _service_central_angle_rad(reference_altitude_km, 0.0)
        )
        hex_radius_km = topology.mss_dc.beam_positioning.service_grid.beam_radius / 1000.0
        num_beams = int(topology.mss_dc.num_beams)
        footprint_ring_count = _hex_ring_count(num_beams)
        beam_center_spacing_km = np.sqrt(3.0) * hex_radius_km
        system4 = self.parameters.imt.bs.antenna.antenna_system_4
        antenna_high = system4.antenna_parameters_high
        antenna_low = system4.antenna_parameters_low
        antenna_7db_high_angle_deg = None
        antenna_7db_low_angle_deg = None
        antenna_7db_radius_km = None
        antenna_system4_high = None
        antenna_system4_low = None

        if antenna_high.antenna_3_dB_bw is not None and antenna_low.antenna_3_dB_bw is not None:
            antenna_7db_high_angle_deg = _s1528_relative_gain_angle_deg(
                antenna_3db_bw_deg=antenna_high.antenna_3_dB_bw,
                loss_db=7.0,
            )
            antenna_7db_low_angle_deg = _s1528_relative_gain_angle_deg(
                antenna_3db_bw_deg=antenna_low.antenna_3_dB_bw,
                loss_db=7.0,
            )
            antenna_7db_radius_km = hex_radius_km * (
                antenna_7db_high_angle_deg
                / (antenna_high.antenna_3_dB_bw / 2.0)
            )
            antenna_system4_high = {
                "gainDb": float(antenna_high.antenna_gain),
                "beamwidth3dbDeg": float(antenna_high.antenna_3_dB_bw),
                "nearSideLobeDb": float(antenna_high.antenna_l_s),
                "farSideLobeDb": float(antenna_high.far_out_side_lobe or 0.0),
            }
            antenna_system4_low = {
                "gainDb": float(antenna_low.antenna_gain),
                "beamwidth3dbDeg": float(antenna_low.antenna_3_dB_bw),
                "nearSideLobeDb": float(antenna_low.antenna_l_s),
                "farSideLobeDb": float(antenna_low.far_out_side_lobe or 0.0),
            }
        footprint_3db_radius_km = footprint_ring_count * beam_center_spacing_km + hex_radius_km
        footprint_7db_radius_km = (
            footprint_ring_count * beam_center_spacing_km + antenna_7db_radius_km
            if antenna_7db_radius_km is not None
            else None
        )
        # Calcula a margem de segurança em km (ex: 150 km)
        margin_km = topology.mss_dc.power_control_zones.zones[0].geometry.from_countries.margin_from_border
        # Calcula quantos hexágonos cabem nessa margem (ex: 150 / (24 * 2) = ~3.1 -> 3)
        guardband_hex_count = round(margin_km / (hex_radius_km * 2))
        # Ganho sem power backoff (ex: 30 dBi) e ganho com power backoff (ex: 20 dBi)
        gain_high = system.antenna.gain
        power_backoff_db = max(
            zone.power_backoff_db
            for zone in topology.mss_dc.power_control_zones.zones
        )
        gain_low = gain_high - power_backoff_db
        try:
            bs_azimuth_deg = float(system.geometry.azimuth.fixed)
        except Exception:
            bs_azimuth_deg = 90.0

        return {
            "meta": {
                "profile": self.profile.name,
                "intervalSeconds": self.profile.interval_secs,
                "frameCount": len(frames),
                "satelliteCount": len(satellite_ids),
                "paramFile": str(self.param_file),
                "serviceAreaCountryNames": self.country_names,
                "serviceAreaLabel": ", ".join(self.country_names),
                "beamRadiuskm": hex_radius_km,
                "footprintDiameterKm": round(float(footprint_diameter_km), 6),
                "serviceFootprintDiameterKm": round(float(footprint_diameter_km), 6),
                "interferenceActiveFootprintDiameterKm": round(
                    float(interference_active_footprint_diameter_km),
                    6,
                ),
                "interferencePathFootprintDiameterKm": round(
                    float(interference_path_footprint_diameter_km),
                    6,
                ),
                "numBeams": num_beams,
                "footprintRingCount": footprint_ring_count,
                "footprint3dbRadiusKm": round(float(footprint_3db_radius_km), 6),
                "footprint7dbRadiusKm": _round_or_none(footprint_7db_radius_km),
                "antenna7dbRadiusKm": _round_or_none(antenna_7db_radius_km),
                "antenna7dbHighAngleDeg": _round_or_none(antenna_7db_high_angle_deg),
                "antenna7dbLowAngleDeg": _round_or_none(antenna_7db_low_angle_deg),
                "minimumServiceAngleDeg": minimum_service_angle_deg,
                "guardbandHexCount": guardband_hex_count,
                "antennaGainHigh": gain_high,
                "antennaGainLow": gain_low,
                "powerBackoffDb": power_backoff_db,
                "sharcInterferencePathMinElevationDeg": 0.0,
                "sharcInterferenceActiveMinElevationDeg": interference_active_min_elevation_deg,
                "enableCochannel": bool(self.parameters.general.enable_cochannel),
                "enableAdjacentChannel": bool(self.parameters.general.enable_adjacent_channel),
                "imtFrequencyMHz": float(self.parameters.imt.frequency),
                "imtBandwidthMHz": float(self.parameters.imt.bandwidth),
                "imtConductedPowerDbm": float(self.parameters.imt.bs.conducted_power),
                "imtBsOhmicLossDb": float(self.parameters.imt.bs.ohmic_loss),
                "imtAdjacentChEmissions": self.parameters.imt.adjacent_ch_emissions,
                "imtAdjacentChLeakRatioDb": float(self.parameters.imt.bs.adjacent_ch_leak_ratio),
                "singleEarthStationGainDb": float(system.antenna.gain),
                "singleEarthStationFrequencyMHz": float(system.frequency),
                "singleEarthStationBandwidthMHz": float(system.bandwidth),
                "singleEarthStationAdjacentChReception": system.adjacent_ch_reception,
                "singleEarthStationAdjacentChSelectivityDb": (
                    float(system.adjacent_ch_selectivity)
                    if system.adjacent_ch_selectivity is not None
                    else None
                ),
                "polarizationLossDb": float(system.polarization_loss or 0.0),
                "bsAzimuthDeg": bs_azimuth_deg,
                "antennaSystem4High": antenna_system4_high,
                "antennaSystem4Low": antenna_system4_low,
            },
            "station": station,
            "satelliteIds": satellite_ids,
            "brazilGeoJson": mapping(self.brazil_geometry.simplify(0.05, preserve_topology=True)),
            "frames": frames,
        }


def build_simulation(profile: str = "fast", param_file: str | Path | None = None) -> dict:
    return OrbitSimulationBackend(profile=profile, param_file=param_file).build_simulation()

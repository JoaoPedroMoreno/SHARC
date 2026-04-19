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
}


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_param_file() -> Path:
    return _package_root() / "campaigns" / "01_DC_MSS_to_EESS" / "Script" / "Base.yaml"


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


def _load_brazil_geometry():
    try:
        shp_path = shapereader.natural_earth(
            resolution="110m",
            category="cultural",
            name="admin_0_countries",
        )
        countries = gpd.read_file(shp_path)
        brazil = countries[countries["ADMIN"] == "Brazil"].geometry
        if not brazil.empty:
            return unary_union(brazil.tolist())
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
        self.param_file = Path(param_file) if param_file else default_param_file()
        self.parameters = self._load_parameters()
        self.brazil_geometry = _load_brazil_geometry()

    def _load_parameters(self) -> Parameters:
        parameters = Parameters()
        parameters.set_file_name(str(self.param_file))
        parameters.read_params()
        return parameters

    def _build_orbit_model(self) -> OrbitModel:
        orbit_params = self.parameters.mss_d2d.orbits[0]
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
        grid_lat = np.linspace(-35, 5, self.profile.grid_size)
        grid_lon = np.linspace(-75, -30, self.profile.grid_size)
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
        theta_min = np.radians(
            topology.mss_dc.beam_positioning.service_grid.minimum_service_angle
        )
        # ConversÃ£o correta: Ã¢ngulo de cobertura na Terra considerando limite fisico de visibilidade (horizonte)
        theta_service_raw = (np.pi / 2) - theta_min

        grid_points, grid_norm, brazil_mask = self._build_grid()
        brazil_indices = np.flatnonzero(brazil_mask)
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

            grid_active = np.zeros(len(grid_points), dtype=bool)
            active_satellite_ids = []
            footprints = []
            satellites = []

            for sat_index, sat_id in enumerate(satellite_ids):
                sat_xyz = np.array([sx[sat_index], sy[sat_index], sz[sat_index]], dtype=float)
                sat_radius = np.linalg.norm(sat_xyz)
                nadir = sat_xyz / sat_radius
                theta = np.arccos(np.clip(grid_norm @ nadir, -1.0, 1.0))
                sat_norm = np.linalg.norm(sat_xyz)
                theta_horizon = np.arccos(EARTH_RADIUS_KM / sat_norm)

                theta_service = min(theta_service_raw, theta_horizon)

                coverage = theta <= theta_service
                covered_points = [
                grid_points[i]
                    for i in range(len(grid_points))
                    if coverage[i] and brazil_mask[i]
                    ]
                grid_active |= coverage

                covers_brazil = bool(np.any(coverage & brazil_mask))
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

        return {
            "meta": {
                "profile": self.profile.name,
                "intervalSeconds": self.profile.interval_secs,
                "frameCount": len(frames),
                "satelliteCount": len(satellite_ids),
                "paramFile": str(self.param_file),
                "beamRadiusMeters": float(
                    topology.mss_dc.beam_positioning.service_grid.beam_radius
                ),
            },
            "station": station,
            "satelliteIds": satellite_ids,
            "brazilGeoJson": mapping(self.brazil_geometry.simplify(0.05, preserve_topology=True)),
            "frames": frames,
        }


def build_simulation(profile: str = "fast", param_file: str | Path | None = None) -> dict:
    return OrbitSimulationBackend(profile=profile, param_file=param_file).build_simulation()

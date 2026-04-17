"""Implements a Space Station Orbit model as described in Rec. ITU-R S.1325-3
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Point

from sharc.satellite.ngso.constants import (EARTH_RADIUS_KM,
                                            EARTH_ROTATION_RATE, KEPLER_CONST)
from sharc.satellite.ngso.custom_functions import (eccentric_anomaly, eci2ecef,
                                                   keplerian2eci, wrap2pi)


class OrbitModel():
    """Orbit Model for satellite positions."""

    def __init__(self,
                 Nsp: int,
                 Np: int,
                 phasing: float,
                 long_asc: float,
                 omega: float,
                 delta: float,
                 hp: float,
                 ha: float,
                 Mo: float,
                 *,
                 model_time_as_random_variable: bool,
                 t_min: float,
                 t_max: float | None
             ):
        """Instantiates and OrbitModel object from the Orbit parameters as specified in S.1529.

        Parameters
        ----------
        Nsp : int
            number of satellites in the orbital plane (A.4.b.4.b)
        Np : int
            number of orbital planes (A.4.b.2)
        phasing : float
            satellite phasing between planes, in degrees
        long_asc : float
            initial longitude of ascending node of the first plane, in degrees
        omega : float
            argument of perigee, in degrees
        delta : float
            orbital plane inclination, in degrees
        perigee_alt_km : float
            altitude of perigee in km
        ha : float
            altitude of apogee in km
        Mo : float
            initial mean anomaly for first satellite of first plane, in degrees
        model_time_as_random_variable: bool
            whether get_orbit_positions_random will use only time as random variable
        t_min: float
            if model_time_as_random_variable == True,
            defines the lower bound of the time distribution
        t_max: float
            if model_time_as_random_variable == True,
            defines the upper bound of the time distribution
        """
        self.Nsp = Nsp
        self.Np = Np
        self.phasing = phasing
        self.long_asc = long_asc
        self.omega_0 = omega
        self.omega = omega
        self.delta = delta
        self.perigee_alt_km = hp
        self.apogee_alt_km = ha
        self.Mo = Mo

        # Derive other orbit parameters
        self.semi_major_axis = (
            hp + ha + 2 * EARTH_RADIUS_KM) / 2  # semi-major axis, in km
        self.eccentricity = (ha + EARTH_RADIUS_KM - self.semi_major_axis) / \
            self.semi_major_axis  # orbital eccentricity (e)
        # TODO: consider J2 perturbations for mean motion and orbital period
        self.mean_motion = np.sqrt(KEPLER_CONST / self.semi_major_axis ** 3)
        # orbital period, in seconds
        self.orbital_period_sec = 2 * np.pi / self.mean_motion
        # satellite separation angle in the plane (degrees)
        self.sat_sep_angle_deg = 360 / self.Nsp
        # angle between plane intersections with the equatorial plane (degrees)
        self.orbital_plane_spacing = 360 / self.Np

        # Initial mean anomalies for all the satellites
        initial_mean_anomalies_deg = (
            Mo + np.arange(Nsp) * self.sat_sep_angle_deg + np.arange(
                self.Np)[
                :,
                np.newaxis] * self.phasing) % 360
        self.initial_mean_anomalies_rad = np.radians(
            initial_mean_anomalies_deg.flatten())

        # Initial longitudes of ascending node for all the planes
        inital_raan = (self.long_asc * np.ones(self.Nsp) + np.arange(self.Np)
                       [:, np.newaxis] * self.orbital_plane_spacing) % 360
        self.inital_raan_rad = np.radians(inital_raan.flatten())

        self.model_time_as_random_variable = model_time_as_random_variable
        self.t_min = t_min

        if t_max is not None:
            self.t_max = t_max
        else:
            # sane default
            self.t_max = t_min + self.orbital_period_sec * 1e3
            # TODO: implement 1503 secular drift to enable correct higher time ceiling
            # self.t_max = t_min + 365 * 24 * 60 * 60
            # self.t_max = sys.float_info.max

        # Calculated variables
        self.mean_anomaly = None  # computed mean anomalies
        self.raan_rad = None  # computed longitudes of the ascending node
        self.eccentric_anomaly = None  # computed eccentric anomalies
        self.true_anomaly = None  # computed true anomalies
        self.distance = None  # computed distance to Earth's center
        # computed true anomaly relative to the line of nodes
        self.true_anomaly_rel_line_nodes = None

    def get_satellite_positions_time_interval(
            self,
            initial_time_secs=0,
            interval_secs=5,
            n_periods=4) -> dict:
        """
        Return the orbit positions vector.

        Parameters
        ----------
        initial_time_secs : int, optional
            initial time instant in seconds, by default 0
        interval_secs : int, optional
            time interval between points, by default 5
        n_periods : int, optional
            number of orbital peridos, by default 4

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, sx, sy, sz
        """
        t = np.arange(
            initial_time_secs,
            n_periods *
            self.orbital_period_sec +
            interval_secs,
            interval_secs)
        return self.get_orbit_positions_time_instant(t)

    def get_orbit_positions_time_instant(self, time_instant_secs=0) -> dict:
        """Returns the Satellite positins for a given time vector within the orbit period.

        Parameters
        ----------
        time_instant_secs: np.array
            time instants inside the orbit period in seconds

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, alt, sx, sy, sz
        """
        t = np.atleast_1d(time_instant_secs)

        assert t.ndim == 1, "Input must be scalar or 1D array"

        # TODO: add J2 perturbations based on 1503
        # Mean anomaly (M)
        self.mean_anomaly = (
            self.initial_mean_anomalies_rad[:, None] + self.mean_motion * t
        ) % (2 * np.pi)

        # TODO: add J2 perturbations based on 1503
        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        self.raan_rad = self.inital_raan_rad[:, None]

        # TODO: add J2 perturbations based on 1503
        # perigee argument
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        # The time to be used for calculation of Earth's rotation angle
        earth_rotated_t = t

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def get_orbit_positions_random(
            self,
            rng: np.random.RandomState,
            n_samples=1) -> dict:
        """Returns satellite positions in a random time instant in seconds.
                Parameters
                ----------
                rng : np.random.RandomState
                    Random number generator for reproducibility
                n_samples : int
                    Number of random samples to generate, by default 1
                Returns
                -------
                dict
                    A dictionary with satellite positions in spherical and ecef coordinates.
                        lat, lon, sx, sy, sz
        """
        if self.model_time_as_random_variable:
            return self.get_orbit_positions_time_instant(
                self.t_min + (self.t_max - self.t_min) * rng.random_sample(n_samples)
            )
        # Mean anomaly (M)
        self.mean_anomaly = (self.initial_mean_anomalies_rad[:, None] +
                             2 * np.pi * rng.random_sample(n_samples)) % (2 * np.pi)

        # just selecting a random earth rotation for later coordinate transformation
        earth_rotated_t = 2 * np.pi * rng.random_sample(n_samples) / EARTH_ROTATION_RATE

        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        # FIXME: previous implementation, due to unexpected behavior, did not
        # use the drawn random samples. Choose whether to maintain behavior
        # self.raan_rad = (self.inital_raan_rad[:, None] +
        #             2 * np.pi * rng.random_sample(n_samples))
        self.raan_rad = self.inital_raan_rad[:, None]

        # perigee argument
        # NOTE: using fixed perigee argument for circular orbits always make sense
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def __get_satellite_positions_from_angles(
        self,
        mean_anomaly: np.ndarray,
        raan_rad: np.ndarray,
        omega_rad: np.array,
        earth_rotated_t: np.ndarray,
    ):
        """
        mean_anomaly:
            Mean anomaly (M)
        raan_rad: np.ndarray
            Longitudes of the ascending node (OmegaG)
        omega_rad: np.ndarray
            Perigee argument
            NOTE: doesn't matter for circular orbits
        earth_rotated_t:
            The time to be used for calculation of Earth's rotation angle
        """
        assert (raan_rad.shape == (self.Np * self.Nsp, len(earth_rotated_t))) or (
            raan_rad.shape == (self.Np * self.Nsp, 1)
        )

        # Eccentric anomaly (E)
        self.eccentric_anom = eccentric_anomaly(
            self.eccentricity, mean_anomaly)

        # True anomaly (v)
        self.true_anomaly = 2 * np.arctan(np.sqrt((1 + self.eccentricity) / (
            1 - self.eccentricity)) * np.tan(self.eccentric_anom / 2))

        self.true_anomaly = np.mod(self.true_anomaly, 2 * np.pi)

        # Distance of the satellite to Earth's center (r)
        r = self.semi_major_axis * \
            (1 - self.eccentricity ** 2) / (1 + self.eccentricity * np.cos(self.true_anomaly))

        # True anomaly relative to the line of nodes (gamma)
        self.true_anomaly_rel_line_nodes = wrap2pi(
            self.true_anomaly +
            omega_rad)  # gamma in the interval [-pi, pi]

        # Latitudes of the satellites, in radians (theta)
        # theta = np.arcsin(np.sin(gamma) * np.sin(np.radians(self.delta)))

        # Longitude variation due to angular displacement, in radians (phiS)
        # phiS = np.arccos(np.cos(gamma) / np.cos(theta)) * np.sign(gamma)

        raan_rad = wrap2pi(raan_rad)

        # POSITION CALCULATION IN ECEF COORDINATES - ITU-R S.1503
        r_eci = keplerian2eci(self.semi_major_axis,
                              self.eccentricity,
                              self.delta,
                              np.degrees(raan_rad),
                              np.degrees(omega_rad),
                              np.degrees(self.true_anomaly))

        r_ecef = eci2ecef(earth_rotated_t, r_eci)
        sx, sy, sz = r_ecef[0], r_ecef[1], r_ecef[2]
        lat = np.degrees(np.arcsin(sz / r))
        lon = np.degrees(np.arctan2(sy, sx))
        # (lat, lon, _) = ecef2lla(sx, sy, sz)

        pos_vector = {
            'lat': lat,
            'lon': lon,
            'alt': r - EARTH_RADIUS_KM,
            'sx': sx,
            'sy': sy,
            'sz': sz
        }
        return pos_vector

import plotly.graph_objects as go
import geopandas as gpd

EARTH_RADIUS = 6371

# Alternar entre "fast" e "high_quality" sem editar o restante do script.
RENDER_PROFILE = "fast"

RENDER_PROFILES = {
    "fast": {
        "interval_secs": 30,
        "grid_size": 36,
        "footprint_points": 60,
        "video_fps": 20,
        "video_width": 960,
        "video_height": 544,
        "texture_max_width": 360,
    },
    "high_quality": {
        "interval_secs": 10,
        "grid_size": 60,
        "footprint_points": 120,
        "video_fps": 24,
        "video_width": 1280,
        "video_height": 720,
        "texture_max_width": 720,
    },
}

if RENDER_PROFILE not in RENDER_PROFILES:
    raise ValueError(
        f"RENDER_PROFILE invalido: {RENDER_PROFILE}. "
        f"Use um destes: {', '.join(RENDER_PROFILES)}"
    )

PROFILE = RENDER_PROFILES[RENDER_PROFILE]
DEFAULT_INTERVAL_SECS = PROFILE["interval_secs"]
DEFAULT_GRID_SIZE = PROFILE["grid_size"]
DEFAULT_FOOTPRINT_POINTS = PROFILE["footprint_points"]
DEFAULT_VIDEO_FPS = PROFILE["video_fps"]
DEFAULT_VIDEO_WIDTH = PROFILE["video_width"]
DEFAULT_VIDEO_HEIGHT = PROFILE["video_height"]
DEFAULT_TEXTURE_MAX_WIDTH = PROFILE["texture_max_width"]

def latlon_to_ecef(lat, lon, r=EARTH_RADIUS):
    x = r * np.cos(lat) * np.cos(lon)
    y = r * np.cos(lat) * np.sin(lon)
    z = r * np.sin(lat)
    return x, y, z

def ecef_to_latlon(x, y, z):
    r = np.sqrt(x**2 + y**2 + z**2)
    lat = np.arcsin(z / r)
    lon = np.arctan2(y, x)
    return lat, lon

def _find_earth_texture() -> Path:
    spec = importlib.util.find_spec("cartopy")

    candidates = []
    if spec and spec.submodule_search_locations:
        cartopy_dir = Path(next(iter(spec.submodule_search_locations)))
        candidates.append(
            cartopy_dir / "data" / "raster" / "natural_earth" / "50-natural-earth-1-downsampled.png"
        )

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(
        repo_root / ".venv" / "Lib" / "site-packages" / "cartopy" / "data"
        / "raster" / "natural_earth" / "50-natural-earth-1-downsampled.png"
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Nao foi possivel localizar a textura da Terra do Natural Earth."
    )


def _build_texture_colorscale(texture_rgb: np.ndarray):
    palette_img = Image.fromarray(texture_rgb).convert(
        "P", palette=Image.Palette.ADAPTIVE, colors=256
    )
    palette = np.array(palette_img.getpalette()[: 256 * 3], dtype=np.uint8).reshape(-1, 3)
    texture_idx = np.asarray(palette_img, dtype=np.float32)

    colorscale = []
    for idx, (red, green, blue) in enumerate(palette):
        position = idx / 255 if len(palette) > 1 else 0
        colorscale.append([position, f"rgb({red},{green},{blue})"])

    return texture_idx, colorscale


def criar_terra():
    texture_img = Image.open(_find_earth_texture()).convert("RGB")
    if texture_img.width > DEFAULT_TEXTURE_MAX_WIDTH:
        texture_img = texture_img.resize(
            (
                DEFAULT_TEXTURE_MAX_WIDTH,
                max(2, round(texture_img.height * DEFAULT_TEXTURE_MAX_WIDTH / texture_img.width)),
            ),
            Image.Resampling.BILINEAR,
        )

    texture = np.asarray(texture_img)
    # O raster vem em [-180, 180]; deslocamos para alinhar o meridiano de Greenwich.
    texture = np.roll(texture, shift=texture.shape[1] // 2, axis=1)
    texture = np.concatenate([texture, texture[:, :1, :]], axis=1)

    n_lat, n_lon = texture.shape[:2]
    lon = np.linspace(0, 2 * np.pi, n_lon)
    colat = np.linspace(0, np.pi, n_lat)

    x = (EARTH_RADIUS * np.outer(np.cos(lon), np.sin(colat))).T
    y = (EARTH_RADIUS * np.outer(np.sin(lon), np.sin(colat))).T
    z = (EARTH_RADIUS * np.outer(np.ones_like(lon), np.cos(colat))).T

    surfacecolor, colorscale = _build_texture_colorscale(texture)

    return go.Surface(
        x=x,
        y=y,
        z=z,
        surfacecolor=surfacecolor,
        cmin=0,
        cmax=255,
        colorscale=colorscale,
        opacity=1.0,
        showscale=False,
        hoverinfo="skip",
        lighting=dict(ambient=0.9, diffuse=0.7, specular=0.05, roughness=0.95),
    )


def _orthonormal_basis(unit_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    reference = np.array([0.0, 0.0, 1.0])
    if np.abs(np.dot(unit_vector, reference)) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])

    tangent_1 = np.cross(unit_vector, reference)
    tangent_1 /= np.linalg.norm(tangent_1)
    tangent_2 = np.cross(unit_vector, tangent_1)
    tangent_2 /= np.linalg.norm(tangent_2)
    return tangent_1, tangent_2


def _footprint_circle(
    sat_xyz: np.ndarray,
    central_angle_rad: float,
    n_points: int = DEFAULT_FOOTPRINT_POINTS,
) -> np.ndarray:
    nadir = sat_xyz / np.linalg.norm(sat_xyz)
    tangent_1, tangent_2 = _orthonormal_basis(nadir)
    angles = np.linspace(0.0, 2.0 * np.pi, n_points)

    return EARTH_RADIUS * (
        np.cos(central_angle_rad) * nadir[None, :]
        + np.sin(central_angle_rad) * (
            np.cos(angles)[:, None] * tangent_1[None, :]
            + np.sin(angles)[:, None] * tangent_2[None, :]
        )
    )


def _footprints_trace(footprints: list[np.ndarray]) -> go.Scatter3d:
    if not footprints:
        return go.Scatter3d(
            x=[],
            y=[],
            z=[],
            mode="lines",
            line=dict(color="#00FFFF", width=4),
            name="Footprints",
            hoverinfo="skip",
        )

    x_values, y_values, z_values = [], [], []
    for footprint in footprints:
        x_values.extend(footprint[:, 0].tolist() + [None])
        y_values.extend(footprint[:, 1].tolist() + [None])
        z_values.extend(footprint[:, 2].tolist() + [None])

    return go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode="lines",
        line=dict(color="#00FFFF", width=4),
        name="Footprints",
        hoverinfo="skip",
    )


def _build_dynamic_traces(
    all_sat_xyz: np.ndarray,
    active_sat_xyz: np.ndarray,
    coverage_xyz: np.ndarray,
    active_footprints: list[np.ndarray],
) -> list:
    return [
        go.Scatter3d(
            x=all_sat_xyz[:, 0], y=all_sat_xyz[:, 1], z=all_sat_xyz[:, 2],
            mode='markers',
            marker=dict(size=3, color='#B084F5', opacity=0.9),
            name="Satélites",
            hoverinfo="skip"
        ),
        go.Scatter3d(
            x=active_sat_xyz[:, 0] if len(active_sat_xyz) else [],
            y=active_sat_xyz[:, 1] if len(active_sat_xyz) else [],
            z=active_sat_xyz[:, 2] if len(active_sat_xyz) else [],
            mode='markers',
            marker=dict(size=7, color='#00FF7F', line=dict(color='white', width=1)),
            name="Satélites cobrindo o Brasil",
            hoverinfo="skip"
        ),
        go.Scatter3d(
            x=coverage_xyz[:, 0] if len(coverage_xyz) else [],
            y=coverage_xyz[:, 1] if len(coverage_xyz) else [],
            z=coverage_xyz[:, 2] if len(coverage_xyz) else [],
            mode='markers',
            marker=dict(size=2, color='cyan', opacity=0.75),
            name="Cobertura",
            hoverinfo="skip"
        ),
        _footprints_trace(active_footprints),
    ]


def _build_inset_chart_svg(cobertura_percentual: list[float], width: int = 320, height: int = 180) -> str:
    left_pad, right_pad = 34, 10
    top_pad, bottom_pad = 14, 24
    plot_width = width - left_pad - right_pad
    plot_height = height - top_pad - bottom_pad

    values = np.asarray(cobertura_percentual, dtype=float)
    if len(values) == 0:
        values = np.array([0.0])

    x_coords = left_pad + np.linspace(0, plot_width, len(values))
    y_coords = top_pad + (1.0 - values / 100.0) * plot_height
    path_data = " ".join(
        f"{'M' if idx == 0 else 'L'} {x:.2f} {y:.2f}"
        for idx, (x, y) in enumerate(zip(x_coords, y_coords))
    )

    guide_lines = []
    for percent in (0, 50, 100):
        y = top_pad + (1.0 - percent / 100.0) * plot_height
        guide_lines.append(
            f"<line x1='{left_pad}' y1='{y:.2f}' x2='{left_pad + plot_width}' y2='{y:.2f}' "
            "stroke='rgba(255,255,255,0.16)' stroke-width='1'/>"
        )
        guide_lines.append(
            f"<text x='{left_pad - 6}' y='{y + 4:.2f}' fill='white' font-size='11' "
            "text-anchor='end'>{percent}%</text>"
        )

    return f"""
<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="{width}" height="{height}" rx="14" fill="rgba(0,0,0,0.72)" stroke="rgba(255,255,255,0.16)"/>
  <text x="{left_pad}" y="16" fill="white" font-size="12" font-weight="600">Cobertura do Brasil</text>
  {''.join(guide_lines)}
  <path d="{path_data}" fill="none" stroke="#00e5ff" stroke-width="3" stroke-linecap="round"/>
  <line id="coverage-cursor" x1="{left_pad}" y1="{top_pad}" x2="{left_pad}" y2="{top_pad + plot_height}" stroke="#7cffb2" stroke-width="2"/>
  <circle id="coverage-dot" cx="{x_coords[0]:.2f}" cy="{y_coords[0]:.2f}" r="4" fill="#7cffb2" stroke="white" stroke-width="1"/>
</svg>
""".strip()


def _write_interactive_viewer_html(
    html_path: Path,
    earth_trace: go.Surface,
    frame_payloads: list[dict],
    cobertura_percentual: list[float],
) -> None:
    html_path.parent.mkdir(parents=True, exist_ok=True)

    earth_trace_json = earth_trace.to_plotly_json()
    frames_json = [
        [trace.to_plotly_json() for trace in _build_dynamic_traces(**payload)]
        for payload in frame_payloads
    ]
    layout_json = {
        "paper_bgcolor": "black",
        "plot_bgcolor": "black",
        "font": {"color": "white"},
        "uirevision": "earth-view",
        "showlegend": True,
        "legend": {
            "bgcolor": "rgba(0,0,0,0.35)",
            "font": {"color": "white"},
        },
        "margin": {"l": 0, "r": 0, "t": 48, "b": 0},
        "title": {
            "text": "Cobertura Satelital sobre o Brasil",
            "font": {"color": "white"},
        },
        "scene": {
            "xaxis": {"visible": False, "showbackground": False},
            "yaxis": {"visible": False, "showbackground": False},
            "zaxis": {"visible": False, "showbackground": False},
            "bgcolor": "black",
            "aspectmode": "data",
            "camera": {"eye": {"x": -1.6, "y": -1.8, "z": 1.0}},
        },
    }

    svg_chart = _build_inset_chart_svg(cobertura_percentual)
    earth_json = json.dumps(earth_trace_json)
    frames_json_str = json.dumps(frames_json)
    layout_json_str = json.dumps(layout_json)
    coverage_json = json.dumps([round(value, 4) for value in cobertura_percentual])

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cobertura Satelital sobre o Brasil</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #000;
      color: white;
      font-family: "Segoe UI", sans-serif;
    }}
    .viewer {{
      position: relative;
      width: min(96vw, 1280px);
      margin: 16px auto;
      border: 1px solid rgba(255,255,255,0.12);
      box-shadow: 0 24px 60px rgba(0,0,0,0.45);
      background: #000;
      overflow: hidden;
    }}
    #plot {{
      width: 100%;
      height: min(78vw, 820px);
    }}
    .hud {{
      position: absolute;
      right: 18px;
      bottom: 88px;
      display: grid;
      gap: 8px;
      pointer-events: none;
    }}
    .badge {{
      justify-self: end;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(0,0,0,0.72);
      border: 1px solid rgba(255,255,255,0.16);
      font-size: 12px;
      font-weight: 600;
    }}
    .chart {{
      width: min(34vw, 320px);
      max-width: 320px;
    }}
    .controls {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 12px 16px 16px;
      background: rgba(0,0,0,0.88);
      border-top: 1px solid rgba(255,255,255,0.08);
    }}
    button {{
      background: #111;
      color: white;
      border: 1px solid #444;
      border-radius: 8px;
      padding: 8px 14px;
      cursor: pointer;
    }}
    input[type="range"] {{
      width: 100%;
    }}
    .frame-label {{
      min-width: 88px;
      text-align: right;
      font-size: 12px;
      color: rgba(255,255,255,0.84);
    }}
  </style>
</head>
<body>
  <div class="viewer">
    <div id="plot"></div>
    <div class="hud">
      <div class="badge" id="coverage-label">Cobertura: --%</div>
      <div class="chart">
        {svg_chart}
      </div>
    </div>
    <div class="controls">
      <button id="play-btn" type="button">Play</button>
      <input id="frame-slider" type="range" min="0" max="{max(0, len(frame_payloads) - 1)}" value="0" step="1" />
      <div class="frame-label" id="frame-label">Frame 1/{max(1, len(frame_payloads))}</div>
    </div>
  </div>
  <script>
    const earthTrace = {earth_json};
    const frames = {frames_json_str};
    const coverage = {coverage_json};
    const layout = {layout_json_str};
    const plotDiv = document.getElementById("plot");
    const slider = document.getElementById("frame-slider");
    const playBtn = document.getElementById("play-btn");
    const frameLabel = document.getElementById("frame-label");
    const coverageLabel = document.getElementById("coverage-label");
    const cursor = document.getElementById("coverage-cursor");
    const dot = document.getElementById("coverage-dot");
    const leftPad = 34;
    const topPad = 14;
    const plotWidth = 320 - 34 - 10;
    const plotHeight = 180 - 14 - 24;
    let playing = false;
    let timerId = null;

    function updateHud(frameIndex) {{
      const value = coverage[frameIndex] ?? 0;
      const x = leftPad + (plotWidth * frameIndex) / Math.max(1, coverage.length - 1);
      const y = topPad + (1 - value / 100) * plotHeight;
      cursor.setAttribute("x1", x.toFixed(2));
      cursor.setAttribute("x2", x.toFixed(2));
      dot.setAttribute("cx", x.toFixed(2));
      dot.setAttribute("cy", y.toFixed(2));
      coverageLabel.textContent = `Cobertura: ${{value.toFixed(1)}}%`;
      frameLabel.textContent = `Frame ${{frameIndex + 1}}/${{frames.length}}`;
    }}

    function renderFrame(frameIndex) {{
      const data = [earthTrace, ...frames[frameIndex]];
      Plotly.react(plotDiv, data, layout, {{
        responsive: true,
        displaylogo: false,
        scrollZoom: true
      }});
      updateHud(frameIndex);
    }}

    function stopPlayback() {{
      playing = false;
      playBtn.textContent = "Play";
      if (timerId !== null) {{
        clearInterval(timerId);
        timerId = null;
      }}
    }}

    function startPlayback() {{
      stopPlayback();
      playing = true;
      playBtn.textContent = "Pause";
      timerId = setInterval(() => {{
        const next = (Number(slider.value) + 1) % frames.length;
        slider.value = String(next);
        renderFrame(next);
      }}, {max(40, int(1000 / max(1, DEFAULT_VIDEO_FPS)))});
    }}

    slider.addEventListener("input", () => {{
      stopPlayback();
      renderFrame(Number(slider.value));
    }});

    playBtn.addEventListener("click", () => {{
      if (playing) {{
        stopPlayback();
      }} else {{
        startPlayback();
      }}
    }});

    renderFrame(0);
  </script>
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")

def main():

    def latlon_to_ecef(lat, lon, r=EARTH_RADIUS):
        x = r * np.cos(lat) * np.cos(lon)
        y = r * np.cos(lat) * np.sin(lon)
        z = r * np.sin(lat)
        return np.array([x, y, z])

    def ecef_to_latlon(x, y, z):
        r = np.sqrt(x**2 + y**2 + z**2)
        lat = np.arcsin(z / r)
        lon = np.arctan2(y, x)
        return lat, lon

    # =========================
    # SHARC
    # =========================
    from sharc.parameters.parameters import Parameters

    param_file = r"C:\GitHub\SHARC\sharc\campaigns\01_DC_MSS_to_EESS\Script\Base.yaml"

    parameters = Parameters()
    parameters.set_file_name(param_file)
    parameters.read_params()

    orbit_model_params = parameters.mss_d2d.orbits[0]

    orbit_model = OrbitModel(
        Nsp=orbit_model_params.sats_per_plane,
        Np=orbit_model_params.n_planes,
        phasing=orbit_model_params.phasing_deg,
        long_asc=orbit_model_params.long_asc_deg,
        omega=orbit_model_params.omega_deg,
        delta=orbit_model_params.inclination_deg,
        hp=orbit_model_params.perigee_alt_km,
        ha=orbit_model_params.apogee_alt_km,
        Mo=orbit_model_params.initial_mean_anomaly,
        model_time_as_random_variable=orbit_model_params.model_time_as_random_variable,
        t_min=orbit_model_params.t_min,
        t_max=orbit_model_params.t_max,
    )

    positions = orbit_model.get_satellite_positions_time_interval(
        interval_secs=DEFAULT_INTERVAL_SECS,
        n_periods=1,
    )

    # =========================
    # BRASIL
    # =========================
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    world = gpd.read_file(url)
    brasil = world[world['NAME'] == "Brazil"].geometry.values[0]

    # =========================
    # GRID
    # =========================
    grid_lat = np.linspace(-35, 5, DEFAULT_GRID_SIZE)
    grid_lon = np.linspace(-75, -30, DEFAULT_GRID_SIZE)

    grid_points = [(lon, lat) for lat in grid_lat for lon in grid_lon]

    # pré-cálculo ECEF
    grid_xyz = np.array([
        latlon_to_ecef(np.radians(lat), np.radians(lon))
        for lon, lat in grid_points
    ])

    grid_norm = grid_xyz / np.linalg.norm(grid_xyz, axis=1)[:, None]

    # pontos do Brasil
    brasil_mask = np.array([
        brasil.contains(Point(lon, lat))
        for lon, lat in grid_points
    ], dtype=bool)
    indices_brasil = np.flatnonzero(brasil_mask)

    print(f"Pontos no Brasil: {len(indices_brasil)}")

    # =========================
    # PARÂMETRO FÍSICO REAL
    # =========================
    theta_service = np.radians(
        parameters.imt.topology.mss_dc.beam_positioning.service_grid.minimum_service_angle
    )

    # =========================
    # ANIMAÇÃO
    # =========================
    frame_payloads = []
    cobertura_percentual = []

    num_frames = positions["sx"].shape[1]
    print(
        f"Gerando {num_frames} frames com interval_secs={DEFAULT_INTERVAL_SECS}s, "
        f"grid={DEFAULT_GRID_SIZE}x{DEFAULT_GRID_SIZE}."
    )

    for t in range(num_frames):

        if t % 50 == 0:
            print(f"Frame {t}/{num_frames}")

        sx = positions["sx"][:, t]
        sy = positions["sy"][:, t]
        sz = positions["sz"][:, t]

        grid_ativos = np.zeros(len(grid_points), dtype=bool)

        all_sat_xyz = np.column_stack((sx, sy, sz))
        active_sat_xyz = []
        active_footprints = []

        for i in range(len(sx)):

            sat = np.array([sx[i], sy[i], sz[i]])
            Rs = np.linalg.norm(sat)

            nadir = sat / Rs

            # vetorizar cobertura
            cos_theta = grid_norm @ nadir
            theta = np.arccos(np.clip(cos_theta, -1, 1))

            cobertura = theta <= theta_service
            grid_ativos |= cobertura

            cobre_brasil = np.any(cobertura & brasil_mask)
            if cobre_brasil:
                active_sat_xyz.append(sat)
                active_footprints.append(_footprint_circle(sat, theta_service))

        # =========================
        # COBERTURA PONDERADA
        # =========================
        ativos = 0
        total = 0

        for i in indices_brasil:
            lat = np.radians(grid_points[i][1])
            peso = np.cos(lat)

            total += peso
            if grid_ativos[i]:
                ativos += peso

        cobertura_pct = 100 * ativos / total
        cobertura_percentual.append(cobertura_pct)

        # =========================
        # GRID ATIVO
        # =========================
        ativos_idx = np.where(grid_ativos)[0]

        frame_payloads.append(
            {
                "all_sat_xyz": all_sat_xyz,
                "active_sat_xyz": np.asarray(active_sat_xyz, dtype=float).reshape(-1, 3),
                "coverage_xyz": grid_xyz[ativos_idx],
                "active_footprints": active_footprints,
            }
        )

    # =========================
    # FIGURA FINAL
    # =========================
    earth_trace = criar_terra()
    interactive_html_path = (
        Path(__file__).resolve().parents[2]
        / "campaigns" / "01_DC_MSS_to_EESS" / "Videos" / "simulacao_dinamica_plotly_interactive.html"
    )
    try:
        _write_interactive_viewer_html(
            html_path=interactive_html_path,
            earth_trace=earth_trace,
            frame_payloads=frame_payloads,
            cobertura_percentual=cobertura_percentual,
        )
        print(f"Visualizador 3D interativo salvo em: {interactive_html_path}")
    except Exception as exc:
        print(f"Não foi possível gerar o HTML interativo automaticamente: {exc}")

if __name__ == "__main__":
    main()

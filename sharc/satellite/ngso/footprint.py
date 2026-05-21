"""Footprint geometry helpers for NGSO visualizations."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from sharc.satellite.ngso.constants import EARTH_RADIUS_KM


@dataclass(frozen=True)
class HexBeamFootprint:
    """Aggregated footprint for a complete hexagonal beam cluster."""

    beam_radius_km: float
    num_beams: int
    ring_count: int
    beam_center_spacing_km: float
    enclosing_radius_km: float
    enclosing_diameter_km: float
    equivalent_area_radius_km: float
    equivalent_area_diameter_km: float
    central_angle_rad: float


def hex_ring_count(num_beams: int) -> int:
    """Return the number of complete hexagonal rings represented by num_beams."""
    if num_beams < 1:
        raise ValueError("num_beams must be greater than or equal to 1")

    ring_count = 0
    beams_in_cluster = 1
    while beams_in_cluster < num_beams:
        ring_count += 1
        beams_in_cluster = 1 + 3 * ring_count * (ring_count + 1)

    if beams_in_cluster != num_beams:
        raise ValueError(
            "num_beams must describe a complete hexagonal cluster "
            f"(1, 7, 19, 37, ...), got {num_beams}"
        )

    return ring_count


def calculate_hex_beam_footprint(
    *,
    beam_radius_km: float,
    num_beams: int,
    earth_radius_km: float = EARTH_RADIUS_KM,
) -> HexBeamFootprint:
    """Calculate the circular footprint that contains an aggregate hex beam cluster.

    SHARC models each beam cell as a regular hexagon with radius ``beam_radius`` and
    places adjacent beam centers at ``sqrt(3) * beam_radius``. The returned
    ``enclosing_*`` values represent the smallest concentric circle that covers the
    outer vertices of a complete hexagonal cluster.
    """
    if beam_radius_km <= 0:
        raise ValueError("beam_radius_km must be greater than 0")
    if earth_radius_km <= 0:
        raise ValueError("earth_radius_km must be greater than 0")

    ring_count = hex_ring_count(num_beams)
    beam_center_spacing_km = math.sqrt(3.0) * beam_radius_km
    enclosing_radius_km = ring_count * beam_center_spacing_km + beam_radius_km
    enclosing_diameter_km = 2.0 * enclosing_radius_km

    hex_area_km2 = (3.0 * math.sqrt(3.0) / 2.0) * beam_radius_km**2
    equivalent_area_radius_km = math.sqrt(num_beams * hex_area_km2 / math.pi)
    equivalent_area_diameter_km = 2.0 * equivalent_area_radius_km
    central_angle_rad = enclosing_radius_km / earth_radius_km

    return HexBeamFootprint(
        beam_radius_km=beam_radius_km,
        num_beams=num_beams,
        ring_count=ring_count,
        beam_center_spacing_km=beam_center_spacing_km,
        enclosing_radius_km=enclosing_radius_km,
        enclosing_diameter_km=enclosing_diameter_km,
        equivalent_area_radius_km=equivalent_area_radius_km,
        equivalent_area_diameter_km=equivalent_area_diameter_km,
        central_angle_rad=central_angle_rad,
    )


def s1528_relative_gain_angle_deg(*, antenna_3db_bw_deg: float, loss_db: float) -> float:
    """Return the off-axis angle where S.1528 section 1.2 reaches ``loss_db``.

    The first S.1528 section used by SHARC is:
    ``G = Gmax - 3 * (psi / psi_b) ** 1.5``.
    The 7 dB point falls inside that section for the System 4 parameters used
    by the current campaign.
    """
    if antenna_3db_bw_deg <= 0:
        raise ValueError("antenna_3db_bw_deg must be greater than 0")
    if loss_db <= 0:
        raise ValueError("loss_db must be greater than 0")

    psi_b = antenna_3db_bw_deg / 2.0
    return psi_b * (loss_db / 3.0) ** (1.0 / 1.5)


def complete_hex_lattice_offsets(num_beams: int, center_spacing: float) -> list[tuple[float, float]]:
    """Generate complete hexagonal cluster center offsets."""
    ring_count = hex_ring_count(num_beams)
    offsets = [(0.0, 0.0)]

    for ring in range(1, ring_count + 1):
        for side in range(6):
            angle = math.radians(side * 60.0)
            offsets.append(
                (
                    ring * center_spacing * math.cos(angle),
                    ring * center_spacing * math.sin(angle),
                )
            )
            if ring == 1:
                continue

            next_angle = math.radians((side + 1) * 60.0)
            for step in range(1, ring):
                offsets.append(
                    (
                        (ring - step) * center_spacing * math.cos(angle)
                        + step * center_spacing * math.cos(next_angle),
                        (ring - step) * center_spacing * math.sin(angle)
                        + step * center_spacing * math.sin(next_angle),
                    )
                )

    return offsets


def orthonormal_basis(unit_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Create a stable orthonormal basis perpendicular to ``unit_vector``."""
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(unit_vector, reference))) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])

    tangent_1 = np.cross(unit_vector, reference)
    tangent_1 /= np.linalg.norm(tangent_1)
    tangent_2 = np.cross(unit_vector, tangent_1)
    tangent_2 /= np.linalg.norm(tangent_2)
    return tangent_1, tangent_2


def direction_from_angular_offset(
    axis: np.ndarray,
    tangent_1: np.ndarray,
    tangent_2: np.ndarray,
    offset_x_rad: float,
    offset_y_rad: float,
) -> np.ndarray:
    """Rotate ``axis`` by small angular offsets expressed in its tangent plane."""
    rho = math.hypot(offset_x_rad, offset_y_rad)
    if rho == 0:
        return axis

    azimuth = math.atan2(offset_y_rad, offset_x_rad)
    direction = (
        math.cos(rho) * axis
        + math.sin(rho)
        * (math.cos(azimuth) * tangent_1 + math.sin(azimuth) * tangent_2)
    )
    return direction / np.linalg.norm(direction)


def ray_sphere_intersection(
    origin_xyz: np.ndarray,
    direction: np.ndarray,
    *,
    radius_km: float = EARTH_RADIUS_KM,
) -> np.ndarray | None:
    """Intersect a ray with a sphere and return the closest forward point."""
    b = 2.0 * float(np.dot(origin_xyz, direction))
    c = float(np.dot(origin_xyz, origin_xyz) - radius_km**2)
    discriminant = b * b - 4.0 * c
    if discriminant < 0:
        return None

    sqrt_disc = math.sqrt(discriminant)
    roots = [(-b - sqrt_disc) / 2.0, (-b + sqrt_disc) / 2.0]
    forward_roots = [root for root in roots if root > 0]
    if not forward_roots:
        return None

    return origin_xyz + min(forward_roots) * direction


def cone_sphere_polygon(
    sat_xyz: np.ndarray,
    axis: np.ndarray,
    half_angle_rad: float,
    *,
    n_points: int = 6,
    radius_km: float = EARTH_RADIUS_KM,
) -> np.ndarray:
    """Project a cone around ``axis`` onto the Earth sphere."""
    tangent_1, tangent_2 = orthonormal_basis(axis)
    angles = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)
    points = []

    for angle in angles:
        ray_direction = (
            math.cos(half_angle_rad) * axis
            + math.sin(half_angle_rad)
            * (math.cos(angle) * tangent_1 + math.sin(angle) * tangent_2)
        )
        ray_direction /= np.linalg.norm(ray_direction)
        point = ray_sphere_intersection(sat_xyz, ray_direction, radius_km=radius_km)
        if point is not None:
            points.append(point)

    return np.array(points, dtype=float)


def ground_elevation_deg(sat_xyz: np.ndarray, ground_xyz: np.ndarray) -> float:
    """Calculate satellite elevation angle seen from a ground point."""
    ground_unit = ground_xyz / np.linalg.norm(ground_xyz)
    look = sat_xyz - ground_xyz
    look /= np.linalg.norm(look)
    return math.degrees(math.asin(float(np.clip(np.dot(look, ground_unit), -1.0, 1.0))))

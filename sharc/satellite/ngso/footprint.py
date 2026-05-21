"""Footprint geometry helpers for NGSO visualizations."""

from __future__ import annotations

from dataclasses import dataclass
import math

from sharc.satellite.ngso.constants import EARTH_RADIUS_KM


@dataclass(frozen=True)
class HexBeamFootprint:
    """Aggregated footprint for a complete hexagonal beam cluster."""

    beam_radius_km: float
    num_beams: int
    ring_count: int
    intersite_distance_km: float
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
    intersite_distance_km = math.sqrt(3.0) * beam_radius_km
    enclosing_radius_km = ring_count * intersite_distance_km + beam_radius_km
    enclosing_diameter_km = 2.0 * enclosing_radius_km

    hex_area_km2 = (3.0 * math.sqrt(3.0) / 2.0) * beam_radius_km**2
    equivalent_area_radius_km = math.sqrt(num_beams * hex_area_km2 / math.pi)
    equivalent_area_diameter_km = 2.0 * equivalent_area_radius_km
    central_angle_rad = enclosing_radius_km / earth_radius_km

    return HexBeamFootprint(
        beam_radius_km=beam_radius_km,
        num_beams=num_beams,
        ring_count=ring_count,
        intersite_distance_km=intersite_distance_km,
        enclosing_radius_km=enclosing_radius_km,
        enclosing_diameter_km=enclosing_diameter_km,
        equivalent_area_radius_km=equivalent_area_radius_km,
        equivalent_area_diameter_km=equivalent_area_diameter_km,
        central_angle_rad=central_angle_rad,
    )

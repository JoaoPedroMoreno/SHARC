"""Presentation figures with a clipped hexagonal grid and the paper satellite.

The geographical illustrations are schematic, not simulated snapshots. Their
hexagonal grid uses the campaign's 25.803-km radius in a metric projection.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle, Polygon as MplPolygon
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Affine2D
import numpy as np
from pyproj import CRS, Transformer
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, transform, unary_union

from generate_presentation_images import load_countries, country_name


HERE = Path(__file__).resolve().parent
OUT = HERE / "v3"
DPI = 200
DRAWING_RADIUS_M = 25803.0
COVER_SNAPSHOT_SEED = 838
COVER_LOAD_FACTOR = 0.5
COVER_AFFECTED_FRACTION = 0.1
MECHANISM_PBO_DB = 10.0
MECHANISM_VISUAL_GAMMA = 0.25
OFF_AXIS_OPACITY = 0.74
BORDER_DRAWING_WIDTH_M = 2 * DRAWING_RADIUS_M
BLUE = "#6BA8CA"
BLUE_EDGE = "#7DADC5"
BLUE_PALE = "#ECF5F9"
BLUE_SELECTED = "#B7D9E9"
ORANGE = "#DB8B4D"
ORANGE_PALE = "#F6D7BA"
RED = "#BF5750"
GREEN = "#5A9E92"
INK = "#46525A"
BORDER = "#738C99"
WHITE = "#FFFFFF"
SATELLITE = OUT / "satellite_from_paper.png"


def polygons(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def mpl_path(polygon):
    polygon = orient(polygon, sign=1)
    parts = []
    for ring in (polygon.exterior, *polygon.interiors):
        vertices = np.asarray(ring.coords)
        codes = np.full(len(vertices), MplPath.LINETO, dtype=np.uint8)
        codes[0], codes[-1] = MplPath.MOVETO, MplPath.CLOSEPOLY
        parts.append(MplPath(vertices, codes))
    return MplPath.make_compound_path(*parts)


def canvas(width, height, xmax, ymax):
    fig = plt.figure(figsize=(width / DPI, height / DPI), dpi=DPI, facecolor=WHITE)
    ax = fig.add_axes((0, 0, 1, 1), xlim=(0, xmax), ylim=(0, ymax))
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def label(ax, x, y, text, size=23, color=INK, ha="left", va="center", weight="normal"):
    return ax.text(x, y, text, fontsize=size, fontfamily="DejaVu Sans", color=color,
                   ha=ha, va=va, weight=weight, linespacing=1.13, zorder=25)


def leader(ax, source, target, color=INK, width=1.5):
    ax.add_patch(FancyArrowPatch(source, target, color=color, linewidth=width,
                                arrowstyle="-|>", mutation_scale=14, zorder=24))


def satellite(ax, x, y, width):
    asset = mpimg.imread(SATELLITE)
    height = width * asset.shape[0] / asset.shape[1]
    ax.imshow(asset, extent=(x - width / 2, x + width / 2, y - height / 2, y + height / 2),
              interpolation="lanczos", zorder=18)
    return np.array((x, y - height * 0.29))


def hex_vertices(center, radius):
    angles = np.arange(6) * math.pi / 3
    return np.asarray(center) + radius * np.column_stack((np.cos(angles), np.sin(angles)))


def geography():
    countries = {}
    for record in load_countries():
        name = country_name(record)
        countries[name] = unary_union([Polygon(ring) for ring in record.rings if len(ring) >= 4])
    brazil_ll = countries["Brazil"]
    center = brazil_ll.centroid
    crs = CRS.from_proj4(f"+proj=laea +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m")
    project = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    # Only boundaries shared with another country define the illustrative zone.
    shared = {name: brazil_ll.boundary.intersection(country.boundary)
              for name, country in countries.items() if name != "Brazil"}
    neighbors = {name: border for name, border in shared.items() if border.length > 0}
    projected = {"Brazil": transform(project.transform, brazil_ll)}
    for name in neighbors:
        # Keep French Guiana, not France's unrelated overseas/mainland polygons.
        adjacent = unary_union([part for part in polygons(countries[name])
                                if part.boundary.intersection(brazil_ll.boundary).length > 0])
        projected[name] = transform(project.transform, adjacent)
    brazil = projected["Brazil"]
    land_border_ll = linemerge(unary_union(list(neighbors.values())))
    land_border = transform(project.transform, land_border_ll)
    zone = brazil.intersection(land_border.buffer(BORDER_DRAWING_WIDTH_M, cap_style=2))
    r = DRAWING_RADIUS_M
    xmin, ymin, xmax, ymax = brazil.bounds
    cells = []
    row = 0
    for y in np.arange(ymin - r, ymax + 2 * r, math.sqrt(3) * r / 2):
        for x in np.arange(xmin - 2 * r, xmax + 3 * r, 3 * r):
            x += (row % 2) * 1.5 * r
            hexagon = Polygon(hex_vertices((x, y), r))
            if not hexagon.intersects(brazil):
                continue
            clipped = hexagon.intersection(brazil)
            if clipped.area <= 1:
                continue
            cells.append({"center": (x, y), "hexagon": hexagon, "shape": clipped,
                          "active": True, "pbo": False})
        row += 1
    return projected, cells, zone, project


def cover_selection(country, cells):
    # Reuse only the campaign's pure selector; no simulation object is created.
    sys.path.insert(0, str(HERE.parents[3]))
    from sharc.simulation_downlink import SimulationDownlink

    eligible = np.array([country.covers(Point(cell["center"])) for cell in cells])
    activity_rng = np.random.default_rng(COVER_SNAPSHOT_SEED)
    active = eligible & (activity_rng.random(len(cells)) < COVER_LOAD_FACTOR)
    selected, realized_fraction = SimulationDownlink.select_active_beams_for_pbo(
        active, COVER_AFFECTED_FRACTION, COVER_SNAPSHOT_SEED)
    repeated, _ = SimulationDownlink.select_active_beams_for_pbo(
        active, COVER_AFFECTED_FRACTION, COVER_SNAPSHOT_SEED)
    assert not np.any(selected & ~active)
    assert np.array_equal(selected, repeated)
    assert selected.sum() == int(np.floor(active.sum() * COVER_AFFECTED_FRACTION + 0.5))
    drawn_cells = [dict(cell, active=bool(on), pbo=bool(affected))
                   for cell, on, affected in zip(cells, active, selected)]
    metadata = {
        "mode": "ACTIVE_FRACTION",
        "illustrative_snapshot_seed": COVER_SNAPSHOT_SEED,
        "load_factor": COVER_LOAD_FACTOR,
        "requested_affected_fraction": COVER_AFFECTED_FRACTION,
        "realized_affected_fraction": realized_fraction,
        "active_beams": int(active.sum()),
        "orange_cells": int(selected.sum()),
        "inactive_beams_with_pbo": int(np.count_nonzero(selected & ~active)),
        "selected_grid_indices": np.flatnonzero(selected).tolist(),
        "selector": "SimulationDownlink.select_active_beams_for_pbo",
        "reproducibility_check_passed": bool(np.array_equal(selected, repeated)),
    }
    return drawn_cells, metadata


def border_selection(cells, zone):
    return [dict(cell, pbo=zone.covers(cell["shape"].representative_point()))
            for cell in cells]


def draw_geometry(ax, geometry, affine, face, edge="none", linewidth=0.0, zorder=2):
    artists = []
    for polygon in polygons(geometry):
        patch = PathPatch(mpl_path(polygon), transform=affine + ax.transData,
                          facecolor=face, edgecolor=edge, linewidth=linewidth,
                          joinstyle="round", zorder=zorder)
        ax.add_patch(patch)
        artists.append(patch)
    return artists


def draw_grid(ax, country, cells, affine, line_width=0.50):
    draw_geometry(ax, country, affine, BLUE_PALE, zorder=2)
    patches, faces, edges = [], [], []
    for cell in cells:
        for polygon in polygons(cell["shape"]):
            patches.append(PathPatch(mpl_path(polygon)))
            faces.append(ORANGE_PALE if cell["pbo"] else BLUE_PALE)
            edges.append(ORANGE if cell["pbo"] else BLUE_EDGE)
    collection = PatchCollection(patches, facecolors=faces, edgecolors=edges,
                                 linewidths=line_width, zorder=3)
    collection.set_transform(affine + ax.transData)
    ax.add_collection(collection)
    draw_geometry(ax, country, affine, "none", BORDER, 1.3, 9)


def fit_map(country, screen_box, vertical_scale=1.0):
    xmin, ymin, xmax, ymax = country.bounds
    left, bottom, right, top = screen_box
    scale = min((right - left) / (xmax - xmin),
                (top - bottom) / ((ymax - ymin) * vertical_scale))
    return (Affine2D().translate(-(xmin + xmax) / 2, -(ymin + ymax) / 2)
            .scale(scale, scale * vertical_scale)
            .translate((left + right) / 2, (bottom + top) / 2))


def beam(ax, source, footprint, pbo=False, broad=False, visual_scale=None, beam_id=None):
    color = ORANGE if pbo else BLUE
    hull = np.asarray(MultiPoint([tuple(source), *map(tuple, footprint)]).convex_hull.exterior.coords)
    opacity = (0.13 if pbo else 0.18) if visual_scale is None else 0.18 * visual_scale
    ax.add_patch(MplPolygon(hull, facecolor=to_rgba(color, opacity),
                             edgecolor="none", zorder=5, gid=beam_id))
    center = footprint.mean(axis=0)
    ax.plot((source[0], center[0]), (source[1], center[1]), color=color,
            linewidth=0.8 if not broad else 1.25,
            alpha=0.75 if visual_scale is None else 0.75 * visual_scale,
            zorder=6, gid=None if beam_id is None else beam_id + ":axis")


def closest_cell(cells, project, lon, lat, pbo):
    target = np.array(project.transform(lon, lat))
    available = [cell for cell in cells if cell["active"] and cell["pbo"] == pbo
                 and cell["shape"].area > 0.98 * cell["hexagon"].area]
    return min(available, key=lambda cell: np.linalg.norm(np.array(cell["center"]) - target))


def cover(countries, cells, project):
    fig, ax = canvas(3000, 1688, 160, 90)
    affine = fit_map(countries["Brazil"], (16, 5, 144, 64), vertical_scale=0.62)
    draw_grid(ax, countries["Brazil"], cells, affine, line_width=0.44)
    groups = [
        ((52, 77, 22), [(-65, -5, False), (-58, 0, False), (-61, -5, True)]),
        ((84, 82, 23), [(-48, -4, False), (-51, -18, False), (-51, -28, False)]),
        ((116, 77, 22), [(-40, -8, False), (-47, -13, False),
                        (-44, -21, False), (-43, -17, True)]),
    ]
    selected = set()
    for position, targets in groups:
        source = satellite(ax, *position)
        for lon, lat, affected in targets:
            cell = closest_cell(cells, project, lon, lat, affected)
            key = tuple(cell["center"])
            if key in selected:
                continue
            selected.add(key)
            footprint = affine.transform(np.asarray(cell["hexagon"].exterior.coords)[:-1])
            beam(ax, source, footprint, affected)
            draw_geometry(ax, cell["shape"], affine,
                          ORANGE_PALE if affected else BLUE_SELECTED,
                          ORANGE if affected else BLUE, 1.2, 8)
    save(fig, "cover_pbo_brazil.png")


def overview(countries, cells, project):
    fig, ax = canvas(2400, 2400, 120, 120)
    affine = fit_map(countries["Brazil"], (8, 20, 114, 107))
    context_clip = Rectangle((6, 20), 110, 87, transform=ax.transData)
    for name, country in countries.items():
        if name == "Brazil":
            continue
        for artist in draw_geometry(ax, country, affine, WHITE, "#DCE4E8", 0.9, 1):
            artist.set_clip_path(context_clip)
            artist.set_gid("context-country:" + name)
    draw_grid(ax, countries["Brazil"], cells, affine)
    #label(ax, 10, 113, "Brasil", 29)
    target_cell = closest_cell(cells, project, -57, -23, True)
    target = affine.transform(target_cell["center"])
    label(ax, 3, 38, "Região de aplicação \n          do PBO", 23, color=ORANGE, va="center")
    leader(ax, (35, 42), target, ORANGE, 1.8)
    for x, color, fill, text in ((21, BLUE, BLUE_PALE, "Nominal"),
                                (67, ORANGE, ORANGE_PALE, "Com PBO")):
        ax.add_patch(MplPolygon(hex_vertices((x, 9), 2.5), facecolor=fill,
                                 edgecolor=color, linewidth=1.8, zorder=22))
        label(ax, x + 5, 9, text, 22)
    save(fig, "itu_pbo_overview_brazil.png")


def tower(ax, x, y):
    ax.plot((x - 2.1, x, x + 2.1), (y, y + 8, y), color=GREEN, linewidth=2.3, zorder=13)
    ax.plot((x - 1.1, x + 1.1), (y + 3, y + 3), color=GREEN, linewidth=1.6, zorder=13)
    ax.plot((x - 0.7, x + 0.7), (y + 5, y + 5), color=GREEN, linewidth=1.6, zorder=13)
    for dx in (-1.4, 1.4):
        ax.add_patch(FancyBboxPatch((x + dx - 0.48, y + 6.6), 0.96, 3.2,
                     boxstyle="round,pad=0.05,rounding_size=0.23", facecolor="#B8D7CD",
                     edgecolor=GREEN, linewidth=1.25, zorder=14))
    return (x, y + 8.8)


def local_coverage_geometry():
    terrain = Polygon(((-44, -20), (46, -20), (46, 43), (-44, 43)))
    cells = []
    for column in range(7):
        for row in range(-3, 7):
            center = (1.5 * 5.6 * column,
                      math.sqrt(3) * 5.6 * (row + 0.5 * (column % 2)))
            # Snap shared vertices before the union to avoid numerical slivers.
            shape = Polygon(np.round(hex_vertices(center, 5.6), 8)).intersection(terrain)
            if shape.area > 1e-8:
                cells.append((column, row, shape))
    brazil = unary_union([shape for _, _, shape in cells])
    neighbor = terrain.difference(brazil)
    frontier = brazil.boundary.intersection(neighbor.boundary)
    if frontier.geom_type == "MultiLineString":
        frontier = linemerge(frontier)
    assert frontier.geom_type == "LineString"
    assert brazil.geom_type == "Polygon" and not brazil.interiors
    assert neighbor.geom_type == "Polygon" and not neighbor.interiors
    return terrain, cells, brazil, neighbor, frontier


def mechanism_visual_scale(pbo):
    # Gamma compression keeps reduced power visible; opacity is not a dB scale.
    power_ratio = 10 ** (-MECHANISM_PBO_DB / 10) if pbo else 1.0
    return power_ratio ** MECHANISM_VISUAL_GAMMA


def off_axis_radiation(ax, source, footprint, visual_scale, beam_id):
    source = np.asarray(source)
    center = footprint.mean(axis=0)
    direction = center - source
    distance = np.linalg.norm(direction)
    boresight = math.atan2(direction[1], direction[0])
    directions = np.arctan2(footprint[:, 1] - source[1], footprint[:, 0] - source[0])
    offsets = np.arctan2(np.sin(directions - boresight), np.cos(directions - boresight))
    edge = boresight + offsets.min()
    # Localize each soft skirt alongside its own border beam, not the satellite.
    band_angle = edge - math.radians(4.5)
    angular_scale = math.radians(1.8)
    halo_sigma = math.radians(12)
    inner, outer = band_angle + 4 * halo_sigma, band_angle - 4 * halo_sigma
    angles = np.linspace(outer, inner, 80)
    rim = 1.9 * distance * np.stack((np.cos(angles), np.sin(angles)), axis=1)
    bounds = np.vstack((np.zeros(2), rim))
    xmin, ymin = bounds.min(axis=0)
    xmax, ymax = bounds.max(axis=0)
    x, y = np.meshgrid(np.linspace(xmin, xmax, 640), np.linspace(ymin, ymax, 640))
    radial = np.hypot(x, y) / distance
    angular_offset = np.arctan2(np.sin(np.arctan2(y, x) - band_angle),
                                np.cos(np.arctan2(y, x) - band_angle))
    # A single smooth falloff joins the peak to long shoulders, without a stripe.
    core_radius_sq = ((angular_offset / angular_scale) ** 2
                      + ((radial - 0.85) / 0.23) ** 2)
    core_weight = np.exp(0.8 - np.sqrt(0.8 ** 2 + core_radius_sq))
    halo_weight = np.exp(-0.5 * (angular_offset / halo_sigma) ** 2)
    # Fade near the feed so the two beam-linked regions remain distinguishable.
    fade_in = np.clip((radial - 0.18) / 0.40, 0, 1)
    fade_out = np.clip((1.9 - radial) / 0.30, 0, 1)
    radial_weight = (fade_in ** 2 * (3 - 2 * fade_in)
                     * fade_out ** 2 * (3 - 2 * fade_out))
    core = core_weight * radial_weight
    # Retain the broad haze from the version with the two distinct opaque cores.
    halo_radial = np.exp(-0.5 * ((radial - 0.85) / 0.36) ** 2)
    halo_radial *= fade_in ** 2 * (3 - 2 * fade_in)
    intensity = core + 0.48 * (1 - core) * halo_weight * halo_radial
    mask = (np.abs(angular_offset) <= 4 * halo_sigma) & (radial <= 1.9)
    rgba = np.empty((*radial.shape, 4))
    rgba[..., :3] = to_rgba(RED)[:3]
    rgba[..., 3] = OFF_AXIS_OPACITY * visual_scale * intensity * mask
    ax.imshow(rgba, extent=(source[0] + xmin, source[0] + xmax,
                           source[1] + ymin, source[1] + ymax),
              origin="lower", interpolation="bilinear", zorder=4,
              gid="off-axis:" + beam_id)
    return source + 0.66 * distance * np.array((math.cos(band_angle), math.sin(band_angle)))


def lobe_callout(ax, text, position, target, color, side="right"):
    # Matplotlib anchors the leader to the actual text box, with a 3-pt gap.
    return ax.annotate(text, xy=target, xytext=position,
                       fontsize=20, fontfamily="DejaVu Sans", color=INK,
                       ha="left", va="center", linespacing=1.13, zorder=25,
                       arrowprops={"arrowstyle": "-|>", "color": color,
                                   "linewidth": 1.5, "mutation_scale": 14,
                                   "relpos": (1 if side == "right" else 0, 0.5),
                                   "shrinkA": 3, "shrinkB": 2})


def local_scene(ax, base, selective):
    label(ax, 6, base + 53, "(b) PBO seletivo" if selective else "(a) Sem PBO", 27)
    local = Affine2D().scale(0.92, 0.40).skew_deg(8, 0).translate(59, base + 11)
    # One ground projection anchors both territories, the cells and the tower.
    ground, grid, _, _, border = local_coverage_geometry()
    terrain = local.transform(np.asarray(ground.exterior.coords))
    ax.add_patch(MplPolygon(terrain, facecolor="#F1F7F2", edgecolor="#A4B9AD",
                           linewidth=1.3, zorder=1, gid="shared-ground"))
    frontier = np.asarray(border.coords)
    if frontier[0, 1] > frontier[-1, 1]:
        frontier = frontier[::-1]
    frontier = local.transform(frontier)
    ax.plot(frontier[:, 0], frontier[:, 1], color=INK, linewidth=2.0,
            linestyle=(0, (5, 3)), zorder=10, gid="ground-frontier")
    label(ax, 32, base + 30, "País vizinho", 18, ha="center")
    label(ax, 99, base + 30, "Brasil", 19, ha="center")
    label(ax, 51, base, "Fronteira", 18, ha="center")
    leader(ax, (51, base + 1.5), frontier[0], INK, 1.3)
    cells = []
    for column, row, shape in grid:
        vertices = local.transform(np.asarray(shape.exterior.coords)[:-1])
        affected = selective and column == 0
        color, fill = (ORANGE, ORANGE_PALE) if affected else (BLUE, BLUE_PALE)
        ax.add_patch(MplPolygon(vertices, facecolor=fill, edgecolor=color,
                                 linewidth=1.25, zorder=3, gid="ground-cell"))
        cells.append((column, row, vertices, affected))
    source = satellite(ax, 77, base + 45, 27)
    targets = {(0, 0), (0, 2), (2, 3), (4, 0), (4, 2)}
    off_axis_target = None
    for column, row, vertices, affected in cells:
        if (column, row) not in targets:
            continue
        beam_id = f"{column}:{row}"
        intensity = mechanism_visual_scale(affected)
        if column == 0:
            region_target = off_axis_radiation(ax, source, vertices, intensity, beam_id)
            if row == 2:
                off_axis_target = region_target
        beam(ax, source, vertices, affected, broad=True, visual_scale=intensity,
             beam_id="service-beam:" + beam_id)
        # Cell edges stay visible over the illustrative beam translucency.
        ax.add_patch(MplPolygon(vertices, facecolor="none",
                      edgecolor=ORANGE if affected else BLUE, linewidth=1.6, zorder=8))
    foundation = local.transform(((-14.3, -2.2), (-8.7, -2.2),
                                  (-8.7, 2.2), (-14.3, 2.2)))
    ax.add_patch(MplPolygon(foundation, facecolor="#D7E8DE", edgecolor=GREEN,
                           linewidth=1.3, zorder=12, gid="tower-foundation"))
    tower_foot = local.transform((-11.5, 0))
    tower(ax, *tower_foot)
    label(ax, 31, base + 18, "Receptor\nvítima", 19, color=GREEN)
    lobe_callout(ax, "Menor radiação off-axis" if selective else "Radiação off-axis",
                 (6, base + 39), off_axis_target, RED)
    lobe_callout(ax, "Lóbulos\nprincipais", (94, base + 38),
                 (84, base + 30.5), BLUE, side="left")
    if selective:
        label(ax, 84, base + 0.2, "Feixes submetidos a PBO", 21, color=ORANGE, ha="center")
        #label(ax, 84, base - 2.9, "PBO = 10 dB", 19, color=ORANGE, ha="center")
        leader(ax, (70, base + 1.6), local.transform((0, -2)), ORANGE)


def mechanism():
    fig, ax = canvas(2400, 2400, 120, 120)
    local_scene(ax, 62, False)
    local_scene(ax, 6, True)
    save(fig, "itu_pbo_zoom_border.png")


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, facecolor=WHITE)
    plt.close(fig)
    print(OUT / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", nargs="+", choices=("cover", "overview", "mechanism"),
                        default=("cover", "overview", "mechanism"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not SATELLITE.exists():
        raise FileNotFoundError("First render_original_satellite.py with Blender")
    countries, cells, zone, project = geography()
    cover_cells, cover_metadata = cover_selection(countries["Brazil"], cells)
    border_cells = border_selection(cells, zone)
    if "cover" in args.figures:
        cover(countries, cover_cells, project)
    if "overview" in args.figures:
        overview(countries, border_cells, project)
    if "mechanism" in args.figures:
        mechanism()
    union = unary_union([cell["shape"] for cell in cells])
    report = {
        "drawing_radius_m": DRAWING_RADIUS_M,
        "campaign_radius_m": 25803,
        "schematic_not_simulation_snapshot": True,
        "cell_count": len(cells),
        "cover": cover_metadata,
        "overview": {
            "mode": "GEOGRAPHIC",
            "boundary": "shared_land_borders_only",
            "illustrative_band_width_m": BORDER_DRAWING_WIDTH_M,
            "orange_cells": sum(cell["pbo"] for cell in border_cells),
            "zone_formula": "country.intersection(shared_land_border.buffer(band_width, cap_style='flat'))",
        },
        "brazil_covered_fraction": union.area / countries["Brazil"].area,
        "grid_outside_brazil_m2": union.difference(countries["Brazil"]).area,
        "uncovered_brazil_m2": countries["Brazil"].difference(union).area,
        "satellite_source": "illustration/generate_pbo_illustration.py:create_satellite",
        "projection": project.target_crs.to_string(),
    }
    (OUT / "geometry_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"cell_count": len(cells),
                      "cover_orange_cells": cover_metadata["orange_cells"],
                      "cover_active_beams": cover_metadata["active_beams"],
                      "cover_fraction": cover_metadata["realized_affected_fraction"],
                      "overview": report["overview"]}, indent=2))


if __name__ == "__main__":
    main()

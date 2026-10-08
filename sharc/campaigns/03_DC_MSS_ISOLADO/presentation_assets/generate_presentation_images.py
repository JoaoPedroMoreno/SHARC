#!/usr/bin/env python3
"""Generate three 16:9 presentation images for selective DC-MSS PBO.

The country geometry is read directly from the Natural Earth shapefile already
bundled with SHARC. No network access or external map service is required.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.patches import (
    Circle,
    Ellipse,
    FancyArrowPatch,
    FancyBboxPatch,
    Polygon,
    Rectangle,
    RegularPolygon,
)


WIDTH_PX = 1920
HEIGHT_PX = 1080
DPI = 120
FIGSIZE = (WIDTH_PX / DPI, HEIGHT_PX / DPI)

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
COUNTRY_DATA = REPO_ROOT / "sharc" / "data" / "countries"
SHP_PATH = COUNTRY_DATA / "ne_110m_admin_0_countries.shp"
DBF_PATH = COUNTRY_DATA / "ne_110m_admin_0_countries.dbf"

BLUE = "#1787C9"
BLUE_DARK = "#075C8F"
BLUE_LIGHT = "#DDF1FB"
ORANGE = "#F27C32"
ORANGE_DARK = "#B94A12"
ORANGE_LIGHT = "#FDE5D6"
RED = "#C9483B"
GREEN = "#179B82"
INK = "#152534"
MUTED = "#607584"
LAND = "#F4FAFC"
WHITE = "#FFFFFF"
BORDER = "#7A919F"


@dataclass(frozen=True)
class CountryShape:
    attributes: dict[str, str]
    rings: list[list[tuple[float, float]]]


def read_dbf(path: Path) -> list[dict[str, str]]:
    with path.open("rb") as handle:
        header = handle.read(32)
        record_count = struct.unpack("<I", header[4:8])[0]
        header_length, record_length = struct.unpack("<HH", header[8:12])

        fields: list[tuple[str, int]] = []
        while True:
            descriptor = handle.read(32)
            if not descriptor or descriptor[0] == 0x0D:
                break
            name = descriptor[:11].split(b"\0", 1)[0].decode("ascii", errors="replace")
            fields.append((name, descriptor[16]))

        handle.seek(header_length)
        records: list[dict[str, str]] = []
        for _ in range(record_count):
            raw = handle.read(record_length)
            if len(raw) != record_length:
                break
            if raw[0:1] == b"*":
                records.append({})
                continue
            cursor = 1
            values: dict[str, str] = {}
            for name, width in fields:
                value = raw[cursor:cursor + width].decode("utf-8", errors="replace").rstrip("\x00 ")
                values[name] = value
                cursor += width
            records.append(values)
    return records


def read_shp(path: Path) -> list[list[list[tuple[float, float]]]]:
    shapes: list[list[list[tuple[float, float]]]] = []
    with path.open("rb") as handle:
        handle.seek(100)
        while True:
            record_header = handle.read(8)
            if len(record_header) < 8:
                break
            _, content_words = struct.unpack(">II", record_header)
            content = handle.read(content_words * 2)
            if len(content) < 44:
                shapes.append([])
                continue
            shape_type = struct.unpack("<I", content[:4])[0]
            if shape_type == 0:
                shapes.append([])
                continue
            if shape_type not in (5, 15, 25):
                raise ValueError(f"Unsupported shapefile polygon type: {shape_type}")

            part_count, point_count = struct.unpack("<II", content[36:44])
            part_offset = 44
            part_starts = list(struct.unpack(
                f"<{part_count}I",
                content[part_offset:part_offset + 4 * part_count],
            ))
            point_offset = part_offset + 4 * part_count
            points = [
                struct.unpack("<dd", content[point_offset + i * 16:point_offset + (i + 1) * 16])
                for i in range(point_count)
            ]
            part_starts.append(point_count)
            rings = [
                points[part_starts[index]:part_starts[index + 1]]
                for index in range(part_count)
            ]
            shapes.append(rings)
    return shapes


def load_countries() -> list[CountryShape]:
    attributes = read_dbf(DBF_PATH)
    geometries = read_shp(SHP_PATH)
    if len(attributes) != len(geometries):
        raise RuntimeError("Natural Earth DBF/SHP record counts do not match")
    return [
        CountryShape(attrs, rings)
        for attrs, rings in zip(attributes, geometries)
        if attrs and rings
    ]


def country_name(country: CountryShape) -> str:
    for field in ("ADMIN", "NAME_EN", "NAME", "SOVEREIGNT"):
        value = country.attributes.get(field)
        if value:
            return value
    return ""


def find_country(countries: list[CountryShape], name: str) -> CountryShape:
    target = name.casefold()
    for country in countries:
        if country_name(country).casefold() == target:
            return country
    available = ", ".join(sorted(country_name(country) for country in countries))
    raise KeyError(f"Country {name!r} not found. Available: {available}")


def bounds_intersect(
    ring: list[tuple[float, float]],
    limits: tuple[float, float, float, float],
) -> bool:
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    xmin, xmax, ymin, ymax = limits
    return max(xs) >= xmin and min(xs) <= xmax and max(ys) >= ymin and min(ys) <= ymax


def draw_country(
    ax,
    country: CountryShape,
    *,
    facecolor: str,
    edgecolor: str = BORDER,
    linewidth: float = 1.2,
    alpha: float = 1.0,
    zorder: int = 2,
    limits: tuple[float, float, float, float] | None = None,
) -> None:
    for ring in country.rings:
        if len(ring) < 3 or (limits is not None and not bounds_intersect(ring, limits)):
            continue
        ax.add_patch(Polygon(
            ring,
            closed=True,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            alpha=alpha,
            zorder=zorder,
            joinstyle="round",
        ))


def setup_canvas() -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI, facecolor=WHITE)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_facecolor(WHITE)
    ax.axis("off")
    return fig, ax


def save(fig: plt.Figure, filename: str) -> None:
    path = HERE / filename
    fig.savefig(
        path,
        dpi=DPI,
        facecolor=WHITE,
        edgecolor="none",
        bbox_inches=None,
        pad_inches=0,
    )
    plt.close(fig)
    print(path)


def readable_text(ax, x: float, y: float, text: str, **kwargs):
    effects = [pe.withStroke(linewidth=4.5, foreground=WHITE, alpha=0.95)]
    color = kwargs.pop("color", INK)
    return ax.text(
        x,
        y,
        text,
        color=color,
        fontfamily="DejaVu Sans",
        fontweight=kwargs.pop("fontweight", "semibold"),
        path_effects=effects,
        zorder=30,
        **kwargs,
    )


def draw_satellite(ax, x: float, y: float, scale: float = 1.0, zorder: int = 20) -> None:
    body_w = 3.4 * scale
    body_h = 2.0 * scale
    panel_w = 4.0 * scale
    panel_h = 1.55 * scale
    arm = 1.0 * scale

    ax.add_patch(Rectangle(
        (x - body_w / 2 - arm - panel_w, y - panel_h / 2),
        panel_w,
        panel_h,
        facecolor=BLUE_DARK,
        edgecolor=INK,
        linewidth=1.2,
        zorder=zorder,
    ))
    ax.add_patch(Rectangle(
        (x + body_w / 2 + arm, y - panel_h / 2),
        panel_w,
        panel_h,
        facecolor=BLUE_DARK,
        edgecolor=INK,
        linewidth=1.2,
        zorder=zorder,
    ))
    for side in (-1, 1):
        start = x + side * body_w / 2
        end = start + side * arm
        ax.plot([start, end], [y, y], color=INK, linewidth=2.2, zorder=zorder)
        panel_x0 = x - body_w / 2 - arm - panel_w if side < 0 else x + body_w / 2 + arm
        for fraction in (0.25, 0.5, 0.75):
            ax.plot(
                [panel_x0 + fraction * panel_w] * 2,
                [y - panel_h / 2, y + panel_h / 2],
                color="#86C5E8",
                linewidth=1.0,
                zorder=zorder + 1,
            )
    ax.add_patch(FancyBboxPatch(
        (x - body_w / 2, y - body_h / 2),
        body_w,
        body_h,
        boxstyle=f"round,pad=0.12,rounding_size={0.35 * scale}",
        facecolor="#F7FAFC",
        edgecolor=INK,
        linewidth=1.4,
        zorder=zorder + 2,
    ))
    ax.add_patch(Ellipse(
        (x, y - body_h / 2 - 0.33 * scale),
        1.15 * scale,
        0.55 * scale,
        facecolor="#8FA3B0",
        edgecolor=INK,
        linewidth=1.0,
        zorder=zorder + 1,
    ))


def draw_beam(
    ax,
    source: tuple[float, float],
    target: tuple[float, float],
    color: str,
    *,
    footprint_radius: float,
    alpha: float,
    zorder: int = 6,
) -> None:
    sx, sy = source
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    length = math.hypot(dx, dy)
    px, py = -dy / length, dx / length
    throat = 0.10 * footprint_radius
    polygon = [
        (sx + px * throat, sy + py * throat),
        (tx + px * footprint_radius, ty + py * footprint_radius),
        (tx - px * footprint_radius, ty - py * footprint_radius),
        (sx - px * throat, sy - py * throat),
    ]
    ax.add_patch(Polygon(
        polygon,
        closed=True,
        facecolor=color,
        edgecolor="none",
        alpha=alpha,
        zorder=zorder,
    ))
    ax.plot([sx, tx], [sy, ty], color=color, linewidth=2.2, alpha=0.75, zorder=zorder + 1)


def draw_cell(
    ax,
    center: tuple[float, float],
    color: str,
    *,
    radius: float = 1.25,
    alpha: float = 0.22,
    zorder: int = 12,
) -> None:
    ax.add_patch(RegularPolygon(
        center,
        numVertices=6,
        radius=radius,
        orientation=math.pi / 6,
        facecolor=color,
        edgecolor=color,
        linewidth=2.2,
        alpha=alpha,
        zorder=zorder,
    ))
    ax.add_patch(Circle(center, radius * 0.11, facecolor=color, edgecolor=WHITE, linewidth=0.8, zorder=zorder + 1))


def draw_tower(ax, x: float, y: float, scale: float = 1.0, zorder: int = 20) -> None:
    ax.plot([x, x], [y, y + 0.95 * scale], color=INK, linewidth=4.0, zorder=zorder)
    ax.plot([x - 0.42 * scale, x, x + 0.42 * scale], [y, y + 0.95 * scale, y], color=INK, linewidth=2.6, zorder=zorder)
    for level in (0.28, 0.55):
        width = 0.30 * scale * (1.0 - level / 1.4)
        ax.plot([x - width, x + width], [y + level * scale] * 2, color=INK, linewidth=2.1, zorder=zorder)
    for radius in (0.34, 0.58):
        ax.add_patch(FancyArrowPatch(
            (x - radius * scale, y + 1.08 * scale),
            (x + radius * scale, y + 1.08 * scale),
            connectionstyle="arc3,rad=-0.45",
            arrowstyle="-",
            color=GREEN,
            linewidth=2.0,
            zorder=zorder,
        ))


def draw_south_america_context(
    ax,
    countries: list[CountryShape],
    limits: tuple[float, float, float, float],
    brazil_fill: str = BLUE_LIGHT,
) -> CountryShape:
    for country in countries:
        rings_in_view = any(bounds_intersect(ring, limits) for ring in country.rings)
        if not rings_in_view:
            continue
        name = country_name(country)
        fill = brazil_fill if name == "Brazil" else LAND
        draw_country(
            ax,
            country,
            facecolor=fill,
            edgecolor=BORDER,
            linewidth=1.0 if name != "Brazil" else 1.8,
            zorder=2 if name != "Brazil" else 3,
            limits=limits,
        )
    return find_country(countries, "Brazil")


def generate_cover(countries: list[CountryShape]) -> None:
    fig, ax = setup_canvas()
    limits = (-77.5, -30.5, -39.5, 18.0)
    ax.set_xlim(limits[0], limits[1])
    ax.set_ylim(limits[2], limits[3])
    ax.set_aspect("equal", adjustable="box")

    brazil = find_country(countries, "Brazil")
    draw_country(ax, brazil, facecolor="#EDF7FC", edgecolor=BLUE_DARK, linewidth=2.2, zorder=3)

    satellite = (-53.8, 12.1)
    blue_cells = [
        (-60.0, -3.5), (-48.5, -3.0), (-55.8, -10.0), (-45.5, -11.5),
        (-60.2, -16.3), (-48.5, -18.5), (-39.8, -13.0), (-50.5, -28.3),
    ]
    pbo_cells = [(-54.7, -25.4), (-53.3, -24.3), (-52.2, -26.4)]

    beam_targets = [blue_cells[0], blue_cells[2], blue_cells[5], blue_cells[6], pbo_cells[0], pbo_cells[1]]
    for target in beam_targets:
        is_pbo = target in pbo_cells
        draw_beam(
            ax,
            satellite,
            target,
            ORANGE if is_pbo else BLUE,
            footprint_radius=1.35,
            alpha=0.10 if is_pbo else 0.075,
            zorder=5,
        )
    for center in blue_cells:
        draw_cell(ax, center, BLUE, radius=1.35, alpha=0.20)
    for center in pbo_cells:
        draw_cell(ax, center, ORANGE, radius=1.35, alpha=0.34)

    ax.add_patch(Ellipse(
        (-53.7, -25.3),
        8.4,
        6.3,
        angle=-8,
        fill=False,
        edgecolor=ORANGE,
        linewidth=2.2,
        linestyle=(0, (5, 5)),
        alpha=0.8,
        zorder=14,
    ))
    draw_satellite(ax, *satellite, scale=1.05)
    save(fig, "cover_pbo_brazil.png")


def generate_overview(countries: list[CountryShape]) -> None:
    fig, ax = setup_canvas()
    limits = (-77.0, -32.0, -37.0, 9.0)
    ax.set_xlim(limits[0], limits[1])
    ax.set_ylim(limits[2], limits[3])
    ax.set_aspect("equal", adjustable="box")
    draw_south_america_context(ax, countries, limits)

    satellite = (-38.5, 4.8)
    blue_cells = [
        (-61.5, -4.0), (-53.5, -5.0), (-45.0, -5.0),
        (-58.0, -12.0), (-49.0, -12.0), (-41.0, -13.0),
        (-58.0, -20.0), (-48.5, -20.0), (-44.0, -27.0),
    ]
    pbo_cells = [(-54.8, -25.4), (-53.2, -24.4), (-52.3, -27.0)]
    for target in (blue_cells[2], blue_cells[5], pbo_cells[0], pbo_cells[1]):
        is_pbo = target in pbo_cells
        draw_beam(
            ax,
            satellite,
            target,
            ORANGE if is_pbo else BLUE,
            footprint_radius=1.25,
            alpha=0.10,
        )
    for center in blue_cells:
        draw_cell(ax, center, BLUE, radius=1.15, alpha=0.20)
    for center in pbo_cells:
        draw_cell(ax, center, ORANGE, radius=1.18, alpha=0.38)
    draw_satellite(ax, *satellite, scale=0.78)

    ax.add_patch(Ellipse(
        (-53.8, -25.4),
        8.6,
        7.0,
        angle=-8,
        facecolor=ORANGE_LIGHT,
        edgecolor=ORANGE,
        linewidth=2.3,
        linestyle=(0, (5, 4)),
        alpha=0.42,
        zorder=10,
    ))
    for center in pbo_cells:
        draw_cell(ax, center, ORANGE, radius=1.18, alpha=0.48, zorder=13)

    readable_text(ax, -47.0, -13.8, "Área de serviço", fontsize=31, ha="center", va="center")
    readable_text(ax, -66.0, -28.7, "Fronteira", fontsize=29, ha="center", va="center")
    ax.add_patch(FancyArrowPatch(
        (-63.2, -28.0),
        (-57.5, -27.2),
        arrowstyle="-|>",
        mutation_scale=24,
        color=INK,
        linewidth=2.2,
        zorder=25,
    ))
    readable_text(ax, -45.2, -31.2, "Região com PBO", fontsize=31, ha="center", va="center")
    ax.add_patch(FancyArrowPatch(
        (-48.0, -29.8),
        (-52.6, -26.0),
        arrowstyle="-|>",
        mutation_scale=24,
        color=ORANGE_DARK,
        linewidth=2.4,
        connectionstyle="arc3,rad=0.08",
        zorder=25,
    ))
    save(fig, "itu_pbo_overview_brazil.png")


def draw_interference_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    linewidth: float,
    alpha: float = 1.0,
    rad: float = 0.15,
) -> None:
    ax.add_patch(FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=22,
        connectionstyle=f"arc3,rad={rad}",
        linestyle=(0, (5, 4)),
        linewidth=linewidth,
        color=RED,
        alpha=alpha,
        zorder=22,
    ))


def generate_border_zoom(countries: list[CountryShape]) -> None:
    fig, ax = setup_canvas()
    limits = (-56.3, -52.9, -27.2, -23.9)
    ax.set_xlim(limits[0], limits[1])
    ax.set_ylim(limits[2], limits[3])
    ax.set_aspect("equal", adjustable="box")

    country_colors = {
        "Brazil": "#E7F4FB",
        "Paraguay": "#FFF8F1",
        "Argentina": "#F6FAFC",
    }
    for name, fill in country_colors.items():
        draw_country(
            ax,
            find_country(countries, name),
            facecolor=fill,
            edgecolor=BORDER,
            linewidth=2.0,
            zorder=3,
            limits=limits,
        )

    readable_text(ax, -53.55, -24.22, "BRASIL", fontsize=24, ha="center", va="center", color=BLUE_DARK, alpha=0.65)
    readable_text(ax, -55.42, -25.25, "PARAGUAI", fontsize=21, ha="center", va="center", color=MUTED, alpha=0.66)
    readable_text(ax, -55.30, -26.70, "ARGENTINA", fontsize=20, ha="center", va="center", color=MUTED, alpha=0.66)

    critical_center = (-54.55, -25.55)
    ax.add_patch(Ellipse(
        critical_center,
        1.55,
        1.18,
        angle=-18,
        facecolor=ORANGE_LIGHT,
        edgecolor=ORANGE,
        linewidth=2.4,
        linestyle=(0, (5, 4)),
        alpha=0.55,
        zorder=8,
    ))

    blue_cells = [(-53.55, -24.75), (-53.50, -25.55), (-53.85, -26.25)]
    pbo_cells = [(-54.10, -25.05), (-54.02, -25.88)]
    for center in blue_cells:
        draw_cell(ax, center, BLUE, radius=0.22, alpha=0.27, zorder=13)
    for center in pbo_cells:
        draw_cell(ax, center, ORANGE, radius=0.23, alpha=0.52, zorder=14)

    receiver = (-54.95, -25.48)
    draw_tower(ax, *receiver, scale=0.31, zorder=24)

    draw_interference_arrow(ax, blue_cells[0], receiver, linewidth=4.2, alpha=0.92, rad=0.18)
    draw_interference_arrow(ax, pbo_cells[0], receiver, linewidth=1.9, alpha=0.92, rad=-0.10)
    draw_interference_arrow(ax, pbo_cells[1], receiver, linewidth=1.9, alpha=0.92, rad=0.10)

    readable_text(ax, -53.20, -24.52, "Feixes nominais", fontsize=28, ha="center", va="center")
    ax.add_patch(FancyArrowPatch(
        (-53.25, -24.66),
        blue_cells[0],
        arrowstyle="-|>",
        mutation_scale=21,
        color=BLUE_DARK,
        linewidth=2.2,
        zorder=28,
    ))
    readable_text(ax, -53.25, -26.58, "Feixes com PBO", fontsize=28, ha="center", va="center")
    ax.add_patch(FancyArrowPatch(
        (-53.45, -26.43),
        pbo_cells[1],
        arrowstyle="-|>",
        mutation_scale=21,
        color=ORANGE_DARK,
        linewidth=2.2,
        zorder=28,
    ))
    readable_text(ax, -55.38, -24.82, "Menor interferência\nno receptor IMT", fontsize=28, ha="center", va="center")
    ax.add_patch(FancyArrowPatch(
        (-55.08, -25.00),
        (receiver[0], receiver[1] + 0.18),
        arrowstyle="-|>",
        mutation_scale=21,
        color=INK,
        linewidth=2.2,
        zorder=28,
    ))
    readable_text(ax, -54.65, -26.80, "Região crítica", fontsize=27, ha="center", va="center", color=ORANGE_DARK)

    # Small overview inset makes the relationship with the previous image explicit.
    inset = fig.add_axes([0.055, 0.675, 0.18, 0.25], facecolor=WHITE)
    inset.axis("off")
    inset.set_xlim(-76.5, -33.0)
    inset.set_ylim(-35.0, 7.0)
    inset.set_aspect("equal", adjustable="box")
    brazil = find_country(countries, "Brazil")
    draw_country(inset, brazil, facecolor=BLUE_LIGHT, edgecolor=BLUE_DARK, linewidth=1.2, zorder=3)
    inset.add_patch(Rectangle(
        (-56.3, -27.2),
        3.4,
        3.3,
        fill=False,
        edgecolor=ORANGE,
        linewidth=2.2,
        zorder=10,
    ))
    inset.text(
        0.5,
        -0.05,
        "Zoom da fronteira",
        transform=inset.transAxes,
        ha="center",
        va="top",
        fontsize=19,
        fontfamily="DejaVu Sans",
        fontweight="semibold",
        color=INK,
    )

    save(fig, "itu_pbo_zoom_border.png")


def main() -> None:
    countries = load_countries()
    generate_cover(countries)
    generate_overview(countries)
    generate_border_zoom(countries)


if __name__ == "__main__":
    main()

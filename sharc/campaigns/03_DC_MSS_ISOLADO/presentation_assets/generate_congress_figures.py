"""Render two concept/methodology slides without running a SHARC simulation."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon as MplPolygon
from matplotlib.transforms import Affine2D
import numpy as np
from shapely.geometry import Polygon

import generate_hex_presentation_images as style


OUT = Path(__file__).resolve().parent / "v4"
WIDTH, HEIGHT = 3200, 1800
BLUE = style.BLUE
ORANGE = style.ORANGE
RED = style.RED
INK = style.INK
BLUE_TEXT = "#387391"
ORANGE_TEXT = "#AC5F2C"
RULE = "#D9E4EA"
FONT = "DejaVu Sans"


def text(ax, x, y, value, size=23, color=INK, ha="left", va="center", weight="normal"):
    return ax.text(x, y, value, fontsize=size, fontfamily=FONT, color=color,
                   ha=ha, va=va, weight=weight, linespacing=1.22, zorder=30)


def callout(ax, value, position, target, color, side="right", size=23):
    return ax.annotate(value, xy=target, xytext=position, fontsize=size,
                       fontfamily=FONT, color=INK, ha="left", va="center",
                       linespacing=1.22, zorder=30,
                       arrowprops={"arrowstyle": "-|>", "color": color,
                                   "linewidth": 1.7, "mutation_scale": 16,
                                   "relpos": (1 if side == "right" else 0, 0.5),
                                   "shrinkA": 6, "shrinkB": 5})


def illustrative_grid(country):
    # Coarsening is strictly visual: neither the campaign radius nor outputs change.
    radius = 150000.0
    xmin, ymin, xmax, ymax = country.bounds
    cells = []
    for column, x in enumerate(np.arange(xmin - radius, xmax + 2 * radius, 1.5 * radius)):
        for y in np.arange(ymin - radius, ymax + 2 * radius, math.sqrt(3) * radius):
            center = (x, y + (column % 2) * math.sqrt(3) * radius / 2)
            hexagon = Polygon(style.hex_vertices(center, radius))
            clipped = hexagon.intersection(country)
            if clipped.area > 1:
                cells.append({"center": center, "hexagon": hexagon, "shape": clipped,
                              "active": True, "pbo": False})
    eligible = [i for i, cell in enumerate(cells)
                if cell["shape"].area > 0.85 * cell["hexagon"].area]
    rng = np.random.default_rng(838)
    selected = rng.choice(eligible, size=18, replace=False)
    for i in selected:
        cells[i]["pbo"] = True
    return cells


def nearest(cells, project, lon, lat, affected, used):
    target = np.array(project.transform(lon, lat))
    eligible = [(i, c) for i, c in enumerate(cells)
                if i not in used and c["pbo"] == affected
                and c["shape"].area > 0.85 * c["hexagon"].area]
    i, cell = min(eligible, key=lambda item: np.linalg.norm(np.array(item[1]["center"]) - target))
    used.add(i)
    return cell


def right_off_axis(ax, source, footprint):
    # Reflect the existing diffuse skirt; it stays tied to a service beam's edge.
    reflected = np.array((-1.0, 1.0))
    target = style.off_axis_radiation(ax, source * reflected, footprint * reflected,
                                      0.68, "cover-pbo")
    ax.images[-1].set_transform(Affine2D().scale(-1, 1) + ax.transData)
    return target * reflected


def concept():
    countries, _, _, project = style.geography()
    country = countries["Brazil"]
    cells = illustrative_grid(country)
    fig, ax = style.canvas(WIDTH, HEIGHT, 160, 90)
    text(ax, 8, 83, "PBO = redução seletiva de potência", 33, weight="medium")
    affine = style.fit_map(country, (14, 17, 115, 59), vertical_scale=0.62)
    style.draw_grid(ax, country, cells, affine, line_width=0.95)
    source = style.satellite(ax, 72, 71, 31)
    targets = [(-65, -4, False), (-56, -4, False), (-47, -4, False),
               (-53, -15, False), (-44, -16, False), (-51, -27, False),
               (-56, -18, True), (-39, -10, True)]
    used, beam_metadata = set(), []
    for lon, lat, affected in targets:
        cell = nearest(cells, project, lon, lat, affected, used)
        footprint = affine.transform(np.asarray(cell["hexagon"].exterior.coords)[:-1])
        center = footprint.mean(axis=0)
        # Power reduction affects intensity, not the vertices/opening of the beam.
        intensity = 0.68 if affected else 1.10
        style.beam(ax, source, footprint, affected, broad=True, visual_scale=intensity,
                   beam_id=f"concept-beam-{len(beam_metadata)}")
        style.draw_geometry(ax, cell["shape"], affine,
                            style.ORANGE_PALE if affected else style.BLUE_SELECTED,
                            ORANGE if affected else BLUE, 1.8, 8)
        beam_metadata.append({"pbo": affected, "footprint": footprint.tolist(),
                              "visual_scale": intensity})

    for x, color, fill, value in ((51, BLUE, style.BLUE_SELECTED, "Nominal"),
                                 (85, ORANGE, style.ORANGE_PALE, "Com PBO")):
        ax.add_patch(MplPolygon(style.hex_vertices((x, 6.5), 2), facecolor=fill,
                               edgecolor=color, linewidth=1.7, zorder=24))
        text(ax, x + 4, 6.5, value, 24)
    return fig, {"illustrative_cell_count": len(cells),
                 "illustrative_selected_cells": sum(c["pbo"] for c in cells),
                 "grid_radius_m_for_drawing_only": 150000,
                 "not_a_simulation_snapshot": True,
                 "external_receiver_and_callouts": False,
                 "beams": beam_metadata}


def flow_box(ax, x, width, title, number):
    patch = FancyBboxPatch((x, 18), width, 48,
                           boxstyle="round,pad=0,rounding_size=0.6",
                           facecolor="#F6FAFC", edgecolor=RULE, linewidth=1.4,
                           zorder=2, gid=f"flow-box-{number}")
    ax.add_patch(patch)
    text(ax, x + 2, 62.4, f"0{number}", 19, color=BLUE_TEXT)
    text(ax, x + 2, 56, title, 21, weight="medium")
    ax.plot((x + 2, x + width - 2), (50, 50), color=RULE, linewidth=1.1, zorder=3)
    return patch


def methodology():
    fig, ax = style.canvas(WIDTH, HEIGHT, 160, 90)
    text(ax, 6, 83, "SHARC", 39, color=BLUE_TEXT, weight="medium")
    text(ax, 29, 83, "Simulator for SHARing and Compatibility studies", 23)
    text(ax, 6, 73, "1000 snapshots por configuração", 26, color=BLUE_TEXT)
    specs = [(6, 24, "Configuração\ndo cenário"),
             (34, 25, "Snapshots\nMonte Carlo"),
             (63, 25, "Cálculo por\nsnapshot"),
             (92, 26, "Agregação\nestatística"),
             (122, 35, "Métricas")]
    boxes = []
    for i, (x, width, title) in enumerate(specs, 1):
        boxes.append(flow_box(ax, x, width, title, i))
        if i < len(specs):
            ax.add_patch(FancyArrowPatch((x + width + 0.45, 42),
                                         (specs[i][0] - 0.45, 42),
                                         arrowstyle="-|>", mutation_scale=21,
                                         linewidth=2, color=BLUE, zorder=10))

    for y, value in ((44, "LF"), (37, "Nível de PBO"), (30, "Fração afetada"),
                     (23, "Parâmetros\ndo sistema")):
        text(ax, 8, y, value, 19.5)
    text(ax, 36, 44, "Realizações\naleatórias", 19, color=BLUE_TEXT)
    for y, value in ((36, "Snapshot 1"), (30.5, "Snapshot 2"), (25.5, "..."),
                     (21, "Snapshot 1000")):
        text(ax, 36, y, value, 20)
    text(ax, 65, 46.5, "Por usuário", 19, color=BLUE_TEXT)
    text(ax, 65, 40.3, "Sinal desejado S", 19)
    text(ax, 65, 33.5, "Interferência I\nagregada", 19)
    text(ax, 65, 26.3, "Ruído N", 20)
    text(ax, 65, 21.3, r"$\mathrm{SINR}=\frac{S}{I+N}$", 22, color=BLUE_TEXT)
    text(ax, 94, 43, "Distribuições\nempíricas", 20)
    text(ax, 94, 33.5, "Percentis", 20)
    text(ax, 94, 25.5, "IC95%: bootstrap\npor snapshot", 19)
    text(ax, 124, 45, "Outage", 21, color=BLUE_TEXT, weight="medium")
    text(ax, 124, 40.5, r"$P_{\mathrm{out}}=\Pr\{\mathrm{SINR}<-6\ \mathrm{dB}\}$", 19)
    text(ax, 124, 33.7, "Retenção do P5", 21, color=ORANGE_TEXT, weight="medium")
    text(ax, 124, 28.3, "da proxy de eficiência\nespectral vs. baseline", 19)
    text(ax, 124, 21, "CDFs de SNR e I/N", 20, color=BLUE_TEXT)
    text(ax, 80, 8, "Comparação pareada: baseline × PBO", 24, ha="center")
    return fig, {"steps": [s[2].replace("\n", " ") for s in specs],
                 "configured_snapshots": 1000,
                 "sinr": "S / (I + N), in linear power units",
                 "outage_criterion": "SINR < -6 dB",
                 "retention": "100 * P5(proxy_PBO) / P5(proxy_baseline)",
                 "data_source": "existing SHARC selected-UE CSVs; no new simulation",
                 "bootstrap_unit": "snapshot",
                 "source_code": ["sharc/simulation_downlink.py:calculate_sinr",
                                 "sharc/campaigns/03_DC_MSS_ISOLADO/Script/base_input.yaml",
                                 "sharc/campaigns/03_DC_MSS_ISOLADO/post_processing/analyze_results.py"]}


def verify_and_save(fig, name, metadata, expected_size=(WIDTH, HEIGHT)):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = expected_size
    assert tuple(fig.canvas.get_width_height()) == expected_size
    labels, overlaps = [], []
    for item in fig.axes[0].texts:
        # Annotation extents include the leader: test the actual text alone.
        from matplotlib.text import Text
        bbox = Text.get_window_extent(item, renderer)
        assert bbox.x0 >= 0 and bbox.y0 >= 0 and bbox.x1 <= width and bbox.y1 <= height, item.get_text()
        assert item.get_fontsize() >= 19, item.get_text()
        for previous, old in labels:
            if bbox.overlaps(old):
                overlaps.append((previous, item.get_text()))
        labels.append((item.get_text(), bbox))
    assert not overlaps, f"Text overlap: {overlaps}"
    boxes = [p for p in fig.axes[0].patches if (p.get_gid() or "").startswith("flow-box-")]
    for patch in boxes:
        outer = patch.get_window_extent(renderer)
        for value, bbox in labels:
            if outer.contains(*bbox.get_points().mean(axis=0)):
                assert outer.contains(bbox.x0 - 10, bbox.y0 - 8), value
                assert outer.contains(bbox.x1 + 10, bbox.y1 + 8), value
    metadata["qa"] = {"size_px": [width, height], "text_count": len(labels),
                      "minimum_font_pt": min(t.get_fontsize() for t in fig.axes[0].texts),
                      "text_overlap_count": 0, "text_inside_frame": True,
                      "text_padding_checked": bool(boxes)}
    fig.savefig(OUT / name, dpi=style.DPI, facecolor="white")
    plt.close(fig)
    print(OUT / name)
    return metadata


def main():
    from generate_methodology_overview import methodology_overview
    OUT.mkdir(exist_ok=True)
    records = {}
    for name, draw in (("cover_pbo_selective.png", concept),
                       ("sharc_monte_carlo_methodology.png", methodology_overview)):
        fig, metadata = draw()
        records[name] = verify_and_save(fig, name, metadata)
    (OUT / "validation.json").write_text(json.dumps(records, ensure_ascii=False, indent=2),
                                         encoding="utf-8")


if __name__ == "__main__":
    main()

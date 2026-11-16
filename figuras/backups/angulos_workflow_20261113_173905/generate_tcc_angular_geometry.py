"""TCC angular diagram, with approved satellite/FS assets and vector geometry.

Reference: campaign 04, analysis/final_figures/fig01/render_blender.py
at commit 985a630. Geometry is conceptual, not an extracted snapshot.
"""
from pathlib import Path
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Arc, FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.text import Text
from PIL import Image
import numpy as np

import latincom_visual_style as style

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
NAME = "fig_geometria_angular_handover"
BLUE, INK, MUTED = "#287499", "#354650", "#8999a3"
LABELS = []


def label(ax, x, y, value, size=17, color=INK, ha="center"):
    artist = ax.text(x, y, value, fontsize=size, color=color, ha=ha,
                     va="center", linespacing=1.35, zorder=40)
    LABELS.append(artist)
    return artist


def arrow(ax, start, end, color=INK, dashed=False, width=1.8, curve=0):
    item = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13,
                           color=color, lw=width, shrinkA=0, shrinkB=0,
                           linestyle=(0, (5, 4)) if dashed else "-",
                           connectionstyle=f"arc3,rad={curve}", zorder=10)
    ax.add_patch(item)
    return item


def fs(ax, x, y, height=2.55):
    folder = OUT / "tcc_assets/fs_angular"
    m = json.loads((folder / "manifest.json").read_text())["views"]["angular"]
    with Image.open(folder / m["image"]) as source:
        bounds = source.getchannel("A").getbbox()
        pixels = np.asarray(source.crop(bounds))
    left, top, right, bottom = bounds
    scale = height / (bottom-top)
    base = np.array(m["anchors_px"]["base"])

    def project(pixel):
        return np.array([x, y]) + (np.array(pixel)-base)*[scale, -scale]

    lo, hi = project([left, bottom]), project([right, top])
    ax.imshow(pixels, extent=(lo[0], hi[0], lo[1], hi[1]), zorder=25,
              interpolation="lanczos")
    focus = project(m["anchors_px"]["focus"])
    axis = project(m["anchors_px"]["axis_end"])-focus
    axis /= np.linalg.norm(axis)
    assert m["boresight_3d"][2] == 0, "FS boresight must be horizontal"
    return focus, axis


def ground(ax, center):
    center = np.asarray(center)
    for q in range(-2, 3):
        for r in range(-1, 2):
            local = np.array([1.42*q, .76*(r+q/2)])
            if abs(local[1]) > 1.1:
                continue
            xy = center+local
            vertices = style.hexagon(0, 0, .95)*[1, .53]+xy
            selected = q == r == 0
            ax.add_patch(Polygon(vertices, facecolor="#dcecf3" if selected else "#f5f8fa",
                                 edgecolor=BLUE if selected else "#cbd6dd",
                                 linewidth=1.5 if selected else .8, zorder=3))
    users = center+np.array([[-.35, -.11], [.27, .20], [.4, -.16]])
    ax.scatter(users[:, 0], users[:, 1], s=26, color=INK, edgecolor="white",
               linewidths=.65, zorder=20)
    return users


def satellite(ax, center, target):
    tilt = style.pointing_angle(*center, target)
    return style.satellite(ax, *center, width=4.4, tilt_deg=tilt)


def angle(ax, origin, endpoint_a, endpoint_b, radius, symbol, label_radius=None):
    a, b = np.asarray(endpoint_a)-origin, np.asarray(endpoint_b)-origin
    aa, bb = np.arctan2(a[1], a[0]), np.arctan2(b[1], b[0])
    delta = (bb-aa+math.pi) % (2*math.pi)-math.pi
    start, end = sorted((aa, aa+delta))
    ax.add_patch(Arc(origin, radius*2, radius*2,
                     theta1=np.degrees(start), theta2=np.degrees(end),
                     lw=2.1, color=BLUE, zorder=22))
    middle = (start+end)/2
    position = origin+(label_radius or radius+.45)*np.array([np.cos(middle), np.sin(middle)])
    label(ax, *position, symbol, size=23, color=BLUE)
    return {"vertex": origin.tolist(), "ray_a": a.tolist(), "ray_b": b.tolist(),
            "illustrative_screen_angle_deg": abs(float(np.degrees(delta)))}


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                         "pdf.fonttype": 42, "mathtext.fontset": "dejavusans"})
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), dpi=100)
    fig.subplots_adjust(left=.015, right=.985, bottom=.025, top=.98, wspace=.04)
    for ax in axes:
        ax.set(xlim=(0, 20), ylim=(0, 18))
        ax.set_aspect("equal")
        ax.axis("off")
    fig.add_artist(Line2D([.5, .5], [.08, .93], transform=fig.transFigure,
                          color="#d7dfe4", lw=.8))

    left, right = axes
    cell = np.array([4.3, 3.0])
    ground(left, cell)
    receiver, axis = fs(left, 16, 2.25)
    serving = satellite(left, (4.3, 13.5), cell)
    candidate = satellite(left, (13.4, 11.5), cell)
    label(left, 4.3, 15.15, "Sat\u00e9lite servidor")
    label(left, 14, 13.15, "Sat\u00e9lite candidato")
    arrow(left, serving, cell+[0, .08], BLUE)
    arrow(left, candidate, cell+[.12, .08], BLUE, dashed=True)
    arrow(left, serving, receiver, MUTED, dashed=True, width=1.4)
    arrow(left, (6.6, 14.25), (11.65, 12.3), INK, curve=-.24, width=1.6)
    label(left, 10.6, 15.55, "Reassocia\u00e7\u00e3o", size=16)
    label(left, 4.3, .9, "Mesma c\u00e9lula e mesmos UEs", size=17)
    label(left, 16.4, .9, "Receptor FS", size=17)
    label(left, 13.3, 7.1, "Interfer\u00eancia", size=16)
    # Small leader identifies the interference ray without crossing service rays.
    mid = serving*.42+receiver*.58
    arrow(left, (11.9, 7.8), mid, MUTED, width=.8)
    label(left, 2.65, 8.7, "Enlace\natual", color=BLUE, size=16)
    label(left, 7.8, 4.9, "Novo enlace", color=BLUE, size=16, ha="left")

    cell_b = np.array([4.2, 3.0])
    ground(right, cell_b)
    rx, bore = fs(right, 16.4, 2.25)
    tx = satellite(right, (10.0, 13.5), cell_b)
    label(right, 10, 15.5, "Sat\u00e9lite DC-MSS-IMT")
    arrow(right, tx, cell_b, BLUE)
    arrow(right, tx, rx, INK, dashed=True, width=1.5)
    axis_end = rx+bore*6.4
    arrow(right, rx, axis_end, INK, width=1.5)
    geometry = {
        "psi_tx": angle(right, tx, cell_b, rx, 2.25, r"$\psi_{\mathrm{TX}}$", 2.95),
        "psi_rx": angle(right, rx, rx+bore, tx, 2.0, r"$\psi_{\mathrm{RX}}$", 2.75),
    }
    label(right, 2.6, 9.25, "Eixo do feixe\npara a c\u00e9lula", color=BLUE, size=16)
    label(right, 17.4, 9.4, "Dire\u00e7\u00e3o de\ninterfer\u00eancia", size=16)
    label(right, 9.3, 4.9, "Eixo fixo FS", size=16)
    label(right, 4.2, .9, "C\u00e9lula atendida", size=17)
    label(right, 16.4, .9, "Receptor FS", size=17)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = [t.get_window_extent(renderer) for t in LABELS]
    for text, box in zip(LABELS, bounds):
        assert fig.bbox.contains(box.x0, box.y0) and fig.bbox.contains(box.x1, box.y1), text.get_text()
    overlaps = [(LABELS[i].get_text(), LABELS[j].get_text())
                for i in range(len(bounds)) for j in range(i+1, len(bounds))
                if bounds[i].overlaps(bounds[j])]
    assert not overlaps, overlaps
    for ext, dpi in (("png", 400), ("pdf", 400), ("svg", 400)):
        fig.savefig(OUT / f"{NAME}.{ext}", dpi=dpi, facecolor="white")
    fig.savefig(OUT / f"{NAME}_preview.png", dpi=100, facecolor="white")
    plt.close(fig)
    report = {"reference": "campaign 04 fig01/render_blender.py at 985a630",
              "conceptual_not_simulation_output": True, "general_title": False,
              "fs_elevation_deg": 0, "rx_points_to_satellite": False,
              "tx_angle_definition": "beam boresight versus satellite-to-FS ray",
              "rx_angle_definition": "fixed FS boresight versus FS-to-satellite ray",
              "angles_are_schematic_not_measured_3d_values": True,
              "cell_and_users_preserved": True, "label_overlaps": overlaps,
              "png_size": [6400, 3000], "vector_text_and_lines": True,
              "embedded_rendered_models": True, "geometry": geometry}
    (OUT / f"{NAME}_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT / f"{NAME}.png")


if __name__ == "__main__":
    main()

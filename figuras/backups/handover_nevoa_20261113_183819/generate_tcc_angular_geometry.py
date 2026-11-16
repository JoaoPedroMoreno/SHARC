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
from matplotlib.transforms import Affine2D
import numpy as np

import latincom_visual_style as style
from tcc_diagram_primitives import ground_plane, service_mesh, ue_dot, fs_on_ground, SATELLITE_TILT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
NAME = "fig_geometria_angular_handover"
BLUE, INK, MUTED = "#287499", "#354650", "#8999a3"
RED = "#bb493f"
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


def ground(ax):
    transform = Affine2D().scale(1, .5).skew_deg(14, 0).translate(0, 2.9)
    ground_plane(ax, transform, (1.8, -3.1, 18, 4))
    center = np.array([9.2, 0.0])
    for key, _, raw_vertices, _ in service_mesh((1.8, -3.1, 12.3, 4), center):
        vertices = transform.transform(raw_vertices)
        selected = key == (0, 0)
        ax.add_patch(Polygon(vertices, facecolor="#dcecf3" if selected else "#f5f8fa",
                             edgecolor=BLUE if selected else "#cbd6dd",
                             linewidth=1.5 if selected else .8, zorder=3))
    border = transform.transform([[12.3, -3.1], [12.3, 4]])
    ax.plot(*border.T, color="#a3b2b1", lw=1, zorder=4)
    for foot in transform.transform(center+[[-.35, -.2], [.28, .15]]):
        ue_dot(ax, foot, "#235d7d", size=24)
    base = transform.transform([14.2, 0])
    foundation = transform.transform([[13.7, -.45], [14.7, -.45], [14.7, .45], [13.7, .45]])
    ax.add_patch(Polygon(foundation, facecolor="#dfe6e5", edgecolor="#a3b2b1", lw=.8, zorder=4))
    rx, axis = fs_on_ground(ax, base)
    return transform.transform(center), rx, axis


def satellite(ax, center, alpha=1):
    feed = style.satellite(ax, *center, width=4.4, tilt_deg=SATELLITE_TILT)
    ax.images[-1].set_alpha(alpha)
    return feed


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

    geometry = {}
    panels = []
    for panel, ax in enumerate(axes):
        cell, rx, bore = ground(ax)
        tx = satellite(ax, (5.4, 13.5))
        candidate = satellite(ax, (14.2, 12.0), alpha=1 if panel == 0 else .10)
        label(ax, 5.4, 15.2, "Sat\u00e9lite servidor")
        label(ax, 16.3, 10.45, "Sat\u00e9lite\ncandidato", color=INK if panel == 0 else "#d6dde1", size=16)
        arrow(ax, tx, cell, BLUE)
        candidate_link = arrow(ax, candidate, cell, BLUE, dashed=True)
        candidate_link.set_alpha(1 if panel == 0 else .09)
        label(ax, 7.3, .9, "Mesma c\u00e9lula e mesmos UEs" if panel == 0 else "C\u00e9lula atendida", size=16)
        label(ax, 15.8, .9, "Receptor FS", size=17)
        panels.append({"cell": cell.tolist(), "rx": rx.tolist(), "tx": tx.tolist(),
                       "candidate": candidate.tolist()})
        if panel == 0:
            arrow(ax, tx, rx, RED, dashed=True, width=1.6)
            arrow(ax, (7.6, 14.25), (12.5, 12.9), INK, curve=-.20, width=1.5)
            label(ax, 11, 15.4, "Reassocia\u00e7\u00e3o", size=16)
            label(ax, 16.2, 8.3, "Caminho de\npropaga\u00e7\u00e3o da\ninterfer\u00eancia", color=RED, size=16)
            mid = tx*.40+rx*.60
            arrow(ax, (14.1, 8.2), mid, RED, width=.8)
            label(ax, 4.1, 8.2, "Enlace\natual", color=BLUE, size=16)
            label(ax, 12.2, 5.8, "Novo enlace", color=BLUE, size=16, ha="left")
        else:
            arrow(ax, tx, rx, MUTED, dashed=True, width=1.6)
            arrow(ax, rx, rx+bore*5.3, INK, width=1.5)
            label(ax, rx[0]-5.5, rx[1], "N", size=14, ha="right")
            geometry = {
                "psi_tx": angle(ax, tx, cell, rx, 3.0, r"$\psi_{\mathrm{TX}}$", 3.9),
                "psi_rx": angle(ax, rx, rx+bore, tx, 2.3, r"$\psi_{\mathrm{RX}}$", 3.05),
            }
            label(ax, 3.9, 8.5, "Eixo do feixe\nservidor", color=BLUE, size=16)
            label(ax, 16.25, 8.1, "Vetor dist\u00e2ncia\n"+r"$\mathbf{d}$", size=16)
            mid = tx*.40+rx*.60
            arrow(ax, (14.3, 8.1), mid, MUTED, width=.8)
            label(ax, 4.6, 5.7, "Pointing do\nreceptor FS", size=16)
            arrow(ax, (6.5, 5.25), rx+bore*4.1, INK, width=.8)
    assert panels[0] == panels[1], "Both panels must show the same geometry"

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
              "fs_horizontal_north": True, "same_ground_plane": True,
              "satellite_tilt_deg": SATELLITE_TILT, "same_geometry_both_panels": True,
              "candidate_opacity_panel_b": .10,
              "tx_angle_definition": "beam boresight versus satellite-to-FS ray",
              "rx_angle_definition": "fixed FS boresight versus FS-to-satellite ray",
              "angles_are_schematic_not_measured_3d_values": True,
              "cell_and_users_preserved": True, "label_overlaps": overlaps,
              "ue_symbols": "dark blue dots in served cell only",
              "service_plane_fully_tessellated": True, "fs_side_has_no_service_grid": True,
              "png_size": [6400, 3000], "vector_text_and_lines": True,
              "embedded_rendered_models": True, "geometry": geometry}
    (OUT / f"{NAME}_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT / f"{NAME}.png")


if __name__ == "__main__":
    main()

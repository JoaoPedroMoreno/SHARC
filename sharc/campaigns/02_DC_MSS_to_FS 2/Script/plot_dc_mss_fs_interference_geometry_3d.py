"""Create a conceptual 3D interference-geometry diagram for DC-MSS into FS.

The figure is intentionally schematic, not geodetic. It illustrates two
coexistence mechanisms used in the campaign:

  (A) regional coverage: the DC-MSS main lobe illuminates Paraguay and couples
      directly into the FS receiver;
  (B) cross-border spillover: official DC-MSS service beams are restricted to
      Brazil/Argentina, while the FS in Paraguay is reached by side-lobe leakage.

Outputs are saved as PNG and PDF for paper use.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d import art3d
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection


IEEE_TEXT_WIDTH_IN = 7.16
FIG_HEIGHT_IN = 3.85
DPI = 350

SERVICE_COLOR = "#6BAED6"
PARAGUAY_COLOR = "#FDD0A2"
BORDER_COLOR = "#3A3A3A"
MAIN_LOBE_COLOR = "#0B3C75"
SIDE_LOBE_COLOR = "#D62728"
FS_COLOR = "#1F7A8C"
SAT_COLOR = "#5A5A5A"


plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "legend.fontsize": 7.7,
        "savefig.dpi": DPI,
    }
)


def add_poly(ax, xy: list[tuple[float, float]], color: str, alpha: float, edgecolor: str = "none") -> None:
    verts = [[(x, y, 0.0) for x, y in xy]]
    poly = Poly3DCollection(verts, facecolors=color, edgecolors=edgecolor, alpha=alpha, linewidths=0.8)
    ax.add_collection3d(poly)


def draw_regions(ax, scenario: str) -> None:
    service = [(-3.4, -1.2), (-0.25, -1.0), (-0.25, 1.25), (-3.4, 1.05)]
    paraguay = [(-0.25, -1.0), (2.4, -1.1), (2.4, 1.15), (-0.25, 1.25)]

    if scenario == "regional":
        add_poly(ax, service, SERVICE_COLOR, 0.22, "#5E8DB8")
        add_poly(ax, paraguay, SERVICE_COLOR, 0.16, "#5E8DB8")
        add_poly(ax, paraguay, PARAGUAY_COLOR, 0.20, "#D9965B")
    else:
        add_poly(ax, service, SERVICE_COLOR, 0.25, "#5E8DB8")
        add_poly(ax, paraguay, PARAGUAY_COLOR, 0.28, "#D9965B")

    ax.plot([-0.25, -0.25], [-1.15, 1.35], [0, 0], color=BORDER_COLOR, linewidth=1.4)


def draw_satellite(ax, pos: tuple[float, float, float], scale: float = 0.16) -> None:
    x, y, z = pos
    body = [
        (x - 0.10 * scale / 0.16, y - 0.07 * scale / 0.16, z - 0.05),
        (x + 0.10 * scale / 0.16, y - 0.07 * scale / 0.16, z - 0.05),
        (x + 0.10 * scale / 0.16, y + 0.07 * scale / 0.16, z + 0.05),
        (x - 0.10 * scale / 0.16, y + 0.07 * scale / 0.16, z + 0.05),
    ]
    ax.add_collection3d(Poly3DCollection([body], facecolors="white", edgecolors=SAT_COLOR, linewidths=1.0))
    for side in (-1, 1):
        panel = [
            (x + side * 0.17, y - 0.18, z - 0.03),
            (x + side * 0.46, y - 0.18, z - 0.03),
            (x + side * 0.46, y + 0.18, z + 0.03),
            (x + side * 0.17, y + 0.18, z + 0.03),
        ]
        ax.add_collection3d(Poly3DCollection([panel], facecolors="#E6EEF7", edgecolors=SAT_COLOR, linewidths=0.8))
    ax.scatter([x], [y], [z], s=14, color=SAT_COLOR, depthshade=False)


def circle_points(center: tuple[float, float], radius: float, n: int = 80) -> np.ndarray:
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack((center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta), np.zeros_like(theta)))


def draw_cone(
    ax,
    apex: tuple[float, float, float],
    center: tuple[float, float],
    radius: float,
    color: str,
    alpha: float,
    edge_alpha: float = 0.55,
) -> None:
    base = circle_points(center, radius)
    faces = []
    for idx in range(len(base)):
        faces.append([apex, tuple(base[idx]), tuple(base[(idx + 1) % len(base)])])
    cone = Poly3DCollection(faces, facecolors=color, edgecolors="none", linewidths=0.0, alpha=alpha)
    ax.add_collection3d(cone)
    ax.plot(base[:, 0], base[:, 1], base[:, 2], color=color, alpha=edge_alpha, linewidth=1.05)
    for idx in (0, len(base) // 3, 2 * len(base) // 3):
        ax.add_collection3d(
            Line3DCollection([[apex, tuple(base[idx])]], colors=color, linewidths=0.55, alpha=0.35)
        )


def draw_link(ax, start: tuple[float, float, float], end: tuple[float, float, float], color: str, linestyle: str, lw: float) -> None:
    line = Line3DCollection([[start, end]], colors=color, linestyles=linestyle, linewidths=lw)
    ax.add_collection3d(line)
    ax.scatter([end[0]], [end[1]], [end[2]], color=color, s=12, depthshade=False)


def draw_fs_receiver(ax, pos: tuple[float, float], azimuth_deg: float = 180) -> None:
    x, y = pos
    mast = [(x, y, 0.0), (x, y, 0.62)]
    ax.add_collection3d(Line3DCollection([mast], colors=FS_COLOR, linewidths=2.0))
    dish_radius = 0.18
    theta = np.linspace(-0.55, 0.55, 18) + np.deg2rad(azimuth_deg)
    rim = np.column_stack((x + dish_radius * np.cos(theta), y + dish_radius * np.sin(theta), np.full_like(theta, 0.62)))
    segments = [[(x, y, 0.62), tuple(point)] for point in rim]
    ax.add_collection3d(Line3DCollection(segments, colors=FS_COLOR, linewidths=1.0))
    ax.text(x + 0.13, y + 0.12, 0.70, "FS", fontsize=8.2, color=FS_COLOR, fontweight="bold")


def setup_axis(ax) -> None:
    ax.set_xlim(-3.6, 2.6)
    ax.set_ylim(-1.7, 1.7)
    ax.set_zlim(0, 3.2)
    ax.view_init(elev=24, azim=-61)
    ax.set_box_aspect((1.7, 1.0, 0.75))
    ax.set_axis_off()
    ax.grid(False)
    ax.xaxis.pane.set_alpha(0)
    ax.yaxis.pane.set_alpha(0)
    ax.zaxis.pane.set_alpha(0)


def draw_panel_a(ax) -> None:
    setup_axis(ax)
    draw_regions(ax, "regional")
    fs_pos = (0.65, 0.12)
    draw_fs_receiver(ax, fs_pos, azimuth_deg=175)

    sat_main = (0.35, 0.25, 3.0)
    sat_service = (-2.0, -0.25, 2.75)
    draw_satellite(ax, sat_main)
    draw_satellite(ax, sat_service)

    draw_cone(ax, sat_service, (-2.0, -0.2), 0.72, MAIN_LOBE_COLOR, 0.08)
    draw_link(ax, sat_service, (-2.0, -0.2, 0.05), MAIN_LOBE_COLOR, "-", 1.7)

    draw_cone(ax, sat_main, fs_pos, 0.66, MAIN_LOBE_COLOR, 0.10)
    draw_link(ax, sat_main, (fs_pos[0], fs_pos[1], 0.62), MAIN_LOBE_COLOR, "-", 2.0)
    draw_link(ax, sat_main, (fs_pos[0], fs_pos[1], 0.62), SIDE_LOBE_COLOR, "--", 1.4)

    ax.text(-3.45, 1.42, 3.02, "(A) Regional coverage", fontsize=10.2, fontweight="bold")
    ax.text(0.92, 0.42, 1.62, "direct\nmain-lobe\ncoupling", fontsize=7.8, color=MAIN_LOBE_COLOR)


def draw_panel_b(ax) -> None:
    setup_axis(ax)
    draw_regions(ax, "spillover")
    fs_pos = (0.72, 0.12)
    draw_fs_receiver(ax, fs_pos, azimuth_deg=175)

    sat_left = (-1.85, 0.15, 2.95)
    sat_right = (-0.95, -0.35, 2.65)
    draw_satellite(ax, sat_left)
    draw_satellite(ax, sat_right)

    draw_cone(ax, sat_left, (-1.9, 0.05), 0.70, MAIN_LOBE_COLOR, 0.09)
    draw_link(ax, sat_left, (-1.9, 0.05, 0.05), MAIN_LOBE_COLOR, "-", 1.8)

    draw_cone(ax, sat_right, (-1.05, -0.45), 0.55, MAIN_LOBE_COLOR, 0.09)
    draw_link(ax, sat_right, (-1.05, -0.45, 0.05), MAIN_LOBE_COLOR, "-", 1.8)

    draw_link(ax, sat_left, (fs_pos[0], fs_pos[1], 0.62), SIDE_LOBE_COLOR, "--", 1.55)
    draw_link(ax, sat_right, (fs_pos[0], fs_pos[1], 0.62), SIDE_LOBE_COLOR, "--", 1.35)

    ax.text(-0.88, 1.10, 0.15, "official coverage\nlimited by border", fontsize=7.4, color=BORDER_COLOR)
    ax.text(-3.45, 1.42, 3.02, "(B) Cross-border spillover", fontsize=10.2, fontweight="bold")


def build_figure(out_dir: Path) -> None:
    fig = plt.figure(figsize=(IEEE_TEXT_WIDTH_IN, FIG_HEIGHT_IN), dpi=DPI)
    ax_a = fig.add_subplot(1, 2, 1, projection="3d")
    ax_b = fig.add_subplot(1, 2, 2, projection="3d")

    draw_panel_a(ax_a)
    draw_panel_b(ax_b)

    legend_handles = [
        Patch(facecolor=SERVICE_COLOR, edgecolor="#5E8DB8", alpha=0.35, label="DC-MSS service area"),
        Patch(facecolor=PARAGUAY_COLOR, edgecolor="#D9965B", alpha=0.45, label="FS victim area"),
        plt.Line2D([0], [0], color=MAIN_LOBE_COLOR, lw=2.0, label="Main-lobe downlink"),
        plt.Line2D([0], [0], color=SIDE_LOBE_COLOR, lw=1.7, linestyle="--", label="Interference path"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
        handlelength=1.8,
        columnspacing=1.0,
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.13, wspace=0.02)

    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "dc_mss_fs_interference_geometry_3d.png"
    pdf_path = out_dir / "dc_mss_fs_interference_geometry_3d.pdf"
    fig.savefig(png_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] {png_path}")
    print(f"[ok] {pdf_path}")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    campaign_dir = script_dir.parent
    build_figure(campaign_dir / "plots" / "conceptual_geometry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

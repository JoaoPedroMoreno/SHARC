"""TCC campaign workflow using the original LATINCOM/Encom visual assets."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.text import Text
from matplotlib.transforms import Affine2D
import numpy as np
import yaml

import latincom_visual_style as style
from tcc_diagram_primitives import ground_plane, service_mesh, ue_dot, fs_on_ground, SATELLITE_TILT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
BLUE, INK, GRAY = style.BLUE, style.INK, "#aab8c0"


def text(ax, x, y, value, size=17, color=INK, **kwargs):
    return ax.text(x, y, value, fontsize=size, color=color, va="center", **kwargs)


def arrow(ax, start, end, color=BLUE, **kwargs):
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle":"-|>", "color":color, "lw":1.7, **kwargs})


def snapshot(ax, cx, cy, phase):
    """Illustrative local grid, not a computed satellite frame or campaign output."""
    rng = np.random.RandomState(100 + phase)
    transform = Affine2D().scale(.31, .14).skew_deg(8, 0).translate(cx, cy)
    ground_plane(ax, transform, (-3.6, -3.2, 5.5, 4.0))
    sources = [style.satellite(ax, cx-.65+phase*.12, cy+1.15, 1.1, tilt_deg=SATELLITE_TILT),
               style.satellite(ax, cx+.65-phase*.08, cy+1.28, 1.1, tilt_deg=SATELLITE_TILT)]
    foundation = transform.transform([[3.6, -.5], [4.6, -.5], [4.6, .5], [3.6, .5]])
    ax.add_patch(Polygon(foundation, fc="#dfe6e5", ec="#a3b2b1", lw=.6, zorder=4))
    base = transform.transform([4.1, 0])
    fs_on_ground(ax, base, .58)
    text(ax, base[0], cy-.62, "FS", 13, ha="center")
    selected = {(0, 0), (1, 1), (2, -1)} if phase == 0 else {(0, 1), (1, -1), (2, 1)}
    for key, center, raw_vertices, _ in service_mesh((-3.6, -3.2, 3, 4), (-2, 0)):
        vertices = transform.transform(raw_vertices)
        active = key in selected
        pbo = key[0] == 2 and active
        color = style.ORANGE if pbo else BLUE if active else GRAY
        ax.add_patch(Polygon(vertices, facecolor=style.original.ORANGE_PALE if pbo else "#d5e7f0" if active else "#f7f9fa",
                             edgecolor=color, lw=.8, zorder=3,
                             linestyle="-" if active else (0, (3, 2))))
        if active:
            style.original.beam(ax, sources[int(key[0]>=2)], vertices, pbo=pbo, broad=True, visual_scale=1)
            point = transform.transform(center + rng.uniform(-.25, .25, 2))
            ue_dot(ax, point, "#945a13" if pbo else "#235d7d", size=12)
    border = transform.transform([[3, -3.2], [3, 4]])
    ax.plot(*border.T, color="#a3b2b1", lw=.8, zorder=4)


def snapshot_legend(ax):
    for x, color, fill, label in ((4.05, BLUE, "#d5e7f0", "C\u00e9lula / feixe ativo"),
                                   (7.60, style.ORANGE, style.original.ORANGE_PALE, "Com PBO")):
        ax.add_patch(Polygon(style.hexagon(x+.14, 5.05, .14),
                             fc=fill, ec=color, lw=1))
        text(ax, x+.42, 5.05, label, 15)
    ax.add_patch(Polygon(style.hexagon(4.19, 4.57, .14), fc="#f7f9fa", ec=GRAY,
                         ls=(0, (3, 2)), lw=1.2))
    text(ax, 4.47, 4.57, "Inativo (sem transmiss\u00e3o)", 15)
    ue_dot(ax, (9.6, 4.57), "#235d7d", size=24)
    text(ax, 9.9, 4.57, "UE", 15)


def distribution(ax, left, bottom, width, height, ccdf):
    ax.plot([left, left, left+width], [bottom+height, bottom, bottom], color=GRAY, lw=1.2)
    t = np.linspace(0, 1, 23)
    values = 1-t**.7 if ccdf else t**.65
    ax.step(left+.07+t*(width-.14), bottom+.06+values*(height-.12),
            where="post", color=BLUE, lw=2)
    text(ax, left-.25, bottom+height/2, "CCDF" if ccdf else "CDF", 13,
         ha="center", rotation=90)
    text(ax, left+width/2, bottom-.23, "INR (dB)" if ccdf else "SINR (dB)", 14, ha="center")
    text(ax, left+width, bottom+height+.16, "Esquem\u00e1tica", 11, GRAY, ha="right")


def build(cfg07, cfg08):
    n07, n08 = [cfg["general"]["num_snapshots"] for cfg in (cfg07, cfg08)]
    fig, ax = plt.subplots(figsize=(16, 9.5))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 16), ylim=(0, 9.5))
    ax.axis("off")
    for x, title in ((.45, "Configura\u00e7\u00e3o"), (3.85, "Realiza\u00e7\u00f5es no SHARC"),
                     (11.8, "An\u00e1lise estat\u00edstica")):
        text(ax, x, 8.95, title, 21, BLUE, weight="bold")

    text(ax, .45, 8.12, "Am\u00e9rica do Sul\nsem Paraguai", 17, linespacing=1.35)
    style.satellite(ax, 1.45, 6.93, 1.8)
    text(ax, .45, 6.23, "Sistema 3: 340 / 525 km", 17)
    text(ax, .45, 5.73, "LF: 20 / 50%", 18)
    style.receiver(ax, 1.05, 3.78, .10)
    text(ax, 1.95, 4.40, "FS\n20 / 40 m", 17, linespacing=1.5)
    text(ax, .45, 3.10, "Configura\u00e7\u00f5es da\nmitiga\u00e7\u00e3o", 18, BLUE,
         weight="bold", linespacing=1.3)
    text(ax, .45, 2.15, "Baseline: sem mitiga\u00e7\u00e3o", 15)
    text(ax, .45, 1.65, "PBO: 10 dB | 10 a 100 km", 15)
    text(ax, .45, 1.15, "HO: 5 a 30 trocas", 15)
    arrow(ax, (3.05, 5.3), (3.65, 5.3))

    text(ax, 7.35, 8.25, "Geometria, associa\u00e7\u00f5es, UEs e atividade por LF", 16, ha="center")
    text(ax, 5.35, 7.65, "Snapshot 1", 17, ha="center")
    text(ax, 9.3, 7.65, "Snapshot N", 17, ha="center")
    snapshot(ax, 5.15, 6.10, 0)
    snapshot(ax, 9.1, 6.10, 1)
    text(ax, 7.38, 6.15, r"$\cdots$", 28, BLUE, ha="center")
    snapshot_legend(ax)
    arrow(ax, (7.35, 4.25), (7.35, 4.02))
    text(ax, 3.85, 3.70, "Em cada snapshot, o SHARC calcula:", 18, BLUE, weight="bold")
    text(ax, 3.85, 3.15, "Interfer\u00eancia agregada (I) e INR no FS", 17)
    text(ax, 3.85, 2.65, "Ganhos, perdas e \u00e2ngulos dos enlaces", 17)
    text(ax, 3.85, 2.08, "UEs, na campanha de desempenho:", 15, BLUE, weight="bold")
    text(ax, 3.85, 1.62, "Pot\u00eancia do sinal (S), ru\u00eddo (N), SNR e SINR", 16)
    text(ax, 3.85, 1.16, "Atendimento e efici\u00eancia espectral (proxy)", 16)

    # The two analyses are separate campaigns, not consecutive processing stages.
    ax.plot([10.95, 11.35, 11.35], [3.7, 3.7, 7.93], color=BLUE, lw=1.5)
    arrow(ax, (11.35, 7.93), (11.72, 7.93))
    arrow(ax, (11.35, 4.43), (11.72, 4.43))
    text(ax, 11.8, 7.93, "Campanha de interfer\u00eancia", 17, BLUE, weight="bold")
    text(ax, 11.8, 7.48, f"{n07:,} snapshots | INR no FS".replace(",", " "), 16)
    distribution(ax, 12.18, 5.77, 3.27, 1.15, True)
    text(ax, 13.8, 5.08, r"$\mathrm{INR}_{20}$, $M_{20}$ e IC de 95%", 16, ha="center")
    text(ax, 11.8, 4.43, "Campanha de desempenho", 17, BLUE, weight="bold")
    text(ax, 11.8, 3.98, f"{n08:,} snapshots | UEs".replace(",", " "), 16)
    distribution(ax, 12.18, 2.27, 3.27, 1.15, False)
    text(ax, 13.8, 1.42, "SINR, atendimento e\nefici\u00eancia espectral (proxy)", 15,
         ha="center", linespacing=1.4)
    return fig


def main():
    plt.rcParams.update({"font.family":"DejaVu Sans", "svg.fonttype":"none", "pdf.fonttype":42})
    paths = [ROOT / f"sharc/campaigns/{name}/Scripts/base_input.yaml" for name in
             ("07_TCC2_DC_MSS_to_FS", "08_TCC2_DC_MSS_performance")]
    configs = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]
    assert [cfg["general"]["num_snapshots"] for cfg in configs] == [10000, 1000]
    assert configs[0]["imt"]["imt_dl_intra_sinr_calculation_disabled"]
    assert not configs[1]["imt"]["imt_dl_intra_sinr_calculation_disabled"]
    fig = build(*configs)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist in fig.findobj(match=Text):
        if not artist.get_visible() or not artist.get_text():
            continue
        box = artist.get_window_extent(renderer)
        assert box.x0 >= 0 and box.y0 >= 0 and box.x1 <= fig.bbox.width and box.y1 <= fig.bbox.height, artist.get_text()
    stem = OUT / "fig_fluxo_sharc_metodologia"
    fig.savefig(stem.with_suffix(".png"), dpi=320, facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), dpi=320, facecolor="white")
    fig.savefig(OUT / "fig_fluxo_sharc_metodologia_preview.png", dpi=100, facecolor="white")
    plt.close(fig)
    report = {"source_configs":[str(path) for path in paths], "snapshots_per_config":[10000, 1000],
              "schematic_not_simulation_output":True, "curves_are_illustrative":True,
              "no_simulations_executed":True, "original_assets":"LATINCOM / Encom Blender assets",
              "treatments_are_alternatives":True, "no_temporal_snapshot_sequence":True,
              "shared_ground_plane":True, "satellite_tilt_deg":SATELLITE_TILT,
              "ue_symbols":"dark cell-colored dots in active cells only", "red_interference_arrows":False,
              "service_plane_fully_tessellated":True, "fs_side_has_no_service_grid":True,
              "legend_cell_symbols":"hexagons",
              "snapshot_colors":"nominal blue, PBO orange when applied; gray dashed inactive",
              "performance_metrics_scope":"campaign 08 only",
              "text_inside_canvas":True}
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()

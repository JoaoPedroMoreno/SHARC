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
    transform = Affine2D().scale(.35, .16).skew_deg(8, 0).translate(cx, cy)
    sources = [style.satellite(ax, cx-.72+phase*.12, cy+1.2, 1.1, tilt_deg=-8),
               style.satellite(ax, cx+.72-phase*.08, cy+1.35, 1.1, tilt_deg=8)]
    target = style.receiver(ax, cx-1.35, cy-.55, .065)
    text(ax, cx-1.35, cy-.93, "FS", 13, ha="center")
    selected = {1, 5, 8} if phase == 0 else {0, 4, 10}
    for col in range(4):
        for row in range(3):
            i = 3*col+row
            center = np.array([(col-1.5)*1.5, np.sqrt(3)*(row-1+.5*(col%2))])
            vertices = transform.transform(style.hexagon(*center, 1))
            active = i in selected
            ax.add_patch(Polygon(vertices, facecolor="#d5e7f0" if active else "#f7f9fa",
                                 edgecolor=BLUE if active else GRAY, lw=.8, zorder=3))
            if active:
                style.original.beam(ax, sources[int(col>=2)], vertices, broad=True, visual_scale=1)
            point = transform.transform(center + rng.uniform(-.3, .3, 2))
            ax.scatter(*point, s=13, facecolor="#b47525", edgecolor="white", linewidth=.3, zorder=20)
    for source in sources:
        arrow(ax, source, target, style.RED, linestyle=(0, (4, 3)))


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
    text(ax, .45, 3.03, "8 cen\u00e1rios-base", 19, BLUE, weight="bold")
    text(ax, .45, 2.48, "YAML por configura\u00e7\u00e3o", 16)
    arrow(ax, (3.05, 5.3), (3.65, 5.3))

    text(ax, 7.35, 8.25, "Geometria, associa\u00e7\u00f5es, UEs e atividade por LF", 16, ha="center")
    text(ax, 5.35, 7.65, "Snapshot 1", 17, ha="center")
    text(ax, 9.3, 7.65, "Snapshot N", 17, ha="center")
    snapshot(ax, 5.35, 5.9, 0)
    snapshot(ax, 9.3, 5.9, 1)
    text(ax, 7.38, 6.15, r"$\cdots$", 28, BLUE, ha="center")
    text(ax, 7.35, 4.60, "Snapshots independentes, sem evolu\u00e7\u00e3o temporal", 15, ha="center")
    arrow(ax, (7.35, 4.32), (7.35, 3.98))
    text(ax, 3.85, 3.70, "Uma estrat\u00e9gia por configura\u00e7\u00e3o", 18, BLUE, weight="bold")
    text(ax, 3.85, 3.17, "Baseline", 17, weight="bold")
    text(ax, 6.25, 3.17, "Sem mitiga\u00e7\u00e3o", 17)
    text(ax, 3.85, 2.55, "PBO geogr\u00e1fico", 17, weight="bold")
    text(ax, 6.25, 2.55, "10 dB | faixa de 10 a 100 km", 17)
    text(ax, 6.25, 2.16, "Lado externo da fronteira paraguaia", 14)
    text(ax, 3.85, 1.61, "Handover", 17, weight="bold")
    text(ax, 3.85, 1.22, "N\u00e3o temporal", 14)
    text(ax, 6.25, 1.61, "5, 10, 15, 20, 25 ou 30 trocas", 17)
    text(ax, 6.25, 1.22, "Limite de reassocia\u00e7\u00f5es aceitas por snapshot", 14)

    # The two analyses are separate campaigns, not consecutive processing stages.
    ax.plot([10.95, 11.35, 11.35], [3.7, 3.7, 7.93], color=BLUE, lw=1.5)
    arrow(ax, (11.35, 7.93), (11.72, 7.93))
    arrow(ax, (11.35, 4.43), (11.72, 4.43))
    text(ax, 11.8, 7.93, f"Campanha 07 | N = {n07:,}".replace(",", " "), 18, BLUE, weight="bold")
    text(ax, 11.8, 7.48, "Interfer\u00eancia agregada no FS", 16)
    distribution(ax, 12.18, 5.77, 3.27, 1.15, True)
    text(ax, 13.8, 5.08, r"$\mathrm{INR}_{20}$, $M_{20}$ e IC de 95%", 16, ha="center")
    text(ax, 11.8, 4.43, f"Campanha 08 | N = {n08:,}".replace(",", " "), 18, BLUE, weight="bold")
    text(ax, 11.8, 3.98, "Desempenho dos UEs", 16)
    distribution(ax, 12.18, 2.27, 3.27, 1.15, False)
    text(ax, 13.8, 1.42, "SINR, atendimento e\nefici\u00eancia espectral (proxy)", 15,
         ha="center", linespacing=1.4)
    ax.plot([.45, 15.55], [.78, .78], color="#dce3e7", lw=1)
    text(ax, 8, .37, "Compara\u00e7\u00e3o estat\u00edstica: baseline, PBO e handover", 19, BLUE, ha="center")
    return fig


def main():
    plt.rcParams.update({"font.family":"DejaVu Sans", "svg.fonttype":"none"})
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
    fig.savefig(OUT / "fig_fluxo_sharc_metodologia_preview.png", dpi=100, facecolor="white")
    plt.close(fig)
    report = {"source_configs":[str(path) for path in paths], "snapshots_per_config":[10000, 1000],
              "schematic_not_simulation_output":True, "curves_are_illustrative":True,
              "no_simulations_executed":True, "original_assets":"LATINCOM / Encom Blender assets",
              "treatments_are_alternatives":True, "no_temporal_snapshot_sequence":True,
              "text_inside_canvas":True}
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(stem.with_suffix(".png"))


if __name__ == "__main__":
    main()

"""Conceptual LF diagram and code-derived campaign spectral configuration."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Patch
from matplotlib.text import Text
from matplotlib.transforms import Affine2D
import numpy as np
import yaml

import latincom_visual_style as style
from sharc.mask.spectral_mask_mss import SpectralMaskMSS


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
BASE = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml"
BLUE, INK, GRAY = style.BLUE, style.INK, "#aab8c0"


def save(fig, name):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(match=Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(renderer)
            assert box.x0 >= 0 and box.y0 >= 0, text.get_text()
            assert box.x1 <= fig.bbox.width and box.y1 <= fig.bbox.height, text.get_text()
    fig.savefig(OUT / f"{name}.png", dpi=320, facecolor="white")
    fig.savefig(OUT / f"{name}.svg", facecolor="white")
    fig.savefig(OUT / f"{name}_preview.png", dpi=100, facecolor="white")
    plt.close(fig)


def load_diagram():
    # One illustrative realization, shared by both panels; not campaign output.
    rng = np.random.RandomState(838)
    axial = [(q, r) for q in range(-2, 3) for r in range(-2, 3)
             if abs(q + r) <= 2]
    uniforms = rng.rand(len(axial))
    centers = np.array([(1.5*q, np.sqrt(3)*(r+q/2)) for q, r in axial])
    transform = Affine2D().scale(1.45, .65).skew_deg(8, 0).translate(10, 3.5)
    positions = transform.transform(centers)
    # Geometrically plausible, fixed cell assignments for the two LF examples.
    assignments = (centers[:, 0] > 0).astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    fig.subplots_adjust(left=.015, right=.985, top=.98, bottom=.16, wspace=.025)
    counts = []
    for ax, lf in zip(axes, (.2, .5)):
        ax.set(xlim=(0, 20), ylim=(-1.5, 13.3))
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(10, 12.5, f"LF = {lf:.0%}", fontsize=23, color=INK, ha="center")
        ax.text(10, 11.55, f"Cada feixe: {lf:.0%} ativo | {1-lf:.0%} inativo",
                fontsize=15, color=INK, ha="center")
        feeds = [style.satellite(ax, 5.7, 9.25, 5.5),
                 style.satellite(ax, 14.3, 9.25, 5.5)]
        for x, label in ((5.7, "Sat\u00e9lite A"), (14.3, "Sat\u00e9lite B")):
            ax.text(x, 10.35, label, fontsize=15, color=INK, ha="center")
        active = uniforms < lf
        for i, center in enumerate(centers):
            vertices = transform.transform(style.hexagon(*center, 1))
            ax.add_patch(Polygon(vertices, facecolor="#d5e7f0" if active[i] else "#f7f9fa",
                                 edgecolor=BLUE if active[i] else GRAY, lw=1.1, zorder=3))
            source = feeds[assignments[i]]
            if active[i]:
                style.original.beam(ax, source, vertices, broad=True, visual_scale=1)
            else:
                ax.plot([source[0], positions[i, 0]], [source[1], positions[i, 1]],
                        color=GRAY, lw=.7, alpha=.48, ls=(0, (3, 4)), zorder=2)
            ax.text(positions[i, 0], positions[i, 1]+.19, "AB"[assignments[i]], color=INK if active[i] else "#7f8d95",
                    fontsize=10, ha="center", va="center", zorder=20)
            # Illustrative UEs remain present even when their beam is inactive.
            users = transform.transform(center + np.array([[-.30, -.30], [.30, -.30]]))
            ax.scatter(users[:, 0], users[:, 1], s=23, facecolor="#b47525",
                       edgecolor="white", linewidth=.55, zorder=21)
        count = int(active.sum())
        counts.append(count)
        ax.text(10, -.65, f"Neste snapshot: {count} de {len(axial)} feixes ativos", fontsize=16,
                color=INK, ha="center")
    fig.text(.5, .145, "Sorteio por feixe a cada snapshot: a fra\u00e7\u00e3o ativa n\u00e3o \u00e9 fixa.",
             ha="center", fontsize=16, color=INK)
    fig.legend(handles=[Patch(facecolor="#d5e7f0", edgecolor=BLUE, label="C\u00e9lula com feixe ativo"),
                        Patch(facecolor="#f7f9fa", edgecolor=GRAY, label="C\u00e9lula com feixe inativo"),
                        Line2D([], [], color=GRAY, ls="--", label="Associa\u00e7\u00e3o sem transmiss\u00e3o"),
                        Line2D([], [], marker="o", ls="none", color="#b47525", label="UE")],
               loc="lower center", bbox_to_anchor=(.5, .035), ncol=4, frameon=False,
               fontsize=14, labelcolor=INK)
    save(fig, "fig_malha_servico_ativacao")
    return {"illustrative_only": True, "seed": 838, "candidates": len(axial),
            "active_counts_lf20_lf50": counts, "shared_uniform_draws": uniforms.tolist(),
            "activation_rule": "uniform < LF; independent per candidate beam",
            "assignment_labels": "A and B identify the associated satellite; no handover illustrated"}


def spectrum(cfg):
    imt, fs = cfg["imt"], cfg["single_earth_station"]
    fc, bw = imt["frequency"], imt["bandwidth"]
    fs_fc, fs_bw = fs["frequency"], fs["bandwidth"]
    assert (fc, bw, fs_fc, fs_bw) == (2155., 5., 2155., 29.)
    assert imt["spectral_mask"] == "MSS"
    assert cfg["general"]["enable_cochannel"] and not cfg["general"]["enable_adjacent_channel"]
    mask = SpectralMaskMSS(fc, bw, imt["spurious_emissions"])
    mask.set_mask(imt["bs"]["conducted_power"])
    f = np.sort(np.unique(np.r_[np.linspace(fc-16, fc+16, 16001), mask.freq_lim]))
    relative = mask.mask_dbm[np.searchsorted(mask.freq_lim, f, side="right")] - mask.p_tx
    inband = (f >= fc-bw/2) & (f <= fc+bw/2)
    assert np.max(np.abs(relative[inband])) < 1e-10
    assert fs_fc-fs_bw/2 < fc-bw/2 < fc+bw/2 < fs_fc+fs_bw/2
    fig = plt.figure(figsize=(16, 9))
    ax = fig.add_axes([.11, .57, .85, .31])
    rx = fig.add_axes([.11, .16, .85, .24])
    for axis in (rx, ax):
        axis.set_xlim(fc-16, fc+16)
    ax.set_title("DC-MSS-IMT: m\u00e1scara de transmiss\u00e3o MSS", loc="left", fontsize=20,
                 color=INK, pad=18)
    rx.set_title("FS: janela equivalente de recep\u00e7\u00e3o cocanal", loc="left", fontsize=20,
                 color=INK, pad=18)
    ax.axvspan(fc-bw/2, fc+bw/2, color=BLUE, alpha=.12, zorder=0)
    ax.axvline(fc, color=INK, lw=1, ls=(0, (3, 4)))
    for edge in (fs_fc-fs_bw/2, fs_fc+fs_bw/2):
        ax.axvline(edge, color=GRAY, lw=1)
    ax.step(f, np.where(~inband, relative, np.nan), where="post", color=BLUE,
            lw=1.8, ls="--")
    ax.plot([fc-bw/2, fc+bw/2], [0, 0], color=BLUE, lw=3,
            label="Banda cocanal contida na banda FS")
    ax.set_ylim(-56, 13)
    ax.set_yticks([-50, -25, 0])
    ax.text(fc, 5, "5 MHz", ha="center", fontsize=16, color=INK,
            bbox={"facecolor":"white", "edgecolor":"none", "pad":2}, zorder=8)
    ax.text(fc, -46, "Emiss\u00f5es fora de banda desativadas na campanha", ha="center",
            fontsize=14, color=INK, bbox={"facecolor":"white", "edgecolor":"none", "pad":4})
    ticks = [fs_fc-fs_bw/2, fc-bw/2, fc, fc+bw/2, fs_fc+fs_bw/2]
    ax.set_ylabel("Densidade relativa\n(dB)", fontsize=17, color=INK, labelpad=15)
    low, high = fs_fc-fs_bw/2, fs_fc+fs_bw/2
    rx.plot([fc-16, low, low, high, high, fc+16], [0, 0, 1, 1, 0, 0],
            color=INK, lw=2.2)
    rx.fill_between([low, high], 0, 1, color="#e9edef")
    rx.axvspan(fc-bw/2, fc+bw/2, color=BLUE, alpha=.25)
    rx.axvline(fc, color=INK, lw=1, ls=(0, (3, 4)))
    rx.annotate("", xy=(high, 1.18), xytext=(low, 1.18),
                arrowprops={"arrowstyle":"<->", "color":INK, "lw":1.1})
    rx.text(fc, 1.18, "29 MHz", ha="center", va="center", fontsize=16, color=INK,
            bbox={"facecolor":"white", "edgecolor":"none", "pad":3}, zorder=8)
    rx.text(fc-8.5, .5, "Banda FS", ha="center", fontsize=16, color=INK)
    rx.annotate("Canal DC-MSS-IMT\ninteiramente contido", xy=(fc+1, .45),
                xytext=(fc+8, .5), ha="center", va="center", fontsize=15, color=INK,
                arrowprops={"arrowstyle":"->", "color":INK, "lw":1.2})
    rx.set_ylim(-.09, 1.35)
    rx.set_yticks([0, 1])
    rx.set_ylabel("Peso de recep\u00e7\u00e3o\n(normalizado)", fontsize=17, color=INK, labelpad=15)
    rx.set_xlabel("Frequ\u00eancia (MHz)", fontsize=17, color=INK, labelpad=15)
    for axis in (rx, ax):
        axis.set_xticks(ticks, [f"{v:g}".replace(".", ",") for v in ticks])
        axis.tick_params(labelsize=14, colors=INK)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color(INK)
    save(fig, "fig_sobreposicao_espectral")
    return {"source": str(BASE), "mask_class": "SpectralMaskMSS",
            "mask_is_integrated_in_campaign": False, "adjacent_channel_enabled": False,
            "fs_band_mhz": [fs_fc-fs_bw/2, fs_fc+fs_bw/2],
            "imt_channel_mhz": [fc-bw/2, fc+bw/2],
            "inband_reference_dbm_per_mhz": float(mask.p_tx),
            "spurious_dbm_per_mhz": imt["spurious_emissions"],
            "fs_reception": "Rectangular equivalent overlap window, not a measured receiver filter",
            "fs_acs_configured_db": fs["adjacent_ch_selectivity"],
            "fs_acs_used_in_this_campaign": False,
            "note": "Nominal channel and configured mask, not individual scheduled resource blocks or measured PSD"}


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    cfg = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    report = {"load_factor": load_diagram(), "spectrum": spectrum(cfg)}
    (OUT / "malha_e_espectro_validacao.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

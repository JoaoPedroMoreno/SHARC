"""Conceptual LF diagram and code-derived campaign spectral configuration."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Patch, Rectangle
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
        ax.set(xlim=(0, 20), ylim=(-1.5, 12))
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(10, 11.4, f"LF = {lf:.0%}", fontsize=23, color=INK, ha="center")
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
            ax.text(*positions[i], "AB"[assignments[i]], color=INK if active[i] else "#7f8d95",
                    fontsize=10, ha="center", va="center", zorder=20)
        count = int(active.sum())
        counts.append(count)
        ax.text(10, -.65, f"Exemplo: {count} ativos / {len(axial)} candidatos", fontsize=17,
                color=INK, ha="center")
    fig.legend(handles=[Patch(facecolor="#d5e7f0", edgecolor=BLUE, label="C\u00e9lula com feixe ativo"),
                        Patch(facecolor="#f7f9fa", edgecolor=GRAY, label="C\u00e9lula com feixe inativo"),
                        Line2D([], [], color=GRAY, ls="--", label="Associa\u00e7\u00e3o sem transmiss\u00e3o")],
               loc="lower center", bbox_to_anchor=(.5, .055), ncol=3, frameon=False,
               fontsize=15, labelcolor=INK)
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
    fig = plt.figure(figsize=(16, 8.4))
    bands = fig.add_axes([.11, .77, .85, .17])
    ax = fig.add_axes([.11, .14, .85, .57])
    for axis in (bands, ax):
        axis.set_xlim(fc-16, fc+16)
    bands.set_ylim(0, 2.5)
    bands.axis("off")
    bands.add_patch(Rectangle((fs_fc-fs_bw/2, 1.5), fs_bw, .38,
                              facecolor="#e9edef", edgecolor=INK, lw=1.2))
    bands.text(fc, 2.08, "Banda de recep\u00e7\u00e3o FS: 29 MHz", ha="center", fontsize=18, color=INK)
    bands.add_patch(Rectangle((fc-bw/2, .2), bw, .38,
                              facecolor="#d5e7f0", edgecolor=BLUE, lw=1.5))
    bands.text(fc, .8, "Canal DC-MSS-IMT: 5 MHz", ha="center", fontsize=18, color=INK)
    ax.axvspan(fc-bw/2, fc+bw/2, color=BLUE, alpha=.12, zorder=0)
    ax.axvline(fc, color=INK, lw=1, ls=(0, (3, 4)))
    for edge in (fs_fc-fs_bw/2, fs_fc+fs_bw/2):
        ax.axvline(edge, color=GRAY, lw=1)
    ax.step(f, np.where(~inband, relative, np.nan), where="post", color="#6d7b84",
            lw=1.8, ls="--", label="M\u00e1scara MSS fora de banda (n\u00e3o integrada)")
    ax.plot([fc-bw/2, fc+bw/2], [0, 0], color=BLUE, lw=3,
            label="Banda cocanal contida na banda FS")
    ax.set_ylim(-56, 5)
    ax.set_yticks([-50, -40, -30, -20, -10, 0])
    ticks = [fs_fc-fs_bw/2, fc-bw/2, fc, fc+bw/2, fs_fc+fs_bw/2]
    ax.set_xticks(ticks, [f"{v:g}".replace(".", ",") for v in ticks])
    ax.set_xlabel("Frequ\u00eancia (MHz)", fontsize=17, color=INK, labelpad=15)
    ax.set_ylabel("Densidade espectral relativa (dB)", fontsize=17, color=INK, labelpad=15)
    ax.tick_params(labelsize=14, colors=INK)
    ax.grid(axis="y", color="#dce3e7", lw=.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK)
    ax.legend(loc="lower center", bbox_to_anchor=(.5, .06), frameon=True,
              facecolor="white", edgecolor="none", framealpha=.97, fontsize=15)
    save(fig, "fig_sobreposicao_espectral")
    return {"source": str(BASE), "mask_class": "SpectralMaskMSS",
            "mask_is_integrated_in_campaign": False, "adjacent_channel_enabled": False,
            "fs_band_mhz": [fs_fc-fs_bw/2, fs_fc+fs_bw/2],
            "imt_channel_mhz": [fc-bw/2, fc+bw/2],
            "inband_reference_dbm_per_mhz": float(mask.p_tx),
            "spurious_dbm_per_mhz": imt["spurious_emissions"],
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

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
from matplotlib.path import Path as MplPath
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
    # Draw each cell's independent six-snapshot example as one row.
    draws = rng.rand(len(axial), 6).T
    uniforms = draws[0]
    centers = np.array([(1.5*q, np.sqrt(3)*(r+q/2)) for q, r in axial])
    transform = Affine2D().scale(1.45, .65).skew_deg(8, 0).translate(10, 3.5)
    positions = transform.transform(centers)
    # Geometrically plausible, fixed cell assignments for the two LF examples.
    assignments = (centers[:, 0] > 0).astype(int)
    highlighted = int(np.argmin(centers[:, 1]))
    # Pedagogical example, not measured output: show both possible states at each LF.
    draws[:, highlighted] = [.32, .74, .12, .41, .08, .62]
    ue_rng = np.random.RandomState(20261113)
    local_hex = MplPath(style.hexagon(0, 0, .83))
    ue_offsets = []
    for _ in centers:
        points = []
        while len(points) < 2:
            point = ue_rng.uniform(-.83, .83, 2)
            # Reserve only the small label area, and keep UE dots distinguishable.
            if (local_hex.contains_point(point) and
                    np.linalg.norm(point-[0, .29]) > .23 and
                    all(np.linalg.norm(point-other) > .32 for other in points)):
                points.append(point)
        ue_offsets.append(np.array(points))
    assert all(local_hex.contains_points(points).all() for points in ue_offsets)
    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    fig.subplots_adjust(left=.015, right=.985, top=.98, bottom=.14, wspace=.025)
    counts = []
    for ax, lf in zip(axes, (.2, .5)):
        ax.set(xlim=(0, 20), ylim=(-6, 13.3))
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
            users = transform.transform(center + ue_offsets[i])
            ax.scatter(users[:, 0], users[:, 1], s=23, facecolor="#b47525",
                       edgecolor="white", linewidth=.55, zorder=21)
        count = int(active.sum())
        counts.append(count)
        ax.add_patch(Polygon(transform.transform(style.hexagon(*centers[highlighted], 1)),
                             facecolor="none", edgecolor=INK, lw=2.2, zorder=22))
        ax.annotate("", xy=(10, -.55), xytext=positions[highlighted]+[0, -.62],
                    arrowprops={"arrowstyle":"->", "color":INK, "lw":1.3})
        ax.text(10, -1.2, "C\u00e9lula destacada: exemplo de sorteios independentes", fontsize=16,
                color=INK, ha="center")
        states = draws[:, highlighted] < lf
        for j, state in enumerate(states):
            x = 3.3 + j*2.68
            ax.add_patch(Polygon(style.hexagon(x, -2.7, .63),
                                 facecolor="#d5e7f0" if state else "#f7f9fa",
                                 edgecolor=BLUE if state else GRAY, lw=1.5))
            ax.text(x, -2.7, "AB"[assignments[highlighted]], ha="center", va="center", fontsize=12, color=INK)
            ax.text(x, -3.85, f"Snap. {j+1}", ha="center", fontsize=12, color=INK)
            ax.text(x, -4.65, "Ativa" if state else "Inativa", ha="center", fontsize=12, color=INK)
    fig.text(.5, .12, "Cada c\u00e9lula eleg\u00edvel tem seu pr\u00f3prio sorteio; n\u00e3o h\u00e1 uma cota de c\u00e9lulas ativas.",
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
            "highlighted_cell_index": highlighted,
            "highlighted_cell_uniforms": draws[:, highlighted].tolist(),
            "highlighted_series": "Constructed pedagogical uniform examples, not simulation observations",
            "ue_offsets": [points.tolist() for points in ue_offsets],
            "ues_within_cells": True,
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
    frequency_half_span = 27
    f = np.sort(np.unique(np.r_[np.linspace(fc-frequency_half_span, fc+frequency_half_span, 27001), mask.freq_lim]))
    relative = mask.mask_dbm[np.searchsorted(mask.freq_lim, f, side="right")] - mask.p_tx
    inband = (f >= fc-bw/2) & (f <= fc+bw/2)
    assert np.max(np.abs(relative[inband])) < 1e-10
    assert fs_fc-fs_bw/2 < fc-bw/2 < fc+bw/2 < fs_fc+fs_bw/2
    fig = plt.figure(figsize=(16, 8.4))
    ax = fig.add_axes([.105, .15, .86, .72])
    ax.set_xlim(fc-frequency_half_span, fc+frequency_half_span)
    ax.set_ylim(-17, 44)
    low, high = fs_fc-fs_bw/2, fs_fc+fs_bw/2
    fs_band = ax.axvspan(low, high, facecolor="#edf2f5", edgecolor="#94a8b5",
                        lw=1.3, label="Banda de recep\u00e7\u00e3o FS: 29 MHz", zorder=0)
    # One uninterrupted trace, identical styling in-band, OOB and spurious regions.
    line, = ax.step(f, relative+mask.p_tx, where="post", color=BLUE, lw=2.8,
                    label="M\u00e1scara DC-MSS-IMT (MSS)", zorder=3)
    floor = ax.axhline(imt["spurious_emissions"], color="#7b858b", ls=(0, (5, 4)),
                      lw=1.5, label="Piso esp\u00fario: \u221213 dBm/MHz", zorder=4)
    ax.annotate("", xy=(fc-bw/2, 39.5), xytext=(fc+bw/2, 39.5),
                arrowprops={"arrowstyle":"<->", "color":INK, "lw":1.2})
    ax.text(fc, 39.5, "5 MHz", fontsize=17, ha="center", va="center", color=INK,
            bbox={"facecolor":"#edf2f5", "edgecolor":"none", "pad":3}, zorder=5)
    ticks = [2130, low, fc, high, 2180]
    ax.set_ylabel("Densidade espectral de pot\u00eancia (dBm/MHz)", fontsize=18, color=INK, labelpad=15)
    ax.set_xlabel("Frequ\u00eancia (MHz)", fontsize=18, color=INK, labelpad=15)
    ax.set_xticks(ticks, [f"{v:g}".replace(".", ",") for v in ticks])
    ax.set_yticks([-10, 0, 10, 20, 30, 40])
    ax.tick_params(labelsize=15, colors=INK)
    ax.grid(axis="y", color="#dce3e7", lw=.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK)
    fig.legend(handles=[line, fs_band, floor], loc="upper center", bbox_to_anchor=(.54, .97),
               ncol=3, fontsize=15, frameon=False, labelcolor=INK)
    save(fig, "fig_sobreposicao_espectral")
    return {"source": str(BASE), "mask_class": "SpectralMaskMSS",
            "mask_is_integrated_in_campaign": False, "adjacent_channel_enabled": False,
            "fs_band_mhz": [fs_fc-fs_bw/2, fs_fc+fs_bw/2],
            "frequency_axis_mhz": [fc-frequency_half_span, fc+frequency_half_span],
            "imt_channel_mhz": [fc-bw/2, fc+bw/2],
            "inband_reference_dbm_per_mhz": float(mask.p_tx),
            "spurious_dbm_per_mhz": imt["spurious_emissions"],
            "fs_reception": "Shaded 29 MHz reception band on the same axes; not a measured receiver filter",
            "display_psd": "Absolute dBm/MHz at nominal 42.8 dBm per-beam power, without PBO",
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

"""Generate the seven final, reproducible figures for the DC-MSS/EESS study."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SITE_PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"
if SITE_PACKAGES.is_dir():
    sys.path.append(str(SITE_PACKAGES))
sys.path.insert(0, str(ROOT))

import matplotlib as mpl
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle
from PIL import Image

from sharc.mask.spectral_mask_mss import SpectralMaskMSS

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
OP_CAMPAIGN = CAMPAIGN.parent / "06_DC_MSS_to_EESS_operational_risk_diagnostics"
OP_ANALYSIS = OP_CAMPAIGN / "analysis"
CP_DIR = OP_ANALYSIS / "clopper_pearson"
RX_DIR = OP_ANALYSIS / "rx_min_operational_risk"

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
CYAN = "#56B4E9"
GRAY = "#777777"
LIGHT = "#D9D9D9"
DARK = "#262626"
RED = "#C43C2F"
PEACH = "#F6C28B"
SCENARIOS = [
    (340, "B", 0.2), (340, "B", 0.5), (340, "D", 0.2), (340, "D", 0.5),
    (525, "B", 0.2), (525, "B", 0.5), (525, "D", 0.2), (525, "D", 0.5),
]
LABELS = [f"{a}-{s}-{lf:.1f}".replace(".", ",") for a, s, lf in SCENARIOS]


def setup_style():
    mpl.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 8.0, "axes.labelsize": 8.3,
        "xtick.labelsize": 7.1, "ytick.labelsize": 7.1, "legend.fontsize": 7.0,
        "axes.linewidth": 0.7, "lines.linewidth": 1.25, "lines.markersize": 4.5,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.facecolor": "white",
        "figure.facecolor": "white", "axes.facecolor": "white",
    })


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unavailable"


def export(fig, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    figure_number = int(folder.name.removeprefix("fig"))
    for suffix, kwargs in (("png", {"dpi": 600}), ("pdf", {}), ("svg", {})):
        fig.savefig(folder / f"figure{figure_number}.{suffix}", bbox_inches="tight", facecolor="white", **kwargs)
    plt.close(fig)


def manifest(folder: Path, *, title: str, caption: str, inputs: list[Path], filters: dict,
             metrics: dict, samples: dict, ci: str = "não aplicável", notes: list[str] | None = None):
    payload = {
        "title": title, "caption_sugerida": caption,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_git_commit": git_commit(), "analysis_script": str(Path(__file__).resolve()),
        "analysis_script_sha256": sha256(Path(__file__)),
        "input_files": [{"path": str(p.resolve()), "sha256": sha256(p)} for p in inputs if p.is_file()],
        "filters": filters, "metric_definitions": metrics, "sample_counts": samples,
        "confidence_interval_method": ci, "notes": notes or [],
    }
    (folder / "manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def clean(ax, axis="both"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=axis, color=LIGHT, linewidth=0.55, alpha=0.65)
    ax.set_axisbelow(True)


def auc_lower_is_positive(labels: np.ndarray, values: np.ndarray) -> float:
    """ROC AUC for smaller values predicting the positive class (tie-aware)."""
    labels = np.asarray(labels, dtype=bool)
    scores = pd.Series(-np.asarray(values, dtype=float)).rank(method="average").to_numpy()
    n_pos = int(labels.sum()); n_neg = int((~labels).sum())
    rank_sum = float(scores[labels].sum())
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def panel(ax, text, fontsize=9):
    ax.text(-0.10, 1.03, text, transform=ax.transAxes, fontweight="bold", fontsize=fontsize, va="bottom")


def sample_mask(center_mhz: float, frequencies: np.ndarray) -> np.ndarray:
    mask = SpectralMaskMSS(center_mhz, 5.0, -13.0)
    mask.set_mask(42.8)
    values = np.full_like(frequencies, mask.mask_dbm[0], dtype=float)
    for index in range(len(mask.freq_lim) - 1, -1, -1):
        values[frequencies < mask.freq_lim[index]] = mask.mask_dbm[index]
        if index == len(mask.delta_f_lim):
            values[frequencies < mask.freq_lim[index]] = mask.p_tx
    return values


def fig01():
    folder = HERE / "fig01"
    source = folder / "figure1_blender_base.png"
    anchor_source = folder / "fig01_anchors.json"
    anchors = json.loads(anchor_source.read_text(encoding="utf-8"))
    image = mpimg.imread(source)
    original_height, original_width = image.shape[:2]

    # The historical Blender render touched both outer camera limits.  Extend
    # it symmetrically so panel (a) moves right and panel (b) moves left by the
    # same amount, preserving the rendered geometry.
    pad = 180
    completed = np.zeros((original_height, original_width + 2 * pad, 4), dtype=image.dtype)
    completed[:, pad:pad + original_width] = image

    # The right-hand EESS object was clipped by the edge of the historical
    # Blender render. Remove only the truncated cone and reflector here; one
    # complete cone and one complete antenna are drawn below at the same
    # physical anchor. This avoids double images.
    # Use a clear ground-only strip; the former edge strip also contained the
    # clipped reflector and therefore replicated it into the new margin.
    ground = image[1320:, 3120:3300][:, ::-1].copy()
    ground_span = ground[..., :3].max(axis=2) - ground[..., :3].min(axis=2)
    ground_mask = ((ground[..., 3] > 0) & (ground_span < .12)
                   & (ground[..., :3].mean(axis=2) > .70))
    ground_target = completed[1320:, pad + 3600:pad + 3780]
    ground_target[ground_mask] = ground[ground_mask]

    cone_region = completed[580:1410, pad + 3290:pad + 3600]
    cone_alpha = cone_region[..., 3]
    cone_mask = ((cone_alpha > .01) & (cone_alpha < .70)
                 & (cone_region[..., 1] > cone_region[..., 0] * 1.05)
                 & (cone_region[..., 2] > cone_region[..., 0] * 1.01))
    cone_region[cone_mask] = 0

    # Remove the clipped render's solid boresight so the reconstructed panel
    # contains exactly one continuous direction line.
    old_boresight = completed[580:1425, pad + 3490:pad + 3585]
    old_boresight_mask = ((old_boresight[..., 3] > .45)
                          & (old_boresight[..., 1]
                             > old_boresight[..., 0] * 1.12)
                          & (old_boresight[..., 1]
                             > old_boresight[..., 2] * .92))
    old_boresight[old_boresight_mask] = 0

    dish_region = completed[1280:1710, pad + 3380:pad + 3600]
    dish_background = completed[1280:1710, pad + 3140:pad + 3360].copy()
    dish_span = dish_region[..., :3].max(axis=2) - dish_region[..., :3].min(axis=2)
    dish_mask = ((dish_region[..., 3] > .08) & (dish_span < .32))
    dish_region[dish_mask] = dish_background[dish_mask]

    # Remove the last feed/reflector pixels from the old clipped object. Keep
    # only the saturated TX/RX direction lines and the bright angular arc.
    remnant = completed[1260:1425, pad + 3470:pad + 3600]
    remnant_rgb = remnant[..., :3]
    remnant_span = remnant_rgb.max(axis=2) - remnant_rgb.min(axis=2)
    remnant_mean = remnant_rgb.mean(axis=2)
    keep_arc = ((remnant[..., 3] > .30) & (remnant_span < .10)
                & (remnant_mean > .78))
    remnant[~keep_arc] = 0

    # Reuse the exact Blender-rendered antenna from panel (a).  Only its upper
    # assembly (reflector/feed) is inclined for panel (b); the mast remains
    # vertical.  The colour mask excludes the service grid, green beam and red
    # interference path from the copied raster.
    antenna = image[1250:1750, 1000:1320].copy()
    antenna_span = antenna[..., :3].max(axis=2) - antenna[..., :3].min(axis=2)
    antenna_mean = antenna[..., :3].mean(axis=2)
    antenna_relative_span = antenna_span / np.maximum(antenna_mean, .04)
    antenna_y, antenna_x = np.indices(antenna.shape[:2])
    antenna_extent = ((antenna_x > 50) & (antenna_x < 270)
                      & (antenna_y > 65) & (antenna_y < 360))
    neutral_body = ((antenna[..., 3] > .08) & (antenna_relative_span < .30)
                    & (antenna_mean > .02) & (antenna_mean < .74)
                    & antenna_extent)
    # The metallic feed has a cyan tint from the Blender lighting, so a purely
    # neutral-colour mask would perforate its arm and terminal sphere. Recover
    # that exact rendered component by its compact geometry while excluding
    # the reddish interference path.
    feed_start = np.asarray((120.0, 105.0))
    feed_end = np.asarray((164.0, 235.0))
    feed_dx, feed_dy = feed_end - feed_start
    feed_den = feed_dx ** 2 + feed_dy ** 2
    feed_t = np.clip(((antenna_x - feed_start[0]) * feed_dx
                      + (antenna_y - feed_start[1]) * feed_dy) / feed_den,
                     0.0, 1.0)
    feed_distance = np.hypot(
        antenna_x - (feed_start[0] + feed_t * feed_dx),
        antenna_y - (feed_start[1] + feed_t * feed_dy),
    )
    feed_geometry = ((feed_distance < 15.0)
                     | (np.hypot(antenna_x - 120.0,
                                 antenna_y - 105.0) < 25.0))
    not_reddish = ~((antenna[..., 0] > antenna[..., 1] * 1.12)
                    & (antenna[..., 0] > antenna[..., 2] * 1.12))
    feed_mask = (feed_geometry & (antenna[..., 3] > .24)
                 & (antenna_mean < .80) & not_reddish)
    antenna_mask = neutral_body | feed_mask
    antenna[~antenna_mask] = 0

    antenna_u8 = np.clip(antenna * 255.0, 0, 255).astype(np.uint8)
    antenna_complete = np.asarray(
        Image.fromarray(antenna_u8, mode="RGBA").rotate(
            -10.0,
            resample=Image.Resampling.BICUBIC,
            center=(167, 340),
            expand=False,
        ),
        dtype=np.float32,
    ) / 255.0

    def alpha_over(destination, foreground):
        src_a = foreground[..., 3:4]
        dst_a = destination[..., 3:4]
        out_a = src_a + dst_a * (1.0 - src_a)
        numerator = (foreground[..., :3] * src_a
                     + destination[..., :3] * dst_a * (1.0 - src_a))
        out_rgb = np.divide(numerator, out_a, out=np.zeros_like(numerator),
                            where=out_a > 1e-8)
        destination[..., :3] = out_rgb
        destination[..., 3:4] = out_a

    antenna_x0, antenna_y0 = 3549, 1250
    antenna_target = completed[
        antenna_y0:antenna_y0 + antenna_complete.shape[0],
        antenna_x0:antenna_x0 + antenna_complete.shape[1],
    ]
    alpha_over(antenna_target, antenna_complete)

    image = completed
    fig, ax = plt.subplots(figsize=(8.25, 4.45))
    content_top = 0.90
    right_eess_x = (anchors["right_eess"]["x"] * original_width + pad) / image.shape[1]
    right_eess_y = anchors["right_eess"]["y"] * content_top - .006
    cone_top_y = .596
    # A single complete receiving beam is placed behind the raster geometry.
    ax.add_patch(Polygon([(right_eess_x, right_eess_y),
                          (right_eess_x - .042, cone_top_y),
                          (right_eess_x + .042, cone_top_y)],
                         closed=True, transform=ax.transAxes,
                         facecolor=GREEN, edgecolor="none", alpha=.105,
                         zorder=-0.5))
    ax.add_patch(Ellipse((right_eess_x, cone_top_y), .084, .037,
                         transform=ax.transAxes, facecolor=GREEN,
                         edgecolor="none", alpha=.105, zorder=-0.5))
    # Compose the two rendered halves separately.  The symmetric padding moves
    # panel (a) right and panel (b) left by the same amount.
    midpoint = image.shape[1] // 2
    ax.imshow(image[:, :midpoint], extent=(0, 0.5, 0, content_top), aspect="auto")
    ax.imshow(image[:, midpoint:], extent=(0.5, 1.0, 0, content_top), aspect="auto")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_axis_off()
    ax.plot([0.503, 0.503], [0.04, content_top], transform=ax.transAxes, color=LIGHT, lw=0.8)
    ax.text(0.015, 0.975, "(a) Reassociação intersatelital", transform=ax.transAxes,
            ha="left", va="top", fontsize=11.0, fontweight="bold")
    ax.text(0.515, 0.975, "(b) Geometria angular", transform=ax.transAxes,
            ha="left", va="top", fontsize=11.0, fontweight="bold")

    def point(key):
        x = (anchors[key]["x"] * original_width + pad) / image.shape[1]
        return x, anchors[key]["y"] * content_top

    # Restore clean continuous direction segments where the clipped antenna
    # was removed from the historical raster.
    right_satellite = np.asarray(point("right_satellite"))
    right_eess = np.asarray(point("right_eess"))
    red_start = right_satellite + .70 * (right_eess - right_satellite)
    ax.plot([red_start[0], right_eess[0]], [red_start[1], right_eess[1]],
            transform=ax.transAxes, color="#E58A77", lw=1.65,
            solid_capstyle="round", zorder=2.2)
    ax.plot([right_eess[0], right_eess[0]],
            [right_eess[1], cone_top_y],
            transform=ax.transAxes, color=GREEN, alpha=.58, lw=2.0,
            solid_capstyle="round", zorder=-0.25)

    def note(key, xytext, text, color=DARK, ha="center"):
        xytext = (xytext[0], xytext[1] * content_top)
        ax.annotate(text, xy=point(key), xytext=xytext, xycoords="axes fraction",
                    textcoords="axes fraction", ha=ha, va="center", color=color,
                    fontsize=8.65, arrowprops=dict(arrowstyle="->", color=color, lw=1.0,
                                                  shrinkA=2, shrinkB=2),
                    bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.90))

    note("left_serving", (0.035, 0.70), "satélite\nservidor", GREEN, ha="left")
    note("left_target", (0.385, 0.77), "satélite\ncandidato", ORANGE)
    note("left_cell", (0.16, 0.08), "mesma célula de\nserviço preservada", BLUE)
    note("left_eess", (0.445, 0.13), "EESS", GREEN)
    note("left_interference", (0.30, 0.54), "caminho de propagação\nda interferência", RED)
    note("left_handover", (0.225, 0.91), "satellite selection", DARK)
    note("left_eess_beam", (0.41, 0.45), "feixe EESS", GREEN)

    note("right_tx_boresight", (0.60, 0.39), "boresight TX\n(em direção à célula)", GREEN)
    note("right_rx_boresight", (0.885, 0.66), "pointing instantâneo\nda EESS", GREEN)
    note("right_psi_tx", (0.70, 0.73), r"$\psi_{\mathrm{TX}}$", ORANGE)
    note("right_psi_rx", (0.85, 0.32), r"$\psi_{\mathrm{RX}}$", GREEN)
    export(fig, folder)
    pd.DataFrame([
        ("servidor", "satélite", "atende a célula e origina o caminho de propagação da interferência"),
        ("candidato", "satélite", "alternativa elegível que preserva a mesma célula de serviço"),
        ("psi_TX", "ângulo", "afastamento entre o boresight do beam transmissor e a direção satélite→EESS"),
        ("psi_RX", "ângulo", "afastamento entre o boresight da antena EESS e a direção EESS→satélite"),
    ], columns=["elemento", "tipo", "definicao"]).to_csv(folder / "figure1.csv", index=False)
    manifest(folder, title="Geometria e funcionamento do método",
             caption="Geometria da reassociação intersatelital orientada à interferência: (a) um satélite candidato pode substituir o satélite servidor, preservando a mesma célula de serviço e alterando o caminho de propagação da interferência; (b) ψTX é o afastamento angular entre o boresight do beam transmissor e a direção satélite→EESS, enquanto ψRX é o afastamento angular entre o boresight da antena EESS e a direção EESS→satélite. O pointing instantâneo da EESS é a informação que poderia ser compartilhada por um mecanismo do tipo ODS.",
             inputs=[source, anchor_source, folder / "render_blender.py"], filters={},
             metrics={"psi_TX": "ângulo entre o boresight do beam e a direção satélite–EESS", "psi_RX": "ângulo entre o pointing EESS e a direção EESS–satélite"},
             samples={"scene": "didática; sem dados estatísticos"},
             notes=["Objetos 3D renderizados no Blender; rótulos e símbolos compostos vetorialmente."])


def fig02():
    folder = HERE / "fig02"; folder.mkdir(parents=True, exist_ok=True)
    f = np.arange(2183.0, 2207.001, 0.01)
    d = pd.DataFrame({"frequency_mhz": f, "mask_gb10_dbm_per_mhz": sample_mask(2187.5, f),
                      "mask_gb5_dbm_per_mhz": sample_mask(2192.5, f)})
    d.to_csv(folder / "figure2.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.16, 3.05))
    ax.plot(f, d.mask_gb10_dbm_per_mhz, color=GREEN, label="GB = 10 MHz")
    ax.plot(f, d.mask_gb5_dbm_per_mhz, color=ORANGE, ls="--", label="GB = 5 MHz")
    ax.axhline(-13, color=GRAY, ls=(0, (4, 3)), lw=.9, label="Piso espúrio: −13 dBm/MHz")
    ax.axvspan(2200, 2204, color=CYAN, alpha=.22, lw=0)
    ax.axvspan(2204, 2206, color=GREEN, alpha=.13, lw=0)
    ax.text(2200.15, 32, "EESS B", color=BLUE)
    ax.text(2204.10, 28, "extensão EESS D", color=GREEN)
    ax.axvspan(2197.5, 2200, color=LIGHT, alpha=.25, lw=0)
    ax.text(2198.4, 18, "OOB", color=GRAY, ha="center")
    ax.text(2184.0, -10.5, "domínio espúrio", color=GRAY)
    ax.annotate("GB ≥ 10: EESS no piso espúrio", xy=(2201, -13), xytext=(2188.2, -5),
                color=GREEN, arrowprops=dict(arrowstyle="->", color=GREEN, lw=.8))
    ax.annotate("GB = 5: EESS intercepta a região OOB", xy=(2200.25, 18), xytext=(2190.8, 29),
                color=ORANGE, arrowprops=dict(arrowstyle="->", color=ORANGE, lw=.8))
    ax.set(xlim=(2183, 2207), ylim=(-17, 38), xlabel="Frequência [MHz]",
           ylabel="Densidade espectral de potência [dBm/MHz]")
    clean(ax, "y")
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(.5, 1.01))
    fig.subplots_adjust(top=.85)
    export(fig, folder)
    manifest(folder, title="Máscara espectral", caption="Máscara espectral empregada na campanha para os casos GB = 10 MHz e GB = 5 MHz. O breakpoint observado decorre da parametrização específica desta campanha e não constitui uma regra universal da UIT.",
             inputs=[ROOT / "sharc" / "mask" / "spectral_mask_mss.py", CAMPAIGN / "Scripts" / "base_input.yaml"],
             filters={"bandwidth_dc_mss_mhz": 5, "guard_bands_mhz": [10, 5], "spectral_mask": "MSS", "adjacent_ch_emissions": "SPECTRAL_MASK"},
             metrics={"mask": "SpectralMaskMSS instanciada pelo StationFactory com potência conduzida de 42,8 dBm, BW=5 MHz e piso de −13 dBm/MHz"}, samples={"frequency_samples": len(d)},
             notes=["A curva é calculada diretamente pela mesma classe usada pela campanha, não é uma aproximação desenhada manualmente."])


def fig03():
    folder = HERE / "fig03"; folder.mkdir(parents=True, exist_ok=True)
    # Portrait layout with enough horizontal room for clean branches.  It is
    # intentionally wider than one strict IEEE column, but remains markedly
    # taller than wide and can be scaled without crushing the labels.
    fig, ax = plt.subplots(figsize=(6.20, 7.40)); ax.set_xlim(0, 13.5); ax.set_ylim(1.70, 17); ax.axis("off")

    def box(x, y, w, h, text, color, fontsize=7.0):
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=.08,rounding_size=.08",
            fc="white", ec=color, lw=1.25)
        ax.add_patch(patch)
        ax.text(x+w/2, y+h/2, text, ha="center", va="center",
                color=DARK, fontsize=fontsize)

    def diamond(cx, cy, w, h, text, color, fontsize=6.9):
        patch = Polygon(
            [(cx, cy+h/2), (cx+w/2, cy), (cx, cy-h/2), (cx-w/2, cy)],
            closed=True, fc="white", ec=color, lw=1.25)
        ax.add_patch(patch)
        ax.text(cx, cy, text, ha="center", va="center", color=DARK,
                fontsize=fontsize)

    def arrow(a, b, color=GRAY, connectionstyle="arc3"):
        ax.add_patch(FancyArrowPatch(
            a, b, arrowstyle="-|>", mutation_scale=9, color=color,
            lw=.9, connectionstyle=connectionstyle))

    def routed_arrow(points, color=GRAY):
        """Draw a solid orthogonal connector whose arrowhead ends at a node border."""
        for start, end in zip(points[:-2], points[1:-1]):
            ax.plot([start[0], end[0]], [start[1], end[1]],
                    color=color, lw=1.0, solid_capstyle="butt", zorder=1)
        arrow(points[-2], points[-1], color=color)

    box(1.40, 15.58, 7.40, .92,
        "Calcular $I_i$ e somar  $I_{agg,antes}=\\sum_i I_i$", BLUE, fontsize=7.3)
    diamond(5.10, 14.35, 5.50, 1.35,
            "$I_{agg,antes}>-154$ dBW/MHz?", ORANGE, fontsize=7.15)
    # The risk decision is centred on the same x-axis as the boxes immediately
    # above and below it.  Its side exit is vertically aligned with the decision.
    box(9.05, 13.675, 2.30, 1.35,
        "Manter\nconfiguração original\ne encerrar", GRAY, fontsize=6.35)
    box(2.05, 12.12, 6.10, 1.00,
        "Ordenar $I_i$ e formar a lista top-3\n($K=3$: até três contribuintes)", ORANGE, fontsize=6.95)
    box(3.30, 10.68, 3.60, .82,
        "Iniciar pelo rank $r=1$", ORANGE, fontsize=7.15)
    box(1.50, 8.35, 7.20, 1.42,
        "Para o contribuinte de rank $r$:\n"
        "enumerar satélites elegíveis\n"
        "para a mesma célula e calcular $I_{candidato}$\n"
        "com o modelo físico empregado", CYAN, fontsize=6.65)
    diamond(5.10, 6.82, 5.20, 1.42,
            "Existe alvo válido com\nredução prevista $\\geq 0$ dB?",
            ORANGE, fontsize=6.75)
    diamond(5.10, 4.78, 3.00, 1.08, "$r<3$?", ORANGE, fontsize=7.15)
    box(8.35, 5.98, 4.55, 1.68,
        "Escolher o candidato de menor interferência\n"
        "Realizar UMA reassociação e atualizar $I_{agg}$\n"
        "Preservar a mesma célula e encerrar", ORANGE, fontsize=6.35)
    box(3.50, 2.78, 3.20, .88,
        "Avançar para $r\\leftarrow r+1$", CYAN, fontsize=6.65)
    box(.20, 4.08, 2.65, 1.40,
        "Manter configuração\noriginal e encerrar\nsem reassociação", GRAY, fontsize=6.25)

    # Main vertical axis: all connectors stop at the corresponding borders.
    arrow((5.10, 15.58), (5.10, 15.025))
    arrow((7.85, 14.35), (9.05, 14.35))
    ax.text(8.45, 14.57, "não", ha="center", color=GRAY, fontsize=6.9)
    arrow((5.10, 13.675), (5.10, 13.12))
    ax.text(5.28, 13.43, "sim", color=GRAY, fontsize=6.9)
    arrow((5.10, 12.12), (5.10, 11.50))
    arrow((5.10, 10.68), (5.10, 9.77))
    arrow((5.10, 8.35), (5.10, 7.53))

    # Target accepted: a short horizontal branch ending at the success box.
    arrow((7.70, 6.82), (8.35, 6.82), color=GRAY)
    ax.text(8.02, 7.03, "sim", ha="center", color=GRAY, fontsize=6.9)

    # No target for this contributor: continue vertically to the rank limit.
    arrow((5.10, 6.11), (5.10, 5.32))
    ax.text(5.28, 5.72, "não", color=GRAY, fontsize=6.9)

    # Rank limit branches are horizontal/vertical and meet node borders only.
    arrow((3.60, 4.78), (2.85, 4.78), color=GRAY)
    ax.text(3.22, 5.02, "não", ha="center", color=GRAY, fontsize=6.9)
    arrow((5.10, 4.24), (5.10, 3.66), color=CYAN)
    ax.text(5.28, 3.96, "sim", color=CYAN, fontsize=6.9)

    # Fully opaque orthogonal retry path, outside all nodes.
    routed_arrow([(6.70, 3.22), (13.18, 3.22), (13.18, 9.06), (8.70, 9.06)],
                 color=CYAN)
    ax.text(13.03, 4.70, "próximo rank", rotation=90,
            va="center", ha="right", color=CYAN, fontsize=6.55)
    ax.text(5.10, 2.12,
            "No máximo uma reassociação por snapshot",
            ha="center", color=RED, fontsize=6.75)
    export(fig, folder)
    pd.DataFrame([
        ("top_k", 3), ("limiar_dbw_per_mhz", -154),
        ("min_reduction_db", 0), ("max_reassociacoes_por_snapshot", 1),
        ("ordem_de_analise", "rank 1 → rank 2 → rank 3"),
    ], columns=["parametro", "valor"]).to_csv(folder / "figure3.csv", index=False)
    manifest(folder, title="Fluxo do método proposto",
             caption="Fluxo da reassociação intersatelital orientada à interferência. Quando o limiar de risco é excedido, até três contribuintes são analisados sequencialmente, do rank 1 ao rank 3. Para cada contribuinte, avaliam-se os satélites elegíveis para a mesma célula; o primeiro rank que possuir um alvo válido encerra a busca após uma única reassociação no snapshot.",
             inputs=[ROOT / "sharc" / "simulation_downlink.py", ROOT / "sharc" / "interference_aware_handover_v2.py", CAMPAIGN / "Scripts" / "base_input.yaml"],
             filters={"trigger_mode": "RISK_GATED_TOP_K", "top_k": 3,
                      "risk_gate_dbw_per_mhz": -154,
                      "max_handovers_per_snapshot": 1},
             metrics={"Iagg": "soma das contribuições individuais em potência linear",
                      "target": "candidato elegível com menor interferência física e redução prevista ≥ 0 dB"},
             samples={"diagram": "lógica determinística implementada"},
             notes=["K=3 limita o número de contribuintes analisados; não é o número de reassociações."])


def fig04():
    folder = HERE / "fig04"; folder.mkdir(parents=True, exist_ok=True)
    source = CP_DIR / "scenario_exceedance_cp95.csv"
    d = pd.read_csv(source); d = d[d.guard_band_mhz.isin([5, 10])].copy()
    d["scenario"] = d.apply(lambda r: f"{int(r.altitude_km)}-{r.eess_system}-{r.load_factor:.1f}".replace(".", ","), axis=1)
    d.to_csv(folder / "figure4.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(9.20, 4.75), sharey=True)
    y = np.arange(8); off = {"before": -.12, "after": .12}
    for ax, gb, tag in zip(axes, [10, 5], ["(a)", "(b)"]):
        s = d[d.guard_band_mhz == gb].set_index("scenario").loc[LABELS]
        for state, label, color, marker in [("before", "sem mitigação", BLUE, "o"), ("after", "com mitigação", ORANGE, "s")]:
            value = s[f"{state}_probability_pct"].to_numpy()
            low = s[f"{state}_cp95_low_pct"].to_numpy(); high = s[f"{state}_cp95_high_pct"].to_numpy()
            ax.errorbar(value, y + off[state], xerr=np.vstack([value-low, high-value]), fmt=marker,
                        color=color, ecolor=color, elinewidth=1.15, capsize=3.2,
                        markersize=7.2, label=label)
        ax.axvline(1, color=GRAY, ls="--", lw=.9)
        ax.text(1, -0.065, "critério: 1%", transform=ax.get_xaxis_transform(),
                ha="center", va="top", color=GRAY, fontsize=9.4)
        ax.set_xlabel("Probabilidade de excedência [%]", fontsize=12.5, labelpad=25)
        ax.set_title(f"{tag} GB = {gb} MHz", fontsize=13.0, pad=10)
        ax.set_yticks(y, LABELS); ax.invert_yaxis(); clean(ax, "x")
        ax.tick_params(axis="both", labelsize=10.5)
    axes[0].legend(frameon=True, facecolor="white", edgecolor="none",
                   framealpha=.90, loc="lower right", fontsize=10.3)
    fig.subplots_adjust(left=.11, right=.985, bottom=.26, top=.88, wspace=.20)
    export(fig, folder)
    manifest(folder, title="Probabilidade de excedência", caption="Probabilidade de excedência do critério de −154 dBW/MHz, antes e após a mitigação, para (a) GB = 10 MHz e (b) GB = 5 MHz. Barras: IC95% binomial exato de Clopper–Pearson; a classificação não é baseada apenas na estimativa pontual.", inputs=[source], filters={"guard_band_mhz": [10, 5], "scenarios": LABELS},
             metrics={"exceedance": "Iagg > −154 dBW/MHz", "probability": "k/n"}, samples={"runs": 16, "snapshots_per_run": 5000},
             ci="Clopper–Pearson exato, 95%, scipy.stats.binomtest(...).proportion_ci(method='exact')")


def discover_final_runs():
    import re
    pattern = re.compile(r"^system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_GB_(5|10)MHz_STRATEGY_V2_RISK_GATE_(\d{4}-\d{2}-\d{2})_(\d+)$")
    selected = {}
    for p in (CAMPAIGN / "output").iterdir():
        m = pattern.fullmatch(p.name) if p.is_dir() else None
        if not m: continue
        snap = p / "interference_aware_handover_v2_snapshot.csv"
        if not snap.is_file() or sum(1 for _ in snap.open("rb")) - 1 != 5000: continue
        key = (int(m[1]), m[2], float(m[3]), int(m[4])); stamp = (m[5], int(m[6]))
        if key not in selected or stamp > selected[key][0]: selected[key] = (stamp, p)
    return {k:v[1] for k,v in selected.items()}


def fig05():
    folder = HERE / "fig05"; folder.mkdir(parents=True, exist_ok=True)
    runs = discover_final_runs(); summary=[]; event_parts=[]; inputs=[]
    for key,p in sorted(runs.items()):
        snap_path=p/"interference_aware_handover_v2_snapshot.csv"; event_path=p/"interference_aware_handover_v2_events.csv"
        snap=pd.read_csv(snap_path); events=pd.read_csv(event_path); inputs += [snap_path,event_path]
        acted=snap.reassigned_beams.gt(0); accepted=events[events.accepted.astype(bool)].copy()
        accepted["elevation_loss_deg"]=accepted.current_service_elevation_deg-accepted.selected_service_elevation_deg
        accepted["guard_band_mhz"]=key[3]; accepted["scenario"]=f"{key[0]}-{key[1]}-{key[2]:.1f}".replace(".",",")
        event_parts.append(accepted[["guard_band_mhz","scenario","snapshot_id","beam_grid_idx","elevation_loss_deg"]])
        summary.append(dict(altitude_km=key[0],eess_system=key[1],load_factor=key[2],guard_band_mhz=key[3],scenario=accepted.scenario.iloc[0] if len(accepted) else f"{key[0]}-{key[1]}-{key[2]:.1f}".replace(".",","),snapshots=len(snap),handover_snapshots=int(acted.sum()),activation_rate_pct=100*acted.mean(),median_reduction_acted_db=float(snap.loc[acted,"iagg_reduction_db"].median()) if acted.any() else np.nan,accepted_events=len(accepted),median_elevation_loss_deg=float(accepted.elevation_loss_deg.median()) if len(accepted) else np.nan))
    d=pd.DataFrame(summary); ev=pd.concat(event_parts,ignore_index=True)
    d.to_csv(folder/"figure5_summary.csv",index=False); ev.to_csv(folder/"figure5_elevation_loss.csv",index=False)
    fig,axes=plt.subplots(1,3,figsize=(7.16,3.65),gridspec_kw={"width_ratios":[1,1,1.05]})
    y=np.arange(8); colors={10:GREEN,5:ORANGE}; marks={10:"o",5:"s"}; offsets={10:-.11,5:.11}
    for ax,metric,xlab,tag in zip(axes[:2],["median_reduction_acted_db","activation_rate_pct"],["Redução mediana de\ninterferência [dB]","Taxa de atuação\n[% dos snapshots]"],["(a)","(b)"]):
        for gb in [10,5]:
            s=d[d.guard_band_mhz.eq(gb)].set_index("scenario").loc[LABELS]
            ax.scatter(s[metric],y+offsets[gb],c=colors[gb],marker=marks[gb],label=f"GB = {gb} MHz")
        ax.set_yticks(y,LABELS if ax is axes[0] else []); ax.invert_yaxis(); ax.set_xlabel(xlab); clean(ax,"x"); panel(ax,tag)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    groups=[ev.loc[ev.guard_band_mhz.eq(g),"elevation_loss_deg"].dropna().to_numpy() for g in [10,5]]
    bp=axes[2].boxplot(groups,tick_labels=["GB = 10","GB = 5"],patch_artist=True,whis=(5,95),showfliers=False,
                       medianprops=dict(color=DARK),whiskerprops=dict(color=GRAY),capprops=dict(color=GRAY))
    for b in bp["boxes"]: b.set(facecolor=PEACH,edgecolor=ORANGE)
    axes[2].set_ylabel("Perda de elevação de serviço [graus]"); clean(axes[2],"y"); panel(axes[2],"(c)")
    fig.legend(handles, legend_labels, frameon=False, loc="upper center",
               bbox_to_anchor=(.50, .995), ncol=2)
    fig.subplots_adjust(wspace=.35,bottom=.15,top=.87)
    export(fig,folder)
    manifest(folder,title="Benefício, atuação e custo da mitigação",caption="Benefício e custo geométrico do método proposto: (a) redução mediana de interferência nos snapshots com reassociação; (b) taxa de atuação; (c) distribuição da perda de elevação de serviço. No painel (c), o retângulo contém a metade central dos eventos, a linha interna é a mediana e as hastes abrangem os percentis 5 a 95. Na campanha, a perda máxima configurada foi 90°, permitindo avaliar o potencial de mitigação sem uma restrição efetiva de QoS por elevação.",inputs=inputs,filters={"guard_band_mhz":[10,5],"accepted_events_only_in_panel_c":True},metrics={"reduction":"Iagg,antes − Iagg,após em dB","activation":"snapshots com ao menos uma reassociação / total","elevation_loss":"elevação servidor original − elevação alvo"},samples={"runs":len(d),"snapshots":int(d.snapshots.sum()),"accepted_events":len(ev)})


def fig06():
    folder=HERE/"fig06"; folder.mkdir(parents=True,exist_ok=True)
    source=RX_DIR/"rx_min_merged_gb10.csv"; d=pd.read_csv(source)
    out=d[["snapshot_id","secondary_seed","scenario","altitude_km","eess_system","load_factor","critical_before","top1_joint_gain_suppression_db","rx_visible_satellite_count","rx_offaxis_min_satellite_idx","rx_offaxis_min_deg"]]
    out.to_csv(folder/"figure6.csv",index=False)
    y=d.critical_before.astype(int).to_numpy()
    auc_joint=auc_lower_is_positive(y,d.top1_joint_gain_suppression_db.to_numpy())
    auc_rx=auc_lower_is_positive(y,d.rx_offaxis_min_deg.to_numpy())
    fig,axes=plt.subplots(1,2,figsize=(7.16,3.35))
    for ax,col,xlab,auc,tag in [(axes[0],"top1_joint_gain_suppression_db","Supressão angular conjunta [dB]",auc_joint,"(a)"),(axes[1],"rx_offaxis_min_deg",r"Menor ângulo off-axis de recepção, $\psi_{RX,min}$ [graus]",auc_rx,"(b)")]:
        vals=[d.loc[~d.critical_before,col].dropna(),d.loc[d.critical_before,col].dropna()]
        vp=ax.violinplot(vals,positions=[0,1],showmeans=False,showmedians=False,showextrema=False,widths=.75)
        for body,color in zip(vp["bodies"],[GRAY,ORANGE]): body.set_facecolor(color);body.set_edgecolor(color);body.set_alpha(.28)
        ax.boxplot(vals,positions=[0,1],widths=.25,whis=(5,95),showfliers=False,patch_artist=True,
                   boxprops=dict(facecolor="white",edgecolor=DARK),medianprops=dict(color=RED),whiskerprops=dict(color=DARK),capprops=dict(color=DARK))
        ax.set_xticks([0,1],["seguros","críticos"]);ax.set_ylabel(xlab);clean(ax,"y");panel(ax,tag)
        ax.text(.97,.95,f"AUC = {auc:.3f}",transform=ax.transAxes,ha="right",va="top",fontsize=8,
                bbox=dict(fc="white",ec=LIGHT,pad=2))
    export(fig,folder)
    manifest(folder,title="Assinatura geométrica dos eventos críticos",caption="Assinatura geométrica em GB = 10 MHz: (a) supressão angular conjunta do link dominante, empregada apenas como diagnóstico físico; (b) menor ângulo off-axis de recepção entre todos os satélites ativos/visíveis, calculado sem consultar o ranking de interferência. AUC calculada para valores menores como preditores de criticidade.",inputs=[source],filters={"guard_band_mhz":10,"critical":"Iagg,antes > −154 dBW/MHz"},metrics={"joint_gain_suppression":"queda de ganho TX + queda de ganho RX do link dominante","psi_RX_min":"mínimo psi_RX entre satélites ativos/visíveis","auc":"ROC AUC, sinal invertido porque valores menores indicam maior risco"},samples={"snapshots":len(d),"safe":int((~d.critical_before).sum()),"critical":int(d.critical_before.sum())},notes=[f"AUC joint={auc_joint:.12f}; AUC psi_RX,min={auc_rx:.12f}"])


def fig07():
    folder=HERE/"fig07"; folder.mkdir(parents=True,exist_ok=True)
    rb=RX_DIR/"rx_min_risk_bins_balanced.csv"; rs=RX_DIR/"rx_min_risk_bins_by_scenario.csv"
    ts=RX_DIR/"rx_min_threshold_sweep_balanced.csv"; tss=RX_DIR/"rx_min_threshold_sweep_by_scenario.csv"; gh=RX_DIR/"rx_min_threshold_group_holdout.csv"
    bins=pd.read_csv(rb); by_s=pd.read_csv(rs); sweep=pd.read_csv(ts); scen=pd.read_csv(tss); hold=pd.read_csv(gh)
    bins.to_csv(folder/"figure7_risk_curve.csv",index=False); by_s.to_csv(folder/"figure7_risk_curve_by_scenario.csv",index=False)
    sweep.to_csv(folder/"figure7_threshold_sweep.csv",index=False);scen.to_csv(folder/"figure7_threshold_sweep_by_scenario.csv",index=False);hold.to_csv(folder/"figure7_stability.csv",index=False)
    fig,axes=plt.subplots(1,2,figsize=(9.40,4.85))
    ax=axes[0];x=bins.psi_rx_min_center_deg.to_numpy();p=100*bins.balanced_p_hat.to_numpy();lo=100*bins.balanced_simultaneous_cp95_low.to_numpy();hi=100*bins.balanced_simultaneous_cp95_high.to_numpy()
    ax.fill_between(x,100*bins.scenario_q25,100*bins.scenario_q75,color=LIGHT,alpha=.55,label="faixa intercenários (Q1–Q3)")
    ax.errorbar(x,p,yerr=np.vstack([p-lo,hi-p]),fmt="o-",color=GREEN,
                capsize=3.2,markersize=7.0,linewidth=1.6,
                label="estimativa balanceada e IC95%")
    ax.text(.98,.06,"n = 4000 por bin",transform=ax.transAxes,ha="right",fontsize=9.2,color=GRAY)
    ax.set_xlabel(r"$\psi_{RX,min}$ [graus]",fontsize=12.5,labelpad=7)
    ax.set_ylabel("Probabilidade empírica de evento crítico [%]",fontsize=12.0,labelpad=7)
    ax.tick_params(axis="both",labelsize=10.5);clean(ax,"both");panel(ax,"(a)",fontsize=12.5)
    ax.legend(frameon=False,loc="upper right",fontsize=9.7)
    ax=axes[1];x=sweep.psi_threshold_deg.to_numpy();mask=x<=12
    series=[("critical_detection_rate","eventos críticos detectados",BLUE), ("false_activation_rate_among_safe","falsas ativações",ORANGE), ("total_activation_rate","ativações totais",GRAY), ("missed_critical_rate","críticos não detectados",RED)]
    for col,label,color in series: ax.plot(x[mask],100*sweep.loc[mask,col],color=color,lw=1.8,label=label)
    global_th=float(sweep.loc[sweep.youden_j.idxmax(),"psi_threshold_deg"])
    ax.axvline(global_th,color=DARK,ls="--",lw=.9)
    ax.annotate("compromisso global candidato\n7,19°",xy=(global_th,92),xytext=(9.05,88),
                ha="center",va="center",fontsize=9.3,color=DARK,
                arrowprops=dict(arrowstyle="->",color=DARK,lw=1.0),
                bbox=dict(fc="white",ec="none",alpha=.9,pad=1.5))
    own=scen.loc[scen.groupby("scenario").youden_j.idxmax()].copy();own["altitude"]=own.scenario.str[:3].astype(int)
    ranges={int(a):(g.psi_threshold_deg.min(),g.psi_threshold_deg.max()) for a,g in own.groupby("altitude")}
    ax.axvspan(*ranges[525],color=CYAN,alpha=.18);ax.axvspan(*ranges[340],color=ORANGE,alpha=.16)
    ax.text(np.mean(ranges[525]),4,"faixa 525 km",rotation=90,ha="center",va="bottom",color=BLUE,fontsize=8.7)
    ax.text(np.mean(ranges[340]),4,"faixa 340 km",rotation=90,ha="center",va="bottom",color=ORANGE,fontsize=8.7)
    ax.set(xlim=(0,12),ylim=(0,103))
    ax.set_xlabel(r"Limiar candidato $\psi_{th}$ [graus]",fontsize=12.5,labelpad=7)
    ax.set_ylabel("Taxa [%]",fontsize=12.0,labelpad=7)
    ax.tick_params(axis="both",labelsize=10.5);clean(ax,"both");panel(ax,"(b)",fontsize=12.5)
    ax.legend(frameon=True,facecolor="white",edgecolor="none",framealpha=.92,
              loc="upper center",bbox_to_anchor=(.52,.78),ncol=2,fontsize=8.7)
    fig.subplots_adjust(left=.09,right=.985,bottom=.18,top=.93,wspace=.26)
    export(fig,folder)
    manifest(folder,title="Gatilho geométrico operacional candidato",caption="Avaliação de um gatilho puramente geométrico: (a) risco empírico condicionado ao menor ângulo off-axis de recepção, com balanceamento igual entre cenários e IC95% conservador derivado de Clopper–Pearson por cenário/bin; (b) desempenho da regra ψRX,min < ψth. O valor 7,19° é apresentado somente como compromisso global candidato; as faixas sombreadas evidenciam a dependência do compromisso com a altitude.",inputs=[rb,rs,ts,tss,gh],filters={"guard_band_mhz":10,"critical":"Iagg,antes > −154 dBW/MHz","threshold_display_range_deg":[0,12]},metrics={"balanced_risk":"média de probabilidades por cenário","detection":"TP/(TP+FN)","false_activation":"FP/(FP+TN)","activation":"(TP+FP)/N","missed":"FN/(TP+FN)"},samples={"snapshots":40000,"scenarios":8,"samples_per_risk_bin":bins.n_total.astype(int).tolist()},ci="Clopper–Pearson por cenário/bin, alpha/8 Bonferroni e média não ponderada dos limites; curva balanceada",notes=[f"Compromisso global candidato={global_th:.12f}°",f"Faixa empírica 340 km={ranges[340][0]:.4f}–{ranges[340][1]:.4f}°",f"Faixa empírica 525 km={ranges[525][0]:.4f}–{ranges[525][1]:.4f}°","Não interpretar como limiar universal ou definitivo."])


def main():
    setup_style()
    for function in [fig01,fig02,fig03,fig04,fig05,fig06,fig07]:
        function(); print(f"generated {function.__name__}")


if __name__ == "__main__":
    main()

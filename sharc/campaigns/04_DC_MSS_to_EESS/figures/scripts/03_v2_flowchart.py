"""Figura 3: fluxo do handover intersatélite orientado à interferência."""
from __future__ import annotations

from _common import DARK, FINAL, prepare_dirs, save_figure, setup_ieee
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
import matplotlib.pyplot as plt


PALE_BLUE = "#DCEFF8"
PALE_ORANGE = "#FCE8CB"
PALE_GREEN = "#DDF2E8"


def box(ax, xy, width, height, text, color=PALE_BLUE, rounded=True):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.018,rounding_size=0.025" if rounded else "square,pad=0.01",
        facecolor=color, edgecolor=DARK, linewidth=0.8,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, text,
            ha="center", va="center", fontsize=7.5)
    return patch


def diamond(ax, center, width, height, text):
    x, y = center
    patch = Polygon([(x, y + height / 2), (x + width / 2, y),
                     (x, y - height / 2), (x - width / 2, y)],
                    closed=True, facecolor=PALE_ORANGE,
                    edgecolor=DARK, linewidth=0.8)
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=7.5)


def arrow(ax, start, end, text=None):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>",
                                 mutation_scale=8, color=DARK, linewidth=0.8))
    if text:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.025,
                text, fontsize=7.0, ha="center", va="bottom")


def main() -> None:
    prepare_dirs(); setup_ieee()
    fig, ax = plt.subplots(figsize=(7.1, 3.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    w, h = 0.18, 0.14
    box(ax, (0.02, 0.72), w, h, "Calcular contribuições\nindividuais $I_i$")
    box(ax, (0.25, 0.72), w, h, "Calcular\n$I_{agg,antes}$")
    diamond(ax, (0.56, 0.79), 0.22, 0.22,
            "$I_{agg,antes}$ >\n−154 dBW/MHz?")
    box(ax, (0.79, 0.72), w, h, "Sem reassociação", color="#EEEEEE")
    arrow(ax, (0.20, 0.79), (0.25, 0.79))
    arrow(ax, (0.43, 0.79), (0.45, 0.79))
    arrow(ax, (0.67, 0.79), (0.79, 0.79), "No")
    ax.text(0.56, 0.96, "Gatilho de risco", ha="center", fontsize=7.2,
            color="#9A5B00")

    upper = [
        (0.03, 0.39, 0.18, "Ordenar links\npor contribuição"),
        (0.27, 0.39, 0.18, "Selecionar dominantes\n(top-$K$, $K=3$)"),
        (0.51, 0.39, 0.22, "Listar satélites elegíveis\npara a mesma célula"),
        (0.79, 0.39, 0.17, "Estimar interferência\ndos candidatos"),
    ]
    for idx, (x, y, width, label) in enumerate(upper):
        box(ax, (x, y), width, 0.14, label)
        if idx:
            previous = upper[idx - 1]
            arrow(ax, (previous[0] + previous[2], 0.46), (x, 0.46))
    lower = [
        (0.69, 0.12, 0.25, "Selecionar alvo de\nmenor interferência"),
        (0.39, 0.12, 0.23, "Reassociar no máximo um\nfeixe por snapshot"),
        (0.05, 0.12, 0.27,
         "$I_{agg,após}=I_{agg,antes}$\n$-I_{atual}+I_{candidato}$"),
    ]
    for x, y, width, label in lower:
        box(ax, (x, y), width, 0.14, label, color=PALE_GREEN)
    arrow(ax, (0.875, 0.39), (0.815, 0.26))
    arrow(ax, (0.69, 0.19), (0.62, 0.19))
    arrow(ax, (0.39, 0.19), (0.32, 0.19))
    arrow(ax, (0.56, 0.68), (0.56, 0.60), "Yes")
    arrow(ax, (0.56, 0.60), (0.12, 0.60))
    arrow(ax, (0.12, 0.60), (0.12, 0.53))
    ax.text(0.62, 0.325, "Mesma célula de serviço preservada",
            ha="center", fontsize=7.2, color="#006B4F")
    save_figure(fig, "fig03_v2_flowchart")


if __name__ == "__main__":
    main()

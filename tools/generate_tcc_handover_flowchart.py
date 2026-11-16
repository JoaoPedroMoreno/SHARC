"""Render the TCC non-temporal handover flow as a code-native PNG diagram.

Visual reference: PIBIC 2026 report, Fig. 3 (page 6).
Algorithm: interference_aware_handover_v2.run_inr_handover and
cochannel_handover.CochannelHandover. Does not import or run simulations.
"""
from pathlib import Path
import ast
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figuras"
INK, BLUE, LIGHT = "#46525A", "#39789C", "#F3F8FB"
TEXTS = []
NODES = {}


def label(ax, x, y, value, size=11.8, color=INK, **kwargs):
    obj = ax.text(x, y, value, ha="center", va="center", fontsize=size,
                  color=color, linespacing=1.38, **kwargs)
    TEXTS.append(obj)
    return obj


def box(ax, key, x, y, w, h, title, body="", terminal=False):
    patch = FancyBboxPatch((x-w/2, y-h/2), w, h,
        boxstyle=f"round,pad=0,rounding_size={.19 if terminal else .065}",
        facecolor=LIGHT if terminal else "white", edgecolor=INK, lw=1.15, zorder=2)
    ax.add_patch(patch)
    title_offset = .59 if body.count("\n") >= 2 else .39
    objects = [label(ax, x, y + (title_offset if body else 0), title,
                     size=12.4, weight="bold", color=BLUE)]
    if body:
        objects.append(label(ax, x, y-.24, body))
    NODES[key] = (patch, objects)


def decision(ax, key, x, y, w, h, value):
    patch = Polygon([(x, y+h/2), (x+w/2, y), (x, y-h/2), (x-w/2, y)],
                    closed=True, fc=LIGHT, ec=BLUE, lw=1.25, zorder=2)
    ax.add_patch(patch)
    NODES[key] = (patch, [label(ax, x, y, value, size=12.0)])


def route(ax, points, caption=None, caption_at=None):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=INK, lw=1.05, solid_joinstyle="round", zorder=1)
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>",
                 mutation_scale=10, lw=1.05, color=INK, shrinkA=0, shrinkB=1.5, zorder=1))
    if caption:
        label(ax, *caption_at, caption, size=11.2,
              bbox=dict(facecolor="white", edgecolor="none", pad=1.2))


def configuration():
    folder = ROOT / "sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts"
    cfg = yaml.safe_load((folder / "base_input.yaml").read_text(encoding="utf-8"))
    mss = cfg["imt"]["topology"]["mss_dc"]
    ho = mss["interference_aware_handover_v2"]
    tree = ast.parse((folder / "generate.py").read_text(encoding="utf-8"))
    limits = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "HANDOVER_LIMITS" for t in n.targets))
    assert limits == [5, 10, 15, 20, 25, 30]
    assert ho["inr_threshold_db"] == -6 and ho["min_reduction_db"] == 0
    assert mss["beam_positioning"]["service_grid"]["minimum_service_angle"] == 32
    return dict(limits=limits, trigger_inr_db=ho["inr_threshold_db"],
                minimum_service_angle_deg=32,
                max_active_beams_per_satellite=ho["max_active_beams_per_satellite"],
                max_service_elevation_loss_deg=ho["max_service_elevation_loss_deg"])


def main():
    settings = configuration()
    plt.rcParams.update({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans"})
    fig, ax = plt.subplots(figsize=(8.2, 9.95))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set(xlim=(0, 15), ylim=(.65, 18.25))
    ax.axis("off")
    x = 5.25

    box(ax, "start", x, 17.15, 7.8, 1.35, "Estado inicial do snapshot",
        "Associa\u00e7\u00f5es, UEs e atividade definidos\nContribui\u00e7\u00f5es individuais e INR no FS")
    decision(ax, "trigger", x, 15.45, 5.6, 1.1, r"INR $> -6$ dB?")
    box(ax, "initial", x, 13.7, 7.8, 1.45, "Fixar a lista inicial de contribuintes",
        "At\u00e9 K feixes ativos com maior interfer\u00eancia\nK = M; contador de trocas aceitas: m = 0")
    box(ax, "limit_note", 12, 14, 4.2, 1.65, "Limite por snapshot",
        "M = 5, 10, 15,\n20, 25 ou 30 trocas")
    ax.plot([9.15, 9.9], [13.7, 13.7], color=BLUE, lw=.9, ls=(0, (3, 3)))
    decision(ax, "stop", x, 11.55, 7.8, 1.65,
             "INR \u2264 \u22126 dB, m \u2265 M\nou lista esgotada?")
    box(ax, "end", 12.1, 11.55, 4.3, 1.55, "Encerrar snapshot",
        "Registrar o estado final\ne o motivo de parada", terminal=True)
    box(ax, "select", x, 9.55, 7.8, 1.35, "Selecionar o maior contribuinte restante",
        "Retirar a c\u00e9lula da lista de busca\nN\u00e3o investig\u00e1-la novamente neste snapshot")
    box(ax, "evaluate", x, 7.6, 7.8, 1.45, "Avaliar sat\u00e9lites alternativos",
        "Escolher a menor contribui\u00e7\u00e3o entre os v\u00e1lidos\nPrever e conferir a redu\u00e7\u00e3o do INR")
    box(ax, "constraints", 12.1, 7.6, 4.3, 2.1, "Restri\u00e7\u00f5es de servi\u00e7o",
        "Sat\u00e9lite eleg\u00edvel\nEleva\u00e7\u00e3o da c\u00e9lula\ne do UE \u2265 32\u00b0")
    ax.plot([9.15, 9.95], [7.6, 7.6], color=BLUE, lw=.9, ls=(0, (3, 3)))
    decision(ax, "improve", x, 5.6, 7.8, 1.65,
             "H\u00e1 troca v\u00e1lida com\nredu\u00e7\u00e3o estrita do INR?")
    box(ax, "accept", x, 3.65, 7.8, 1.5, "Confirmar a reassocia\u00e7\u00e3o",
        "Preservar a c\u00e9lula, seus UEs e a atividade\nAtualizar contribui\u00e7\u00f5es, INR e m \u2190 m + 1")
    box(ax, "reorder", x, 1.65, 7.8, 1.25, "Reordenar os contribuintes restantes",
        "Usar as contribui\u00e7\u00f5es atualizadas\nSem ampliar a lista inicial")

    route(ax, [(x, 16.475), (x, 16)])
    route(ax, [(x, 14.9), (x, 14.425)], "Sim", (5.65, 14.67))
    route(ax, [(8.05, 15.45), (14.65, 15.45), (14.65, 11.55), (14.25, 11.55)],
          "N\u00e3o", (10.1, 15.45))
    route(ax, [(x, 12.975), (x, 12.375)])
    route(ax, [(9.15, 11.55), (9.95, 11.55)], "Sim", (9.55, 11.86))
    route(ax, [(x, 10.725), (x, 10.225)], "N\u00e3o", (5.72, 10.48))
    route(ax, [(x, 8.875), (x, 8.325)])
    route(ax, [(x, 6.875), (x, 6.425)])
    route(ax, [(x, 4.775), (x, 4.4)], "Sim", (5.65, 4.59))
    route(ax, [(x, 2.9), (x, 2.275)])
    # Both paths re-enter the stopping test; a rejected cell is already removed.
    route(ax, [(1.35, 5.6), (.55, 5.6), (.55, 11.55), (1.35, 11.55)],
          "N\u00e3o", (.98, 5.92))
    route(ax, [(1.35, 1.65), (.55, 1.65), (.55, 11.55), (1.35, 11.55)])

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    problems = []
    for key, (patch, objects) in NODES.items():
        for obj in objects:
            bbox = obj.get_window_extent(renderer).expanded(1.02, 1.04)
            corners = [(bbox.x0, bbox.y0), (bbox.x1, bbox.y0),
                       (bbox.x1, bbox.y1), (bbox.x0, bbox.y1)]
            path = patch.get_path().transformed(patch.get_transform())
            if not all(path.contains_point(corner) for corner in corners):
                problems.append(f"Text outside {key}: {obj.get_text()}")
    for i, obj in enumerate(TEXTS):
        a = obj.get_window_extent(renderer)
        for other in TEXTS[i+1:]:
            if a.overlaps(other.get_window_extent(renderer)):
                problems.append(f"Overlapping text: {obj.get_text()} / {other.get_text()}")
    if problems:
        raise ValueError("\n".join(problems))
    OUT.mkdir(exist_ok=True)
    base = OUT / "fig_fluxograma_handover"
    fig.savefig(base.with_suffix(".png"), dpi=600, facecolor="white")
    fig.savefig(base.with_name(base.name + "_preview.png"), dpi=160, facecolor="white")
    base.with_name(base.name + "_validation.json").write_text(json.dumps(
        dict(configuration=settings, text_inside_shapes=True, text_overlaps=0,
             size_inches=[8.2, 9.95], png_dpi=600,
             algorithm="sharc/interference_aware_handover_v2.py:137",
             reference="PIBIC 2026 report, Figure 3, page 6"), indent=2), encoding="utf-8")
    plt.close(fig)
    print(base.with_suffix(".png"))


if __name__ == "__main__":
    main()

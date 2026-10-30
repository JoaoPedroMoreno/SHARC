"""Illustrate verified snapshot associations, deliberately not geographic positions."""

from __future__ import annotations

import math

from matplotlib.patches import Circle, FancyArrowPatch, Polygon as MplPolygon
from matplotlib.colors import to_rgba
import numpy as np

import generate_hex_presentation_images as style
from generate_congress_figures import WIDTH, HEIGHT, INK, BLUE_TEXT, text
from snapshot_illustration_data import load_snapshot


INACTIVE = "#ABB6BC"
UE_COLOR = "#3C8271"


def snapshot_illustration():
    state = load_snapshot()
    active = np.asarray(state["active"])
    affected = np.asarray(state["affected"])
    serving = np.asarray(state["serving_satellite_ids"])
    centers = np.asarray(state["grid_ecef_m"])
    focus = 1203
    selected = np.argsort(np.linalg.norm(centers-centers[focus], axis=1))[:19]
    sat_ids = np.unique(serving[selected])
    assert sat_ids.tolist() == [4041, 4042]
    assert active[selected].sum() == 10 and affected[selected].sum() == 1

    # Assign the real beam/UE IDs to a readable logical hexagon layout.
    slots = [(q, r) for q in range(-2, 3) for r in range(-2, 3)
             if abs(q + r) <= 2]
    slots.sort(key=lambda qr: (qr[0], qr[1] + qr[0] / 2))
    ordered_ids = sorted(selected, key=lambda i: (serving[i], i))
    slot_ids = dict(zip(slots, map(int, ordered_ids)))
    focus_slot = (1, -2)
    old_slot = next(key for key, value in slot_ids.items() if value == focus)
    assert serving[slot_ids[focus_slot]] == serving[focus]
    slot_ids[old_slot], slot_ids[focus_slot] = slot_ids[focus_slot], slot_ids[old_slot]

    fig, ax = style.canvas(WIDTH, HEIGHT, 160, 90)
    text(ax, 6, 84, "O que acontece em um snapshot", 32, weight="medium")
    text(ax, 6, 77, "Snapshot 1  |  LF = 50%  |  PBO = 10 dB  |  fração = 10%", 22, color=BLUE_TEXT)
    ax.plot((111, 111), (6, 71), color="#DFE7EB", linewidth=1.2, zorder=1)

    sources = {}
    for sat_id, x in zip(sat_ids, (35, 82)):
        sources[int(sat_id)] = style.satellite(ax, x, 64, 23)
        text(ax, x, 72, f"Satélite {sat_id}", 21, ha="center")
    text(ax, 58.5, 66, "LEO / 340 km", 19, ha="center", color=BLUE_TEXT)

    radius = 7.8
    rng = np.random.default_rng(17)
    drawn = []
    for (q, r), beam_id in slot_ids.items():
        center = np.array((1.5 * radius * q, math.sqrt(3) * radius * (r + q / 2)))
        footprint = style.hex_vertices(center, radius) * (1.10, 0.50) + (55, 35.5)
        node = (center + rng.uniform(-1.9, 1.9, 2)) * (1.10, 0.50) + (55, 35.5)
        color = style.ORANGE if affected[beam_id] else style.BLUE
        if not active[beam_id]:
            color, fill, linestyle = INACTIVE, "#FCFDFD", (0, (4, 2))
        else:
            fill = style.ORANGE_PALE if affected[beam_id] else style.BLUE_PALE
            linestyle = "solid"
        ax.add_patch(MplPolygon(footprint, facecolor=fill, edgecolor=color,
                               linewidth=1.45, linestyle=linestyle, zorder=2,
                               gid=f"cell:{beam_id}"))
        drawn.append({"beam_id": beam_id, "ue_id": beam_id,
                      "satellite_id": int(serving[beam_id]),
                      "active": bool(active[beam_id]), "pbo": bool(affected[beam_id]),
                      "footprint": footprint, "ue_point": node})

    for item in drawn:
        if item["active"]:
            source = sources[item["satellite_id"]]
            style.beam(ax, source, item["footprint"], item["pbo"], broad=True,
                       visual_scale=0.62 if item["pbo"] else 0.85,
                       beam_id=f"service:{item['beam_id']}")
        color = style.ORANGE if item["pbo"] else UE_COLOR
        if not item["active"]:
            color = INACTIVE
        ax.add_patch(Circle(item["ue_point"], 0.64,
                           facecolor=color if item["active"] else "white",
                           edgecolor=color, linewidth=1.8, zorder=20,
                           gid=f"ue:{item['ue_id']}"))
    focus_node = next(item["ue_point"] for item in drawn if item["beam_id"] == focus)
    ax.add_patch(Circle(focus_node, 1.3, facecolor="none", edgecolor=style.ORANGE,
                       linewidth=1.6, zorder=21))
    for sat_id, color, line_style, width in ((4042, style.ORANGE, "solid", 2.2),
                                            (4041, style.RED, (0, (5, 4)), 1.9)):
        ax.add_patch(FancyArrowPatch(sources[sat_id], focus_node,
                                     arrowstyle="-|>", mutation_scale=16,
                                     color=color, linewidth=width,
                                     linestyle=line_style, shrinkA=7, shrinkB=12,
                                     zorder=17, gid="signal-S" if sat_id == 4042 else "interference-I"))
    text(ax, 80, 46, "S", 26, color="#AC5F2C", weight="medium")
    text(ax, 45, 49, "I", 26, color=style.RED, weight="medium")
    text(ax, focus_node[0]+3, focus_node[1]-0.5, "UE 1203", 19, color="#AC5F2C")

    # Counts refer to the complete recorded snapshot, not the reduced drawing.
    text(ax, 116, 69, "Rede neste snapshot", 23, weight="medium")
    for y, value in ((62, "25 satélites associados"),
                     (56.5, "1.472 feixes / 1.472 UEs"),
                     (51, "717 ativos / 755 inativos"),
                     (45.5, "72 feixes com PBO"),
                     (40, "717 UEs avaliados")):
        text(ax, 116, y, value, 20)
    ax.plot((116, 154), (35, 35), color="#DFE7EB", linewidth=1.2, zorder=1)
    text(ax, 116, 30, "Por UE avaliado", 23, weight="medium")
    text(ax, 116, 24, "S: sinal desejado", 20, color="#AC5F2C")
    text(ax, 116, 18, "I: soma dos demais\n   feixes ativos", 20, color=style.RED)
    text(ax, 116, 12, "N: ruído térmico", 20)
    text(ax, 133, 5, r"$\mathrm{SINR}=\frac{S}{I+N}$", 25, color=BLUE_TEXT, ha="center")

    text(ax, 6, 16, "Recorte: 19 feixes / 10 ativos / 9 inativos / 1 com PBO", 20)
    for x, color, fill, value, dash in (
            (8, style.BLUE, style.BLUE_PALE, "Ativo nominal", False),
            (43, style.ORANGE, style.ORANGE_PALE, "Ativo com PBO", False),
            (79, INACTIVE, "white", "Inativo", True)):
        ax.add_patch(MplPolygon(style.hex_vertices((x, 10), 1.5), facecolor=fill,
                               edgecolor=color, linewidth=1.5,
                               linestyle=(0, (4, 2)) if dash else "solid", zorder=21))
        text(ax, x+3, 10, value, 20)
    ax.add_patch(Circle((7.5, 4.4), 0.58, facecolor=UE_COLOR, edgecolor=UE_COLOR, zorder=21))
    ax.add_patch(Circle((9.2, 4.4), 0.58, facecolor="white", edgecolor=INACTIVE, linewidth=1.7, zorder=21))
    text(ax, 11, 4.4, "UE avaliado / não avaliado", 19)
    text(ax, 66, 4.4, "Associações não geográficas", 19, color=INK)

    metadata = {"snapshot_id": 1, "source_folder": state["source_folder"],
                "layout": "logical associations, not geographic positions",
                "counts": {"drawn_cells": 19, "drawn_satellites": 2,
                           "drawn_ues": 19, "drawn_active_ues": 10,
                           "drawn_inactive_ues": 9, "drawn_pbo_beams": 1,
                           "network_cells": state["cells"],
                           "network_active_ues": state["active_beams"],
                           "network_pbo_beams": state["pbo_beams"]},
                "associations": [{k: v for k, v in item.items()
                                   if k not in ("footprint", "ue_point")} for item in drawn],
                "caution": state["geometry_caution"], "source_checks": state["checks"]}
    return fig, metadata


if __name__ == "__main__":
    import json
    from generate_congress_figures import OUT, verify_and_save
    fig, metadata = snapshot_illustration()
    metadata = verify_and_save(fig, "sharc_snapshot_illustrated.png", metadata)
    (OUT / "snapshot_illustration_validation.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

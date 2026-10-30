"""Render a schematic Monte Carlo overview, without reading or running simulations."""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Polygon
from shapely.geometry import MultiPoint

import generate_congress_figures as common


def snapshot(
    ax,
    x,
    label,
    active,
    pbo,
    shift,
    offsets,
    satellite_layout=None,
    serving=None,
):
    """Positions and activation masks are illustrative, not measured geometry."""

    s = common.style

    if label:
        common.text(
            ax,
            x,
            63 if satellite_layout else 59,
            label,
            20,
            ha="center",
            color=common.BLUE_TEXT,
        )

    if satellite_layout:
        sources = []

        # A e B acima dos satélites foram removidos.
        for dx, y in satellite_layout:
            sources.append(
                s.satellite(
                    ax,
                    x + dx,
                    y,
                    8,
                )
            )

        assert serving is not None and len(serving) == 4
        assert 0 in active

    else:
        sources = [
            s.satellite(
                ax,
                x + shift,
                51,
                12,
            )
        ]
        serving = [0] * 4

    centers = [
        (x - 5, 37),
        (x, 39.9),
        (x + 5, 37),
        (x, 34.1),
    ]

    if satellite_layout:
        # This check concerns only the schematic projection,
        # not orbital distances.
        closest = [
            int(
                np.argmin(
                    np.linalg.norm(
                        np.asarray(sources) - c,
                        axis=1,
                    )
                )
            )
            for c in centers
        ]

        assert serving == closest, (serving, closest)

    for i, center in enumerate(centers):
        source = sources[serving[i]]

        vertices = s.hex_vertices(
            center,
            3.3,
        )

        color = (
            common.ORANGE
            if i == pbo
            else common.BLUE
        )

        if i in active:
            silhouette = np.asarray(
                MultiPoint(
                    np.vstack(
                        (
                            source,
                            vertices,
                        )
                    )
                )
                .convex_hull
                .exterior
                .coords
            )

            ax.add_patch(
                Polygon(
                    silhouette,
                    facecolor=color,
                    alpha=0.14 if i == pbo else 0.20,
                    edgecolor="none",
                    zorder=3 + (40 - center[1]) * 0.01,
                )
            )

            ax.plot(
                [source[0], center[0]],
                [source[1], center[1]],
                color=color,
                linewidth=1.15,
                alpha=0.8,
                zorder=4,
            )

        ax.add_patch(
            Polygon(
                vertices,
                facecolor=(
                    s.ORANGE_PALE
                    if i == pbo
                    else (
                        s.BLUE_SELECTED
                        if i in active
                        else "white"
                    )
                ),
                edgecolor="none",
                zorder=2,
            )
        )

        ax.add_patch(
            Polygon(
                vertices,
                fill=False,
                edgecolor=(
                    color
                    if i in active
                    else "#AAB8C0"
                ),
                linewidth=1.5,
                linestyle=(
                    "-"
                    if i in active
                    else "--"
                ),
                zorder=5,
            )
        )

        dx, dy = offsets[i]

        ax.add_patch(
            Circle(
                (
                    center[0] + dx,
                    center[1] + dy,
                ),
                0.48,
                facecolor=(
                    common.ORANGE_TEXT
                    if i == pbo
                    else (
                        common.BLUE_TEXT
                        if i in active
                        else "white"
                    )
                ),
                edgecolor=(
                    common.ORANGE_TEXT
                    if i == pbo
                    else (
                        common.BLUE_TEXT
                        if i in active
                        else "#AAB8C0"
                    )
                ),
                linewidth=1.3,
                zorder=6,
            )
        )

    if satellite_layout:
        common.text(
            ax,
            x,
            29.4,
            f"Servidor {'AB'[serving[0]]}",
            19,
            ha="center",
            color=common.INK,
        )


def methodology_overview(compact=False):
    height = (
        1100
        if compact
        else common.HEIGHT
    )

    fig, ax = common.style.canvas(
        common.WIDTH,
        height,
        160,
        height / 20,
    )

    if compact:
        ax.set_ylim(
            12,
            67,
        )

    t = common.text

    # ---------------------------------------------------------
    # Setas principais do fluxo
    # ---------------------------------------------------------

    for x in (
        40,
        117,
    ):
        ax.add_patch(
            FancyArrowPatch(
                (x - 3, 46),
                (x + 2, 46),
                arrowstyle="-|>",
                mutation_scale=27,
                linewidth=2.6,
                color=common.BLUE_TEXT,
                zorder=10,
            )
        )

    # ---------------------------------------------------------
    # BLOCO 1 — CONFIGURAÇÃO
    # ---------------------------------------------------------

    t(
        ax,
        20,
        63.2,
        "Configuração",
        19,
        ha="center",
        color=common.BLUE_TEXT,
    )

    for y, label, color in [
        (
            53,
            "LF",
            common.BLUE_TEXT,
        ),
        (
            42,
            "Nível de PBO",
            common.ORANGE_TEXT,
        ),
        (
            30,
            "Fração de feixes\nafetados",
            common.INK,
        ),
    ]:
        t(
            ax,
            7,
            y,
            label,
            26,
            color=color,
        )

    # ---------------------------------------------------------
    # BLOCO 2 — MONTE CARLO / SNAPSHOTS
    # ---------------------------------------------------------

    snapshot(
        ax,
        53,
        "Snapshot 1",
        {0, 1, 3},
        3,
        -2,
        [
            (-1.1, -0.9),
            (-0.4, 0.8),
            (0.5, 0.2),
            (0.2, -0.5),
        ],
        satellite_layout=[
            (-6, 51),
            (2, 50.5),
        ],
        serving=[
            0,
            1,
            1,
            1,
        ],
    )

    snapshot(
        ax,
        77,
        "Snapshot 2",
        {0, 2},
        0,
        1,
        [
            (1.1, 0.9),
            (0.6, -0.4),
            (-0.5, -0.3),
            (0.5, 0.6),
        ],
        satellite_layout=[
            (5, 52),
            (-5, 50.5),
        ],
        serving=[
            1,
            1,
            0,
            1,
        ],
    )

    snapshot(
        ax,
        104,
        "Snapshot 1000",
        {0, 2, 3},
        2,
        -0.5,
        [
            (0.8, -1.0),
            (0.6, 0.1),
            (0.4, -0.6),
            (-0.5, 0.3),
        ],
        satellite_layout=[
            (-3, 50),
            (6, 51),
        ],
        serving=[
            0,
            0,
            1,
            0,
        ],
    )

    t(
        ax,
        90,
        47,
        "...",
        25,
        ha="center",
        color=common.BLUE_TEXT,
    )

    # Explicita o número total de snapshots por configuração.
    # t(
    #     ax,
    #     116.5,
    #     56.0,
    #     "1000 snapshots\npor configuração",
    #     19,
    #     ha="center",
    #     color=common.INK,
    # )

    # ---------------------------------------------------------
    # Legenda dos estados dos feixes
    # ---------------------------------------------------------

    for x, label, color, fill, dash in [
        (
            47,
            "Ativo",
            common.BLUE,
            common.style.BLUE_SELECTED,
            "-",
        ),
        (
            67,
            "Com PBO",
            common.ORANGE,
            common.style.ORANGE_PALE,
            "-",
        ),
        (
            94,
            "Inativo",
            "#AAB8C0",
            "white",
            "--",
        ),
    ]:
        ax.add_patch(
            Polygon(
                common.style.hex_vertices(
                    (x, 26),
                    1.3,
                ),
                facecolor=fill,
                edgecolor=color,
                linestyle=dash,
                linewidth=1.5,
            )
        )

        t(
            ax,
            x + 2.3,
            26,
            label,
            19,
        )

    t(
        ax,
        78.5,
        17.8,
        "Em cada snapshot, o SHARC calcula\n"
        "S, I, N e SINR por usuário.",
        22,
        ha="center",
        color=common.BLUE_TEXT,
    )

    # ---------------------------------------------------------
    # BLOCO 3 — AGREGAÇÃO ESTATÍSTICA
    # ---------------------------------------------------------

    t(
        ax,
        137.5,
        63.2,
        "Agregação estatística",
        19,
        ha="center",
        color=common.BLUE_TEXT,
    )

    # Ícone esquemático de ECDF.
    # Representa apenas a agregação estatística,
    # não um resultado de simulação específico.

    ax.plot(
        [124, 124, 151],
        [47, 59, 59],
        alpha=0,
    )

    ax.plot(
        [124, 124, 151],
        [59, 47, 47],
        color="#AAB8C0",
        linewidth=1.4,
    )

    x = np.linspace(
        125,
        150,
        28,
    )

    for center, color in [
        (
            137,
            common.BLUE_TEXT,
        ),
        (
            140,
            common.ORANGE,
        ),
    ]:
        y = (
            47.4
            + 10
            / (
                1
                + np.exp(
                    -(x - center)
                    / 2.8
                )
            )
        )

        ax.step(
            x,
            y,
            where="post",
            color=color,
            linewidth=2.2,
        )

    t(
        ax,
        123,
        40.5,
        "Outage",
        27,
        color=common.BLUE_TEXT,
    )

    t(
        ax,
        123,
        32.5,
        "P5  •  CDFs",
        27,
        color=common.BLUE_TEXT,
    )

    t(
        ax,
        123,
        21.5,
        "Comparação entre\nconfigurações",
        23,
    )

    # ---------------------------------------------------------
    # Metadata de validação
    # ---------------------------------------------------------

    return fig, {
        "purpose":
            "Three-stage conceptual overview, not a specific snapshot",

        "steps": [
            "Configuração do cenário",
            "Monte Carlo no SHARC",
            "Agregação estatística",
        ],

        "parameters": [
            "LF",
            "nível de PBO",
            "fração de feixes afetados",
        ],

        "configured_snapshots":
            1000,

        "snapshot_examples": [
            1,
            2,
            1000,
        ],

        "illustrative_active_cells": [
            3,
            2,
            3,
        ],

        "illustrative_inactive_cells": [
            1,
            2,
            1,
        ],

        "illustrative_satellites_per_example":
            2,

        "reference_ue_servers": [
            "A",
            "B",
            "A",
        ],

        "reference_ue_mark":
            "none",

        "satellite_to_ue_arrows":
            False,

        "single_boresight_line_per_active_beam":
            True,

        "nearest_satellite_in_schematic_projection_checked":
            True,

        "beam_volumes_drawn_above_ground_faces":
            True,

        "satellite_positions_vary":
            True,

        "ue_positions_vary":
            True,

        "slide_headings_and_footer_removed":
            True,

        "illustrative_positions_and_activation":
            True,

        "illustrative_cdf_not_results":
            True,

        "real_ids_or_network_counts":
            False,

        "new_simulation_run":
            False,

        "raw_data_accessed_or_modified":
            False,
    }


def main():
    common.OUT.mkdir(
        exist_ok=True
    )

    fig, metadata = methodology_overview(
        compact=True
    )

    record = common.verify_and_save(
        fig,
        "sharc_monte_carlo_methodology_labels.png",
        metadata,
        expected_size=(
            3200,
            1100,
        ),
    )

    (
        common.OUT
        / "methodology_labels_validation.json"
    ).write_text(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def illustrations_only():
    """
    A compact image asset, with no slide headings,
    labels or explanatory text.
    """

    fig = plt.figure(
        figsize=(16, 5),
        dpi=200,
        facecolor="white",
    )

    examples = [
        (
            {0, 1, 3},
            3,
            -2,
            [
                (0.5, -0.3),
                (-0.4, 0.8),
                (0.5, 0.2),
                (0.2, -0.5),
            ],
        ),
        (
            {0, 2},
            0,
            1,
            [
                (-0.4, 0.5),
                (0.6, -0.4),
                (-0.5, -0.3),
                (0.5, 0.6),
            ],
        ),
        (
            {1, 2, 3},
            2,
            -0.5,
            [
                (0.1, 0.7),
                (0.6, 0.1),
                (0.4, -0.6),
                (-0.5, 0.3),
            ],
        ),
    ]

    for left, (
        active,
        pbo,
        shift,
        offsets,
    ) in zip(
        [
            0.01,
            0.24,
            0.50,
        ],
        examples,
    ):
        assert pbo in active

        ax = fig.add_axes(
            (
                left,
                0.04,
                0.22,
                0.92,
            ),
            xlim=(
                -11,
                11,
            ),
            ylim=(
                29,
                56,
            ),
        )

        ax.set_aspect(
            "equal"
        )

        ax.axis(
            "off"
        )

        snapshot(
            ax,
            0,
            None,
            active,
            pbo,
            shift,
            offsets,
        )

    decor = fig.add_axes(
        (
            0,
            0,
            1,
            1,
        ),
        xlim=(
            0,
            160,
        ),
        ylim=(
            0,
            50,
        ),
        zorder=0,
    )

    decor.axis(
        "off"
    )

    for x in (
        75,
        76.4,
        77.8,
    ):
        decor.add_patch(
            Circle(
                (
                    x,
                    24,
                ),
                0.35,
                facecolor=common.BLUE_TEXT,
                edgecolor="none",
            )
        )

    decor.add_patch(
        FancyArrowPatch(
            (
                116,
                24,
            ),
            (
                122,
                24,
            ),
            arrowstyle="-|>",
            mutation_scale=27,
            linewidth=2.6,
            color=common.BLUE_TEXT,
        )
    )

    decor.plot(
        [
            127,
            127,
            157,
        ],
        [
            37,
            12,
            12,
        ],
        color="#AAB8C0",
        linewidth=1.6,
    )

    x = np.linspace(
        128,
        156,
        32,
    )

    for center, color in [
        (
            140,
            common.BLUE_TEXT,
        ),
        (
            143,
            common.ORANGE,
        ),
    ]:
        y = (
            12.5
            + 23
            / (
                1
                + np.exp(
                    -(x - center)
                    / 3
                )
            )
        )

        decor.step(
            x,
            y,
            where="post",
            color=color,
            linewidth=2.5,
        )

    fig.canvas.draw()

    assert tuple(
        fig.canvas.get_width_height()
    ) == (
        3200,
        1000,
    )

    assert not any(
        ax.texts
        for ax in fig.axes
    )

    output = (
        common.OUT
        / "sharc_monte_carlo_illustrations.png"
    )

    fig.savefig(
        output,
        dpi=200,
        facecolor="white",
    )

    plt.close(
        fig
    )

    record = {
        "size_px": [
            3200,
            1000,
        ],

        "text_count":
            0,

        "illustrative_active_cells": [
            len(
                item[0]
            )
            for item in examples
        ],

        "illustrative_inactive_cells": [
            4
            - len(
                item[0]
            )
            for item in examples
        ],

        "ues_per_cell":
            1,

        "geometry_and_cdf_are_schematic":
            True,

        "simulation_or_raw_data_modified":
            False,
    }

    (
        common.OUT
        / "illustrations_only_validation.json"
    ).write_text(
        json.dumps(
            record,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        output
    )


if __name__ == "__main__":
    main()
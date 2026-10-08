"""Figura 5: benefício da mitigação e taxa de atuação."""
from __future__ import annotations

from _common import (
    DATA, GREEN, PURPLE, SCENARIO_LABELS, clean_axes, final_runs,
    panel_label, prepare_dirs, require_columns, save_figure, scenario_label,
    setup_ieee,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main() -> None:
    prepare_dirs(); setup_ieee(); runs = final_runs(); records = []
    for key, directory in sorted(runs.items()):
        altitude, eess, load, gb = key
        if gb not in (10, 5):
            continue
        source = directory / "interference_aware_handover_v2_snapshot.csv"
        frame = pd.read_csv(source)
        require_columns(frame, ["reassigned_beams", "iagg_reduction_db"], source)
        acted = frame.reassigned_beams > 0
        records.append({
            "scenario": scenario_label(altitude, eess, load),
            "altitude_km": altitude, "eess_system": eess,
            "load_factor": load, "guard_band_mhz": gb,
            "snapshots": len(frame), "handover_snapshots": int(acted.sum()),
            "activation_rate_pct": 100 * acted.mean(),
            "median_reduction_acted_db": float(frame.loc[acted, "iagg_reduction_db"].median()),
            "source_path": str(directory.resolve()),
        })
    data = pd.DataFrame(records); data.to_csv(DATA / "fig05_data.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.25), sharey=True)
    y = np.arange(len(SCENARIO_LABELS)); offsets = {10: -0.12, 5: 0.12}
    colors = {10: GREEN, 5: PURPLE}; markers = {10: "o", 5: "s"}
    metrics = ["median_reduction_acted_db", "activation_rate_pct"]
    labels = ["Redução mediana de interferência [dB]",
              "Taxa de atuação do handover [% dos snapshots]"]
    for panel, (ax, metric, xlabel) in enumerate(zip(axes, metrics, labels)):
        for gb in (10, 5):
            subset = data[data.guard_band_mhz == gb].set_index("scenario").loc[SCENARIO_LABELS]
            ax.scatter(subset[metric], y + offsets[gb], color=colors[gb],
                       marker=markers[gb], label=f"GB = {gb} MHz", zorder=3)
        ax.set_yticks(y, SCENARIO_LABELS); ax.invert_yaxis()
        ax.set_xlabel(xlabel); clean_axes(ax, grid_axis="x")
        panel_label(ax, f"({chr(97 + panel)})")
    axes[1].legend(loc="lower right", frameon=False)
    fig.subplots_adjust(wspace=0.18)
    save_figure(fig, "fig05_mitigation_behavior")


if __name__ == "__main__":
    main()

"""Figura 4: excedência empírica sem e com mitigação."""
from __future__ import annotations

from _common import (
    BLUE, DARK, DATA, GRAY, SCENARIO_LABELS, VERMILLION,
    clean_axes, final_runs, panel_label, prepare_dirs, require_columns,
    save_figure, scenario_label, setup_ieee,
)
import pandas as pd
import matplotlib.pyplot as plt


def main() -> None:
    prepare_dirs(); setup_ieee(); runs = final_runs()
    records = []
    used = []
    for key, directory in sorted(runs.items()):
        altitude, eess, load, gb = key
        if gb not in (10, 5):
            continue
        source = directory / "interference_aware_handover_v2_snapshot.csv"
        frame = pd.read_csv(source)
        require_columns(frame, ["iagg_before_dbw_per_mhz", "iagg_after_dbw_per_mhz"], source)
        records.append({
            "scenario": scenario_label(altitude, eess, load),
            "altitude_km": altitude, "eess_system": eess,
            "load_factor": load, "guard_band_mhz": gb,
            "snapshots": len(frame),
            "exceedance_before_pct": 100 * (frame["iagg_before_dbw_per_mhz"] > -154).mean(),
            "exceedance_after_pct": 100 * (frame["iagg_after_dbw_per_mhz"] > -154).mean(),
            "source_path": str(directory.resolve()),
        })
        used.append(directory)
    data = pd.DataFrame(records)
    data.to_csv(DATA / "fig04_data.csv", index=False)
    print("Runs used:"); [print(f"  {path}") for path in used]

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.35), sharey=True)
    y = list(range(len(SCENARIO_LABELS)))
    for panel, (ax, gb) in enumerate(zip(axes, (10, 5))):
        subset = data[data.guard_band_mhz == gb].set_index("scenario").loc[SCENARIO_LABELS]
        before = subset.exceedance_before_pct.to_numpy()
        after = subset.exceedance_after_pct.to_numpy()
        for yi, x0, x1 in zip(y, before, after):
            ax.plot([x0, x1], [yi, yi], color=GRAY, linewidth=0.8, zorder=1)
        ax.scatter(before, y, color=BLUE, marker="o", label="Sem mitigação", zorder=2)
        ax.scatter(after, y, color=VERMILLION, marker="D", label="Com mitigação", zorder=3)
        ax.axvline(1.0, color=DARK, linestyle=(0, (4, 3)), linewidth=0.9)
        ax.text(1.0, 0.98, "Critério de proteção: 1%", ha="center", va="top",
                fontsize=6.8, transform=ax.get_xaxis_transform())
        ax.set_title(f"GB = {gb} MHz", fontsize=8.3)
        ax.set_xlabel("Probabilidade de excedência [%]")
        ax.set_yticks(y, SCENARIO_LABELS)
        ax.invert_yaxis(); clean_axes(ax, grid_axis="x")
        panel_label(ax, f"({chr(97 + panel)})")
        maximum = max(float(before.max()), float(after.max()))
        ax.set_xlim(-0.03 * max(maximum, 1), maximum * 1.08 + 0.15)
    axes[1].legend(loc="lower right", frameon=False)
    fig.subplots_adjust(wspace=0.14)
    save_figure(fig, "fig04_exceedance_gb10_gb5")


if __name__ == "__main__":
    main()

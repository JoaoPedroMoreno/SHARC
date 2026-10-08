"""Figure 6: event-level service-elevation loss at GB=10 MHz."""
from __future__ import annotations

from _common import (
    DARK, DATA, GREEN, LIGHT, SCENARIO_LABELS, final_runs, prepare_dirs,
    require_columns, save_figure, scenario_label, setup_ieee,
)
import pandas as pd
import matplotlib.pyplot as plt


def main() -> None:
    prepare_dirs(); setup_ieee(); runs = final_runs(); pieces = []
    for key, directory in sorted(runs.items()):
        altitude, eess, load, gb = key
        if gb != 10:
            continue
        source = directory / "interference_aware_handover_v2_events.csv"
        frame = pd.read_csv(source)
        require_columns(frame, ["accepted", "current_service_elevation_deg",
                                "selected_service_elevation_deg"], source)
        accepted = frame[frame.accepted.astype(str).str.lower() == "true"].copy()
        accepted["service_elevation_loss_deg"] = (
            accepted.current_service_elevation_deg - accepted.selected_service_elevation_deg)
        accepted["scenario"] = scenario_label(altitude, eess, load)
        accepted["source_path"] = str(directory.resolve())
        pieces.append(accepted[["snapshot_id", "scenario", "service_elevation_loss_deg",
                                "current_service_elevation_deg", "selected_service_elevation_deg",
                                "source_path"]])
    data = pd.concat(pieces, ignore_index=True)
    data.to_csv(DATA / "fig06_data.csv", index=False)

    groups = [data.loc[data.scenario == scenario, "service_elevation_loss_deg"].to_numpy()
              for scenario in SCENARIO_LABELS]
    fig, ax = plt.subplots(figsize=(3.5, 3.45))
    bp = ax.boxplot(groups, vert=False, tick_labels=SCENARIO_LABELS,
                    showfliers=False, widths=0.58, patch_artist=True, whis=(5, 95),
                    medianprops={"color": DARK, "linewidth": 1.0},
                    whiskerprops={"color": DARK, "linewidth": 0.8},
                    capprops={"color": DARK, "linewidth": 0.8},
                    boxprops={"edgecolor": DARK, "linewidth": 0.8})
    for patch in bp["boxes"]:
        patch.set_facecolor("#E69F00"); patch.set_alpha(0.30)
    ax.text(0.02, 1.015, "caixa: Q1–Q3 | linha: mediana | bigodes: P5–P95",
            ha="left", va="bottom", fontsize=6.5, transform=ax.transAxes, color=DARK)
    ax.set_xlabel("Perda de elevação de serviço [graus]")
    ax.grid(axis="x", color=LIGHT, linewidth=0.6, alpha=0.65)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    save_figure(fig, "fig06_service_elevation_loss")


if __name__ == "__main__":
    main()

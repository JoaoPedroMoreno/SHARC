"""Figure 1: real campaign geometry and same-cell satellite reassociation."""
from __future__ import annotations

from _common import (
    BLUE, DARK, DATA, FINAL, GRAY, GREEN, ORANGE, REPO, VERMILLION,
    operational_runs, panel_label, prepare_dirs, require_columns,
    save_figure, scenario_label, setup_ieee,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shapefile
import shutil
import subprocess
import sys


def select_representative_event() -> tuple[pd.Series, pd.DataFrame]:
    pieces = []
    for key, directory in sorted(operational_runs().items()):
        altitude, eess, load, gb = key
        if gb != 10:
            continue
        source = directory / "operational_risk_handover_events.csv"
        frame = pd.read_csv(source)
        require_columns(frame, [
            "snapshot_id", "accepted", "predicted_reduction_db",
            "service_elevation_loss_deg", "current_satellite_idx",
            "target_satellite_idx", "current_satellite_latitude_deg",
            "current_satellite_longitude_deg", "target_satellite_latitude_deg",
            "target_satellite_longitude_deg", "service_cell_latitude_deg",
            "service_cell_longitude_deg", "current_satellite_enu_x_m",
            "current_satellite_enu_y_m", "current_satellite_enu_z_m",
            "target_satellite_enu_x_m", "target_satellite_enu_y_m",
            "target_satellite_enu_z_m", "service_cell_enu_x_m",
            "service_cell_enu_y_m", "service_cell_enu_z_m",
            "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
            "current_tx_offaxis_deg", "current_rx_offaxis_deg",
        ], source)
        accepted = frame[frame.accepted.astype(str).str.lower() == "true"].copy()
        accepted["scenario"] = scenario_label(altitude, eess, load)
        accepted["source_path"] = str(directory.resolve())
        pieces.append(accepted)
    events = pd.concat(pieces, ignore_index=True)
    med_reduction = events.predicted_reduction_db.median()
    med_loss = events.service_elevation_loss_deg.median()
    scale_reduction = max(events.predicted_reduction_db.mad()
                          if hasattr(events.predicted_reduction_db, "mad") else
                          np.median(np.abs(events.predicted_reduction_db - med_reduction)), 1e-9)
    scale_loss = max(np.median(np.abs(events.service_elevation_loss_deg - med_loss)), 1e-9)
    events["representativeness_score"] = (
        np.abs(events.predicted_reduction_db - med_reduction) / scale_reduction
        + np.abs(events.service_elevation_loss_deg - med_loss) / scale_loss)
    return events.sort_values(["representativeness_score", "snapshot_id"]).iloc[0], events


def plot_south_america(ax, event: pd.Series) -> None:
    source = REPO / "sharc" / "data" / "countries" / "ne_110m_admin_0_countries.shp"
    reader = shapefile.Reader(str(source))
    fields = [field[0] for field in reader.fields[1:]]
    continent_index = fields.index("CONTINENT") if "CONTINENT" in fields else None
    for shape_record in reader.iterShapeRecords():
        if continent_index is not None and shape_record.record[continent_index] != "South America":
            continue
        points = np.asarray(shape_record.shape.points)
        parts = list(shape_record.shape.parts) + [len(points)]
        for start, end in zip(parts[:-1], parts[1:]):
            segment = points[start:end]
            ax.fill(segment[:, 0], segment[:, 1], facecolor="#F2F2F2",
                    edgecolor="#999999", linewidth=0.45, zorder=0)
    eess = np.array([-54.5746686, -25.5549751])
    service = np.array([event.service_cell_longitude_deg, event.service_cell_latitude_deg])
    current = np.array([event.current_satellite_longitude_deg, event.current_satellite_latitude_deg])
    target = np.array([event.target_satellite_longitude_deg, event.target_satellite_latitude_deg])
    ax.plot([eess[0], current[0]], [eess[1], current[1]], color=VERMILLION,
            linewidth=1.0, label="Interference link")
    ax.plot([service[0], current[0]], [service[1], current[1]], color=BLUE,
            linewidth=1.0, label="Current service link")
    ax.plot([service[0], target[0]], [service[1], target[1]], color=BLUE,
            linewidth=1.0, linestyle="--", label="Target service link")
    ax.scatter(*eess, marker="^", s=35, color=GREEN, zorder=4)
    ax.scatter(*service, marker="s", s=22, facecolor="white", edgecolor=BLUE, zorder=4)
    ax.scatter(*current, marker="o", s=25, color=VERMILLION, zorder=4)
    ax.scatter(*target, marker="D", s=25, color=ORANGE, zorder=4)
    ax.annotate("EESS earth station\nParaguay", eess, xytext=(-18, -18),
                textcoords="offset points", ha="right", fontsize=6.8)
    ax.annotate("Serving satellite", current, xytext=(5, 5),
                textcoords="offset points", fontsize=6.8)
    ax.annotate("Target satellite", target, xytext=(5, -12),
                textcoords="offset points", fontsize=6.8)
    ax.set_xlim(-83, -33); ax.set_ylim(-57, 14)
    ax.set_xlabel("Longitude [deg]"); ax.set_ylabel("Latitude [deg]")
    ax.set_aspect(1 / np.cos(np.deg2rad(-22)))
    ax.spines[:].set_visible(False)
    ax.grid(color="#D9D9D9", linewidth=0.45, alpha=0.55)


def plot_geometry(ax, event: pd.Series) -> None:
    eess = np.array([0.0, 0.0, 15.0]) / 1000
    current = np.array([event.current_satellite_enu_x_m,
                        event.current_satellite_enu_y_m,
                        event.current_satellite_enu_z_m]) / 1000
    target = np.array([event.target_satellite_enu_x_m,
                       event.target_satellite_enu_y_m,
                       event.target_satellite_enu_z_m]) / 1000
    cell = np.array([event.service_cell_enu_x_m,
                     event.service_cell_enu_y_m,
                     event.service_cell_enu_z_m]) / 1000
    boresight = np.array([event.eess_boresight_x,
                          event.eess_boresight_y,
                          event.eess_boresight_z], dtype=float)
    boresight /= np.linalg.norm(boresight)
    desired = eess + boresight * 600

    def line(a, b, color, style="-", width=1.1):
        ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color=color, linestyle=style, linewidth=width)
    line(current, cell, BLUE)
    line(target, cell, BLUE, "--")
    line(current, eess, VERMILLION)
    line(target, eess, ORANGE, ":", 0.9)
    line(eess, desired, GREEN, "-", 1.2)
    ax.scatter(*current, color=VERMILLION, marker="o", s=24,
               label="Serving satellite")
    ax.scatter(*target, color=ORANGE, marker="D", s=24,
               label="Candidate / target")
    ax.scatter(*cell, facecolor="white", edgecolor=BLUE, marker="s", s=22,
               label="Service cell")
    ax.scatter(*eess, color=GREEN, marker="^", s=32,
               label="EESS earth station")
    ax.text(*(eess + 0.72 * (desired - eess)), "EESS boresight", fontsize=6.7, color=GREEN)
    ax.text2D(0.03, 0.97,
              f"$\\psi_{{TX}}$ = {event.current_tx_offaxis_deg:.2f}°\n"
              f"$\\psi_{{RX}}$ = {event.current_rx_offaxis_deg:.2f}°",
              transform=ax.transAxes, va="top", fontsize=7.0)
    direction = target - current
    ax.quiver(*current, *direction, length=0.32, normalize=False,
              color=DARK, arrow_length_ratio=0.08, linewidth=0.8)
    midpoint = current + 0.42 * direction
    ax.text(*midpoint, "Reassociation", fontsize=6.8, color=DARK)
    all_points = np.vstack([eess, current, target, cell, desired])
    mins, maxs = all_points.min(axis=0), all_points.max(axis=0)
    pads = np.maximum((maxs - mins) * 0.08, [20, 20, 20])
    ax.set_xlim(mins[0] - pads[0], maxs[0] + pads[0])
    ax.set_ylim(mins[1] - pads[1], maxs[1] + pads[1])
    ax.set_zlim(min(-20, mins[2] - pads[2]), maxs[2] + pads[2])
    ax.set_xlabel("East [km]"); ax.set_ylabel("North [km]"); ax.set_zlabel("Up [km]")
    ax.view_init(elev=24, azim=-58)
    ax.grid(True, linewidth=0.4, alpha=0.45)
    ax.set_box_aspect((1.2, 1.0, 0.65))
    ax.legend(loc="upper right", bbox_to_anchor=(0.98, 0.96), frameon=False,
              fontsize=5.8, handletextpad=0.35, labelspacing=0.25)


def main() -> None:
    prepare_dirs(); setup_ieee(); event, events = select_representative_event()
    pd.DataFrame([event]).to_csv(DATA / "fig01_representative_event.csv", index=False)
    summary = (
        f"scenario={event.scenario}\n"
        f"snapshot_id={int(event.snapshot_id)}\n"
        f"serving_satellite={int(event.current_satellite_idx)}\n"
        f"target_satellite={int(event.target_satellite_idx)}\n"
        f"predicted_reduction_db={event.predicted_reduction_db:.6f}\n"
        f"service_elevation_loss_deg={event.service_elevation_loss_deg:.6f}\n"
        f"selection=minimum normalized absolute deviation from the GB=10 event medians\n"
        f"source_path={event.source_path}\n"
    )
    (FINAL.parent / "representative_snapshot.txt").write_text(summary, encoding="utf-8")
    source = FINAL.parent / "source" / "blender"
    blender = Path(r"G:\Blender\blender.exe")
    if not blender.exists():
        located = shutil.which("blender")
        if not located:
            raise RuntimeError("Blender executable not found")
        blender = Path(located)
    subprocess.run([
        str(blender), "-b", "--python", str(source / "render_fig01_article.py")
    ], check=True)
    subprocess.run([
        sys.executable, str(source / "compose_fig01_article.py")
    ], check=True)
    print(summary)


if __name__ == "__main__":
    main()

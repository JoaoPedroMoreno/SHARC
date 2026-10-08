"""Audit completeness and provenance before final figures are generated."""
from __future__ import annotations

import csv
import itertools
import re
from pathlib import Path

import yaml


FINAL_CAMPAIGN = Path(__file__).resolve().parents[2]
OPERATIONAL_CAMPAIGN = FINAL_CAMPAIGN.parent / "06_DC_MSS_to_EESS_operational_risk_diagnostics"
AUDIT_CSV = FINAL_CAMPAIGN / "figures" / "data" / "data_audit.csv"
AUDIT_SUMMARY = FINAL_CAMPAIGN / "figures" / "diagnostics" / "data_audit_summary.txt"
FINAL_PATTERN = re.compile(
    r"^system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(5|10|60|65|70|75|80)MHz_STRATEGY_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)
OPERATIONAL_PATTERN = re.compile(
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(10|60|65|70|75|80)MHz_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)
FINAL_GB = (5, 10, 60, 65, 70, 75, 80)
OPERATIONAL_GB = (10, 60, 65, 70, 75, 80)
ALTITUDES = (340, 525)
EESS_SYSTEMS = ("B", "D")
LOAD_FACTORS = (0.2, 0.5)
EXPECTED_SNAPSHOTS = 5000
EXPECTED_TOP_K = 3
GEOMETRY_WANTED = {
    "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
    "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
    "satellite_latitude_deg", "satellite_longitude_deg", "satellite_altitude_m",
    "satellite_enu_x_m", "satellite_enu_y_m", "satellite_enu_z_m",
    "service_cell_latitude_deg", "service_cell_longitude_deg",
    "service_cell_ecef_x_m", "service_cell_ecef_y_m", "service_cell_ecef_z_m",
    "service_cell_enu_x_m", "service_cell_enu_y_m", "service_cell_enu_z_m",
    "tx_offaxis_to_eess_deg", "rx_offaxis_from_eess_boresight_deg",
    "tx_gain_toward_eess_dbi", "rx_gain_from_interferer_dbi",
    "joint_gain_suppression_db", "path_loss_db", "coupling_loss_db",
    "individual_i_linear_mw",
}


def count_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("rb") as stream:
        return max(sum(1 for _ in stream) - 1, 0)


def columns(path: Path) -> list[str]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return next(csv.reader(stream), [])


def count_truthy(path: Path, field: str) -> int:
    if not path.is_file() or field not in columns(path):
        return 0
    with path.open(encoding="utf-8", newline="") as stream:
        return sum(row[field].strip().lower() == "true" for row in csv.DictReader(stream))


def sum_integer(path: Path, field: str) -> int:
    if not path.is_file() or field not in columns(path):
        return 0
    with path.open(encoding="utf-8", newline="") as stream:
        return sum(int(float(row[field] or 0)) for row in csv.DictReader(stream))


def yaml_pointing(directory: Path) -> tuple[str, str, str, str]:
    configs = sorted(directory.glob("*.yaml"))
    if len(configs) != 1:
        return "MISSING", "", "MISSING", ""
    cfg = yaml.safe_load(configs[0].read_text(encoding="utf-8"))
    pointing = cfg["single_earth_station"]["geometry"]
    azimuth = pointing["azimuth"]
    elevation = pointing["elevation"]
    return (
        str(azimuth["type"]), str(azimuth.get("uniform_dist", azimuth.get("constant", {}))),
        str(elevation["type"]), str(elevation.get("uniform_dist", elevation.get("constant", {}))),
    )


def indexed_directories(output: Path, pattern: re.Pattern[str]) -> dict[tuple[int, str, float, int], Path]:
    indexed: dict[tuple[int, str, float, int], tuple[tuple[str, int], Path]] = {}
    if not output.is_dir():
        return {}
    for directory in output.iterdir():
        match = pattern.fullmatch(directory.name) if directory.is_dir() else None
        if not match:
            continue
        key = (int(match[1]), match[2], float(match[3]), int(match[4]))
        stamp = (match[5], int(match[6]))
        if key not in indexed or stamp > indexed[key][0]:
            indexed[key] = (stamp, directory)
    return {key: value[1] for key, value in indexed.items()}


def expected_keys(guard_bands: tuple[int, ...]):
    return itertools.product(ALTITUDES, EESS_SYSTEMS, LOAD_FACTORS, guard_bands)


def base_row(role: str, directory: Path | None, key: tuple[int, str, float, int]) -> dict[str, object]:
    altitude, eess, load, gb = key
    az_type, az_params, el_type, el_params = (
        yaml_pointing(directory) if directory else ("MISSING", "", "MISSING", "")
    )
    return {
        "campaign_role": role,
        "scenario": directory.name if directory else f"MISSING_{altitude}_{eess}_{load}_{gb}",
        "status": "INCOMPLETE",
        "altitude_km": altitude,
        "eess_system": eess,
        "load_factor": load,
        "guard_band_mhz": gb,
        "number_of_snapshots": 0,
        "number_of_topk_rows": 0,
        "number_of_critical_before": 0,
        "number_of_critical_after": 0,
        "number_of_handovers": 0,
        "available_geometry_columns": "NONE",
        "snapshot_columns": "",
        "topk_columns": "",
        "event_columns": "",
        "eess_azimuth_type": az_type,
        "eess_azimuth_parameters": az_params,
        "eess_elevation_type": el_type,
        "eess_elevation_parameters": el_params,
        "realized_eess_pointing_recorded": False,
        "missing_required_files": "",
        "source_path": str(directory.resolve()) if directory else "",
    }


def audit_final() -> list[dict[str, object]]:
    runs = indexed_directories(FINAL_CAMPAIGN / "output", FINAL_PATTERN)
    rows = []
    for key in expected_keys(FINAL_GB):
        directory = runs.get(key)
        row = base_row("final_performance", directory, key)
        missing = []
        if not directory:
            missing.append("run_directory")
            rows.append(row | {"missing_required_files": ";".join(missing)})
            continue
        snapshot = directory / "interference_aware_handover_v2_snapshot.csv"
        events = directory / "interference_aware_handover_v2_events.csv"
        for path in (snapshot, events):
            if not path.is_file():
                missing.append(path.name)
        snapshot_rows = count_rows(snapshot)
        scols, ecols = columns(snapshot), columns(events)
        row.update({
            "status": "COMPLETE" if snapshot_rows == EXPECTED_SNAPSHOTS and not missing else "INCOMPLETE",
            "number_of_snapshots": snapshot_rows,
            "number_of_critical_before": count_truthy(snapshot, "critical_before"),
            "number_of_critical_after": count_truthy(snapshot, "critical_after"),
            "number_of_handovers": sum_integer(snapshot, "reassigned_beams"),
            "snapshot_columns": ";".join(scols),
            "event_columns": ";".join(ecols),
            "missing_required_files": ";".join(missing),
        })
        rows.append(row)
    return rows


def audit_operational() -> list[dict[str, object]]:
    runs = indexed_directories(OPERATIONAL_CAMPAIGN / "output", OPERATIONAL_PATTERN)
    rows = []
    for key in expected_keys(OPERATIONAL_GB):
        directory = runs.get(key)
        row = base_row("operational_geometry", directory, key)
        missing = []
        if not directory:
            missing.append("run_directory")
            rows.append(row | {"missing_required_files": ";".join(missing)})
            continue
        snapshot = directory / "operational_risk_snapshot.csv"
        topk = directory / "operational_risk_topk.csv"
        events = directory / "operational_risk_handover_events.csv"
        for path in (snapshot, topk, events):
            if not path.is_file():
                missing.append(path.name)
        snapshot_rows, topk_rows = count_rows(snapshot), count_rows(topk)
        scols, tcols, ecols = columns(snapshot), columns(topk), columns(events)
        geometry = sorted(GEOMETRY_WANTED.intersection(set(scols + tcols + ecols)))
        pointing_fields = {
            "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
            "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
        }
        row.update({
            "status": "COMPLETE" if (
                snapshot_rows == EXPECTED_SNAPSHOTS
                and topk_rows == EXPECTED_SNAPSHOTS * EXPECTED_TOP_K
                and not missing
            ) else "INCOMPLETE",
            "number_of_snapshots": snapshot_rows,
            "number_of_topk_rows": topk_rows,
            "number_of_critical_before": count_truthy(snapshot, "critical_before_flag"),
            "number_of_critical_after": snapshot_rows - count_truthy(snapshot, "compliant_after_flag"),
            "number_of_handovers": sum_integer(snapshot, "handover_count"),
            "available_geometry_columns": ";".join(geometry) if geometry else "NONE",
            "snapshot_columns": ";".join(scols),
            "topk_columns": ";".join(tcols),
            "event_columns": ";".join(ecols),
            "realized_eess_pointing_recorded": pointing_fields.issubset(scols),
            "missing_required_files": ";".join(missing),
        })
        rows.append(row)
    return rows


def main() -> int:
    rows = audit_final() + audit_operational()
    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    final_rows = [row for row in rows if row["campaign_role"] == "final_performance"]
    operational_rows = [row for row in rows if row["campaign_role"] == "operational_geometry"]
    final_complete = sum(row["status"] == "COMPLETE" for row in final_rows)
    operational_complete = sum(row["status"] == "COMPLETE" for row in operational_rows)
    incomplete = [row for row in operational_rows if row["status"] != "COMPLETE"]
    pointing_types = sorted({
        (row["eess_azimuth_type"], row["eess_elevation_type"])
        for row in rows if row["eess_azimuth_type"] != "MISSING"
    })
    lines = [
        f"final_performance_complete={final_complete}/{len(final_rows)}",
        f"operational_geometry_complete={operational_complete}/{len(operational_rows)}",
        f"pointing_types={pointing_types}",
        "pointing_interpretation=realized per snapshot; not fixed across snapshots",
        "incomplete_operational_runs:",
        *[
            f"- {row['scenario']} ({row['number_of_snapshots']} snapshots; "
            f"{row['missing_required_files'] or 'row-count mismatch'})"
            for row in incomplete
        ],
    ]
    AUDIT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"audit_csv={AUDIT_CSV}")
    print(f"audit_summary={AUDIT_SUMMARY}")
    return 0 if final_complete == 56 and operational_complete == 48 else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare the original and corrected-beam-radius bootstrap summaries.

The old summary is read from Git so the canonical CSV can be replaced by the
new campaign result without losing the comparison baseline.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
CAMPAIGN_DIR = Path(__file__).resolve().parents[1]
OLD_GIT_PATH = (
    "sharc/campaigns/02_DC_MSS_to_FS 2/plots/bootstrap_inr20/"
    "bootstrap_inr20_all_scenarios.csv"
)
NEW_CSV = CAMPAIGN_DIR / "plots" / "bootstrap_inr20" / "bootstrap_inr20_all_scenarios.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "figuras" / "beam_radius_comparison"
OLD_SNAPSHOT_NAME = "bootstrap_inr20_old_snapshot.csv"
NON_COMPLIANT_LABEL = ">100 km / non-compliant within evaluated range"

KEY_FIELDS = (
    "mechanism",
    "altitude_km",
    "load_factor_pct",
    "fs_height_m",
    "distance_km",
)

NUMERIC_FIELDS = (
    "inr_20_pct_db",
    "inr_20_pct_ci95_low_db",
    "inr_20_pct_ci95_high_db",
    "inr_20_pct_ci95_half_width_db",
    "protection_margin_db",
    "protection_margin_ci95_low_db",
    "protection_margin_ci95_high_db",
)


def read_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def read_csv_path(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_git_csv(revision: str, git_path: str) -> tuple[str, list[dict[str, str]]]:
    result = subprocess.run(
        ["git", "show", f"{revision}:{git_path}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout, read_csv_text(result.stdout)


def row_key(row: dict[str, str]) -> tuple[object, ...]:
    return (
        row["mechanism"],
        int(row["altitude_km"]),
        int(row["load_factor_pct"]),
        int(row["fs_height_m"]),
        int(row["distance_km"]),
    )


def technique_label(mechanism: str) -> str:
    return "Exclusion zone" if mechanism == "exclusion zone" else "Power back-off"


def classification_label(value: str) -> str:
    return {
        "supported compliant": "compliant",
        "supported non-compliant": "non-compliant",
        "borderline": "borderline",
    }[value]


def display_distance(value: int | None) -> str:
    return NON_COMPLIANT_LABEL if value is None else f"{value} km"


def first_supported(rows: list[dict[str, str]]) -> dict[tuple[object, ...], int | None]:
    grouped: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["mechanism"],
            int(row["altitude_km"]),
            int(row["load_factor_pct"]),
            int(row["fs_height_m"]),
        )
        grouped[key].append(row)

    result: dict[tuple[object, ...], int | None] = {}
    for key, group in grouped.items():
        distances = [
            int(row["distance_km"])
            for row in group
            if row["classification"] == "supported compliant"
        ]
        result[key] = min(distances) if distances else None
    return result


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    return f"{value:.3f}"


def scenario_text(row: dict[str, object]) -> str:
    return (
        f"{row['Technique']}, {row['Altitude']} km, LF {row['LF']}%, "
        f"FS {row['FS height']} m, {row['Distance']} km"
    )


def markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-revision", default="HEAD")
    parser.add_argument("--old-git-path", default=OLD_GIT_PATH)
    parser.add_argument("--old-csv", type=Path)
    parser.add_argument("--new-csv", type=Path, default=NEW_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    old_snapshot_path = args.output_dir / OLD_SNAPSHOT_NAME
    if args.old_csv is not None:
        old_source_path = args.old_csv.resolve()
        old_text = old_source_path.read_text(encoding="utf-8-sig")
        old_rows = read_csv_text(old_text)
        old_source = str(old_source_path)
    elif old_snapshot_path.exists():
        old_text = old_snapshot_path.read_text(encoding="utf-8-sig")
        old_rows = read_csv_text(old_text)
        old_source = str(old_snapshot_path.resolve())
    else:
        old_text, old_rows = read_git_csv(args.old_revision, args.old_git_path)
        old_source = f"Git {args.old_revision}:{args.old_git_path}"
    new_rows = read_csv_path(args.new_csv.resolve())
    old_by_key = {row_key(row): row for row in old_rows}
    new_by_key = {row_key(row): row for row in new_rows}
    if old_by_key.keys() != new_by_key.keys():
        missing_new = sorted(old_by_key.keys() - new_by_key.keys())
        missing_old = sorted(new_by_key.keys() - old_by_key.keys())
        raise ValueError(f"scenario mismatch: missing NEW={missing_new}, missing OLD={missing_old}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    old_snapshot_path.write_text(old_text, encoding="utf-8")

    comparison_rows: list[dict[str, object]] = []
    for key in sorted(old_by_key, key=lambda item: (item[0], item[1], item[2], item[3], item[4])):
        old = old_by_key[key]
        new = new_by_key[key]
        mechanism, altitude, load_factor, fs_height, distance = key
        comparison: dict[str, object] = {
            "Technique": technique_label(str(mechanism)),
            "Altitude": altitude,
            "LF": load_factor,
            "FS height": fs_height,
            "Distance": distance,
            "Old samples": int(old["samples"]),
            "New samples": int(new["samples"]),
        }
        for field in NUMERIC_FIELDS:
            label = {
                "inr_20_pct_db": "INR_20",
                "inr_20_pct_ci95_low_db": "INR_20 CI low",
                "inr_20_pct_ci95_high_db": "INR_20 CI high",
                "inr_20_pct_ci95_half_width_db": "INR_20 CI half-width",
                "protection_margin_db": "M_20",
                "protection_margin_ci95_low_db": "M_20 CI low",
                "protection_margin_ci95_high_db": "M_20 CI high",
            }[field]
            old_value = float(old[field])
            new_value = float(new[field])
            comparison[f"Old {label} (dB)"] = f"{old_value:.6f}"
            comparison[f"New {label} (dB)"] = f"{new_value:.6f}"
            comparison[f"Delta {label} (dB)"] = f"{new_value - old_value:.6f}"
        old_class = classification_label(old["classification"])
        new_class = classification_label(new["classification"])
        comparison["Old classification"] = old_class
        comparison["New classification"] = new_class
        comparison["Classification changed?"] = "Yes" if old_class != new_class else "No"
        comparison_rows.append(comparison)

    all_fields = list(comparison_rows[0].keys())
    write_csv(args.output_dir / "beam_radius_old_vs_new_all_points.csv", comparison_rows, all_fields)

    changed_rows = [row for row in comparison_rows if row["Classification changed?"] == "Yes"]
    write_csv(args.output_dir / "beam_radius_classification_changes.csv", changed_rows, all_fields)

    old_first = first_supported(old_rows)
    new_first = first_supported(new_rows)
    distance_rows: list[dict[str, object]] = []
    for key in sorted(old_first, key=lambda item: (item[0], item[1], item[2], item[3])):
        mechanism, altitude, load_factor, fs_height = key
        old_distance = old_first[key]
        new_distance = new_first[key]
        distance_rows.append(
            {
                "Technique": technique_label(str(mechanism)),
                "Altitude": altitude,
                "LF": load_factor,
                "FS height": fs_height,
                "Old supported distance": display_distance(old_distance),
                "New supported distance": display_distance(new_distance),
                "Changed?": "Yes" if old_distance != new_distance else "No",
            }
        )
    distance_fields = list(distance_rows[0].keys())
    write_csv(args.output_dir / "beam_radius_supported_distances.csv", distance_rows, distance_fields)

    old_counts = Counter(classification_label(row["classification"]) for row in old_rows)
    new_counts = Counter(classification_label(row["classification"]) for row in new_rows)
    transitions = Counter(
        (row["Old classification"], row["New classification"])
        for row in comparison_rows
        if row["Classification changed?"] == "Yes"
    )

    margin_deltas = [float(row["Delta M_20 (dB)"]) for row in comparison_rows]
    old_half_widths = [float(row["Old INR_20 CI half-width (dB)"]) for row in comparison_rows]
    new_half_widths = [float(row["New INR_20 CI half-width (dB)"]) for row in comparison_rows]
    largest = sorted(comparison_rows, key=lambda row: abs(float(row["Delta M_20 (dB)"])), reverse=True)[:15]
    near_zero = [
        row for row in comparison_rows
        if min(abs(float(row["Old M_20 (dB)"])), abs(float(row["New M_20 (dB)"]))) <= 0.25
    ]
    entered_borderline = [
        row for row in comparison_rows
        if row["Old classification"] != "borderline" and row["New classification"] == "borderline"
    ]
    left_borderline = [
        row for row in comparison_rows
        if row["Old classification"] == "borderline" and row["New classification"] != "borderline"
    ]

    lines = [
        "# Beam-radius correction: OLD vs NEW",
        "",
        "## Provenance and method",
        "",
        f"- OLD source: `{old_source}`.",
        f"- NEW source: `{args.new_csv.resolve()}`.",
        "- Both summaries use the existing empirical 80th percentile, percentile bootstrap with B=10,000, bootstrap seed 20260727, and the existing CI-based classification rule.",
        f"- OLD has {int(old_rows[0]['samples']):,} snapshot-level samples per scenario; NEW has {int(new_rows[0]['samples']):,}. Consequently, this is a campaign-to-campaign comparison and does not isolate beam radius from the increased Monte Carlo sample count.",
        "",
        "## Classification totals",
        "",
    ]
    lines.extend(markdown_table(
        ["Classification", "OLD", "NEW", "Delta"],
        [[name, old_counts[name], new_counts[name], new_counts[name] - old_counts[name]] for name in ("compliant", "borderline", "non-compliant")],
    ))
    lines.extend(["", f"Changed classifications: **{len(changed_rows)} of {len(comparison_rows)} points**.", "", "## Classification transitions", ""])
    lines.extend(markdown_table(
        ["OLD", "NEW", "Points"],
        [[old, new, count] for (old, new), count in sorted(transitions.items())],
    ))
    lines.extend(["", "## First CI-supported compliant distance", ""])
    lines.extend(markdown_table(
        distance_fields,
        [[row[field] for field in distance_fields] for row in distance_rows],
    ))
    lines.extend([
        "",
        "## Margin changes",
        "",
        f"- Mean NEW-OLD M_20: {statistics.fmean(margin_deltas):.3f} dB.",
        f"- Median NEW-OLD M_20: {statistics.median(margin_deltas):.3f} dB.",
        f"- Range of NEW-OLD M_20: {min(margin_deltas):.3f} to {max(margin_deltas):.3f} dB.",
        f"- Mean INR_20 CI half-width: OLD {statistics.fmean(old_half_widths):.3f} dB; NEW {statistics.fmean(new_half_widths):.3f} dB.",
        "",
        "### Largest absolute M_20 differences",
        "",
    ])
    lines.extend(markdown_table(
        ["Scenario", "OLD M_20", "NEW M_20", "Delta"],
        [[scenario_text(row), fmt(float(row["Old M_20 (dB)"])), fmt(float(row["New M_20 (dB)"])), fmt(float(row["Delta M_20 (dB)"]))] for row in largest],
    ))
    lines.extend(["", "### Points near zero in OLD or NEW (|M_20| <= 0.25 dB)", ""])
    lines.extend(markdown_table(
        ["Scenario", "OLD M_20", "OLD class", "NEW M_20", "NEW class", "NEW CI"],
        [[scenario_text(row), fmt(float(row["Old M_20 (dB)"])), row["Old classification"], fmt(float(row["New M_20 (dB)"])), row["New classification"], f"[{fmt(float(row['New M_20 CI low (dB)']))}, {fmt(float(row['New M_20 CI high (dB)']))}]"] for row in near_zero],
    ))
    lines.extend(["", "## Points whose CI started or stopped crossing zero", "", "### Started crossing zero", ""])
    lines.extend([f"- {scenario_text(row)}" for row in entered_borderline] or ["- None."])
    lines.extend(["", "### Stopped crossing zero", ""])
    lines.extend([f"- {scenario_text(row)}: {row['New classification']}" for row in left_borderline] or ["- None."])
    lines.extend(["", "## All changed classifications", ""])
    lines.extend(markdown_table(
        ["Scenario", "OLD M_20", "OLD class", "NEW M_20", "NEW class"],
        [[scenario_text(row), fmt(float(row["Old M_20 (dB)"])), row["Old classification"], fmt(float(row["New M_20 (dB)"])), row["New classification"]] for row in changed_rows],
    ))

    report_path = args.output_dir / "beam_radius_comparison_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OLD rows: {len(old_rows)}; NEW rows: {len(new_rows)}")
    print(f"Changed classifications: {len(changed_rows)}")
    print(f"Wrote: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate IEEE-ready protection-margin figures with bootstrap CIs."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[4]
CAMPAIGN_DIR = Path(__file__).resolve().parents[1]
FIG_DIR = REPO_ROOT / "figuras"
PROTECTION_LIMIT_MARGIN_DB = 0.0

EXPECTED_FIRST_COMPLIANT = {
    "exclusion zone": {
        (340, 20, 20): 90,
        (340, 20, 40): 90,
        (340, 50, 20): None,
        (340, 50, 40): None,
        (525, 20, 20): 50,
        (525, 20, 40): 50,
        (525, 50, 20): 100,
        (525, 50, 40): 100,
    },
    "power back-off": {
        (340, 20, 20): 20,
        (340, 20, 40): 10,
        (340, 50, 20): None,
        (340, 50, 40): None,
        (525, 20, 20): 0,
        (525, 20, 40): 0,
        (525, 50, 20): 70,
        (525, 50, 40): 60,
    },
}

MECHANISM_CONFIG = {
    "exclusion zone": {
        "area": "SouthAmerica",
        "distance_type": "EZ",
        "filename": "margem_zona_exclusao_bootstrap_final",
        "csv": "margem_zona_exclusao_bootstrap_final.csv",
        "xlabel": r"Exclusion-zone radius, $R_{\mathrm{ez}}$ (km)",
    },
    "power back-off": {
        "area": "BR_AR_Paraguay",
        "distance_type": "M",
        "filename": "margem_power_backoff_bootstrap_final",
        "csv": "margem_power_backoff_bootstrap_final.csv",
        "xlabel": r"Border-strip width, $D_{\mathrm{border}}$ (km)",
    },
}

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 15,
        "axes.titlesize": 19,
        "axes.labelsize": 17,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 13,
        "axes.linewidth": 1.0,
        "lines.linewidth": 2.2,
        "savefig.dpi": 600,
    }
)


def read_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    converted: list[dict[str, object]] = []
    for row in rows:
        converted.append(
            {
                **row,
                "altitude_km": int(row["altitude_km"]),
                "fs_height_m": int(row["fs_height_m"]),
                "load_factor_pct": int(row["load_factor_pct"]),
                "distance_km": int(row["distance_km"]),
                "inr_20_pct_db": float(row["inr_20_pct_db"]),
                "inr_20_pct_ci95_low_db": float(row["inr_20_pct_ci95_low_db"]),
                "inr_20_pct_ci95_high_db": float(row["inr_20_pct_ci95_high_db"]),
                "protection_margin_db": float(row["protection_margin_db"]),
                "protection_margin_ci95_low_db": float(row["protection_margin_ci95_low_db"]),
                "protection_margin_ci95_high_db": float(row["protection_margin_ci95_high_db"]),
            }
        )
    return converted


def export_mechanism_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "mechanism",
        "altitude",
        "LF",
        "FS height",
        "distance",
        "INR20 point estimate",
        "INR20 CI lower",
        "INR20 CI upper",
        "margin point estimate",
        "margin CI lower",
        "margin CI upper",
        "classification",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "mechanism": row["mechanism"],
                    "altitude": row["altitude_km"],
                    "LF": row["load_factor_pct"],
                    "FS height": row["fs_height_m"],
                    "distance": row["distance_km"],
                    "INR20 point estimate": f"{row['inr_20_pct_db']:.6f}",
                    "INR20 CI lower": f"{row['inr_20_pct_ci95_low_db']:.6f}",
                    "INR20 CI upper": f"{row['inr_20_pct_ci95_high_db']:.6f}",
                    "margin point estimate": f"{row['protection_margin_db']:.6f}",
                    "margin CI lower": f"{row['protection_margin_ci95_low_db']:.6f}",
                    "margin CI upper": f"{row['protection_margin_ci95_high_db']:.6f}",
                    "classification": row["classification"],
                }
            )


def first_supported_compliant(rows: list[dict[str, object]]) -> dict[tuple[int, int, int], int | None]:
    result: dict[tuple[int, int, int], int | None] = {}
    grouped: dict[tuple[int, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (row["altitude_km"], row["load_factor_pct"], row["fs_height_m"])
        grouped[key].append(row)
    for key, group in grouped.items():
        compliant = sorted(
            (row for row in group if row["classification"] == "supported compliant"),
            key=lambda row: row["distance_km"],
        )
        result[key] = compliant[0]["distance_km"] if compliant else None
    return result


def plot_mechanism(rows: list[dict[str, object]], mechanism: str, out_base: Path, xlabel: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), dpi=600, sharey=True, constrained_layout=True)
    style = {
        20: {"color": "#0072B2", "marker": "o", "linestyle": "-", "label": "FS 20 m"},
        40: {"color": "#D55E00", "marker": "s", "linestyle": "--", "label": "FS 40 m"},
    }
    for ax, altitude in zip(axes, (340, 525)):
        ax.axhline(PROTECTION_LIMIT_MARGIN_DB, color="0.0", linestyle=":", linewidth=1.4, label=r"$M_{20}=0$ dB")
        for load_factor in (20, 50):
            for fs_height in (20, 40):
                group = sorted(
                    [
                        row for row in rows
                        if row["altitude_km"] == altitude
                        and row["load_factor_pct"] == load_factor
                        and row["fs_height_m"] == fs_height
                    ],
                    key=lambda row: row["distance_km"],
                )
                if not group:
                    continue
                x = np.asarray([row["distance_km"] for row in group], dtype=float)
                y = np.asarray([row["protection_margin_db"] for row in group], dtype=float)
                yerr_low = y - np.asarray([row["protection_margin_ci95_low_db"] for row in group], dtype=float)
                yerr_high = np.asarray([row["protection_margin_ci95_high_db"] for row in group], dtype=float) - y
                st = style[fs_height]
                alpha = 1.0 if load_factor == 20 else 0.86
                ax.errorbar(
                    x,
                    y,
                    yerr=np.vstack([yerr_low, yerr_high]),
                    color=st["color"],
                    linestyle=st["linestyle"] if load_factor == 20 else (0, (4, 2)),
                    marker=st["marker"],
                    markersize=6.5,
                    linewidth=2.15,
                    elinewidth=1.55,
                    capsize=4,
                    capthick=1.55,
                    alpha=alpha,
                    label=f"{st['label']}, LF {load_factor}%",
                )
        ax.set_title(f"System 3 -- {altitude} km")
        ax.set_xlabel(xlabel)
        ax.grid(True, which="major", linewidth=0.65, alpha=0.35)
        ax.tick_params(width=1.0, length=3.4)
    axes[0].set_ylabel(r"Protection margin, $M_{20}$ (dB)")
    handles, labels = axes[1].get_legend_handles_labels()
    seen: dict[str, object] = {}
    for handle, label in zip(handles, labels):
        seen.setdefault(label, handle)
    ordered = [r"$M_{20}=0$ dB", "FS 20 m, LF 20%", "FS 40 m, LF 20%", "FS 20 m, LF 50%", "FS 40 m, LF 50%"]
    axes[1].legend(
        [seen[label] for label in ordered if label in seen],
        [label for label in ordered if label in seen],
        loc="best",
        frameon=True,
        fancybox=False,
        framealpha=0.92,
        borderpad=0.35,
        labelspacing=0.28,
        handlelength=2.3,
    )
    fig.savefig(out_base.with_suffix(".png"), bbox_inches="tight", pad_inches=0.02, dpi=600)
    fig.savefig(out_base.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def print_summary(mechanism: str, rows: list[dict[str, object]]) -> list[str]:
    counts = Counter(row["classification"] for row in rows)
    first = first_supported_compliant(rows)
    messages = [
        f"{mechanism}: total points = {len(rows)}",
        f"{mechanism}: supported compliant = {counts['supported compliant']}",
        f"{mechanism}: borderline = {counts['borderline']}",
        f"{mechanism}: supported non-compliant = {counts['supported non-compliant']}",
    ]
    for key in sorted(first):
        messages.append(f"{mechanism}: first supported compliant {key} = {first[key]}")
    expected = EXPECTED_FIRST_COMPLIANT[mechanism]
    for key, expected_value in expected.items():
        observed = first.get(key)
        if observed != expected_value:
            messages.append(
                f"WARNING: {mechanism} first supported compliant changed for "
                f"(altitude, LF, FS height)={key}: expected {expected_value}, observed {observed}"
            )
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bootstrap-csv",
        type=Path,
        default=CAMPAIGN_DIR / "plots" / "bootstrap_inr20" / "bootstrap_inr20_all_scenarios.csv",
    )
    args = parser.parse_args()

    all_rows = read_rows(args.bootstrap_csv)
    report_lines: list[str] = []
    for mechanism, cfg in MECHANISM_CONFIG.items():
        rows = [
            row for row in all_rows
            if row["area"] == cfg["area"]
            and row["distance_type"] == cfg["distance_type"]
            and row["azimuth_deg"] == "90"
        ]
        out_base = FIG_DIR / cfg["filename"]
        export_mechanism_csv(rows, FIG_DIR / cfg["csv"])
        plot_mechanism(rows, mechanism, out_base, cfg["xlabel"])
        report_lines.extend(print_summary(mechanism, rows))
    for line in report_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

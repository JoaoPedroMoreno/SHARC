"""Shared provenance and IEEE plotting helpers for the final figure set."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[2]
FIGURES = CAMPAIGN / "figures"
DATA = FIGURES / "data"
FINAL = FIGURES / "final"
DIAGNOSTICS = FIGURES / "diagnostics"
REPO = CAMPAIGN.parents[2]
OPERATIONAL_CAMPAIGN = CAMPAIGN.parent / "06_DC_MSS_to_EESS_operational_risk_diagnostics"
SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
if SITE_PACKAGES.is_dir() and str(SITE_PACKAGES) not in sys.path:
    sys.path.append(str(SITE_PACKAGES))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FINAL_PATTERN = re.compile(
    r"^system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(5|10|60|65|70|75|80)MHz_STRATEGY_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)
OP_PATTERN = re.compile(
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(10|60|65|70|75|80)MHz_V2_RISK_GATE_"
    r"(\d{4}-\d{2}-\d{2})_(\d+)$"
)

BLUE = "#0072B2"
VERMILLION = "#D55E00"
GREEN = "#009E73"
ORANGE = "#E69F00"
SKY = "#56B4E9"
PURPLE = "#CC79A7"
DARK = "#333333"
GRAY = "#7F7F7F"
LIGHT = "#D9D9D9"

SCENARIOS = [
    (340, "B", 0.2), (340, "B", 0.5),
    (340, "D", 0.2), (340, "D", 0.5),
    (525, "B", 0.2), (525, "B", 0.5),
    (525, "D", 0.2), (525, "D", 0.5),
]
SCENARIO_LABELS = [f"{a}-{e}-{lf:.1f}" for a, e, lf in SCENARIOS]


def setup_ieee() -> None:
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8.0,
        "axes.labelsize": 8.3,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "legend.fontsize": 7.2,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.2,
        "lines.markersize": 4.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def prepare_dirs() -> None:
    for directory in (DATA, FINAL, DIAGNOSTICS):
        directory.mkdir(parents=True, exist_ok=True)


def count_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("rb") as stream:
        return max(sum(1 for _ in stream) - 1, 0)


def _latest_complete(output: Path, pattern: re.Pattern[str], required: dict[str, int]):
    selected = {}
    for directory in output.iterdir():
        match = pattern.fullmatch(directory.name) if directory.is_dir() else None
        if not match:
            continue
        key = (int(match[1]), match[2], float(match[3]), int(match[4]))
        if any(count_rows(directory / name) != rows for name, rows in required.items()):
            continue
        stamp = (match[5], int(match[6]))
        if key not in selected or stamp > selected[key][0]:
            selected[key] = (stamp, directory)
    return {key: value[1] for key, value in selected.items()}


def final_runs() -> dict[tuple[int, str, float, int], Path]:
    runs = _latest_complete(
        CAMPAIGN / "output", FINAL_PATTERN,
        {"interference_aware_handover_v2_snapshot.csv": 5000},
    )
    if len(runs) != 56:
        raise RuntimeError(f"Expected 56 final runs, found {len(runs)}")
    return runs


def operational_runs() -> dict[tuple[int, str, float, int], Path]:
    runs = _latest_complete(
        OPERATIONAL_CAMPAIGN / "output", OP_PATTERN,
        {"operational_risk_snapshot.csv": 5000,
         "operational_risk_topk.csv": 15000},
    )
    if len(runs) != 48:
        raise RuntimeError(f"Expected 48 operational runs, found {len(runs)}")
    return runs


def scenario_label(altitude: int | float, eess: str, load: float) -> str:
    return f"{int(altitude)}-{eess.removeprefix('EESS_')}-{float(load):.1f}"


def add_scenario_columns(frame: pd.DataFrame, key: tuple[int, str, float, int]) -> pd.DataFrame:
    altitude, eess, load, gb = key
    frame = frame.copy()
    frame["altitude_km"] = altitude
    frame["eess_system"] = eess
    frame["load_factor"] = load
    frame["guard_band_mhz"] = gb
    frame["scenario"] = scenario_label(altitude, eess, load)
    return frame


def save_figure(fig: mpl.figure.Figure, stem: str) -> None:
    prepare_dirs()
    fig.savefig(FINAL / f"{stem}.png", dpi=600, bbox_inches="tight")
    plt.close(fig)


def require_columns(frame: pd.DataFrame, required: list[str], source: Path) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise RuntimeError(f"Missing columns in {source}: {missing}")


def print_runs(title: str, runs: list[Path]) -> None:
    print(title)
    for run in runs:
        print(f"  {run}")


def panel_label(ax, label: str) -> None:
    draw_text = getattr(ax, "text2D", ax.text)
    draw_text(-0.10, 1.04, label, transform=ax.transAxes,
              fontsize=9, fontweight="bold", va="bottom")


def clean_axes(ax, *, grid_axis: str | None = None) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, color=LIGHT, linewidth=0.6, alpha=0.65)
        ax.set_axisbelow(True)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054):
    if total <= 0:
        return np.nan, np.nan
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - half, center + half

"""Bootstrap confidence intervals for the INR value exceeded 20% of the time.

The protection criterion used in the campaign is I/N <= -6 dB for 20% of time.
For each scenario, this script estimates:

    INR_20% = empirical 80th percentile of system_inr

and a bootstrap confidence interval for that statistic.  The bootstrap seed is
kept separate from the SHARC Monte Carlo seed.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from plot_system_inr_ccdf import FIELD, discover_scenarios, read_series_csv, scenario_sort_key
from plot_system_inr_margin_heatmap import inr_at_exceedance_probability


PROTECTION_LIMIT_DB = -6.0
EXCEEDANCE_PROBABILITY = 0.2
DEFAULT_BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 20260727


def bootstrap_inr20_ci(
    samples: np.ndarray,
    *,
    n_bootstrap: int,
    rng: np.random.Generator,
    confidence: float = 0.95,
    chunk_size: int = 250,
) -> tuple[float, float, float]:
    """Return point estimate and percentile bootstrap CI for INR_20%."""
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return math.nan, math.nan, math.nan

    point = inr_at_exceedance_probability(x, EXCEEDANCE_PROBABILITY)
    n = x.size
    quantile_index = int(math.ceil((1.0 - EXCEEDANCE_PROBABILITY) * n)) - 1
    quantile_index = max(0, min(quantile_index, n - 1))

    estimates: list[np.ndarray] = []
    remaining = n_bootstrap
    while remaining > 0:
        current = min(chunk_size, remaining)
        indices = rng.integers(0, n, size=(current, n), endpoint=False)
        resampled = x[indices]
        # Partition is much faster than fully sorting every bootstrap sample.
        kth = np.partition(resampled, quantile_index, axis=1)[:, quantile_index]
        estimates.append(kth)
        remaining -= current

    boot = np.concatenate(estimates)
    alpha = (1.0 - confidence) / 2.0
    ci_low, ci_high = np.quantile(boot, [alpha, 1.0 - alpha])
    return float(point), float(ci_low), float(ci_high)


def classify_margin(margin_ci_low: float, margin_ci_high: float) -> str:
    if margin_ci_low >= 0.0:
        return "supported compliant"
    if margin_ci_high < 0.0:
        return "supported non-compliant"
    return "borderline"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "output",
        help="Campaign output directory.",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "plots" / "bootstrap_inr20",
        help="Directory where CSV summaries will be written.",
    )
    parser.add_argument("--all-runs", action="store_true", help="Use all dated runs, not only the latest per scenario.")
    parser.add_argument("--n-bootstrap", type=int, default=DEFAULT_BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    parser.add_argument(
        "--near-margin-db",
        type=float,
        default=0.25,
        help="Also write a filtered CSV with scenarios whose absolute margin is below this value.",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    scenarios = discover_scenarios(args.output_root, all_runs=args.all_runs)
    args.plots_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for scenario in sorted(scenarios, key=scenario_sort_key):
        path = scenario.folder / f"{FIELD}.csv"
        samples = read_series_csv(path, FIELD)
        if samples is None or samples.size == 0:
            print(f"[skip] no samples: {path}")
            continue

        point, ci_low, ci_high = bootstrap_inr20_ci(
            samples,
            n_bootstrap=args.n_bootstrap,
            rng=rng,
        )
        margin = PROTECTION_LIMIT_DB - point
        margin_ci_low = PROTECTION_LIMIT_DB - ci_high
        margin_ci_high = PROTECTION_LIMIT_DB - ci_low
        rows.append(
            {
                "area": scenario.area,
                "system": scenario.system,
                "altitude_km": scenario.altitude_km,
                "fs_height_m": scenario.fs_height_m,
                "load_factor_pct": scenario.load_factor_pct,
                "mechanism": "exclusion zone" if scenario.distance_type == "EZ" else "power back-off",
                "distance_type": scenario.distance_type,
                "distance_km": scenario.margin_km,
                "azimuth_deg": scenario.azimuth_deg,
                "samples": int(samples.size),
                "bootstrap_resamples": args.n_bootstrap,
                "bootstrap_seed": args.seed,
                "inr_20_pct_db": f"{point:.6f}",
                "inr_20_pct_ci95_low_db": f"{ci_low:.6f}",
                "inr_20_pct_ci95_high_db": f"{ci_high:.6f}",
                "inr_20_pct_ci95_half_width_db": f"{0.5 * (ci_high - ci_low):.6f}",
                "protection_margin_db": f"{margin:.6f}",
                "protection_margin_ci95_low_db": f"{margin_ci_low:.6f}",
                "protection_margin_ci95_high_db": f"{margin_ci_high:.6f}",
                "classification": classify_margin(margin_ci_low, margin_ci_high),
            }
        )

    fieldnames = list(rows[0].keys()) if rows else []
    all_path = args.plots_dir / "bootstrap_inr20_all_scenarios.csv"
    with all_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    near_rows = [
        row for row in rows
        if abs(float(row["protection_margin_db"])) <= args.near_margin_db
        or row["classification"] == "borderline"
    ]
    near_path = args.plots_dir / "bootstrap_inr20_near_limit.csv"
    with near_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(near_rows)

    print(f"Wrote {len(rows)} rows: {all_path}")
    print(f"Wrote {len(near_rows)} near-limit rows: {near_path}")


if __name__ == "__main__":
    main()

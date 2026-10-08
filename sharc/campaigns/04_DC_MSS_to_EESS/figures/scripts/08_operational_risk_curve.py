"""Figure 8: scenario-balanced empirical risk versus observable geometry."""
from __future__ import annotations

from _common import (
    DARK, DATA, LIGHT, VERMILLION, prepare_dirs, save_figure, setup_ieee,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_feature_module():
    path = Path(__file__).with_name("07_risk_features.py")
    spec = spec_from_file_location("risk_features", path)
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module


def choose_operational_feature(stats: pd.DataFrame) -> str:
    pooled = stats[stats.scope == "POOLED"].copy()
    pooled["score"] = pooled.median_scenario_oriented_auc * pooled.scenario_direction_consistency
    best = pooled.sort_values("score", ascending=False).iloc[0]
    rx = pooled[pooled.feature == "top1_rx_offaxis_deg"].iloc[0]
    # Prefer the directly observable RX angle when its discrimination is
    # practically equivalent to the best geometry-derived feature.
    return "top1_rx_offaxis_deg" if rx.score >= best.score - 0.02 else str(best.feature)


def main() -> None:
    prepare_dirs(); setup_ieee(); risk = load_feature_module()
    data, _ = risk.load_data(); stats = risk.feature_statistics(data)
    feature = choose_operational_feature(stats)
    values = data[feature].to_numpy(float)
    edges = np.unique(np.quantile(values[np.isfinite(values)], np.linspace(0, 1, 11)))
    if len(edges) < 7:
        raise RuntimeError("Insufficient unique feature values for robust quantile bins")
    data = data[np.isfinite(data[feature])].copy()
    data["bin"] = pd.cut(data[feature], bins=edges, include_lowest=True, duplicates="drop")

    rng = np.random.default_rng(157); records = []
    grouped = data.groupby("bin", observed=True, sort=True)
    for interval, group in grouped:
        scenario_rows = []
        for scenario, scenario_group in group.groupby("scenario", sort=True):
            total = len(scenario_group); critical = int(scenario_group.critical.sum())
            scenario_rows.append((scenario, total, critical, critical / total))
        risks = np.array([row[3] for row in scenario_rows])
        boot = np.empty(2000)
        for index in range(len(boot)):
            draws = [rng.binomial(total, critical / total) / total
                     for _, total, critical, _ in scenario_rows]
            boot[index] = np.mean(draws)
        records.append({
            "feature": feature,
            "bin_left": float(interval.left), "bin_right": float(interval.right),
            "feature_center": float(group[feature].median()),
            "snapshots": len(group), "critical_snapshots": int(group.critical.sum()),
            "scenario_count": len(scenario_rows),
            "balanced_risk_pct": 100 * risks.mean(),
            "ci95_low_pct": 100 * np.quantile(boot, 0.025),
            "ci95_high_pct": 100 * np.quantile(boot, 0.975),
            "scenario_q25_pct": 100 * np.quantile(risks, 0.25),
            "scenario_q75_pct": 100 * np.quantile(risks, 0.75),
        })
    result = pd.DataFrame(records).sort_values("feature_center")
    result.to_csv(DATA / "fig08_bins.csv", index=False)

    labels = risk.FEATURES
    x = result.feature_center.to_numpy()
    y = result.balanced_risk_pct.to_numpy()
    low = result.ci95_low_pct.to_numpy(); high = result.ci95_high_pct.to_numpy()
    fig, ax = plt.subplots(figsize=(3.5, 3.05))
    ax.fill_between(x, result.scenario_q25_pct, result.scenario_q75_pct,
                    color=VERMILLION, alpha=0.14, linewidth=0,
                    label="Inter-scenario IQR")
    ax.errorbar(x, y, yerr=[y - low, high - y], color=VERMILLION,
                marker="o", linestyle="-", linewidth=1.1, capsize=2,
                label="Balanced empirical risk (95% CI)")
    ax.axhline(1.0, color=DARK, linestyle=(0, (4, 3)), linewidth=0.9)
    ax.text(ax.get_xlim()[1] if ax.get_xlim()[1] else x.max(), 1.05,
            "Protection criterion: 1%", ha="right", va="bottom", fontsize=6.8)
    ax.set_xlabel(labels[feature])
    ax.set_ylabel("Empirical exceedance risk [%]")
    ax.grid(axis="y", color=LIGHT, linewidth=0.6, alpha=0.65)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    save_figure(fig, "fig08_operational_risk_curve")
    print(f"Selected operational feature: {feature}")


if __name__ == "__main__":
    main()

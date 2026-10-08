"""Figura 7: variáveis geométricas que separam snapshots seguros e críticos."""
from __future__ import annotations

from _common import (
    DATA, GRAY, LIGHT, VERMILLION, operational_runs, panel_label,
    prepare_dirs, require_columns, save_figure, scenario_label, setup_ieee,
)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import rankdata


FEATURES = {
    "top1_rx_offaxis_deg": "Ângulo off-axis de recepção da EESS, $\\psi_{RX}$ [graus]",
    "top1_joint_gain_suppression_db": "Supressão angular conjunta [dB]",
    "top1_tx_offaxis_deg": "Ângulo off-axis de transmissão, $\\psi_{TX}$ [graus]",
    "top1_eess_to_satellite_elevation_deg": "Elevação do interferente vista pela EESS [graus]",
    "top1_service_elevation_deg": "Elevação de serviço [graus]",
    "top1_path_loss_db": "Perda de percurso [dB]",
}


def auc(score: np.ndarray, critical: np.ndarray) -> float:
    valid = np.isfinite(score)
    score, critical = score[valid], critical[valid].astype(bool)
    n1, n0 = int(critical.sum()), int((~critical).sum())
    if not n1 or not n0:
        return np.nan
    ranks = rankdata(score, method="average")
    return float((ranks[critical].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def load_data() -> tuple[pd.DataFrame, list[str]]:
    runs = operational_runs(); pieces = []; used = []
    required = ["snapshot_id", "critical_before_flag", *FEATURES]
    for key, directory in sorted(runs.items()):
        altitude, eess, load, gb = key
        if gb != 10:
            continue
        source = directory / "operational_risk_snapshot.csv"
        frame = pd.read_csv(source)
        require_columns(frame, required, source)
        frame = frame[required].copy()
        frame["critical"] = frame.critical_before_flag.astype(str).str.lower() == "true"
        frame["scenario"] = scenario_label(altitude, eess, load)
        frame["source_path"] = str(directory.resolve())
        pieces.append(frame); used.append(str(directory.resolve()))
    return pd.concat(pieces, ignore_index=True), used


def feature_statistics(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in FEATURES:
        pooled_auc = auc(data[feature].to_numpy(float), data.critical.to_numpy(bool))
        scenario_aucs = []
        for scenario, group in data.groupby("scenario", sort=True):
            value = auc(group[feature].to_numpy(float), group.critical.to_numpy(bool))
            scenario_aucs.append(value)
            rows.append({
                "scope": scenario, "feature": feature,
                "auc_higher_predicts_critical": value,
                "oriented_auc": max(value, 1 - value),
                "risk_direction": "higher" if value >= 0.5 else "lower",
                "safe_median": group.loc[~group.critical, feature].median(),
                "critical_median": group.loc[group.critical, feature].median(),
                "safe_n": int((~group.critical).sum()),
                "critical_n": int(group.critical.sum()),
            })
        directions = np.asarray(scenario_aucs) >= 0.5
        majority_fraction = max(directions.mean(), 1 - directions.mean())
        rows.append({
            "scope": "POOLED", "feature": feature,
            "auc_higher_predicts_critical": pooled_auc,
            "oriented_auc": max(pooled_auc, 1 - pooled_auc),
            "risk_direction": "higher" if pooled_auc >= 0.5 else "lower",
            "safe_median": data.loc[~data.critical, feature].median(),
            "critical_median": data.loc[data.critical, feature].median(),
            "safe_n": int((~data.critical).sum()),
            "critical_n": int(data.critical.sum()),
            "scenario_direction_consistency": majority_fraction,
            "median_scenario_oriented_auc": float(np.nanmedian(
                np.maximum(scenario_aucs, 1 - np.asarray(scenario_aucs)))),
        })
    return pd.DataFrame(rows)


def choose_features(stats: pd.DataFrame) -> list[str]:
    pooled = stats[stats.scope == "POOLED"].copy()
    pooled["selection_score"] = (
        pooled.median_scenario_oriented_auc
        * pooled.scenario_direction_consistency)
    stable = pooled[pooled.scenario_direction_consistency >= 0.75]
    if len(stable) < 2:
        raise RuntimeError("No two geometry features have stable direction across scenarios")
    return stable.sort_values("selection_score", ascending=False).feature.head(2).tolist()


def main() -> None:
    prepare_dirs(); setup_ieee(); data, used = load_data()
    stats = feature_statistics(data); chosen = choose_features(stats)
    stats["selected_for_figure"] = stats.feature.isin(chosen)
    stats.to_csv(DATA / "fig07_feature_stats.csv", index=False)
    data[["snapshot_id", "scenario", "critical", *chosen, "source_path"]].to_csv(
        DATA / "fig07_data.csv", index=False)
    print("Runs used:"); [print(f"  {path}") for path in used]
    print("Selected features:", chosen)

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.15))
    rng = np.random.default_rng(157)
    for panel, (ax, feature) in enumerate(zip(axes, chosen)):
        safe = data.loc[~data.critical, feature].dropna().to_numpy()
        critical = data.loc[data.critical, feature].dropna().to_numpy()
        vp = ax.violinplot([safe, critical], positions=[0, 1], widths=0.72,
                           showmeans=False, showmedians=False, showextrema=False)
        for body, color in zip(vp["bodies"], [GRAY, VERMILLION]):
            body.set_facecolor(color); body.set_edgecolor(color); body.set_alpha(0.25)
        bp = ax.boxplot([safe, critical], positions=[0, 1], widths=0.28,
                        patch_artist=True, showfliers=False,
                        medianprops={"color": "#333333", "linewidth": 1.0},
                        boxprops={"linewidth": 0.8},
                        whiskerprops={"linewidth": 0.8}, capprops={"linewidth": 0.8})
        for patch, color in zip(bp["boxes"], [GRAY, VERMILLION]):
            patch.set_facecolor(color); patch.set_alpha(0.55)
        for x, values, color in ((0, safe, GRAY), (1, critical, VERMILLION)):
            sample = rng.choice(values, size=min(180, len(values)), replace=False)
            jitter = rng.uniform(-0.11, 0.11, len(sample))
            ax.scatter(x + jitter, sample, s=4, color=color, alpha=0.28,
                       linewidths=0, rasterized=True)
        pooled = stats[(stats.scope == "POOLED") & (stats.feature == feature)].iloc[0]
        auc_text = f"{pooled.oriented_auc:.3f}".replace(".", ",")
        ax.text(0.98, 0.98,
                f"AUC = {auc_text}\n"
                "valores menores indicam maior risco",
                transform=ax.transAxes, ha="right", va="top", fontsize=7.0)
        ax.set_xticks([0, 1], ["Seguros", "Críticos"])
        ax.set_ylabel(FEATURES[feature])
        ax.grid(axis="y", color=LIGHT, linewidth=0.6, alpha=0.65)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        panel_label(ax, f"({chr(97 + panel)})")
    fig.subplots_adjust(wspace=0.28)
    save_figure(fig, "fig07_risk_features")


if __name__ == "__main__":
    main()

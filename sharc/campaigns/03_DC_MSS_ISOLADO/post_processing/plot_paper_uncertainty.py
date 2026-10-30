"""Render the paper's nominal binomial approximation without rerunning SHARC."""

from pathlib import Path

import numpy as np
import pandas as pd

from analyze_results import configure_matplotlib, plot_system_performance


STEM = "fig_system_performance_outage_se_p5_binomial_outage"


def paper_outage_intervals(values: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    """Use snapshot count as reference n, not as validated Bernoulli trials."""
    counts = metrics.loc[
        (metrics["group"] == "all") & (metrics["affected_fraction"] == 0)
        | (metrics["group"] == "all") & (metrics["pbo_db"] > 0),
        ["scenario_id", "n_snapshots"],
    ]
    result = values.merge(counts, on="scenario_id", how="left", validate="one_to_one")
    p = result["outage_probability_m6"].to_numpy(float)
    n = result["n_snapshots"].to_numpy(float)
    if not (np.all(np.isfinite(p)) and np.all((p >= 0) & (p <= 1))):
        raise ValueError("Outage probabilities must be finite and within [0, 1]")
    if not (np.all(np.isfinite(n)) and np.all(n > 0) and np.all(n == np.floor(n))):
        raise ValueError("Every scenario needs a positive integer snapshot count")
    error = np.sqrt(p * (1 - p) / n)
    result["outage_binomial_reference_se"] = error
    result["outage_binomial_lower_unclipped"] = p - 1.96 * error
    result["outage_binomial_upper_unclipped"] = p + 1.96 * error
    for side in ("lower", "upper"):
        column = f"outage_m6_ci95_{side}"
        result[f"outage_m6_bootstrap_ci95_{side}"] = result[column]
        result[column] = result[f"outage_binomial_{side}_unclipped"].clip(0, 1)
    result["outage_interval_method"] = "nominal_wald_snapshot_reference_approximation"
    result["retention_interval_method"] = "paired_snapshot_percentile_bootstrap"
    return result


def main() -> None:
    root = Path(__file__).resolve().parent / "generated"
    values = pd.read_csv(root / "data/system_performance_figure_values.csv")
    metrics = pd.read_csv(root / "data/scenario_metrics.csv")
    result = paper_outage_intervals(values, metrics)
    if len(result) != 26 or result["is_baseline"].sum() != 2:
        raise ValueError("Expected 24 PBO scenarios and two baselines")
    if not result["n_snapshots"].eq(1000).all():
        raise ValueError("This paper version requires 1000 snapshots per scenario")
    configure_matplotlib()
    plot_system_performance(
        result, root / "figures", filename=STEM,
        show_retention_uncertainty=False,
        method_note=(
            "Outage: IC95% nominal, aproximação binomial (n = 1000 snapshots).\n"
            "Retenção: estimativas pontuais, sem barras de incerteza."
        ),
    )
    result["retention_uncertainty_displayed"] = False
    result.to_csv(root / f"data/{STEM}_values.csv", index=False)
    note = """# Figura para a apresentacao: metodos de incerteza distintos

Esta variante nao substitui a analise agrupada original nem altera dados brutos.

- Outage: p e a proporcao agregada de registros com SINR < -6 dB.
- Aproximacao do artigo: p +/- 1.96 * sqrt(p * (1-p) / n), n = 1000 snapshots.
- Os limites desenhados sao restringidos a [0, 1]; limites sem truncamento e
  limites bootstrap originais tambem estao no CSV desta variante.
- O numero de snapshots e um tamanho amostral de referencia adotado no artigo,
  nao uma contagem de ensaios Bernoulli de usuarios. A cobertura de 95% desta
  aproximacao para o estimador agrupado nao foi demonstrada. Em probabilidades
  muito baixas, a aproximacao normal pode ser especialmente inadequada.
- Retencao: razao dos P5 da proxy, exibida apenas como estimativa pontual,
  sem barras de incerteza. Os IC95% de bootstrap pareado por snapshot
  (2000 reamostragens, semente 838) continuam salvos no CSV, mas nao sao
  desenhados. Nenhum bootstrap foi refeito.
- Estimativas pontuais, ICs de retencao, relatorios e tabelas da analise original
  permanecem inalterados. Os relatorios originais descrevem a versao bootstrap,
  nao esta variante. Nao inferir que os intervalos dos dois metodos sao iguais.

## Casos citados no artigo

Para PBO de 20 dB e fracao afetada de 5%, os intervalos aproximados de outage
sao [3.38%, 6.00%] em LF20 e [3.65%, 6.35%] em LF50. Ambos interceptam 5%
sob esta aproximacao. Isso nao substitui a classificacao pela analise agrupada.

## Reproducao

Executar `python sharc/campaigns/03_DC_MSS_ISOLADO/post_processing/plot_paper_uncertainty.py`.
O script le apenas dois CSVs processados e gera PNG, PDF, CSV e esta nota.
"""
    (root / "reports/paper_uncertainty_figure.md").write_text(note, encoding="utf-8")
    print(root / f"figures/{STEM}.png")


if __name__ == "__main__":
    main()

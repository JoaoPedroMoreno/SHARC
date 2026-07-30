# Pós-processamento da Campanha 03

Este diretório contém a análise reprodutível dos outputs já concluídos da
campanha `03_DC_MSS_ISOLADO`. O script não chama o simulador, não modifica os
CSVs brutos e não altera os YAMLs.

## Execução

Na raiz do repositório:

```powershell
python sharc/campaigns/03_DC_MSS_ISOLADO/post_processing/analyze_results.py `
  --campaign-dir sharc/campaigns/03_DC_MSS_ISOLADO `
  --output-dir sharc/campaigns/03_DC_MSS_ISOLADO/post_processing/generated `
  --outage-threshold -10 `
  --bootstrap-repetitions 2000 `
  --bootstrap-seed 838
```

O valor de `-10 dB` é tratado em todos os artefatos como **limiar operacional
adotado para comparação**, não como requisito normativo.

## Metodologia

- Os diretórios de output são descobertos recursivamente.
- Os parâmetros de cenário são extraídos dos YAMLs copiados para cada output.
- Quando existem execuções duplicadas, é selecionado o candidato com mais
  snapshots e registros; os demais permanecem intocados e são registrados.
- As métricas são calculadas para todos os usuários, feixes afetados e feixes
  não afetados.
- O baseline por grupo é classificado pela máscara pareada do cenário de 5 dB,
  somente após validar chaves e igualdade das máscaras entre níveis de PBO.
- Os percentis usam `numpy.quantile(..., method="linear")`.
- Os IC95% usam bootstrap percentil agrupado por snapshot. Cada snapshot
  sorteado carrega conjuntamente todos os seus usuários.
- A coluna `spectral_efficiency_proxy` é reportada como **proxy de eficiência
  espectral baseada em Shannon**, em `bit/s/Hz`, e nunca como throughput.
- Outage é definido por `sinr_db < outage_threshold`.

## Artefatos

`generated/data/` contém manifesto, métricas pontuais, bootstrap absoluto e
diferenças pareadas. `generated/figures/` contém PDF vetorial e PNG a 350 dpi.
`generated/tables/` contém CSV e LaTeX. `generated/reports/` contém o relatório,
legendas e comandos LaTeX. `generated/quality_control/` registra todas as
verificações como PASS, WARNING ou FAIL.

## Testes

```powershell
python -m unittest discover `
  -s sharc/campaigns/03_DC_MSS_ISOLADO/post_processing/tests `
  -p "test_*.py" -v
```

Os testes usam DataFrames artificiais e não acessam nem alteram os outputs da
campanha.

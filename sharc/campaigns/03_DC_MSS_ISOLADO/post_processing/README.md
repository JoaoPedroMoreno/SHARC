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
  --outage-threshold -6 `
  --bootstrap-repetitions 2000 `
  --bootstrap-seed 838
```

São calculados três indicadores de outage diretamente dos CSVs:

- `-1 dB`: referência NR-NTN mais restritiva;
- `-6 dB`: limiar operacional principal adotado no artigo;
- `-10 dB`: indicador complementar de degradação severa.

Esses valores são referências analíticas da campanha e não são apresentados
como limiares universais de conformidade NR-NTN.

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
- A retenção da proxy de eficiência espectral P5 é calculada como
  `100 * SE_P5_PBO / SE_P5_baseline`; seu IC95% usa a razão repetição a
  repetição do bootstrap pareado.
- O I/N é derivado de SNR e SINR em escala linear. Resultados não positivos ou
  não finitos são contabilizados e omitidos, sem substituição artificial.
- O arquivo achatado `imt_path_loss.csv` é alinhado ao CSV estruturado pela
  ordem validada contra `imt_dl_snr.csv` e depois associado às mesmas chaves.
- A coluna `spectral_efficiency_proxy` é reportada como **proxy de eficiência
  espectral baseada em Shannon**, em `bit/s/Hz`, e nunca como throughput.
- Outage é calculado para `sinr_db < -1`, `< -6` e `< -10 dB`. O argumento
  `--outage-threshold` permanece em `-6 dB` para identificar o critério
  principal nas tabelas e conclusões.

## Artefatos

`generated/data/` contém manifesto, métricas pontuais, bootstrap, retenção
pareada, valores das CDFs e controles pareados. A figura principal combina
outage e retenção da proxy P5; a segunda figura mostra o mecanismo por SNR e
I/N. `generated/figures/` contém PDF vetorial e PNG a 300 dpi.
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

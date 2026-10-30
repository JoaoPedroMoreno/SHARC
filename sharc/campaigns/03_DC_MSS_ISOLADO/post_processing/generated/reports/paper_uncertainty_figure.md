# Figura para a apresentacao: metodos de incerteza distintos

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

# Resultados da Campanha 03 — disponibilidade, qualidade e mecanismo

## Escopo e integridade

O controle de qualidade registrou 374 verificações PASS, 1 WARNING e 0 FAIL. Foram processados 26 cenários selecionados, cada um com 1.000 snapshots.

O pós-processamento leu os CSVs existentes sem executar novamente o simulador ou modificar os dados brutos.

A disponibilidade e a qualidade são apresentadas conjuntamente. Outage ≤ 5% para SINR < −6 dB e SINR P5 ≥ −6 dB expressam essencialmente o mesmo corte estatístico e não são tratados como análises independentes.

O limiar de −6 dB é o critério operacional principal desta análise; não é apresentado como limiar universal de conformidade NR-NTN.

## 1. Disponibilidade: qual é a probabilidade de SINR < −6 dB?

- Baseline LF = 20%: outage 0.09%, IC95% [0.06%, 0.13%].
- Baseline LF = 50%: outage 0.23%, IC95% [0.18%, 0.28%].

16 dos 24 cenários com PBO possuem outage pontual ≤ 5%. O maior outage foi 14.45% em LF=50%, PBO=20 dB e fração=15%.

Os IC95% foram obtidos por bootstrap agrupado por snapshot. A figura principal contém os 24 cenários com PBO e os dois baselines.

## 2. Qualidade: quanto da proxy de eficiência espectral P5 é preservado?

A retenção foi calculada diretamente da proxy salva pelo SHARC como 100 × SE P5 do cenário / SE P5 do baseline. O IC95% usa a razão repetição a repetição do bootstrap pareado por snapshot.

A menor retenção pontual foi 0.00% em LF=20%, PBO=20 dB e fração=10%. Não foi aplicado limiar arbitrário à retenção.

A grandeza permanece identificada como proxy de eficiência espectral; não é chamada de throughput.

## 3. Mecanismo: redução de SNR e benefício de interferência

As comparações usam as mesmas chaves `snapshot_id`, `ue_id` e `beam_id`. O baseline recebe a mesma máscara da fração analisada.

- LF=20%, fração=10% e PBO=10 dB: mediana da ΔSNR dos usuários afetados = -10.00 dB; mediana da ΔI/N dos usuários não afetados = -0.32 dB.
- LF=20%, fração=10% e PBO=20 dB: mediana da ΔSNR dos usuários afetados = -20.00 dB; mediana da ΔI/N dos usuários não afetados = -0.35 dB.
- LF=50%, fração=10% e PBO=10 dB: mediana da ΔSNR dos usuários afetados = -10.00 dB; mediana da ΔI/N dos usuários não afetados = -0.35 dB.
- LF=50%, fração=10% e PBO=20 dB: mediana da ΔSNR dos usuários afetados = -20.00 dB; mediana da ΔI/N dos usuários não afetados = -0.38 dB.

O I/N foi derivado registro a registro por `SNR_linear / SINR_linear - 1`. Valores não positivos ou não finitos foram omitidos, sem substituição artificial.

- LF=20%, baseline: 0 de 247605 registros de I/N omitidos por precisão numérica.
- LF=20%, PBO=10 dB: 0 de 247605 registros de I/N omitidos por precisão numérica.
- LF=20%, PBO=20 dB: 0 de 247605 registros de I/N omitidos por precisão numérica.
- LF=50%, baseline: 0 de 620140 registros de I/N omitidos por precisão numérica.
- LF=50%, PBO=10 dB: 0 de 620140 registros de I/N omitidos por precisão numérica.
- LF=50%, PBO=20 dB: 0 de 620140 registros de I/N omitidos por precisão numérica.

## Controles pareados

- SNR dos usuários não afetados praticamente constante: 24/24 cenários.
- Path loss sobreposto ao baseline por chave: 24/24 cenários.
- Mediana de I/N dos usuários não afetados reduzida: 24/24 cenários.
- Redução de SNR dos afetados dominante sobre a redução de I/N: 24/24 cenários.

A CDF de path loss é usada apenas como controle de qualidade, pois o PBO não deve alterar a perda de propagação.

## Método estatístico e limitações

- Os IC95% usam bootstrap agrupado por snapshot com 2000 repetições.
- A retenção usa bootstrap pareado; os mesmos snapshots são reamostrados no cenário e no baseline.
- As CDFs não recebem bandas de confiança para preservar a legibilidade.
- A proxy de eficiência espectral não modela scheduler, MCS/BLER, HARQ, overhead ou entrega de bits na camada 3.

## Valores sugeridos para citação no artigo

- O maior outage para SINR < −6 dB foi 14.45% em LF=50%, PBO=20 dB e fração=15%.
- A menor retenção da proxy de eficiência espectral P5 foi 0.00% em LF=20%, PBO=20 dB e fração=10%.

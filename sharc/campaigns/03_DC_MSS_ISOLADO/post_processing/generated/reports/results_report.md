# Resultados da Campanha 03 — DC-MSS isolado

## 1. Integridade dos dados

O controle de qualidade registrou 336 verificações PASS, 1 WARNING e 0 FAIL. Foram processados 26 cenários selecionados, cada um com 1.000 snapshots.

Os diretórios incompletos ou substituídos detectados durante a busca recursiva foram mantidos sem alteração e não foram combinados com os cenários completos.

## 2. Baselines

- LF = 20%: SINR média 8.33 dB, SINR P5 4.20 dB, proxy de eficiência espectral baseada em Shannon média 2.413 bit/s/Hz, P5 1.488 bit/s/Hz e outage 0.01%.
- LF = 50%: SINR média 7.17 dB, SINR P5 2.88 dB, proxy de eficiência espectral baseada em Shannon média 2.160 bit/s/Hz, P5 1.245 bit/s/Hz e outage 0.03%.

## 3. Efeito do aumento do PBO

A maior redução da SINR P5 de todos os usuários foi -18.09 dB em LF=20%, PBO=20 dB e fração=15%, com IC95% pareado [-18.13, -18.05] dB.

## 4. Efeito da fração afetada

- LF = 20%, PBO = 10 dB — Δ SINR P5 por fração: 5%: -1.30 dB, 10%: -6.84 dB, 15%: -8.16 dB.
- LF = 20%, PBO = 20 dB — Δ SINR P5 por fração: 5%: -8.61 dB, 10%: -16.65 dB, 15%: -18.09 dB.
- LF = 50%, PBO = 10 dB — Δ SINR P5 por fração: 5%: -2.22 dB, 10%: -6.69 dB, 15%: -7.87 dB.
- LF = 50%, PBO = 20 dB — Δ SINR P5 por fração: 5%: -8.86 dB, 10%: -16.33 dB, 15%: -17.72 dB.

## 5. Comparação LF20 versus LF50

- Fração 5% em PBO = 20 dB — LF=20%: -8.61 dB; LF=50%: -8.86 dB.
- Fração 10% em PBO = 20 dB — LF=20%: -16.65 dB; LF=50%: -16.33 dB.
- Fração 15% em PBO = 20 dB — LF=20%: -18.09 dB; LF=50%: -17.72 dB.

## 6. Usuários afetados e não afetados

Os grupos do baseline foram construídos por correspondência um a um de `snapshot_id`, `ue_id` e `beam_id`, usando a máscara validada do cenário de 5 dB da mesma fração.

- LF = 20%, fração 10% e PBO 20 dB: Δ SINR P5 dos usuários não afetados = 0.09 dB, IC95% [0.08, 0.10] dB.
- LF = 50%, fração 10% e PBO 20 dB: Δ SINR P5 dos usuários não afetados = 0.21 dB, IC95% [0.19, 0.23] dB.

## 7. Outage

Outage foi calculado para o limiar operacional adotado para comparação de SINR < -10.0 dB. A maior probabilidade observada foi 11.03% em LF=50%, PBO=20 dB e fração=15%.

## 8. Proxy de eficiência espectral

A coluna salva pelo SHARC foi usada diretamente. Ela representa a proxy de eficiência espectral baseada em Shannon, em bit/s/Hz, com fator de atenuação e limites de SINR da configuração. Ela não foi tratada como throughput.

## 9. Maiores degradações observadas

- LF=20%, PBO=20 dB e fração=15%: Δ SINR P5 = -18.09 dB, IC95% [-18.13, -18.05] dB.
- LF=50%, PBO=20 dB e fração=15%: Δ SINR P5 = -17.72 dB, IC95% [-17.76, -17.68] dB.
- LF=20%, PBO=20 dB e fração=10%: Δ SINR P5 = -16.65 dB, IC95% [-16.72, -16.59] dB.
- LF=50%, PBO=20 dB e fração=10%: Δ SINR P5 = -16.33 dB, IC95% [-16.38, -16.28] dB.
- LF=20%, PBO=15 dB e fração=15%: Δ SINR P5 = -13.10 dB, IC95% [-13.14, -13.06] dB.

## 10. Possíveis melhorias dos usuários não afetados

- LF=50%, PBO=20 dB e fração=15%: Δ SINR P5 = 0.31 dB, IC95% [0.29, 0.33] dB.
- LF=50%, PBO=15 dB e fração=15%: Δ SINR P5 = 0.30 dB, IC95% [0.28, 0.32] dB.
- LF=50%, PBO=10 dB e fração=15%: Δ SINR P5 = 0.28 dB, IC95% [0.26, 0.29] dB.
- LF=50%, PBO=20 dB e fração=10%: Δ SINR P5 = 0.21 dB, IC95% [0.19, 0.23] dB.
- LF=50%, PBO=5 dB e fração=15%: Δ SINR P5 = 0.21 dB, IC95% [0.19, 0.22] dB.
- LF=50%, PBO=15 dB e fração=10%: Δ SINR P5 = 0.20 dB, IC95% [0.19, 0.22] dB.
- LF=50%, PBO=10 dB e fração=10%: Δ SINR P5 = 0.19 dB, IC95% [0.17, 0.20] dB.
- LF=50%, PBO=5 dB e fração=10%: Δ SINR P5 = 0.14 dB, IC95% [0.13, 0.15] dB.
- LF=20%, PBO=20 dB e fração=15%: Δ SINR P5 = 0.14 dB, IC95% [0.13, 0.15] dB.
- LF=20%, PBO=15 dB e fração=15%: Δ SINR P5 = 0.13 dB, IC95% [0.12, 0.15] dB.
- LF=20%, PBO=10 dB e fração=15%: Δ SINR P5 = 0.12 dB, IC95% [0.11, 0.14] dB.
- LF=50%, PBO=20 dB e fração=5%: Δ SINR P5 = 0.10 dB, IC95% [0.09, 0.12] dB.
- LF=50%, PBO=15 dB e fração=5%: Δ SINR P5 = 0.10 dB, IC95% [0.09, 0.11] dB.
- LF=20%, PBO=5 dB e fração=15%: Δ SINR P5 = 0.09 dB, IC95% [0.09, 0.10] dB.
- LF=50%, PBO=10 dB e fração=5%: Δ SINR P5 = 0.09 dB, IC95% [0.08, 0.10] dB.
- LF=20%, PBO=20 dB e fração=10%: Δ SINR P5 = 0.09 dB, IC95% [0.08, 0.10] dB.
- LF=20%, PBO=15 dB e fração=10%: Δ SINR P5 = 0.09 dB, IC95% [0.08, 0.10] dB.
- LF=20%, PBO=10 dB e fração=10%: Δ SINR P5 = 0.08 dB, IC95% [0.07, 0.09] dB.
- LF=50%, PBO=5 dB e fração=5%: Δ SINR P5 = 0.07 dB, IC95% [0.06, 0.08] dB.
- LF=20%, PBO=5 dB e fração=10%: Δ SINR P5 = 0.06 dB, IC95% [0.06, 0.07] dB.
- LF=20%, PBO=20 dB e fração=5%: Δ SINR P5 = 0.04 dB, IC95% [0.04, 0.05] dB.
- LF=20%, PBO=15 dB e fração=5%: Δ SINR P5 = 0.04 dB, IC95% [0.04, 0.05] dB.
- LF=20%, PBO=10 dB e fração=5%: Δ SINR P5 = 0.04 dB, IC95% [0.03, 0.05] dB.
- LF=20%, PBO=5 dB e fração=5%: Δ SINR P5 = 0.03 dB, IC95% [0.03, 0.03] dB.

## 11. Verificação pelos intervalos de confiança

Em 355 comparações pareadas de métricas, o IC95% da diferença não incluiu zero. Essa contagem usa exclusivamente o critério numérico IC95% inferior > 0 ou superior < 0.

## 12. Limitações estatísticas

- Os IC95% são intervalos percentis de bootstrap agrupado por snapshot com 2000 repetições.
- Usuários do mesmo snapshot são reamostrados conjuntamente; não foi assumida independência entre usuários de um mesmo snapshot.
- A campanha contém níveis discretos de PBO e fração; não foram interpolados cruzamentos entre níveis simulados.
- A proxy de eficiência espectral não modela scheduler, MCS/BLER, HARQ, overhead ou entrega de bits na camada 3.

## Valores sugeridos para citação no artigo

- Para LF = 20% e fração de 10%, o PBO de 10 dB alterou a SINR P5 em -6.84 dB em relação ao baseline, com IC95% de [-6.92, -6.76] dB.
- Para LF = 50% e fração de 10%, o PBO de 10 dB alterou a SINR P5 em -6.69 dB em relação ao baseline, com IC95% de [-6.75, -6.62] dB.
- A maior probabilidade de outage observada foi 11.03% em LF=50%, PBO=20 dB e fração=15%.

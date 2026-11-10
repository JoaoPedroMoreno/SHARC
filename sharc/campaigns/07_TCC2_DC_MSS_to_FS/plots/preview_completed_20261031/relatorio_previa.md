# Previa TCC2: resultados concluidos e capacidade

Leitura de referencia: 31/10/2026, aproximadamente 00:45 (Brasilia).
Analise somente de outputs existentes. Nenhuma simulacao foi iniciada, interrompida ou alterada.

## Progresso

Lote atual: 112 casos; 26 concluidos, 12 ativos, 70 na fila, 4 interrompidos.
Os CSVs dos 26 concluidos confirmam 10000 snapshots consecutivos e INR finito.
Com os 16 controles anteriores, sao 42 casos concluidos. Os oito HO30 antigos continuam parciais e fora da fila por solicitacao anterior.
Snapshots registrados no lote atual: 332,520 / 1,120,000. Os parciais interrompidos nao sao checkpoints retomaveis.

## Resultados

INR20 = amostra ordenada ceil(0.8*N), sem interpolacao; M20 = -6 - INR20. CCDF = 1 - rank/N, como no script da campanha/GUI.
Somente casos com 10000 snapshots entram nas figuras. Nao foi calculado IC/bootstrap nesta previa; M20 positivo indica atendimento pontual, nao conformidade sustentada por IC.
Pareamento de todos os seis casos HO completos com baseline conferido por seeds e hashes de realizacao/enlaces iniciais.

- 340 km, FS20, LF20: baseline INR20=-6.229 dB; HO5/10/15/20/25 INR20=-6.428 dB. Ganho no criterio: 0.198 dB.
- No mesmo perfil, a excedencia de -6 dB cai de 18.91% para 16.36% (HO5) e 15.80% (HO25). Ha melhora, mas ganho marginal pequeno ao aumentar o limite.
- O gatilho so atua acima de -6 dB; o percentil 80 ja estava abaixo desse limiar no baseline. Portanto, esta metrica pode saturar sem que as curvas inteiras sejam identicas. A figura CCDF mostra a cauda.
- 340 km, FS20, LF20: PBO100 eleva M20 de +0.229 para +2.442 dB.
- 340 km, FS20, LF50: PBO100 melhora INR20 de +3.434 para -3.381 dB, mas M20=-2.619 dB ainda fica abaixo do criterio. Nenhum PBO de 10 a 100 km desse perfil atende pontualmente.
- 525 km, LF50: PBO100 tem M20=+0.677 dB (FS20) e +0.790 dB (FS40). Ainda nao ha novos casos de HO ou varredura PBO nessa altitude.
- Nenhum HO LF50 do lote novo concluiu; nao extrapolar para LF50 a saturacao observada em LF20.

## Tempo restante

Estimativa central: 149 h adicionais, cerca de 6.2 dias. Referencia aproximada: 06/11/2026.
Faixa de planejamento: 4 a 9 dias adicionais (aproximadamente 04 a 09/11), NAO um intervalo estatistico de confianca.
Condicoes: 12 workers, computador continuamente ligado, desempenho semelhante e espaco em disco suficiente. A fila atual nao refaz automaticamente os quatro casos interrompidos.
A projecao com quatro reexecucoes completas inclui seu custo; elas cabem nos workers liberados antes do ultimo HO terminar no modelo estatico. Isso nao significa que vao reiniciar sozinhas.
Taxas: tempo de cada execucao desde a criacao do output ate o ultimo snapshot dividido por N. Casos nao iniciados usam perfis equivalentes; HO525 usa a razao historica HO30 entre altitudes. As alturas nao observadas usam a outra altura no mesmo perfil. PBO525 usa a taxa historica ajustada pela relacao antigo/novo observada em 340 km.
O intervalo curto entre as duas leituras serve apenas para confirmar progresso, nao determina a previsao central. Periodos de suspensao ou mudanca de carga podem distorcer a media historica.

### Casos ativos

| Cenario | Snapshots | Horas restantes aproximadas |
|---|---:|---:|
| 340km_FS20m_LF50_Azi90_HO10 | 5894 | 27.1 |
| 340km_FS20m_LF50_Azi90_HO15 | 4442 | 48.7 |
| 340km_FS20m_LF50_Azi90_HO20 | 3628 | 68.3 |
| 340km_FS20m_LF50_Azi90_HO25 | 3139 | 85.0 |
| 340km_FS20m_LF50_Azi90_HO5 | 9617 | 1.5 |
| 340km_FS40m_LF20_Azi90_HO20 | 8577 | 3.0 |
| 340km_FS40m_LF20_Azi90_HO25 | 7011 | 7.0 |
| 340km_FS40m_LF20_Azi90_PBO50km | 3072 | 6.9 |
| 340km_FS40m_LF20_Azi90_PBO60km | 3067 | 6.9 |
| 340km_FS40m_LF20_Azi90_PBO70km | 3063 | 6.9 |
| 340km_FS40m_LF20_Azi90_PBO80km | 3071 | 6.9 |
| 340km_FS40m_LF20_Azi90_PBO90km | 1096 | 9.1 |

### Casos interrompidos

Todos sao 340 km, FS40, LF20. Os logs de encerramento terminam em 30/10 as 21:40:23-24, sem causa registrada; nao havia processos ativos para esses inputs.
Sem evidencia suficiente para atribuir a causa a disco, memoria, cancelamento manual ou erro de simulacao.

- HO15: 8194 / 10000.
- HO5: 8126 / 10000.
- PBO30km: 494 / 10000.
- PBO40km: 29 / 10000.

## Espaco

Campanha no C: 109.6 GiB. Campanha no D: 234.8 GiB. Livre no D: 264.9 GiB.
Projecao adicional central: 664 GiB, sendo 640 GiB HO e 24 GiB PBO.
Campanha no D ao final: aproximadamente 899 GiB. Deficit central de espaco: 399 GiB.
Faixa exploratoria de espaco adicional: 465 a 996 GiB. Usa multiplicadores 0.7 e 1.5 da projecao central, nao limites estatisticos.
A extrapolacao usa bytes por snapshot do perfil correspondente, ou proxy explicitado no CSV de previsao. Inclui os arquivos parciais existentes e novas reexecucoes completas dos quatro interrompidos, sem apagar nada.
Num modelo linear de escrita e agendamento, o D esgotaria em cerca de 49 h (2.1 dias), ANTES de terminar. Este instante e especialmente incerto; depende de novas execucoes, do perfil de trocas e de outros usos do disco.
Nao ha capacidade suficiente para prometer o termino com a gravacao atual. E necessario providenciar espaco adicional ou planejar uma reducao da duplicacao dos registros detalhados HO sem perder as variaveis de interesse. Nenhuma mudanca desse tipo foi aplicada.

## Todos os pontos concluidos

| Altitude | FS | LF | Tratamento | INR20 (dB) | M20 (dB) | P(INR > -6) |
|---:|---:|---:|---|---:|---:|---:|
| 340 | 20 | 20 | BASELINE | -6.229 | 0.229 | 18.91% |
| 340 | 20 | 20 | PBO100km | -8.442 | 2.442 | 9.89% |
| 340 | 20 | 50 | BASELINE | 3.434 | -9.434 | 89.00% |
| 340 | 20 | 50 | PBO100km | -3.381 | -2.619 | 69.45% |
| 340 | 40 | 20 | BASELINE | -6.318 | 0.318 | 18.71% |
| 340 | 40 | 20 | PBO100km | -8.503 | 2.503 | 9.68% |
| 340 | 40 | 50 | BASELINE | 3.345 | -9.345 | 88.10% |
| 340 | 40 | 50 | PBO100km | -3.440 | -2.560 | 67.25% |
| 525 | 20 | 20 | BASELINE | -9.661 | 3.661 | 15.30% |
| 525 | 20 | 20 | PBO100km | -12.355 | 6.355 | 4.29% |
| 525 | 20 | 50 | BASELINE | 0.963 | -6.963 | 38.63% |
| 525 | 20 | 50 | PBO100km | -6.677 | 0.677 | 16.45% |
| 525 | 40 | 20 | BASELINE | -9.752 | 3.752 | 15.22% |
| 525 | 40 | 20 | PBO100km | -12.461 | 6.461 | 4.15% |
| 525 | 40 | 50 | BASELINE | 0.854 | -6.854 | 38.37% |
| 525 | 40 | 50 | PBO100km | -6.790 | 0.790 | 16.05% |
| 340 | 20 | 20 | HO10 | -6.428 | 0.428 | 16.04% |
| 340 | 20 | 20 | HO15 | -6.428 | 0.428 | 15.94% |
| 340 | 20 | 20 | HO20 | -6.428 | 0.428 | 15.87% |
| 340 | 20 | 20 | HO25 | -6.428 | 0.428 | 15.80% |
| 340 | 20 | 20 | HO5 | -6.428 | 0.428 | 16.36% |
| 340 | 20 | 20 | PBO10km | -6.493 | 0.493 | 17.77% |
| 340 | 20 | 20 | PBO20km | -6.756 | 0.756 | 16.19% |
| 340 | 20 | 20 | PBO30km | -7.013 | 1.013 | 14.33% |
| 340 | 20 | 20 | PBO40km | -7.299 | 1.299 | 11.87% |
| 340 | 20 | 20 | PBO50km | -7.536 | 1.536 | 10.95% |
| 340 | 20 | 20 | PBO60km | -7.779 | 1.779 | 10.52% |
| 340 | 20 | 20 | PBO70km | -8.010 | 2.010 | 10.33% |
| 340 | 20 | 20 | PBO80km | -8.164 | 2.164 | 10.23% |
| 340 | 20 | 20 | PBO90km | -8.311 | 2.311 | 9.99% |
| 340 | 20 | 50 | PBO10km | 0.943 | -6.943 | 88.60% |
| 340 | 20 | 50 | PBO20km | -0.389 | -5.611 | 87.83% |
| 340 | 20 | 50 | PBO30km | -1.743 | -4.257 | 86.92% |
| 340 | 20 | 50 | PBO40km | -2.545 | -3.455 | 85.47% |
| 340 | 20 | 50 | PBO50km | -2.786 | -3.214 | 83.65% |
| 340 | 20 | 50 | PBO60km | -2.947 | -3.053 | 81.51% |
| 340 | 20 | 50 | PBO70km | -3.097 | -2.903 | 78.97% |
| 340 | 20 | 50 | PBO80km | -3.211 | -2.789 | 76.17% |
| 340 | 20 | 50 | PBO90km | -3.295 | -2.705 | 73.17% |
| 340 | 40 | 20 | HO10 | -6.474 | 0.474 | 15.93% |
| 340 | 40 | 20 | PBO10km | -6.580 | 0.580 | 17.51% |
| 340 | 40 | 20 | PBO20km | -6.849 | 0.849 | 15.89% |

## Arquivos

- margens_concluidos_340km.png/pdf: resumo de margem com lacunas explicitas.
- ccdf_HO_340km_FS20_LF20.png/pdf: baseline e todos os limites HO completos.
- ccdf_PBO_340km_FS20_LF20.png/pdf e ccdf_PBO_340km_FS20_LF50.png/pdf: varreduras completas.
- completed_metrics.csv: pontos concluidos e caminhos das fontes.
- progress.csv: situacao dos 112 inputs do lote.
- forecast_cases.csv: projecao e fonte de extrapolacao para cada caso restante.
- summary.json: parametros e resultados numericos do levantamento.

# Diagnóstico do Interference-Aware Inter-Satellite Handover

## Escopo e integridade da auditoria

Esta auditoria usa somente os resultados já existentes em `output/`. Nenhuma
simulação foi relançada e nenhuma equação, parâmetro físico ou lógica do
handover foi alterada.

Foram encontrados 132 diretórios de output:

- 24 runs completos: 10.000 amostras de interferência e, para HO ON, 10.000
  linhas de métricas com `snapshot_id` contínuo de 1 a 10.000;
- 96 primeiras tentativas sem CSV agregado de interferência;
- 12 runs parciais/interrompidos, incluindo um CSV truncado com bytes NUL.

Os 24 runs completos formam 12 pares HO OFF/ON. Todos são de 340 km, EESS
System B, posição Paraguai, com load factors 0,2 e 0,5 e guard bands de 0, 2,
4, 6, 8 e 10 MHz. Não há resultado completo de 525 km nem System D.

Todos os pares têm `seed: 157`, 10.000 snapshots e hashes SHA-256 idênticos
para `num_of_active_beams.csv`, `num_of_candidate_sats.csv` e
`num_of_sat.csv`. Assim, a comparação é pareada
por cenário e por linha/snapshot; não é uma comparação de distribuições
independentes.

`num_of_beams_per_sat.csv` é idêntico nos seis pares LF=0,2, sem eventos, e
difere nos seis pares LF=0,5. Essa diferença é esperada: o arquivo descreve a
distribuição das associações entre satélites e muda quando o serving satellite
de um beam é trocado. Ele não deve ser usado como teste de igualdade da
realização aleatória.

No `Model`, o seed mestre gera deterministicamente um secondary seed para
cada snapshot. A métrica de handover grava o `snapshot_id` recebido pelo mesmo
fluxo que grava a amostra agregada. A igualdade dos quatro arquivos de
topologia e a igualdade bit a bit da interferência em todos os snapshots sem
handover confirmam empiricamente o alinhamento ON/OFF.

## Como o handover atual funciona

Para cada beam ativo no snapshot, o algoritmo testa simultaneamente:

1. `psi_DC <= 4.322755 graus`;
2. `psi_EESS < phi_min` da S.465.

Se o serving satellite primário satisfaz as duas condições, os outros
satélites geometricamente elegíveis são testados em ordem decrescente de
elevação. O primeiro candidato que atende a mesma célula acima do ângulo mínimo
e não é main-main se torna o serving satellite. A decisão é determinística e
local ao snapshot.

O trigger depende somente da geometria. Isso explica por que, para um mesmo
load factor, os mesmos snapshots são acionados em todos os guard bands.

## Resultados numéricos

### Frequência de atuação

| Load factor | Cenários completos | Snapshots por cenário | Triggers por cenário | Handovers por cenário | Unresolved | Frequência por snapshot |
|---:|---:|---:|---:|---:|---:|---:|
| 0,2 | 6 | 10.000 | 0 | 0 | 0 | 0% |
| 0,5 | 6 | 10.000 | 4 | 4 | 0 | 0,04% |

No LF=0,5, os triggers ocorrem nos snapshots 3151, 5010, 6463 e 9648 em todos
os seis guard bands. Há um evento e um handover bem-sucedido em cada um desses
snapshots.

### Localização dos triggers na distribuição

Tomando HO OFF como baseline, os quatro snapshots com trigger são exatamente
os quatro maiores valores de interferência agregada:

| Snapshot | Rank OFF | Rank ON, GB=0 | Redução pareada |
|---:|---:|---:|---:|
| 3151 | 1 | 3 | 9,805 dB |
| 9648 | 2 | 6 | 15,492 dB |
| 5010 | 3 | 1 | 4,758 dB |
| 6463 | 4 | 4 | 8,711 dB |

Logo, 100% dos triggers estão dentro do top 1%, e também dentro do top 0,1%.
Isso não significa que 100% do top 1% recebe handover: apenas 4 dos 100
snapshots desse conjunto são acionados, isto é, 4%. Para o top 0,1%, são 4 dos
10 snapshots, ou 40%.

A redução líquida do agregado nesses quatro snapshots equivale a aproximadamente
66,6%, 86,5%, 89,5% e 97,2% em potência linear. Portanto, no nível do snapshot,
o handover não está atuando sobre uma perturbação irrelevante: ele modifica
fortemente os quatro extremos que aciona.

### Por que o critério de 1% não muda

Com 10.000 snapshots, o nível de 1% de excedência é determinado pelo 100º maior
valor. O handover altera somente quatro valores. Mesmo após a redução, ele não
modifica o valor que ocupa a fronteira do top 100. Por isso, o percentil de 1%
é numericamente idêntico em todos os 12 pares.

O mesmo ocorre no percentil de 0,1%: apesar de quatro dos dez maiores snapshots
serem reduzidos, o valor de fronteira do top 10 continua sendo definido por um
snapshot não alterado.

| GB (MHz) | P99 OFF/ON LF=0,2 (dBW/MHz) | P99 OFF/ON LF=0,5 (dBW/MHz) | Excedência de -154 LF=0,2 OFF/ON | Excedência de -154 LF=0,5 OFF/ON |
|---:|---:|---:|---:|---:|
| 0 | -113,374 / -113,374 | -108,435 / -108,435 | 100% / 100% | 100% / 100% |
| 2 | -121,472 / -121,472 | -116,533 / -116,533 | 84,88% / 84,88% | 99,99% / 99,99% |
| 4 | -126,735 / -126,735 | -121,796 / -121,796 | 54,05% / 54,05% | 92,37% / 92,37% |
| 6 | -130,687 / -130,687 | -125,748 / -125,748 | 40,05% / 40,05% | 77,95% / 77,95% |
| 8 | -135,669 / -135,669 | -130,730 / -130,730 | 22,14% / 22,14% | 52,27% / 52,27% |
| 10 | -155,089 / -155,089 | -150,149 / -150,149 | 0,82% / 0,82% | 1,91% / 1,91% |

Nenhum dos quatro snapshots reduzidos cruza o limiar de -154 dBW/MHz. Assim,
até a contagem de excedências permanece igual.

## Dados disponíveis nos outputs

Existem, por snapshot:

- interferência agregada em `system_dl_interf_power_per_mhz.csv`;
- interferência agregada total e INR;
- contagens de beams/satélites;
- para HO ON, beams ativos avaliados, triggers, handovers bem-sucedidos e
  unresolved em `interference_aware_handover_snapshot_metrics.csv`.

Também existem vetores achatados de potência, ganhos de antena e path loss.
Eles são gravados como uma única coluna `samples`, sem uma chave relacional que
identifique de forma completa cada amostra.

Não existem nos runs atuais:

- `interference_aware_handover_events.csv`, porque
  `record_event_details: false`;
- contribuição individual final `I_i` de cada beam para o EESS;
- `snapshot_id` nos CSVs achatados de ganho/path loss;
- associação conjunta `snapshot_id`, `beam_grid_idx`, beam row, serving
  satellite e contribuição individual;
- identificação do primary/target nos outputs concluídos;
- decomposição top-1/top-3/top-5/top-10 por snapshot.

O cálculo acumula diretamente cada potência em escala linear em um escalar
`rx_interference` e salva apenas o logaritmo do total. Embora os CSVs achatados
contenham alguns termos intermediários, não há informação suficiente para
reconstruir sem ambiguidade a segmentação e a identidade de cada link. Além
disso, não é salvo o `oob_power` final que efetivamente entra na soma.

## A pergunta sobre os maiores contribuintes

Com os outputs existentes, não é possível afirmar formalmente se o beam que
sofreu handover era top-1, top-3, top-5 ou top-10 no snapshot. Também não é
possível calcular as frações de `I_agg` desses grupos.

É possível, entretanto, concluir algo mais limitado: nos quatro snapshots
acionados, a troca provoca redução líquida de 4,76 a 15,49 dB no agregado.
Portanto, a reassociação afeta materialmente o agregado desses snapshots. Isso
é compatível com atuação sobre um interferente dominante, mas não prova sua
posição no ranking individual.

## Instrumentação mínima recomendada

Não foi feita instrumentação nesta auditoria para manter o código físico
intocado. Para uma campanha diagnóstica, a alteração mínima deve ser opcional e
desabilitada por padrão:

1. no laço que calcula a interferência externa em
   `SimulationDownlink.calculate_external_interference`, preservar a
   contribuição linear por beam antes de adicioná-la a `rx_interference`;
2. para cada snapshot, manter somente top-10 contribuintes e, adicionalmente,
   qualquer beam com trigger/handover, mesmo que esteja fora do top-10;
3. gravar um CSV estruturado com:
   `snapshot_id`, `beam_row_idx`, `beam_grid_idx`, `primary_satellite_idx`,
   `serving_satellite_idx`, `target_satellite_idx`, flags de trigger/success/
   unresolved, `contribution_linear`, `contribution_dbw_mhz`, `I_agg`, rank e
   fração de `I_agg`;
4. ativar `record_event_details: true` somente na campanha diagnóstica para
   obter os ângulos, elevações e IDs já previstos pelo mecanismo;
5. adicionar a escrita estruturada em `Results`, sem adicionar RNG nem alterar
   a soma de interferência existente.

Armazenar apenas top-10 + beams afetados é muito mais leve que salvar todos os
aproximadamente 1.600 beams ativos por snapshot no LF=0,5.

Recomenda-se uma campanha diagnóstica inicial de 500–1.000 snapshots com um
único cenário geométrico. Contudo, como os quatro eventos observados ocorreram
em seeds secundários associados aos snapshots 3151, 5010, 6463 e 9648, uma
execução simplesmente truncada aos primeiros 1.000 snapshots provavelmente
não reproduzirá nenhum deles. A opção mais informativa é permitir uma lista
determinística de snapshot IDs diagnósticos ou executar os 10.000 snapshots de
um único par LF=0,5/GB escolhido, armazenando somente top-10 + eventos.

## Conclusão

O problema observado não é evidência de que o target escolhido não reduz a
interferência. Nos eventos existentes, a redução é grande. O motivo comprovado
para a ausência de efeito no critério de 1% é a raridade do trigger atual:
0,04% dos snapshots no LF=0,5 e zero no LF=0,2. Ele atua nos quatro extremos,
mas deixa intocados os demais 96 snapshots que formam o top 1% e, em particular,
o 100º maior valor que define esse percentil.

A hipótese de atuação sobre um beam individual não dominante não pode ser
testada com os outputs atuais. Ela exige a instrumentação leve descrita acima.

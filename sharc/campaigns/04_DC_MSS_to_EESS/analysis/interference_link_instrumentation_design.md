# Instrumentação diagnóstica de interferência por link

## Estado

Implementada e testada, mas ainda não executada em campanha de 10.000
snapshots. A feature flag é desabilitada por padrão e é independente do
handover existente.

```yaml
imt:
  topology:
    mss_dc:
      interference_link_diagnostics:
        enabled: false
        top_n: 10
        eess_position_label: ""
```

Para o diagnóstico proposto, somente a cópia diagnóstica deve usar
`enabled: true` e `eess_position_label: Paraguay`.

## Arquivos modificados/criados

- `sharc/parameters/imt/parameters_imt_mss_dc.py`: configuração opcional;
- `sharc/simulation_downlink.py`: captura do termo físico por link antes da
  soma e metadados geométricos;
- `sharc/results.py`: dois CSVs estruturados;
- `sharc/interference_link_diagnostics.py`: ranking determinístico e frações;
- `tests/test_interference_link_diagnostics.py`: testes específicos;
- `analysis/verify_instrumentation_snapshot.py`: reprodução isolada do
  snapshot histórico 3151.

Nenhum modelo de antena, propagação, potência, máscara ou handover foi
alterado.

## Pseudocódigo

```text
calcular ganhos, path loss e coupling loss normalmente
rx_interference_linear = 0

para cada beam ativo:
    calcular oob_power pelo fluxo original
    I_link_linear = sum(10**(oob_power/10))
    rx_interference_linear += I_link_linear

    se diagnostics.enabled:
        preservar I_link_linear e os termos já calculados

I_agg = rx_interference_linear

se diagnostics.enabled:
    ordenar I_link de forma estável e decrescente
    calcular ranks e frações top-1/top-3/top-5/top-10
    selecionar união(top-N, beams trigger/HO/unresolved)
    gravar linhas selecionadas e resumo do snapshot

continuar o fluxo normal do SHARC
```

Quando a flag está OFF, o código executa literalmente a expressão de soma
baseline. Não há chamada aleatória na instrumentação.

## Arquivos de saída

### `interference_link_diagnostics.csv`

Uma linha por link retido. Unidades lineares são explicitamente mW, porque o
SHARC soma `10 ** (0.1 * potência_dBm)`.

Identificação:

- `snapshot_id`, `secondary_seed`;
- `beam_row_idx`, `beam_grid_idx`, `service_cell_id`;
- `primary_satellite_idx`, `serving_satellite_idx`,
  `target_satellite_idx`;
- `guard_band_mhz`, `altitude_km`, `load_factor`;
- `eess_system`, `eess_position_label`;
- posição EESS: latitude, longitude de referência, altitude P.619 e XYZ local;
- `trigger_flag`, `handover_flag`, `unresolved_flag`.

Interferência e ranking:

- `i_link_linear_mw`, `i_link_dbw_per_mhz`;
- `i_agg_linear_mw`, `i_agg_dbw_per_mhz`;
- `rank_in_snapshot`, `fraction_of_iagg_linear`;
- `fraction_top1`, `fraction_top3`, `fraction_top5`, `fraction_top10`.

TX DC-MSS:

- `tx_offaxis_to_eess_deg`;
- `g_tx_toward_eess_dbi`, `g_tx_peak_dbi`,
  `tx_gain_drop_from_peak_db`;
- latitude/longitude da service cell;
- `satellite_elevation_from_service_cell_deg`.

RX EESS:

- `rx_offaxis_from_eess_boresight_deg`;
- boresight realizado azimute/elevação;
- azimute/elevação do interferente visto pela EESS;
- `g_rx_from_interferer_dbi`, `g_rx_peak_dbi`,
  `rx_gain_drop_from_peak_db`.

Acoplamento:

- `joint_gain_suppression_db`;
- `path_loss_db`, `spectral_coupling_db`;
- potência conduzida, potência espectral total e PSD espectral utilizadas;
- `additional_loss_db`;
- `geometric_coupling_score_db`;
- `full_coupling_score_dbm` e `full_coupling_score_dbw_per_mhz`.

O full coupling é o próprio `I_link` calculado fisicamente, não uma
reconstrução aproximada.

### `interference_link_snapshot_summary.csv`

Uma linha por snapshot com seed, número de links ativos/retidos, `I_agg`, soma
de todos os `I_link`, erro de reconstrução e frações top-1/3/5/10.

## Definições geométricas

`tx_offaxis_to_eess_deg` usa o mesmo método geométrico chamado pelo cálculo de
ganho do BS: ângulo entre o pointing realizado do beam DC-MSS, dirigido à
service cell, e o vetor satélite→EESS.

`rx_offaxis_from_eess_boresight_deg` usa o mesmo método no receptor: ângulo
entre `pointn_azim_global`/`pointn_elev_global` realizados naquele snapshot e
o vetor EESS→satélite.

Os ganhos gravados são os arrays efetivamente produzidos pelo cálculo de
coupling loss. Assim, ângulos e ganhos não são recalculados com um padrão
aproximado.

## Testes

Foram executados 30 testes: 7 novos e os 23 testes existentes do handover.
Todos passaram.

Os testes novos cobrem:

- default OFF e carregamento YAML;
- top-10 + beam afetado fora do top-10;
- ranks e frações top-1/3/5/10;
- ausência de RNG;
- geometria TX e RX conhecida;
- identidade da service cell e satélites;
- escrita e schema dos dois CSVs;
- ausência de arquivos quando desabilitada;
- igualdade exata de `I_agg` com instrumentação OFF/ON;
- reconstrução linear de `I_agg` pelo somatório dos links.

Na reprodução real isolada do snapshot 3151:

- diagnostics OFF: `-116.748910013654239 dBW/MHz`;
- diagnostics ON:  `-116.748910013654239 dBW/MHz`;
- erro da soma linear: `9.926e-24 mW`;
- links gravados: 10.

O output histórico contém `-116.752059055167209 dBW/MHz`, diferença de
`+0.003149041512970 dB` em relação à reprodução atual. Como OFF e ON são
idênticos, essa diferença não foi causada pela instrumentação. O YAML copiado
no output e o YAML atual têm SHA-256 idêntico. Antes de uma afirmação global de
reprodução bit a bit do arquivo histórico, essa pequena deriva preexistente
deve ser tratada separadamente.

## Tamanho estimado

Com top-10, 10.000 snapshots produzem aproximadamente 100.000 linhas por run.
Uma linha sintética ocupa cerca de 348 bytes; a estimativa mínima é 33 MB por
run. Considerando mais dígitos e eventos adicionais, deve-se reservar 35–60 MB
para o CSV de links e cerca de 2–4 MB para o resumo. Para o par OFF/ON,
aproximadamente 75–130 MB.

## Cenário diagnóstico recomendado

Executar, depois de aprovação, um único par:

- 340 km, EESS System B, Paraguai;
- LF=0,5, GB=10 MHz;
- seed 157, 10.000 snapshots;
- run 1: handover antigo OFF, diagnostics ON;
- run 2: handover antigo ON, diagnostics ON e event details ON.

Esse par é apropriado porque o baseline tem P99 próximo do critério e 1,91%
de excedência. O OFF instrumentado é necessário para identificar os links
originais dos snapshots críticos; somente instrumentar o ON mostraria a
geometria posterior à troca nos quatro eventos conhecidos.

## Crítica metodológica

Há uma tensão entre “guardar somente top-10” e posteriormente analisar “todos
os links”. O CSV implementado não permite scatter/modelagem individual de
todos os aproximadamente 16 milhões de links; isso violaria deliberadamente a
restrição de armazenamento. Ele permite análise exata de todos os top-10,
frações calculadas sobre toda a população e qualquer beam afetado.

Para uma distribuição de toda a população sem salvar cada link, recomenda-se
adicionar, antes do run, histogramas streaming com bins declarados ou uma
amostra diagnóstica determinística separada. Bins fixos introduzem resolução e
efeito de borda; amostragem exige intervalos de confiança. Nenhuma dessas
alternativas deve ser apresentada como dados brutos completos.

O pointing instantâneo EESS é informação perfeita no simulador. Um operador
DC-MSS provavelmente conhece localização protegida, efemérides e pointing de
seus próprios beams, mas não necessariamente azimute/elevação instantâneos da
EESS. Portanto, `rx_offaxis` e `joint_gain_suppression` pertencem inicialmente
ao diagnóstico/oracle. Uma regra implementável deverá usar informação pública,
coordenação regulatória, pior caso RX ou estatísticas documentadas.

Um trigger oracle baseado apenas em `I_agg > -154 - margem` é inadequado para
GB pequenos: a auditoria mostrou excedência próxima de 100% em alguns casos,
o que transformaria o oracle em handover quase contínuo. Percentis são úteis
como upper bound retrospectivo de pesquisa, mas não são uma regra operacional
instantânea. O oracle e qualquer threshold ficam explicitamente fora desta
implementação inicial.

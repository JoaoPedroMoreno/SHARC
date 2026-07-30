# Auditoria tecnica: capacidade do SHARC para analise de desempenho DC-MSS-IMT

Data da auditoria: 2026-07-27  
Escopo correto: campanha `sharc/campaigns/03_DC_MSS_ISOLADO`, topologia `imt.topology.type: MSS_DC`, enlace `general.imt_link: DOWNLINK`.  
Observacao: este relatorio substitui a versao anterior, que analisava por engano a campanha `02_DC_MSS_to_FS 2`.

## 1. Resumo executivo

A campanha `03_DC_MSS_ISOLADO` e muito mais adequada para analise de desempenho do proprio DC-MSS-IMT do que a campanha 02. A diferenca decisiva esta em `sharc/campaigns/03_DC_MSS_ISOLADO/Script/base_input.yaml`, linha 144: `imt_dl_intra_sinr_calculation_disabled: false`. Com isso, o fluxo downlink calcula e salva SINR, SNR, perda de percurso, ganhos de antena, perda de acoplamento e a grandeza chamada `imt_dl_tput`.

Ainda assim, o SHARC nao calcula throughput no sentido do Report ITU-R M.2514-0. O campo `imt_dl_tput` e uma proxy de eficiencia espectral baseada em Shannon, em `bits/s/Hz`, calculada por `attenuation_factor * log2(1 + SINR_linear)` com saturacao por `sinr_min` e `sinr_max`. Nao ha bits corretamente entregues a camada 3, pacotes, SDUs, trafego oferecido, scheduler temporal real, MCS, BLER, HARQ, retransmissoes ou overhead.

Portanto, para a campanha 03:

- SINR por usuario/celula: suportado e salvo, mas em CSV achatado sem IDs de usuario/feixe/satelite.
- Eficiencia espectral media e percentil 5 por proxy Shannon: derivavel imediatamente de `imt_dl_tput.csv` ou de `imt_dl_sinr.csv`.
- Outage por limiar de SINR: derivavel imediatamente de `imt_dl_sinr.csv`, desde que o limiar seja uma hipotese declarada.
- Throughput ITU-R M.2514: nao suportado.
- Comparacao formal com 0.03 bit/s/Hz e 0.5 bit/s/Hz da M.2514: nao formal; apenas comparacao aproximada se rotulada como proxy PHY/Shannon.

## 2. Mapa das classes e funcoes envolvidas

| Papel | Arquivo | Classe/funcao | Linha aprox. | Logica relevante |
|---|---|---:|---:|---|
| Configuracao da campanha isolada | `sharc/campaigns/03_DC_MSS_ISOLADO/Script/base_input.yaml` | YAML | 1-144 | Define 4000 snapshots, `MSS_DC`, downlink, `interfered_with: false` e intra-SINR habilitado. |
| Geracao de cenarios | `sharc/campaigns/03_DC_MSS_ISOLADO/Script/generate_input.py` | `update_template` | 151-164 | Forca `interfered_with=false`, `imt_dl_intra_sinr_calculation_disabled=false`, varia altitude, raio de feixe, altura FS e load factor. |
| Pos-processamento | `sharc/campaigns/03_DC_MSS_ISOLADO/Script/plot_imt_performance_cdf.py` | `PERFORMANCE_FIELDS` | 17-22 | Plota CDF de `imt_dl_sinr`, `imt_dl_tput`, `imt_dl_snr`, `imt_path_loss`. |
| Selecao da topologia | `sharc/topology/topology_factory.py` | `createTopology` | 56-60 | `type == "MSS_DC"` instancia `TopologyImtMssDc`. |
| Satelites/feixes DC-MSS | `sharc/topology/topology_imt_mss_dc.py` | `get_coordinates` | 284-372 | Repete satelite por feixe e retorna posicoes, apontamentos e `sat_power_backoff`. |
| Grade de servico e apontamento | `sharc/topology/topology_imt_mss_dc.py` | `get_satellite_pointing` | 397-532 | Gera grade, escolhe satelite de maior elevacao por ponto e filtra por `minimum_service_angle`. |
| Power back-off por zona | `sharc/topology/topology_imt_mss_dc.py` | `get_satellite_pointing` | 412-421, 520 | Converte `power_control_zones` em `grid_power_backoffs` por ponto/feixe. |
| Criacao dos transmissores | `sharc/station_factory.py` | `generate_imt_base_stations` | 111-145 | Cria cada feixe como `IMT_BS`, sorteia atividade por `load_probability`, aplica `tx_power = conducted_power - power_backoff`. |
| Criacao dos UEs | `sharc/station_factory.py` | `generate_imt_ue_outdoor` | 322-384 | Cria `num_bs * k * k_m` UEs; com `k=1`, `k_m=1`, ha um UE por feixe/celula. |
| Associacao UE-feixe | `sharc/simulation.py` | `connect_ue_to_bs` | 475-489 | Associa blocos de UEs aos indices de BS/feixe. |
| Scheduler simplificado | `sharc/simulation.py` | `scheduler` | 554-578 | Divide RBs igualmente entre UEs de uma BS; com `k=1`, o UE recebe a banda alocada do feixe. |
| SINR downlink | `sharc/simulation_downlink.py` | `calculate_sinr` | 173-228 | Calcula sinal desejado, interferencia intra-IMT co-RB, ruido, SINR e SNR por UE. |
| Proxy de SE/tput | `sharc/simulation.py` | `calculate_imt_tput` | 687-720 | Calcula `attenuation_factor * log2(1+SINR)` com clipping. |
| Coleta de resultados | `sharc/simulation_downlink.py` | `collect_results` | 676-719 | Salva `imt_path_loss`, `imt_coupling_loss`, ganhos, `imt_dl_tput`, `imt_dl_sinr`, `imt_dl_snr`, `imt_dl_tx_power`. |
| Escrita dos CSVs | `sharc/results.py` | `write_files` | 201-223 | Escreve cada `SampleList` como CSV de uma coluna `samples`. |

## 3. Fluxo desde o YAML ate os outputs

1. `base_input.yaml`, linhas 1-10, define a simulacao downlink, co-canal, 4000 snapshots e diretorio `campaigns/03_DC_MSS_ISOLADO/output/`.
2. Linhas 13-16 definem IMT como sistema interferente (`interfered_with: false`), frequencia 2155 MHz, banda 5 MHz e RB de 0.18 MHz.
3. Linhas 27-84 definem a topologia `MSS_DC`, orbitas, criterios de satelite ativo, grade de servico, raio de feixe e zonas de power control.
4. Linhas 87-88 definem `load_probability: 0.2` e `conducted_power: 42.8`.
5. Linhas 112-144 definem um UE por feixe (`k=1`, `k_m=1`), perdas/ruido de UE, limites de SINR e intra-SINR habilitado.
6. `SimulationDownlink.snapshot`, linhas 59-108, cria topologia, BS/feixes, sistema externo, UEs, associa UE-BS, seleciona UE, agenda RBs e aplica potencia.
7. Como `interfered_with=false`, o ramo executado e IMT interferindo em outro sistema; mas como `imt_dl_intra_sinr_calculation_disabled=false`, linhas 127-130 calculam tambem o acoplamento e a SINR intra-IMT antes da interferencia externa.
8. `calculate_sinr`, linhas 188-228, calcula potencia recebida desejada, interferencia intra-IMT, ruido, SINR e SNR.
9. `collect_results`, linhas 676-719, salva os KPIs IMT: `imt_path_loss`, `imt_coupling_loss`, `imt_bs_antenna_gain`, `imt_ue_antenna_gain`, `imt_dl_tput`, `imt_dl_tx_power`, `imt_dl_sinr`, `imt_dl_snr`.
10. Outputs existentes em um diretorio real da campanha 03 incluem `imt_dl_sinr.csv`, `imt_dl_snr.csv`, `imt_dl_tput.csv`, `imt_path_loss.csv`, `imt_coupling_loss.csv`, `imt_bs_antenna_gain.csv`, `imt_ue_antenna_gain.csv`, alem de `system_inr.csv`.

## 4. Equacoes implementadas

### Potencia transmitida e back-off

Em `sharc/station_factory.py`, `generate_imt_base_stations`, linhas 119 e 144:

```text
power_backoff = topology.power_backoff
tx_power = conducted_power - power_backoff
```

Em `sharc/simulation_downlink.py`, `power_control`, linhas 155-165:

```text
total_power = bs.tx_power + bs_power_gain
tx_power_per_selected_ue = total_power - 10*log10(k)
```

Na campanha 03, `k = 1`, entao nao ha divisao de potencia entre multiplos UEs no mesmo feixe.

### Perda de acoplamento desejada

Em `sharc/simulation.py`, `calculate_intra_imt_coupling_loss`, linhas 441-471:

```text
coupling_loss = path_loss_imt
                - imt_bs_antenna_gain
                - imt_ue_antenna_gain
                + bs_ohmic_loss + ue_ohmic_loss + ue_body_loss
```

### Potencia recebida, ruido e SINR

Em `sharc/simulation_downlink.py`, `calculate_sinr`, linhas 188-228:

```text
rx_power = bs.tx_power - coupling_loss
interference = sum_linear(interfering_bs_tx_power - coupling_loss_interferers)
thermal_noise_dBm = 10*log10(kB*T*1e3) + 10*log10(BW_Hz) + NF
total_interference = 10*log10(10^(I/10) + 10^(N/10))
sinr = rx_power - total_interference
snr = rx_power - thermal_noise
```

### Proxy chamada `imt_dl_tput`

Em `sharc/simulation.py`, `calculate_imt_tput`, linhas 706-720:

```text
tput = attenuation_factor * log2(1 + 10^(SINR_dB/10))
tput = 0 se SINR < sinr_min
tput = attenuation_factor * log2(1 + 10^(sinr_max/10)) se SINR > sinr_max
```

`sharc/results.py`, linhas 82-85, documenta `imt_dl_tput` como `Throughput [bits/s/Hz]`; portanto a unidade real e eficiencia espectral normalizada, nao bits/s.

## 5. A. Modelagem dos usuarios e enlace desejado

1. O SHARC cria UEs individuais para o DC-MSS. Evidencia: `StationFactory.generate_imt_ue_outdoor`, linhas 322-327.
2. Na campanha 03, cada feixe/celula possui um UE, pois `base_input.yaml` linhas 112-114 define `k=1`, `k_m=1`.
3. Existe associacao explicita UE-BS/feixe por indice em `Simulation.connect_ue_to_bs`, linhas 481-489. A associacao feixe-satelite existe implicitamente pelas posicoes repetidas em `TopologyImtMssDc.get_coordinates`, linhas 296-329, mas nao e salva como `satellite_id`/`beam_id`.
4. O codigo calcula potencia desejada recebida no terminal em `calculate_sinr`, linhas 188-191, e a campanha 03 executa esse trecho.
5. A campanha 03 calcula SINR do usuario DC-MSS e tambem calcula interferencia DC-MSS em um sistema externo dummy/FS, porque `interfered_with=false` mas intra-SINR esta habilitada.
6. Perdas, ganhos e ruidos no enlace desejado: FSPL (`base_input.yaml` linha 142), ganho BS, ganho UE, perdas ohmicas, body loss UE, temperatura de ruido IMT e figura de ruido UE (`calculate_intra_imt_coupling_loss` linhas 453-471; `calculate_sinr` linhas 216-228).
7. A interferencia entre feixes/satelites do proprio DC-MSS e calculada em `calculate_sinr`, linhas 193-208, considerando BS/feixes interferentes no mesmo RB.
8. Ha alocacao de RBs em `scheduler`, linhas 554-578. Com `k=1`, todos os feixes usam um unico grupo de RB por UE; a interferencia co-RB entre feixes entra no SINR. Nao ha um plano de reuso de frequencia configuravel por celula.

## 6. B. Significado de load factor

O parametro da campanha e `imt.bs.load_probability`, `base_input.yaml` linha 87. Ele e usado em `StationFactory.generate_imt_base_stations`, linhas 139-141:

```text
active = random_number_gen.rand(num_bs) < load_probability
```

Ele representa probabilidade de ativacao por feixe/BS em cada snapshot. Nao representa numero de usuarios, nao altera `k`, nao altera banda por usuario, nao modela ocupacao temporal persistente e nao cria throughput temporal. Ele altera o conjunto de transmissores ativos e, portanto, o sinal/interferencia observados nos UEs e no sistema externo.

O sorteio ocorre por snapshot e por feixe/BS criado.

## 7. C. Throughput e eficiencia espectral

Existe variavel, output e grafico chamados `imt_dl_tput`. Evidencias:

- `sharc/results.py`, linhas 82-85: `imt_dl_tput`.
- `sharc/simulation.py`, linhas 687-720: funcao `calculate_imt_tput`.
- `sharc/campaigns/03_DC_MSS_ISOLADO/Script/plot_imt_performance_cdf.py`, linhas 17-22: inclui `imt_dl_tput`.
- Outputs reais da campanha 03 incluem `imt_dl_tput.csv`.

Mas esse `tput` nao e throughput M.2514. A equacao e Shannon-like, a unidade e `bits/s/Hz`, e o resultado e por UE selecionado. Nao ha dimensao temporal real; nao ha verificacao de bits corretamente entregues; nao ha camada MAC ou L3.

Elementos ausentes no simulador para throughput formal:

| Elemento | Existe? | Evidencia |
|---|---|---|
| Scheduler | Parcial | `scheduler` divide RBs igualmente, linhas 554-578. |
| Resource blocks | Parcial | `num_rb_per_bs` e `num_rb_per_ue`, `simulation.py` linhas 238-246. |
| Divisao de banda entre usuarios | Parcial | existe por `k`; na campanha 03 `k=1`. |
| MCS | Nao | nao ha implementacao encontrada. |
| SINR-MCS | Nao | nao ha tabela. |
| Codificacao | Nao | nao ha modelo. |
| BLER | Nao | nao ha modelo. |
| HARQ/retransmissoes | Nao | nao ha modelo. |
| Overhead | Nao | nao ha modelo explicito. |
| Pacotes/SDUs | Nao | nao ha modelo. |
| Trafego oferecido | Nao | nao ha filas/trafego. |

Com os outputs atuais da campanha 03 e possivel derivar imediatamente:

| Metrica | Como derivar | Hipotese |
|---|---|---|
| CDF de SINR | `imt_dl_sinr.csv` | amostras achatadas representam UEs/snapshots. |
| Percentil 5 de SINR | percentil 5 de `imt_dl_sinr.csv` | sem ponderacao por feixe/satelite, salvo se IDs forem adicionados. |
| SE proxy Shannon | `log2(1 + 10^(SINR/10))` ou usar `imt_dl_tput.csv` | receptor ideal, sem MCS/BLER/overhead. |
| SE media proxy | media de `imt_dl_tput.csv` | mesma hipotese Shannon-like. |
| Outage | `Pr[SINR < limiar]` | limiar operacional definido externamente. |
| Link margin | `SINR - SINR_limiar` | limiar definido externamente. |
| Achievable-rate proxy | `SE_proxy * BW_UE` | full-buffer e camada fisica idealizada. |

Uma eficiencia espectral Shannon nao deve ser comparada formalmente com 0.03 bit/s/Hz da M.2514. Ela pode ser comparada apenas como benchmark aproximado, com rotulo explicito: `SE proxy PHY/Shannon`, nao `user-experienced data rate`.

## 8. D. Power back-off

No YAML base, `power_control_zones` esta em `base_input.yaml` linhas 67-84: uma zona de 0 dB com margem 25 km e uma zona de 10 dB sem margem. No gerador da campanha 03, entretanto, `replace_power_backoff_values` linhas 115-124 muda ambas as zonas para 0 dB, e `replace_mss_border_margins` linhas 127-131 zera as margens. Assim, os YAMLs gerados da campanha 03 atual sao cenarios isolados sem power back-off efetivo.

A implementacao do mecanismo fica em `TopologyImtMssDc.get_satellite_pointing`, `topology_imt_mss_dc.py` linhas 412-421: cada ponto da grade recebe `zone.power_backoff_db`; depois a potencia de transmissao e reduzida em `StationFactory.generate_imt_base_stations`, linha 144.

Vereditos:

| Pergunta | Resposta |
|---|---|
| A reducao e aplicada a potencia conduzida, EIRP ou ganho? | Potencia conduzida (`tx_power`). O EIRP efetivo cai por consequencia; ganho de antena nao muda. |
| Afeta sinal desejado? | Sim, quando `calculate_sinr` roda, porque `rx_power = bs.tx_power - coupling_loss`. A campanha 03 roda esse caminho. |
| Afeta interferencia? | Sim, interferencia intra-IMT e externa usam `bs.tx_power`. |
| Existe caminho onde reduz so interferencia? | Na campanha 03, nao para a SINR intra habilitada: o mesmo `bs.tx_power` alimenta sinal e interferencia. |
| Diferentes back-offs em varredura? | Mecanismo existe, mas o gerador 03 zera todos. E preciso reintroduzir parametro de varredura em `generate_input.py`. |
| Back-off global | Alterar gerador para setar todas as zonas em `X` ou usar uma zona unica cobrindo toda a grade. |
| Fracao de feixes | Nao suportado diretamente; exige novo parametro e sorteio por feixe/grade em `topology_imt_mss_dc.py`. |
| Regiao geografica | Suportado por `power_control_zones` com `FROM_COUNTRIES`/margem/circulo; gerador precisa preservar e variar a geometria em vez de zerar. |

## 9. E. Beam steering e beamforming

O apontamento dos feixes para a grade de servico ocorre em `TopologyImtMssDc.get_satellite_pointing`:

- `parameters_grid.py` linhas 300-318 gera a grade de pontos.
- `topology_imt_mss_dc.py` linhas 456-467 calcula elevacao de cada ponto para satelites elegiveis.
- Linhas 465-467 escolhem o melhor satelite por ponto.
- Linhas 469-494 calculam azimute/elevacao do vetor satelite-ponto.
- Linhas 498-503 descartam pontos cujo melhor satelite fica abaixo de `minimum_service_angle`.

O boresight e direcionado ao ponto de grade/celula, nao necessariamente ao UE aleatorio dentro da celula. O steering e ideal: nao ha scan loss, erro de apontamento, quantizacao de fase, degradacao de ganho maximo com angulo de steering ou deformacao do padrao.

O padrao `ITU-R-S.1528-Taylor` usa ganho maximo constante (`antenna_s1528.py` linhas 27-31) e calcula ganho por angulo off-axis e `theta_vec` (`antenna_s1528.py` linhas 84-105). O off-axis e calculado pela geometria em `support/geometry.py` linhas 275-295 e passado ao ganho em `simulation.py` linhas 616-632.

Na configuracao atual:

- 5 graus (`base_input.yaml` linha 42) e o limiar para selecionar satelites ativos a partir da referencia/FS.
- 32 graus (`base_input.yaml` linha 65) e o limiar minimo de servico para aceitar pontos de grade servidos.

Manter o beam steering fixo entre campanhas de power back-off produziria uma comparacao controlada. Hoje `transform_grid_randomly: true` (linha 50) faz a grade variar por snapshot; para comparar somente back-off, recomenda-se controlar seeds e/ou congelar a grade/orbit state.

## 10. F. Outputs e estatistica

Outputs reais observados na campanha 03:

| Output | Existe? | Nivel salvo |
|---|---:|---|
| `imt_dl_sinr.csv` | Sim | amostras achatadas por UE selecionado/snapshot |
| `imt_dl_snr.csv` | Sim | amostras achatadas |
| `imt_dl_tput.csv` | Sim | proxy em bits/s/Hz, amostras achatadas |
| `imt_path_loss.csv` | Sim | amostras achatadas |
| `imt_coupling_loss.csv` | Sim | amostras achatadas |
| `imt_bs_antenna_gain.csv` | Sim | amostras achatadas |
| `imt_ue_antenna_gain.csv` | Sim | amostras achatadas |
| `imt_dl_tx_power.csv` | Sim | amostras achatadas dos feixes ativos |
| `num_of_active_beams.csv` | Sim | por snapshot |
| `num_of_sat.csv`, `num_of_candidate_sats.csv` | Sim | por snapshot |
| `system_inr.csv` | Sim | interferencia no sistema externo, agregado |
| Posicao UE/celula | Nao | descartada/nao persistida |
| Satelite associado | Nao | implicito em memoria, nao salvo |
| Feixe/beam ID | Nao | implicito por indice, nao salvo |
| Status de back-off por amostra | Nao | `tx_power` reflete, mas `backoff_db`/zona nao sao salvos |
| Status de servico | Parcial | so UEs de BS ativos entram nos KPIs; nao ha tabela de UEs nao servidos |

Ha informacao suficiente para CDF de SINR, percentil 5, media de SE proxy, outage por limiar e bootstrap dos KPIs agregados. Nao ha informacao suficiente para comparacao robusta entre feixes com/sem back-off, por satelite, por regiao ou fracao de usuarios atendidos, porque IDs e estados sao descartados.

## 11. Validade do throughput

`imt_dl_tput` nao deve ser chamado de throughput no texto cientifico principal. O nome no codigo e historico, mas a formula implementada e uma eficiencia espectral Shannon-like com fator de atenuacao, em `bits/s/Hz`.

Uso recomendado:

- Correto: "eficiencia espectral proxy baseada em Shannon", "SE proxy", "`imt_dl_tput` do SHARC".
- Incorreto: "throughput de usuario", "user-experienced data rate", "throughput de camada 3".

Para converter em `achievable rate proxy`, pode-se multiplicar por a banda efetiva do UE (`ue.bandwidth`) ou pela banda configurada, mas isso ainda nao vira throughput M.2514.

## 12. Metricas imediatas e metricas que exigem implementacao

Metricas utilizaveis imediatamente:

- CDF, media e percentil 5 de SINR (`imt_dl_sinr.csv`).
- CDF, media e percentil 5 de SNR (`imt_dl_snr.csv`).
- CDF, media e percentil 5 de SE proxy (`imt_dl_tput.csv`).
- Outage por limiar de SINR definido pelo pesquisador.
- Link margin por limiar de SINR definido pelo pesquisador.
- CDF de perda de percurso e ganhos.

Metricas que exigem implementacao adicional:

- SE por feixe/satelite/regiao com back-off identificado.
- Fracao de usuarios atendidos incluindo usuarios nao servidos.
- Intervalos bootstrap estratificados por feixe/satelite.
- Throughput PHY com MCS/BLER.
- Throughput MAC/L3.
- User-experienced data rate M.2514.

## 13. Recomendacao de campanha

Entre as tres opcoes:

1. `a) varredura de power back-off global`
2. `b) varredura de power back-off e fracao de feixes afetados`
3. `c) varredura de power back-off e largura de regiao geografica`

Recomendacao: comecar por `a)` na campanha 03, porque ela ja mede SINR e SE proxy do DC-MSS e o back-off global testa diretamente a degradacao do enlace desejado. Em seguida, executar `c)`, pois a arquitetura ja tem `power_control_zones` por geometria. A opcao `b)` deve ficar para a terceira etapa, pois exige novo mecanismo para escolher uma fracao de feixes e salvar quais foram afetados.

Antes de qualquer varredura, ajustar o gerador da campanha 03: hoje `generate_input.py` linhas 115-124 zera todos os `power_backoff_db`, entao ele remove justamente a variavel de interesse.

## 14. Plano minimo de implementacao

1. Preservar a estrutura da campanha 03, mantendo `imt_dl_intra_sinr_calculation_disabled: false`.
2. Alterar o gerador para parametrizar `power_backoff_db` em vez de zerar as zonas.
3. Para varredura global: uma zona cobrindo todos os feixes com `power_backoff_db = X`.
4. Para varredura geografica: variar `margin_from_border`, `grid_exclusion_zone` ou geometria de `power_control_zones`.
5. Persistir em CSV estruturado: `snapshot`, `ue_id`, `beam_id`, `sat_id`, `active`, `served`, `power_backoff_db`, `tx_power_dbm`, `rx_power_dbm`, `interference_dbm`, `noise_dbm`, `sinr_db`, `snr_db`, `bandwidth_mhz`, `beam_center_lat/lon`.
6. Calcular pos-processamento: SINR p5/media, SE proxy p5/media, outage, link margin e bootstrap.
7. Se M.2514 formal for indispensavel, implementar depois MCS, BLER, HARQ, overhead, trafego e bits L3 entregues.

## 15. Tabela de evidencias

| Afirmacao | Evidencia |
|---|---|
| Campanha 03 habilita SINR intra-IMT | `base_input.yaml` linha 144. |
| Campanha usa MSS_DC | `base_input.yaml` linhas 23-28. |
| Um UE por feixe/celula | `base_input.yaml` linhas 112-114; `station_factory.py` linhas 322-327. |
| Load factor e probabilidade de feixe ativo | `base_input.yaml` linha 87; `station_factory.py` linhas 139-141. |
| Power back-off existe no YAML base | `base_input.yaml` linhas 67-84. |
| Gerador 03 zera o power back-off | `generate_input.py` linhas 115-124 e 160-161. |
| Sinal desejado e calculado | `simulation_downlink.py` linhas 188-191. |
| Interferencia intra-IMT e calculada | `simulation_downlink.py` linhas 193-208. |
| Ruido/SINR/SNR sao calculados | `simulation_downlink.py` linhas 216-228. |
| Tput e Shannon-like | `simulation.py` linhas 687-720. |
| Outputs de desempenho sao coletados | `simulation_downlink.py` linhas 676-719. |
| Outputs sao uma coluna de samples | `results.py` linhas 201-223. |
| Plot da campanha usa SINR/tput/SNR/path loss | `plot_imt_performance_cdf.py` linhas 17-22 e 190-217. |

## 16. Veredito final das metricas

Classificacao: 1 = diretamente suportado; 2 = derivavel com outputs atuais; 3 = possivel somente como proxy; 4 = exige implementacao adicional; 5 = incompativel com a arquitetura atual.

| Metrica | Classificacao | Justificativa |
|---|---:|---|
| SINR por usuario | 1 | `imt_dl_sinr.csv` e salvo na campanha 03; falta apenas ID por amostra para analises por feixe/satelite. |
| Link margin | 2 | Derivavel de `imt_dl_sinr.csv` se for definido um limiar de SINR. |
| Outage | 2 | Derivavel como `Pr[SINR < limiar]`. |
| Eficiencia espectral pelo modelo de Shannon | 3 | `imt_dl_tput.csv` ja e uma proxy Shannon-like; nao e SE real de sistema. |
| Eficiencia espectral baseada em MCS/BLER | 4 | MCS/BLER nao existem. |
| Throughput de camada fisica | 4 | Nao ha modelo de bits/codificacao; so proxy bps/Hz. |
| Throughput MAC | 4 | Nao ha MAC/HARQ/overhead/trafego. |
| Throughput de camada 3 | 4 | Nao ha pacotes/SDUs/bits entregues. |
| User-experienced data rate da ITU-R M.2514 | 4 | Exige throughput L3 p5; nao implementado. |
| Eficiencia espectral media por feixe | 4 | Media global de proxy e derivavel; por feixe exige IDs por amostra. |
| Fracao de usuarios atendidos | 4 | Exige salvar UEs nao servidos/criterio de atendimento. |

## 17. Respostas objetivas finais

- Podemos usar a palavra "throughput" com os outputs atuais?  
  Nao no sentido da ITU-R M.2514. Para a campanha 03 existe `imt_dl_tput.csv`, mas ele deve ser chamado de eficiencia espectral proxy/Shannon-like em `bits/s/Hz`.

- Podemos comparar formalmente o resultado com a ITU-R M.2514?  
  Nao. Podemos apenas fazer uma comparacao aproximada e explicitamente qualificada entre a SE proxy e os valores 0.03/0.5 bit/s/Hz.

- Qual e a metrica mais rigorosa disponivel hoje?  
  SINR downlink por UE/celula em `imt_dl_sinr.csv`. A partir dela, outage e link margin por limiar definido sao defensaveis.

- Quais modificacoes minimas sao necessarias para medir o desempenho do DC-MSS-IMT sob power back-off?  
  Ajustar o gerador da campanha 03 para realmente varrer `power_backoff_db`, salvar IDs e estado por amostra (`ue_id`, `beam_id`, `sat_id`, `backoff_db`, `active`, `served`) e calcular SINR p5/media, outage, link margin e SE proxy. Para throughput M.2514, e necessario implementar camada de enlace/sistema com bits L3 corretamente entregues.

# Figuras para o congresso

## PNGs atuais

- `sharc_monte_carlo_methodology_labels.png`: versao corrigida para inserir
  no slide (3200 x 1100). Preserva parametros, nomes dos snapshots, legendas,
  frase S/I/N/SINR e metricas. Remove somente titulo geral, titulos das tres
  etapas e frase de fluxo do rodape. Segundo exemplo: duas celulas ativas
  e duas inativas. Gerador: `generate_methodology_overview.py`.
  As versoes abaixo sem texto e com titulos completos sao historicas.

- `sharc_monte_carlo_illustrations.png`: versao apenas ilustracoes, sem
  titulos, parametros, legendas ou rodape de slide. PNG 3200 x 1000.
  Mostra tres exemplos com 3, 2 e 3 celulas ativas, respectivamente;
  cada exemplo tem quatro celulas, com um UE por celula. Curvas esquematicas.
  Gerado por `generate_methodology_overview.py`; capa preservada.

- `cover_pbo_selective.png`: capa limpa, sem radiacao off-axis, receptor,
  anotacoes de sinal/interferencia ou suas setas. Mantem satelite, Brasil,
  celulas, feixes, titulo e legenda nominal/PBO.
- `sharc_monte_carlo_methodology.png`: nova metodologia em tres etapas:
  configuracao, Monte Carlo no SHARC e agregacao estatistica. Os tres
  snapshots desenhados sao exemplos esquematicos, sem IDs ou contagens reais.
  As posicoes, ativacoes e pequenas curvas sao ilustrativas, nao resultados.

Ambos: 3200 x 1800 px, 16:9, fundo branco. `sharc_snapshot_illustrated.png`
foi substituido na apresentacao; permanece somente como versao anterior.
As figuras em `v3/` nao foram alteradas nesta revisao.

Para gerar apenas a metodologia, sem tocar na capa ou nos dados:

```powershell
& '.\.venv\Scripts\python.exe' 'sharc\campaigns\03_DC_MSS_ISOLADO\presentation_assets\generate_methodology_overview.py'
```

`methodology_overview_validation.json` registra a verificacao da nova imagem.
O gerador nao le CSVs, nao reconstroi geometria e nao executa simulacoes.

## Historico: esquema anterior do snapshot

O usuario optou expressamente por **associacoes nao geograficas**. Os IDs,
estados ativo/inativo, mascara de PBO e totais vem do snapshot 1 ja salvo em:

`output/output_dc_mss_isolado_Sys3_340km_LF50_PBO10dB_F10pct_2026-07-28_02/`

Na rede completa desse snapshot:

- 25 satelites associados a celulas;
- 1472 feixes e 1472 UEs gerados;
- 717 feixes ativos e 717 UEs avaliados;
- 755 feixes inativos e 755 UEs nao avaliados;
- 72 feixes ativos com PBO, ou 10.041841% dos ativos.

LF=50% e uma probabilidade de ativacao por feixe, nao uma cota exata.
A fracao de PBO solicitada e 10%; sua contagem usa arredondamento para o
inteiro mais proximo: floor(0.1 * 717 + 0.5) = 72.

O desenho reduzido usa 19 associacoes reais, proximas da celula 1203 no
indice da grade: 2 satelites (4041 e 4042), 19 feixes/UEs, 10 ativos,
9 inativos e 1 com PBO. O feixe 1203 atende logicamente o UE 1203 e esta
associado ao satelite 4042. As 19 associacoes estao em `validation.json`.

As posicoes no desenho foram reorganizadas para leitura. Colocar o simbolo
de um UE dentro de um hexagono significa **associacao**, nao sua localizacao
fisica. Cones so aparecem nos feixes ativos. Circulos preenchidos identificam
UEs avaliados e circulos vazios identificam UEs nao avaliados. Inatividade
por carga nao e uma classificacao de outage.

A seta S identifica o enlace desejado de um UE selecionado. A seta vermelha
I mostra um exemplo de contribuicao interferente de outro satelite; o calculo
de I inclui a soma dos demais feixes ativos com recursos sobrepostos,
inclusive feixes do mesmo satelite. N e o ruido termico do receptor.
A formula SINR = S/(I+N) usa potencias lineares. Os resultados salvos usam dB.

## Conferencia contra o codigo e os resultados

Nao foi executada uma campanha, nem `SimulationDownlink.snapshot`, nem um
novo calculo de SINR. Foram reconstruidos somente a geometria e os sorteios
do primeiro snapshot, com a seed secundaria 2182114437, para conferir as
associacoes. O logger de resultados permaneceu sem diretorio de saida.
Nenhum CSV original foi alterado.

- `sharc/model.py`: seeds secundarias de `random.Random(838)`.
- `sharc/topology/topology_imt_mss_dc.py`: posicoes orbitais, transformacao
  da grade, selecao por elevacao e associacoes celula-satelite.
- `sharc/station_factory.py:sample_imt_base_station_active_mask`: sorteio
  Bernoulli com probabilidade LF por feixe.
- `sharc/simulation_downlink.py:select_active_beams_for_pbo`: selecao somente
  dos ativos, em RNG separado, com mascara aninhada.
- `sharc/station_factory.py:generate_imt_ue_outdoor`: numero de UEs por
  feixe = k * k_m = 1 * 1 = 1.
- `sharc/simulation.py:connect_ue_to_bs/select_ue`: somente os UEs dos
  feixes ativos sao ativados para avaliacao.
- `sharc/simulation_downlink.py:calculate_sinr`: S, soma de I, N, SINR e SNR.

As listas completas de IDs ativos e com PBO coincidem com o CSV estruturado
salvo. Os totais por satelite coincidem com os logs existentes. A verificacao
das distancias UE-satelite contra os 717 path losses salvos apresentou erro
maximo de 2.84e-14 dB, usando a mesma formula FSPL do SHARC.

### Ressalva de geometria

A reconstrucao revelou que o caminho atual `SERVICE_GRID` retorna
`sectors_x = sectors_y = 0`, e `UNIFORM_IN_CELL` usa essas ancoras em
`StationFactory.get_random_position`. Assim, os UEs reproduzidos ficam perto
da origem de referencia, nao distribuidos nas respectivas celulas geograficas
da grade. A distancia UE-centro da celula associada tem minimo de 99.127 km,
mediana de 1082.591 km e maximo de 1731.720 km neste snapshot.

Esse comportamento foi comunicado ao usuario, que escolheu o esquema nao
geografico. O desenho nao corrige nem valida essa modelagem. Nenhuma equacao
ou rotina fisica da simulacao foi modificada.

## Capa

O satelite e a paleta sao reutilizados das figuras anteriores. O contorno
brasileiro vem da base Natural Earth existente no repositorio. A malha e
deliberadamente simplificada para projecao: o raio de desenho e 150 km,
nao os 25.803 km da campanha. As 18 celulas laranja sao escolhidas por RNG
com seed 838, apenas para ilustrar a selecao dispersa. Nao representam um
snapshot real nem uma estimativa da fracao afetada na campanha.

Sao explicitados seis feixes nominais e dois com PBO. O PBO e codificado por
cor e intensidade, nunca por estreitamento ou alteracao do footprint. O
mesmo conjunto de vertices seria usado para desenhar cada feixe em potencia
nominal. As intensidades sao ilustrativas, nao uma escala quantitativa de dB.

`validation.json` registra a checagem de tamanho, sobreposicao de textos,
limites da imagem e as associacoes usadas no esquema. Fonte minima: 19 pt na tela de
3200 px, equivalente a aproximadamente 32 px quando exibida a 1920 px.

## Regerar

Na raiz do repositorio:

```powershell
& '.\.venv\Scripts\python.exe' 'sharc\campaigns\03_DC_MSS_ISOLADO\presentation_assets\generate_congress_figures.py'
```

O gerador atual produz a capa e a metodologia de tres etapas. O cache
`snapshot_1_geometry.json` pertence apenas ao esquema anterior e nao e usado
pela metodologia atual. As figuras sao inspecionadas tambem em 1280 x 720.

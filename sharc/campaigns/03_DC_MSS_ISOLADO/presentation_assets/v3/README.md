# Figuras da apresentacao - malha hexagonal e estilo do paper

## PNGs finais

- cover_pbo_brazil.png: 3000 x 1688, capa sem texto.
- itu_pbo_overview_brazil.png: 2400 x 2400, malha nacional e destaque geografico.
- itu_pbo_zoom_border.png: 2400 x 2400, mecanismo local antes/depois.

Fundo branco, paleta suave azul/laranja do paper, interferencia salmao e
receptor verde. Nenhum celular foi desenhado. As duas figuras quadradas foram
inspecionadas lado a lado a 876 pixels de largura em um slide 1920 x 1080.

## Reutilizacao do desenho original

O satelite foi renderizado diretamente pela funcao create_satellite de
../illustration/generate_pbo_illustration.py, usando seus materiais e iluminacao.
Nao foi redesenhado por um gerador de imagens. O PNG transparente intermediario
e a cena Blender estao nesta pasta. Os scripts do paper nao foram alterados.

## Geometria e significado

O mapa usa o contorno Natural Earth disponivel em sharc/data/countries.
A malha foi construida em projecao Lambert Azimuthal Equal Area, com raio
de 25803 m, como no base_input.yaml da Campanha 03. Os hexagonos sao regulares
nessa projecao e recortados no contorno do Brasil. A inclinacao da capa e a do
zoom sao recursos de representacao visual.

Foram desenhadas 5163 celulas, incluindo recortes parciais de fronteira.
A uniao cobre o poligono do Brasil, com area exterior e area descoberta nulas
na verificacao geometrica. Esse numero nao e a quantidade de feixes ativos em
um snapshot. geometry_validation.json registra os valores da verificacao.

Na capa, as celulas com PBO sao sorteadas somente entre feixes ativos pela
propria funcao SimulationDownlink.select_active_beams_for_pbo. O desenho usa
LF=50%, fracao solicitada de 10% e seed ilustrativa 838. A atividade e sorteada
com um RNG independente daquele usado pelo seletor de PBO. Foram obtidos
2434 feixes ativos e 243 selecionados (9,9836%), sem PBO em feixes inativos.
A repeticao do seletor confirmou uma mascara identica. Nao se trata de um
snapshot recuperado dos resultados: a geometria nacional e ilustrativa.
As celulas azuis fornecem o contexto da malha, sem codificar visualmente a
atividade; os enlaces explicitamente desenhados terminam em celulas ativas.

Na imagem 2, o PBO e geografico, formando um anel ao longo de TODO o contorno
do Brasil, inclusive o litoral. Essa escolha acompanha a geometria
FROM_COUNTRIES do repositorio: pais menos o interior recuado por buffer
negativo. O anel desenhado tem largura ilustrativa de dois raios de celula
(51,606 km), sem pretender fixar a largura para todos os casos da contribuicao.
Ha 745 celulas laranja nessa figura. Esse anel de potencia nao deve ser
confundido com uma zona de exclusao ou uma area sem cobertura.

Evidencias da geometria: parameters_grid.py, _calculate_polygon de from_countries,
recuo com shrink_countries_by_km; sharc_geom.py, shrink_lonlat_polygon_by_km,
polygon_proj.buffer(-km * 1000); topology_imt_mss_dc.py, get_satellite_pointing,
prioridade da zona interior de PBO=0 sobre a zona do pais inteiro.
No Script/base_input.yaml da campanha 02_DC_MSS_to_FS 2, power_control_zones
usa essas duas zonas FROM_COUNTRIES. O desenho ilustra essa regra geometrica,
nao um resultado quantitativo de compatibilidade do documento ITU-R.

A malha nacional representa a distribuicao de celulas; apenas alguns enlaces
sao desenhados para comunicar a operacao multifeixe. A capa usa tres satelites
menores do mesmo modelo do paper, com enlaces distribuidos sobre o territorio.
As posicoes e associacoes ilustradas nao representam uma solucao orbital ou
uma predicao de cobertura simultanea. A mascara aleatoria de PBO foi mantida.

No zoom, mantem-se a malha e o receptor antes/depois. O PBO modifica a cor e a
intensidade dos feixes selecionados. Os lobulos principais sao identificados
sobre as celulas, com boresights para o lado brasileiro. A radiacao off-axis
e representada por regioes secundarias difusas, contiguas aos dois feixes de
servico desenhados junto a fronteira. Essas regioes sao calculadas a partir
da direcao e das bordas dos feixes de servico, sem usar a posicao do receptor
para aponta-las. Nao ha um cone fechado, eixo proprio, secao eliptica ou feixe
deliberadamente dirigido a vitima. A radiacao off-axis pode incluir roll-off
do lobulo principal e/ou lobulos laterais, sem identifica-la exclusivamente
como um destes mecanismos.

No painel (b), "Feixes com PBO" e "PBO = 10 dB" identificam os feixes reduzidos.
A geometria dos feixes principais e das regioes off-axis e identica nos dois
paineis. O PBO altera apenas a potencia transmitida: com ganho de antena fixo,
EIRP_PBO(theta, phi) = EIRP_nominal(theta, phi) - 10 dB em todas as direcoes.
Nenhuma abertura, apontamento, roll-off ou formato relativo e modificado.
Na ilustracao, o mesmo fator visual e aplicado a cada feixe reduzido e a sua
regiao off-axis. A opacidade usa (10^(-PBO_dB/10))^0.25 para preservar a
visibilidade em projecao; nao e uma escala quantitativa de potencia ou EIRP.
O ganho visual da regiao off-axis foi reforcado para 0.28, e os rotulos foram
simplificados para "Radiacao off-axis" e "Menor radiacao off-axis".
Os feixes nao submetidos ao PBO permanecem visualmente inalterados. As cores
das celulas indicam categorias (nominal ou com PBO), nao potencia recebida.
Nao se trata de um diagrama quantitativo de radiacao da antena. Os lideres
das anotacoes sao ancorados no bounding box dos textos, com espacamento de
3 pt, em vez de partir de coordenadas independentes dos rotulos.
O receptor foi aproximado da fronteira, mantendo toda sua base no pais
vizinho. O satelite conserva a maior separacao vertical em relacao ao solo.
Receptor e celulas compartilham
um unico plano de terreno verde muito claro, usando a mesma projecao geometrica.
A fronteira tracejada atravessa todo esse plano, separando o receptor no
"Pais vizinho" das celulas no "Brasil". No zoom, o contorno da fronteira segue
exatamente as arestas da malha hexagonal. Toda a parte brasileira do terreno
e preenchida por celulas, recortadas somente nas bordas externas do plano,
sem uma faixa vazia junto a fronteira. Esse alinhamento e uma simplificacao
didatica, nao a geometria real de uma fronteira nacional nem uma comprovacao
de disponibilidade de sinal. Os rotulos dos paises ficam fora da malha.
A base do receptor e projetada sobre o terreno para tornar explicita sua
posicao no solo. A anotacao "Esquema sem escala" foi removida do PNG a pedido
do autor; tamanhos, distancias, espessuras e intensidades continuam qualitativos.
As celulas nao sao fontes de retransmissao; o verde nao certifica conformidade.

## Regerar

Execute a partir de C:\GitHub\SHARC:

```powershell
& 'G:\Blender\blender.exe' --background --python 'sharc\campaigns\03_DC_MSS_ISOLADO\presentation_assets\render_original_satellite.py'
& '.\.venv\Scripts\python.exe' 'sharc\campaigns\03_DC_MSS_ISOLADO\presentation_assets\generate_hex_presentation_images.py'
```

Para atualizar apenas o mecanismo local, adicione `--figures mechanism`
ao ultimo comando. A capa e o mapa aprovados foram preservados nesta revisao:

- SHA256 da capa: `CF9F16E91044E4C3F9453FA545DEB3227ADC9C93F00A5DD70DEDAE9CED4101C5`.
- SHA256 do mapa: `47B571C3664EA9F62CBC23112B67C41352510F0726D188D499E4A14619AEE65A`.

Nenhuma simulacao foi executada. Os resultados brutos e as versoes anteriores
das figuras foram preservados.

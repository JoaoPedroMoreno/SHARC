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

Na imagem 2, o PBO e geografico, somente junto as fronteiras terrestres do
Brasil. A linha de fronteira e extraida da intersecao do limite brasileiro
com os limites dos demais paises do mesmo mapa Natural Earth. O litoral nao
e usado para gerar a faixa. Os limites compartilhados incluem a fronteira
com a Guiana Francesa, identificada como France na base cartografica.
O contexto inclui os contornos dos dez vizinhos terrestres: Argentina,
Uruguai, Paraguai, Bolivia, Peru, Colombia, Venezuela, Guiana, Suriname e
Guiana Francesa. Todos mantem o mesmo cinza claro #DCE4E8 e espessura de
0.9 pt, recortados na janela do mapa, sem alterar a escala do Brasil.
A faixa tem largura ilustrativa de dois raios de celula (51,606 km), buffer
com extremidades planas e recorte no territorio brasileiro. Os hexagonos sao
selecionados pelo ponto representativo de sua parte dentro do pais. A
contagem de celulas laranja esta em geometry_validation.json. A faixa nao
deve ser confundida com uma zona de exclusao ou uma area sem cobertura.

Esta revisao modifica somente a ilustracao, conforme solicitado pelo autor.
Nao modifica o mecanismo FROM_COUNTRIES, os YAMLs ou os resultados de
simulacao. O buffer negativo do poligono inteiro usado na versao anterior
incluia o litoral; ele nao e usado para a faixa da imagem 2 atual.
A figura permanece esquematica, nao um resultado quantitativo de
compatibilidade do documento ITU-R.

A malha nacional representa a distribuicao de celulas; apenas alguns enlaces
sao desenhados para comunicar a operacao multifeixe. A capa usa tres satelites
menores do mesmo modelo do paper, com enlaces distribuidos sobre o territorio.
As posicoes e associacoes ilustradas nao representam uma solucao orbital ou
uma predicao de cobertura simultanea. A mascara aleatoria de PBO foi mantida.

No zoom, mantem-se a malha e o receptor antes/depois. O PBO modifica a cor e a
intensidade dos feixes selecionados. Os lobulos principais sao identificados
sobre as celulas, com boresights para o lado brasileiro. A radiacao off-axis
e representada por duas faixas secundarias suaves, uma junto a borda de cada
feixe de servico desenhado junto a fronteira. Esta revisao parte da versao
com dois nucleos opacos e nevoa ampla, anterior a suavizacao geral do centro.
A opacidade maxima dos nucleos foi mantida, com area central mais opaca
estreita e transicao continua ate a nevoa. O nucleo usa um unico perfil
exponencial suavizado em duas dimensoes: exp(0.8 - sqrt(0.8^2 + q)), com
q = (desvio_angular/1.8_graus)^2 + ((distancia_normalizada-0.85)/0.23)^2.
O pico normalizado permanece igual a 1. O decaimento varia suavemente tanto
nas laterais como ao longo da faixa, removendo o trecho extenso de opacidade
constante e a separacao marcada entre uma linha escura e a nevoa.
A nevoa ampla foi preservada (sigma de 12 graus, peso 0.48 fora do nucleo),
assim como seu decaimento radial gaussiano. As partes translucidas se
sobrepoem e conectam os dois nucleos claramente identificaveis. Mantem-se o esmaecimento junto ao
satelite para nao sugerir emissao uniforme de toda a sua lateral. Sao calculadas a partir
da direcao e das bordas dos feixes de servico, sem usar a posicao do receptor
para aponta-las. Nao ha um cone fechado, eixo proprio, secao eliptica ou feixe
deliberadamente dirigido a vitima. A radiacao off-axis pode incluir roll-off
do lobulo principal e/ou lobulos laterais, sem identifica-la exclusivamente
como um destes mecanismos.

No painel (b), "Feixes submetidos a PBO" identifica os feixes reduzidos.
O nivel ilustrativo de 10 dB permanece no script, sem rotulo numerico no PNG.
A geometria dos feixes principais e das regioes off-axis e identica nos dois
paineis. O PBO altera apenas a potencia transmitida: com ganho de antena fixo,
EIRP_PBO(theta, phi) = EIRP_nominal(theta, phi) - 10 dB em todas as direcoes.
Nenhuma abertura, apontamento, roll-off ou formato relativo e modificado.
Na ilustracao, o mesmo fator visual e aplicado a cada feixe reduzido e a sua
regiao off-axis. A opacidade usa (10^(-PBO_dB/10))^0.25 para preservar a
visibilidade em projecao; nao e uma escala quantitativa de potencia ou EIRP.
O ganho visual de cada faixa off-axis e 0.74, com vermelho mais escuro
(#BF5750), para reforcar o contraste em projecao. O reforco e aplicado aos
dois paineis sem alterar a geometria nem a razao de intensidade visual entre
eles. A opacidade maxima de cada regiao isolada e aproximadamente 0.740
sem PBO e 0.416 com PBO, antes da sobreposicao das duas regioes. Os rotulos foram
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
ao ultimo comando. Para atualizar apenas o mapa, use `--figures overview`.
A capa e o mecanismo local foram preservados na revisao das fronteiras:

- SHA256 da capa: `CF9F16E91044E4C3F9453FA545DEB3227ADC9C93F00A5DD70DEDAE9CED4101C5`.
- SHA256 do mecanismo: `0DFAC6F9F4ED2F83FE590E2027F2CE0D3B1082E690683D3C3204060D1CB90602`.

Nenhuma simulacao foi executada. Os resultados brutos e as versoes anteriores
das figuras foram preservados.

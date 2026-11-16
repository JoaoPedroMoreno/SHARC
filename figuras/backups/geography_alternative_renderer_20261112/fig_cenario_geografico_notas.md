# Cenario geografico do TCC2

Figura: `fig_cenario_geografico.png`, 3200 x 2200 pixels.

Renderizada com Cesium 1.120 e o fundo cartografico do visualizador NGSO
usado nos slides Latincom. A grade hexagonal dourada representa celulas com
associacao geometrica no instante orbital t=0 do System 3, a 340 km.
As posicoes sao calculadas pelo OrbitModel nativo do SHARC. A grade fixa segue
o frontend NGSO (raio de 25.803 km), com associacao por maior elevacao e limiar
de 32 graus, usando calc_elevation nativo. Nao sao snapshots dos outputs de INR.
Verde identifica satelite com ao menos uma celula associada; ciano indica outro
satelite. Os cones sao envelopes ilustrativos das celulas atendidas, nao
contornos de ganho ou lobulos de radiacao calculados. Assim como no perfil
de apresentacao, ha no maximo dez envelopes por vista para evitar poluicao.
Os vertices 3D sao projetados pela camera Cesium em uma camada de exportacao.
O Paraguai aparece sem atendimento DC-MSS-IMT: os centros sao filtrados e a
malha desenhada e recortada nos limites dos paises para nao invadir o Paraguai.
Nao ha zona circular de exclusao, power back-off, handover ou sorteio de
atividade LF representados nesta figura. "Em servico" refere-se a associacao
geometrica do visualizador, nao a ativacao probabilistica do Monte Carlo.

## Posicao do receptor

Por escolha explicita do usuario, esta figura representa o cenario pretendido
em Ciudad del Este, Paraguai. O marcador usa a referencia urbana aproximada
latitude -25.5169, longitude -54.6169, nao a localizacao de uma estacao real.
Referencia: https://mapcarta.com/Ciudad_del_Este (dados OpenStreetMap/GeoNames).

A campanha 07 permanece com latitude -25.5549751, longitude -54.5746686.
A figura NAO documenta essa posicao simulada. Nenhum YAML ou output foi alterado.
Nao usar a figura como prova de que os resultados existentes foram obtidos
com o receptor em Ciudad del Este.

## Area de atendimento

Lista lida diretamente de `07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml`:
Argentina, Bolivia, Brazil, Chile, Colombia, Ecuador, Peru, Uruguay,
Venezuela, Guyana e Suriname. Paraguai e Guiana Francesa nao integram a lista.
Assim, a expressao "toda a America do Sul, exceto Paraguai" no texto deve
ser entendida como os 11 paises configurados, nao todos os territorios.

Fronteiras: Natural Earth 1:110m local, o mesmo conjunto cartografico do SHARC.
Limites generalizados sao adequados ao enquadramento continental e regional,
mas nao permitem resolver a qual pais pertence um ponto a poucos quilometros
de uma fronteira. Nao inferir precisao cadastral a partir do detalhe ampliado.
Creditos de imagem cartografica sao preservados no rodape.

## Reproducao

1. Executar `tools/prepare_tcc_geography.py` com Python e os leitores locais.
2. Executar `node tools/capture_tcc_geography.cjs`.

O capturador abre um servidor local temporario em porta livre e um Chrome
headless separado. Nao inicia simulacoes SHARC e nao altera o visualizador
NGSO original. HTML e JavaScript especificos ficam em `tools/tcc_geography.*`.
O JSON `tcc_geography_data.json` registra a origem, lista de paises, coordenadas
da figura e coordenadas da campanha para rastreabilidade.

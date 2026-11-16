# Figuras didaticas: perdas e bootstrap

Gerador: `tools/generate_tcc_explanatory_figures.py`.
Arquivos finais: PNG a 600 dpi e PDF vetorial, com o mesmo nome-base.
As figuras sao conceituais: nao contem novos resultados de campanha nem executam o SHARC.
O esboco original em Downloads foi preservado.

## Perdas no enlace

Nome-base: `esboco_figura2_perdas_enlace`.

Para a mesma frequencia, uma distancia obliqua menor resulta em menor perda
em espaco livre. Nao se deve concluir que todas as demais perdas sao menores
em LEO: elas dependem da geometria, polarizacao, ambiente e modelo adotado.
As distancias e a espessura da atmosfera no desenho nao estao em escala.
O desenho nao implica a aplicacao simultanea de todos esses mecanismos em
todos os enlaces da campanha. Em particular, a base atual da campanha 08
usa FSPL no enlace IMT e P.619 no enlace com a vitima FS.

Os satelites usam o mesmo `satellite_from_paper.png` dos slides Latincom.
O receptor e um UE, com o mesmo desenho de terminal dos slides Latincom;
nao representa a antena FS, pois esta figura explica o enlace de servico.
Os edificios usam `figuras/tcc_assets/urban_obstruction.png`, renderizado
no Blender por `tools/render_tcc_urban_asset.py`, com os materiais do satelite
original. O modelo editavel esta na mesma pasta. Os arquivos do Latincom nao
foram alterados. Os satelites foram rotacionados na composicao para orientar
suas antenas na direcao do UE. Os edificios interceptam os trajetos diretos
ilustrativos; o trecho interno e tracejado, nao um raio que atravessa
sem perdas o edificio. A cena e conceitual, sem escala e nao descreve uma
realizacao especifica ou garante NLOS em todos os snapshots. Na revisao atual,
a camera urbana e quase frontal, os edificios estao alinhados no solo e
afastados do UE. Os trajetos usam a silhueta dos edificios para delimitar
trechos internos: tracejados finos e semitransparentes, sem contorno branco.
Fora dos edificios, as linhas sao continuas. Essa convencao indica um trajeto
obstruido, sem implicar propagacao sem atenuacao nem quantificar penetracao.
Ambas as figuras estao sem titulos gerais e sem rodapes.
O PDF de perdas combina textos e linhas vetoriais com os renders incorporados;
nao e um PDF puramente vetorial. O PDF de bootstrap permanece vetorial.

Referencia fisica: ITU-R P.525-5, Calculation of free-space attenuation:
https://www.itu.int/rec/R-REC-P.525-5-202411-I/en

## Bootstrap

Nome-base: `fig_bootstrap_inr_incerteza`.

Procedimento conferido em:
- `sharc/campaigns/02_DC_MSS_to_FS 2/Script/bootstrap_inr20_confidence.py`
- `sharc/campaigns/02_DC_MSS_to_FS 2/Script/plot_system_inr_margin_heatmap.py`
- `tmp/tcc2_bootstrap_ho_20261031.py`, que reutiliza o procedimento na campanha 07.

Para cada cenario, o codigo seleciona as N amostras finitas de INR, calcula
o percentil empirico 80 pelo elemento de ordem ceil(0.8*N), e gera B=10000
reamostras de tamanho N, com reposicao. O mesmo estimador e calculado em
cada reamostra. O IC percentil de 95% usa np.quantile nos niveis 0.025 e 0.975
das estimativas bootstrap. A seed padrao de bootstrap e 20260727, separada
da seed da simulacao. O gerador das figuras nao executa esse bootstrap.

O ponto M20 usa o INR20 da amostra original, nao a media das estimativas
bootstrap. Se o IC do INR20 e [q_inf, q_sup], o IC de M20 e
[-6-q_sup, -6-q_inf]. A classificacao implementada e:
- Conforme: limite inferior do IC da margem >= 0.
- Nao conforme: limite superior do IC da margem < 0.
- Limitrofe: demais casos.

A figura mostra um exemplo numerico ficticio com cinco snapshots
(-12, -9, -7, -5, -3 dB), duas reamostras explicitas e seus percentis 80.
Na ordem decrescente, o indice do estimador e N-ceil(0.8*N), baseado em zero;
para N=5, corresponde ao segundo valor. As repeticoes dos IDs ilustram o
sorteio aleatorio com reposicao, nao uma regra sobre qual snapshot repetir
nem uma simples permutacao dos valores.
O IC e representado pelos percentis delimitadores (2.5 e 97.5) das estimativas,
sem limites numericos ficticios. A curva em sino e somente ilustrativa:
nao impoe normalidade nem substitui o IC percentil por um IC normal.
Isso nao altera o bootstrap de producao, que continua usando numpy.
Os dados e parametros do exemplo estao em `bootstrap_exemplo_didatico.json`.
A imagem termina no IC, sem a conversao em margem ou classificacao.
O procedimento nao supoe distribuicao gaussiana do INR.
O IC representa incerteza amostral do estimador, nao a faixa contendo 95%
dos snapshots e nao a incerteza do modelo fisico. A reamostragem individual
pressupoe snapshots adequados ao bootstrap i.i.d.; dados temporais correlacionados
exigiriam outra justificativa/metodologia. A figura descreve ICs por cenario,
nao um teste pareado da diferenca entre duas tecnicas.

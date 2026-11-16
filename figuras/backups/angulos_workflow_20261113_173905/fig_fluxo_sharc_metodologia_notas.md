# Fluxo das campanhas 07 e 08

Arquivo: `fig_fluxo_sharc_metodologia.png`, 5120 x 3040 pixels.
Tambem disponiveis SVG e preview. O SVG preserva o desenho vetorial e incorpora
os modelos de satelite e antena do Blender como imagens.
Gerador: `tools/generate_tcc_simulation_workflow.py`.

Reaproveita o estilo de `tools/generate_fs_mitigation_methodology.py` e as
primitivas e assets de `tools/latincom_visual_style.py`. As figuras originais
LATINCOM/Encom nao foram modificadas.

## Conteudo verificado

- Oito cenarios-base: 340/525 km, LF 20/50%, FS 20/40 m.
- Atendimento na America do Sul, exceto Paraguai, conforme a lista dos YAMLs.
- Baseline, PBO e handover sao alternativas, nao etapas sequenciais.
- PBO de 10 dB na faixa externa a fronteira paraguaia, de 10 a 100 km.
- Handover nao temporal, com limites de 5, 10, 15, 20, 25 e 30 trocas aceitas
  por snapshot. Limite nao significa quantidade obrigatoria de trocas.
- Campanha 07: N = 10 000 snapshots por configuracao, desempenho UE desativado.
- Campanha 08: N = 1 000 snapshots por configuracao, desempenho UE ativado.
- Snapshots sao realizacoes independentes, nao instantes consecutivos.

As duas campanhas executam sua propria matriz. A bifurcacao indica os dois
objetivos de analise, nao que a campanha 08 apenas processe resultados da 07.
A campanha 08 ainda calcula INR no FS para decidir o handover, embora seu
objetivo de analise seja o desempenho dos UEs. Os pequenos graficos CDF/CCDF
sao puramente esquematicos; nao foram extraidos de outputs nem recalculados.
O esquema nao detalha a ordem interna de cada funcao do SHARC: a aplicacao
do PBO e o controle iterativo do handover seguem suas implementacoes existentes.

Os pontos ocre sao UEs e as setas vermelhas tracejadas representam contribuicoes
interferentes para o FS. Geometrias e estados de atividade sao ilustrativos.
As curvas nao ilustram diferencas quantitativas entre tecnicas.
O indicador de eficiencia espectral e um proxy, nao throughput medido.

## Legenda sugerida

Fluxo geral das campanhas de simulacao Monte Carlo no SHARC, desde a
configuracao dos cenarios e da estrategia de mitigacao ate a analise estatistica.
A campanha 07 utiliza 10 000 snapshots por configuracao para avaliar o FS,
enquanto a campanha 08 utiliza 1 000 para avaliar o desempenho dos UEs.
As geometrias e distribuicoes apresentadas sao esquematicas.

Fonte: elaboracao propria.

Nenhuma simulacao foi executada e nenhum input ou resultado foi alterado.

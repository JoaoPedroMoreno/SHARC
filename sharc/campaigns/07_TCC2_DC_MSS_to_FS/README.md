# TCC2: varredura de handover e PBO

## Analise da vitima sem desempenho dos UEs

Os novos inputs em `input/` usam 10000 snapshots e a opcao existente do SHARC:

```yaml
imt:
  imt_dl_intra_sinr_calculation_disabled: true
```

O modo pula os enlaces internos e o SINR dos UEs no inicio e apos cada troca.
Geometria dos usuarios, atividade, recursos, elegibilidade e restricoes do
handover continuam iguais. As decisoes atuais nao usam SINR dos UEs.
Os registros indicam `ue_performance_calculated=false`; SINR e outras medidas
nao calculadas ficam NaN, e atendimento/outage/perda ficam vazios, nao zero.
As posicoes e identidades de todos os usuarios continuam na simulacao.
Somente os inputs HO exportam tabelas detalhadas por usuario/link;
baseline e PBO preservam os registros resumidos de INR.

Para avaliar desempenho futuramente, mudar essa opcao para false no base.
Se forem necessarias tabelas individuais tambem de baseline/PBO, ajustar a
politica `record_detailed_links_and_users` no generate (atualmente somente HO).
Regenerar com o numero de snapshots desejado. Conferir pareamento das
realizacoes antes de comparar as duas analises. Nao alterar a opcao enquanto
um lote estiver em execucao. A validacao continua restrita a FSPL nos enlaces
de servico, que nao consome numeros aleatorios nesse calculo omitido.

Nao ha retomada automatica dos snapshots; um novo run inicia novas execucoes.
O run padrao executa somente os YAMLs pendentes deixados em `input/`. Resultados
anteriores nao sao alterados pelo gerador. Os inputs oficiais ficam somente
em `input/`, que e a pasta lida pelo run. A antiga pasta de preparacao
`input_HO30_ready/` foi removida.

## Estrutura

```text
Scripts/
    base_input.yaml
    generate.py
    run_multiple_campaigns_mut_thread.py
    plot_system_inr_ccdf.py
    validate_physics.py
input/
output/
plots/system_inr_ccdf/
```

O fluxo e o mesmo das demais campanhas: editar o base, gerar os inputs,
executar o run e, depois, gerar as imagens. Nao ha runner pareado separado.

## Inputs

Matriz completa: 2 altitudes (340/525 km) x 2 alturas FS (20/40 m) x
2 LFs (20/50%) x 17 tratamentos = 136 cenarios:

| Tratamento | Handover | PBO |
| --- | --- | --- |
| BASELINE | desligado | desligado |
| HO5, HO10, HO15, HO20, HO25, HO30 | limite de trocas aceitas e top_k iguais ao numero do caso | desligado |
| PBO10km ate PBO100km, passo 10 km | desligado | 10 dB na faixa externa correspondente do Paraguai |

HO e PBO NAO sao combinados. O limite nao obriga trocas: para ao atingir
INR <= -6 dB, esgotar a busca nos top_k feixes iniciais ou atingir o limite aceito.
Cada celula continua limitada a uma reassociacao aceita por snapshot.

## Fila pendente

O gerador consulta manifestos, configuracoes executadas e snapshots salvos.
Um caso so e considerado concluido se a configuracao corresponder ao base/perfil,
o manifesto marcar conclusao e os snapshots confirmados estiverem no CSV.
Uma alteracao de seed, parametros ou quantidade de snapshots impede esse reuso.
Somente o caminho do diretorio de saida e a opcao de exportacao detalhada
sao ignorados na comparacao; os parametros fisicos continuam obrigatorios.

Por solicitacao do usuario, os HO30 existentes tambem ficam fora da fila mesmo
parciais (`PRESERVE_PARTIAL_MODES = {"HO30"}`). Eles NAO sao marcados como
concluidos: o relatorio usa `preserved_partial_by_request`. Nao ha retomada
automatica, nem alteracao dos manifestos originais. Sem resultado compativel,
um caso HO30 ainda e gerado normalmente.

Na preparacao de 28/10/2026: 16 casos concluidos (8 baseline + 8 PBO100km),
8 HO30 parciais preservados e 112 inputs pendentes (40 HO5/10/15/20/25 +
72 PBO10/20/30/40/50/60/70/80/90km). O run nao repete os 24 casos excluidos.
`input/generation_report.json` lista os inputs criados e as fontes de reuso.
Ao terminar novos casos, execute generate novamente antes do proximo run para
retirar seus inputs da fila. Nao execute generate com um lote ainda ativo.

Todos usam a mesma service grid nos 11 paises sul-americanos da lista do base,
sem Paraguai. O PBO nao altera nem exclui pontos dessa grid. No base, a zona
Paraguay com margem zero e back-off zero tem prioridade; a segunda zona usa
Paraguay com margem -100 km (expansao externa) e back-off 10 dB. Assim, os
pontos fora do pais, mas dentro da faixa expandida, recebem a reducao. A
fronteira e a geometria do shapefile existente do SHARC, nao um novo mapa.

Isso e diferente do antigo PBO sobre as bordas de Brasil/Argentina: aqui a
referencia e somente a fronteira do Paraguai, conforme a proposta do TCC2.

`generate.py` parte de `base_input.yaml` e altera somente o perfil orbital,
altura/clutter FS, LF, limite HO, distancia PBO, exportacao detalhada por tratamento
e nome de saida. Os demais parametros vem
do base. SYSTEMS e FS_HEIGHTS no gerador definem os perfis. Ele gera os inputs
pendentes e remove somente inputs obsoletos ou reutilizados com nomes desta campanha.
Nao modifica outputs nem outras campanhas.

## Armazenamento no D e exportacao compacta

O destino de NOVOS resultados e definido somente em `Scripts/base_input.yaml`:

```yaml
general:
  output_dir: D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS
```

O generate preserva esse caminho nos inputs. O run padrao nao muda, e o
SHARC cria as subpastas de cada execucao no destino. Codigo, inputs, ambiente
Python e figuras continuam no C. Os outputs antigos nao sao movidos/apagados.
Para mudar o destino, editar o base e regenerar com o lote parado.

Por padrao, o gerador e o plot consultam tanto `output/` local quanto o destino
do base. `--results-dir` (generate) e `--output-root` (plot) podem ser repetidos
para escolher explicitamente as pastas de leitura. Nenhum desses argumentos
move arquivos. Nao iniciar uma campanha se o D estiver indisponivel/sem espaco.

No base (PBO), `imt.topology.mss_dc.interference_aware_handover_v2` inclui:

```yaml
record_detailed_links_and_users: false
```

O generate define essa opcao como true somente nos HO5/10/15/20/25/30 e
como false no baseline e em todos os PBO. O calculo de desempenho dos UEs
continua desligado nos tres tratamentos; reativar exports nao calcula SINR.
O valor false desliga SOMENTE os exports `tcc2_links.csv.gz` e `tcc2_users.csv.gz`.
Os arquivos foram adicionados para a auditoria TCC2; nao sao exports padrao
do SHARC. Links tambem servem para decompor a interferencia por feixe, nao
apenas desempenho. Sem eles, essa auditoria individual posterior fica limitada.
Nao se altera geometria, usuarios, atividade, potencia, restricoes, RNG,
calculo de INR ou decisoes de handover. Mantem snapshots, steps, candidates,
events, manifesto, hashes de pareamento e os CSVs normais do SHARC.
CCDF, INR20, M20 e bootstrap por snapshot nao precisam das duas tabelas.
Quando omitida, a opcao vale true, preservando as outras configuracoes.
Mudar a verbosidade nao torna um resultado INR antigo incompativel para reuso.
O gerador nao apaga outputs antigos. Na limpeza autorizada de 28/10/2026,
somente essas duas tabelas foram removidas dos oito baseline e oito PBO100km
existentes. Os arquivos de INR, manifestos, configuracoes e todos os outputs
HO foram preservados. Desligar a gravacao, por si so, nao remove arquivos.

O base mantem 10000 snapshots por arquivo: 1120000 novos snapshots na fila
de 112 casos. Para uma previa menor, altere `general.num_snapshots` no base antes
de executar generate.py. A potencia nominal continua 42.8 dBm; nos feixes
afetados pelo PBO passa a 32.8 dBm. Beam radii: 25803 e 39844 m.

FS preservado em (-25.5549751, -54.5746686), referencia 200 m, lookup FOZ.
Azimute 90 graus e norte na convencao do codigo; elevacao zero e horizontal.
Frequencia 2155 MHz, bandas nominais IMT/FS de 5/29 MHz. O scheduler preserva
4.5 MHz uteis (guard_band_ratio=0.1); nao existe varredura de guard band.

## Execucao

```powershell
& C:/GitHub/SHARC/.venv/Scripts/python.exe C:/GitHub/SHARC/sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/generate.py
& C:/GitHub/SHARC/.venv/Scripts/python.exe C:/GitHub/SHARC/sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/run_multiple_campaigns_mut_thread.py
```

O run usa apenas `run_campaign`, executando os YAMLs pendentes da pasta input.
Esse lancador padrao usa processos concorrentes conforme o numero de CPUs.
O calculo de SINR pode consumir bastante RAM. Outputs nao sao sobrescritos.

## CCDF do INR

```powershell
& C:/GitHub/SHARC/.venv/Scripts/python.exe C:/GitHub/SHARC/sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_system_inr_ccdf.py
```

Gera quatro graficos (altitude x altura FS), PNG 300 dpi e PDF. Cada grafico
compara baseline, HO30, PBO e o HO5 historico quando disponivel, nos dois LFs:
LF20 continuo, LF50 tracejado. HO5 e HO30 nunca sao agrupados na mesma curva.
O criterio e marcado em -6 dB entre probabilidades 1 e 0.2.

Usa uma amostra final de INR por snapshot de `tcc2_snapshots.csv.gz`, ou
`system_inr.csv` quando o primeiro nao existe. A regra e a mesma da GUI_new:
ordenar as amostras e calcular CCDF=1-arange(1,N+1)/N. O piso 1e-4 e aplicado
somente para exibir no eixo logaritmico. Nao le pontos de curvas como se
fossem novas amostras e nao usa cada troca como um novo snapshot.

Seleciona a execucao mais recente disponivel de cada cenario, sem concatenar
repeticoes. Imprime os caminhos e tamanhos das amostras e salva a lista de
fontes junto de cada figura. Resultados parciais podem ser plotados, mas
amostras pequenas nao justificam conclusoes estatisticas. Curvas ausentes sao
informadas; nao sao criados dados ficticios.

Para a previa de LF20 com os mesmos snapshots concluidos nos tratamentos:

```powershell
& C:/GitHub/SHARC/.venv/Scripts/python.exe C:/GitHub/SHARC/sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_system_inr_ccdf.py --lf 20 --paired --plots-dir C:/GitHub/SHARC/sharc/campaigns/07_TCC2_DC_MSS_to_FS/plots/preview_LF20
```

`--paired` usa a intersecao dos IDs e confere as seeds. Entre baseline e HO,
tambem confere os hashes da realizacao e enlaces iniciais. O hash de desempenho
inicial e comparado somente quando os dois modos calculam desempenho dos UEs.
Nao exige igualdade das potencias iniciais do PBO, pois este ja foi aplicado.
Le apenas snapshots concluidos, mostra N e identifica as figuras como previas.

`--handover-preview --handover-mode HO30` gera o resumo antes/depois no criterio
e as CCDFs pareadas para HO30. Use `--handover-mode HO5` para a versao antiga.
Sem essa escolha explicita, a previa usa HO30 quando ha dados, senao HO5.
Baseline de outra data/numero de execucao pode ser reutilizado somente quando
as seeds e os hashes iniciais disponiveis correspondem; o numero da pasta nao e
evidencia de pareamento. Os arquivos novos de previa incluem HO5/HO30 no nome.

## Otimizacao do handover

No HO30, o conjunto inicial sao os 30 maiores contribuintes. Cada celula
e examinada no maximo uma vez, reordenando as restantes apos uma troca aceita.
Nao ha novas celulas, novos usuarios ou nova atividade sorteada durante a busca.

Apenas no modo com desempenho habilitado: apos uma troca, a linha de enlaces do transmissor movido para todos os
usuarios e recalculada. Os demais enlaces sao preservados; o SINR de todos os
usuarios ainda e recalculado. O modelo FSPL, as antenas e as mascaras sao os
mesmos do caminho completo. Nao se usa uma aproximacao de interferencia.
O P.619 continua sendo avaliado com sua dependencia atmosferica global e com
o mesmo estado aleatorio. Foram removidas avaliacoes duplicadas sem troca.

Processos Python ja abertos nao recebem essas alteracoes automaticamente.
Nao misture execucoes novas com as anteriores na mesma pasta de resultados.

## Registros e hipoteses preservadas

Os CSVs `tcc2_*` preservados registram INR antes/depois e por troca, contadores,
candidatos e decisoes. Usuarios e todas as contribuicoes/potencias/associacoes
por link requerem `record_detailed_links_and_users: true`.
O manifesto registra seeds, configuracao
e hashes do codigo. Para PBO, `inr_before_db` significa antes de handover,
JA com PBO aplicado; compare com o tratamento BASELINE para medir o efeito
do PBO. Para HO, step=0 e o estado sem handover da mesma realizacao.

O run padrao nao verifica automaticamente pareamento entre arquivos distintos.
Mesmo mantendo a seed, confira geometria e atividade nos registros antes de
fazer uma analise pareada; a CCDF marginal nao requer esse pareamento.

No modo COCHANNEL_INR os usuarios sao reancorados nas celulas reais da grid;
isso corrige o posicionamento provisorio legado e vale para os tres tratamentos.
Usuarios nunca sao descartados apos perda de atendimento. A capacidade fisica
maxima de feixes por satelite continua configuravel e null por padrao, isto e,
sem um limite adicional inventado. Nao apresente isso como um estudo com
capacidade finita de payload sem definir esse parametro.

`validate_physics.py --output PASTA_NOVA` foi mantido para o teste isolado do
handover. O limite padrao agora e 30; `--max-handovers 5` reproduz o teste antigo.
`--check-incremental` compara uma atualizacao com o calculo completo
e registra tempos e erros numericos. Os testes ficam em tests/, fora de Scripts.

`validate_physics.py --compare-victim-only --output PASTA_NOVA` compara seis
perfis nas duas altitudes, com dois snapshots consecutivos por modo. Confere
igualdade exata dos CSVs de INR, contribuicoes, candidatos, decisoes e geometria
(exceto campos de desempenho omitidos), alem do estado aleatorio final.
O teste impede chamadas ao calculo de enlaces internos/SINR no modo rapido e
exercita a escrita normal dos resultados. Nao inicia a campanha completa.

`validate_physics.py --compare-recording --output PASTA_NOVA` compara os
exports ligados/desligados em quatro perfis (baseline, HO e PBO; ambas
altitudes), com dois snapshots por execucao. Exige igualdade exata de INR,
steps, eventos, candidatos, hashes de pareamento e RNG, e ausencia das duas
tabelas no modo compacto. Os demais modos de auditoria reativam explicitamente
as tabelas detalhadas nas suas pastas isoladas de teste.

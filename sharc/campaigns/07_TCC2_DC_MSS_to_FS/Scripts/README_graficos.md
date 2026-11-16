# Graficos da campanha de interferencia

Os scripts sao exclusivamente de pos-processamento: nao executam o SHARC,
nao alteram os inputs e nao escrevem nos outputs brutos.
Execute com o ambiente Python do SHARC (numpy, matplotlib, PyYAML).
Os comandos abaixo podem ser usados a partir da raiz do repositorio.

## Todos os graficos principais

```powershell
python sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/run_plots.py
```

O destino de leitura vem de `base_input.yaml`: atualmente
`D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS`. O output local antigo tambem e
consultado, caso exista. Duplicatas de um mesmo cenario causam erro em vez
de serem combinadas silenciosamente. Nada e regenerado pelo generate.

Produtos em `plots/interferencia_completa` da campanha:

- 16 CCDFs: baseline e todos os limites HO ou todas as distancias PBO,
  separados por altitude, altura FS e LF, para evitar 34 curvas num painel.
- 12 graficos de varredura: INR20, margem M20 e excedencia de -6 dB,
  por tecnica e altitude, com FS20/40 e LF20/50 nas curvas.
- 8 figuras de distribuicao de trocas efetivas e ganho de INR no mesmo snapshot.
- 8 figuras de motivos de parada e 2 de quantidade de feixes ativos sob PBO.
- 2 figuras de esforco de busca: candidatos avaliados e trocas aceitas.
- Tabelas com metricas de todos os cenarios, classificacoes, primeiras
  configuracoes com conformidade sustentada nos pontos avaliados e motivos
  de parada. O ganho medio e a reducao no mesmo snapshot nao sao desempenho UE.

PNG e o padrao; `plot_interference_results.py --formats png pdf` gera ambos.
Nao ha titulo geral nas figuras. Os arquivos identificam os cenarios.

## Estatistica e amostras

- Fonte: `tcc2_snapshots.csv.gz`, INR final por snapshot, sem descartar as
  quatro execucoes PBO parciais preservadas. Seu N real aparece nas tabelas
  e legendas CCDF; losangos vazados identificam os pontos parciais das curvas.
- CCDF empirica: 1-rank/N, mesma convencao dos graficos anteriores. O ultimo
  ponto, de probabilidade zero, nao e desenhado no eixo logaritmico.
- INR20: elemento de indice ceil(0.8*N)-1 na amostra ordenada.
- Bootstrap: 10000 reamostragens de N snapshots com reposicao; recalculo do
  INR20 em cada uma; percentis 2.5/97.5 das estimativas. Mesmo algoritmo da
  campanha 02, verificado por teste de igualdade com sua funcao original.
- Seed de pos-processamento 20260727, separada da simulacao; um gerador
  reiniciado por configuracao garante reproducibilidade de selecoes isoladas.
- M20 = -6 - INR20; IC invertido corretamente: [-6-IC_superior, -6-IC_inferior].
  Conforme quando IC inferior >= 0; nao conforme quando IC superior < 0;
  limitrofe nos outros casos. Classificacao usa precisao integral.
- ICs sao pontuais, nao bandas simultaneas. Conformidade sustentada refere-se
  apenas aos pontos de varredura avaliados, nao a todo o intervalo continuo.
- Baseline aparece em x=0 (mitigacao desligada). O eixo HO e limite configurado,
  nao numero de trocas efetivamente realizadas.
- Nao presumimos pareamento entre execucoes. A comparacao HO antes/depois usa
  os valores dentro do mesmo snapshot de cada execucao HO. Nao produzimos IC
  de diferenca pareada entre campanhas com base apenas em seeds iguais.
- Cache usa hash do arquivo de snapshots, numero de reamostragens, seed e
  versao do metodo; nao reutiliza estatistica de uma entrada modificada.

Para uma previa rapida sem IC/classificacao:

```powershell
python sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_interference_results.py --no-bootstrap --plots-dir tmp/tcc07_previa
```

## Angulos e geometria do handover

Analise mais leve de todos os candidatos selecionados, sem ler os links grandes:

```powershell
python sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_handover_geometry.py
```

Analise completa antes/depois, para os 48 cenarios HO:

```powershell
python sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_handover_geometry.py --with-links
```

Esta segunda etapa e demorada: le os arquivos comprimidos de links em fluxo,
sem extrair/copiar os arquivos brutos e sem carregar arquivos de usuarios.
Usa o decodificador DELTA existente no SHARC, preservando estados completos.
Relaciona eventos e links por snapshot, beam, celula, satelite e passo:
o estado anterior e o imediatamente anterior a troca, nao necessariamente
o inicio do snapshot. Falta de correspondencia causa erro explicito.

Produz CDFs da elevacao de servico e angulos fora do eixo TX e FS, densidade
do ganho agregado versus angulo anterior, dados por decisao, motivos de rejeicao
de candidatos e fracao de decisoes aceitas por faixa angular entre celulas
examinadas. Cada configuracao permanece separada. A amostra e ponderada por
decisoes, nao por usuarios ou por satelites visiveis.

Esses graficos sao exploratorios: nao demonstram um limiar posicional causal
ou universal. Decisoes tambem dependem do INR inicial, recursos, candidatos,
elegibilidade e condicoes de parada. Candidatos rejeitados antes do calculo
fisico podem ter angulos RF ausentes; nao sao substituidos por zero.

Para testar um subconjunto, sem confundi-lo com a analise final:

```powershell
python sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/plot_handover_geometry.py --with-links --ho 30 --altitude 340 --fs-height 20 --lf 20 --max-snapshots 20 --plots-dir tmp/tcc07_geometria_teste
```

As previas recebem sufixo explicito com o limite de snapshots.
Metricas de SNR, SINR, P5, eficiencia espectral e outage dos UEs nao sao
inventadas a partir desta campanha sem desempenho; pertencem a campanha 08.

## Transferencia dos outputs

Os 16 outputs completos que estavam em C foram transferidos para D mediante
copia e verificacao SHA-256 arquivo a arquivo antes da remocao da origem.
O registro de transferencia fica em `reports/tcc07_migration_20261116.json`.
Caminhos antigos dentro dos manifestos sao proveniencia historica e foram
preservados, assim como os hashes e arquivos originais. Estes novos scripts
descobrem o diretorio atual sem depender daqueles caminhos antigos.

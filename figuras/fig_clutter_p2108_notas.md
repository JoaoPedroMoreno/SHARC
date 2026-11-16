# Clutter espacial no SHARC: interpretação da figura

## Entrega e reprodução

- Gerador: `tools/generate_tcc_clutter_statistics.py`.
- Figura: `figuras/fig_clutter_p2108.png`, 5670 x 2565 pixels, 450 dpi.
- Versão vetorial: `figuras/fig_clutter_p2108.pdf`.
- Valores numéricos: `figuras/fig_clutter_p2108_curvas.csv`.
- Auditoria, testes, commit e hashes: `figuras/fig_clutter_p2108_validacao.json`.

Em um ambiente Python com as dependências do SHARC, executar na raiz:

```powershell
python tools/generate_tcc_clutter_statistics.py
```

O script apenas lê configurações, constrói dicionários em memória com `build()`
dos geradores e chama o modelo de clutter. Não inicia campanhas, não altera
YAMLs e não lê nem sobrescreve resultados de simulação. O CSV entregue contém
avaliações das equações, não snapshots. A seed 2108 serve exclusivamente aos
testes da máscara; as curvas de quantis são determinísticas.

## O que foi conferido

Implementação utilizada: `sharc/propagation/propagation_clutter_loss.py`, método
`PropagationClutterLoss.get_spatial_clutter_loss`. O script importa e chama o
método original, sem transcrever ou substituir suas equações. Foram conferidos
os dois geradores, seus YAMLs-base e os 232 inputs disponíveis das campanhas
07 e 08 no momento desta entrega. Isso não constitui auditoria de versões
históricas do código em todas as execuções já realizadas.

| Parâmetro | Interface efetivamente usada | Valor na figura |
|---|---|---|
| Frequência | `frequency`, em MHz; conversão interna para GHz | 2155 |
| Elevação | `elevation_angle`, em graus | 0 a 90, passo 0,005 |
| Percentil de localização | `loc_percentage`, fração; multiplicação interna por 100 | 0,10; 0,50; 0,90 |
| Altura da antena | `earth_station_height`, metros | 20 ou 40 |
| Categoria do clutter | `mean_clutter_height`, string | `low` ou `mid` |
| Seleção externa de aplicação | `below_rooftop`, porcentagem | 60 ou 10, respectivamente |

A documentação interna do método cita GHz e porcentagens, mas a implementação
recebe **MHz e frações** e faz as conversões internamente. A figura respeita
o código executável. `mean_clutter_height` é uma categoria, não a altura da
antena nem uma altura numérica de prédio. A documentação associa `low` a
altura mediana de clutter até 8 m e `mid` ao intervalo acima de 8 até 20 m.

O gerador combina 20 m com `low`/60 e 40 m com `mid`/10. Portanto, a comparação
muda conjuntamente altura e categoria ambiental; não isola o efeito causal
de apenas uma delas. Os 60% e 10% são entradas explícitas: não são calculados
por comparação entre a altura do FS e um conjunto de alturas de edifícios.

## Caminho de cálculo e condições

1. A fábrica de propagação encaminha os parâmetros `param_p619` para P.619.
2. `PropagationP619.get_path_loss` obtém a altura da estação terrestre de
   `geom.z_global` e a elevação geométrica local do satélite. A fábrica da
   estação FS inicializa essa coordenada com `geometry.height`.
3. Em DC-MSS interferindo no FS, `imt.interfered_with` é falso, e a chamada
   utiliza o ramo `single_entry=False` de P.619. Esse ramo soma clutter à
   perda total. O ramo `single_entry=True` não faz essa mesma chamada de clutter.
4. O núcleo espacial calcula `pLoS` a partir da elevação, altura e categoria;
   calcula `pFcLoS_LoS` e `pFcLoS`, acrescentando dependência de frequência.
5. Se `p > pLoS`, usa o ramo NLoS, com quantil normal transformado e piso de
   6 dB. Se `p <= pFcLoS`, usa o ramo de Fresnel desobstruído, dado por uma
   soma de duas exponenciais negativas. Entre esses limites usa interpolação
   linear de 0 a 6 dB. Não há imposição global de perda não negativa.
6. `get_loss` obtém percentis aleatórios uniformes quando não são informados
   e multiplica o resultado por uma máscara de aplicação de clutter.

A máscara escolhe sem reposição `round(N * below_rooftop / 100)` posições
do vetor/matriz recebido por chamada e zera as demais. Assim, não são
Bernoullis independentes por enlace. A fração efetiva depende de arredondamento
para N pequeno e as escolhas dentro de uma chamada são dependentes. Não é uma
realização persistente de prédios nem um estado permanente do receptor FS.

O método espacial documenta frequência de 0,5 a 100 GHz, elevação de 0 a 90
graus e altura a partir de 1 m; estes limites não são todos validados pelo
próprio código. Aqui foram usados apenas valores dentro desses intervalos.
O percentil deve ficar estritamente entre 0 e 1; não avaliamos as singularidades
dos extremos 0 e 1.

A elevação do eixo X é a direção satélite-FS vista do solo, **não** a elevação
de apontamento da antena FS (0 graus no YAML), nem um limiar de seleção de
células. O intervalo 0 a 90 graus explora o domínio do modelo; não afirma
que todos esses ângulos apareçam nos snapshots da campanha.

A altitude geográfica de 200 m em P.619 não substitui as alturas de antena
de 20 e 40 m nesta função. Distância, altitude orbital, LF, largura de banda,
PBO e limite de handovers não são argumentos do núcleo espacial. A distância
entra no invólucro para fornecer a forma das matrizes, mas não entra nas suas
equações espaciais. Não há motivo para duplicar as curvas em 340 e 525 km a
uma mesma elevação, frequência e condição terrestre.

## Estatísticas representadas

P10, P50 e P90 são quantis de **não excedência** da perda espacial, antes da
máscara `below_rooftop`. Não são percentis de tempo, probabilidades de
implantação abaixo das coberturas ou percentis da perda total P.619.

Os valores 60% e 10% nos painéis identificam a seleção configurada nas
campanhas, mas **não multiplicam os quantis desenhados**. Após a seleção, a
distribuição inclui uma massa de enlaces com clutter igual a zero. Seus
quantis não se obtêm multiplicando as curvas por 0,60 ou 0,10. Como o núcleo
também devolve valores negativos, tampouco se pode presumir que todos os
enlaces zerados pertençam à extremidade inferior da distribuição.

Para representar a distribuição efetivamente aplicada seria necessária uma
figura diferente, com os quantis da mistura núcleo + máscara, explicitando
o tamanho do conjunto de enlaces. Essa alternativa não foi confundida com
os percentis do núcleo pedidos nesta figura.

## Resultado numérico e escolha gráfica

| Condição | Percentil | Em 0 graus (dB) | Em 90 graus (dB) |
|---|---|---:|---:|
| 20 m / low | P10 | -0,420909 | -0,562182 |
| 20 m / low | P50 | -0,010464 | -0,044479 |
| 20 m / low | P90 | 24,340429 | -0,003519 |
| 40 m / mid | P10 | -0,552065 | -0,562182 |
| 40 m / mid | P50 | -0,040619 | -0,044479 |
| 40 m / mid | P90 | -0,002989 | -0,003519 |

Os valores ligeiramente negativos são devolvidos pelo ramo de Fresnel
desobstruído. Não foram truncados, convertidos para módulo ou corrigidos.
Não representam uma mudança de ganho da antena: são o termo de correção
de propagação que esta implementação soma à perda total.

Nestas seis curvas especificamente, não foram encontrados incrementos
positivos acima de 1e-10 dB na grade de elevações. Isso é um resultado da
avaliação, não uma restrição imposta ao desenho nem uma generalização a
todos os parâmetros. Há transições de ramo que não devem ser suavizadas.

Os painéis têm **escalas verticais distintas**, pois uma escala comum tornaria
ilegíveis as diferenças no perfil de 40 m. A ampliação do painel de 20 m
mostra de 10 a 90 graus e permite distinguir os três quantis próximos de zero.
Não há título geral, apenas identificação dos painéis e legenda dos quantis.

## Revisão normativa: limite de rastreabilidade

Os comentários do arquivo não são uniformes: há referências a P.2108-0,
P.2108-1/2021 e P.2108-2. O histórico registra a introdução das tabelas do
núcleo espacial no commit `c4e83f10726716e52208d9aca621ea082056922e`, de
28/07/2025, com mensagem `Update 2108, fix p619 and p452. Also fix
single_space_station`.

A UIT lista uma revisão 2 do documento SG3/41 publicada em 30/06/2026 e
uma implementação MATLAB/Octave no anexo 14 do documento WP3K/251, publicado
em 03/07/2026. A página de SG3/41 informa acesso restrito a usuários TIES.
Esses metadados não demonstram equivalência entre todas as equações desse
rascunho e este código local. É necessário o documento exato citado no TCC
para certificar essa correspondência. Não substituir o núcleo por outra
versão para fazer a figura parecer mais usual.

Fontes de identificação documental:
- [SG3/41: revisão da P.2108](https://www.itu.int/md/R23-SG03-C-0041/en).
- [WP3K/251: relatório e anexo de implementação](https://www.itu.int/md/R23-WP3K-C-0251/es).

## Legenda sugerida para o TCC

Quantis de não excedência da perda por clutter em função da elevação do
satélite, a 2155 MHz, calculados pela implementação espacial da P.2108
utilizada no SHARC: (a) receptor a 20 m em ambiente low-rise; (b) receptor
a 40 m em ambiente mid-rise. As curvas precedem a seleção de aplicação
de clutter, parametrizada separadamente por 60% e 10% de enlaces abaixo
das coberturas. Os painéis utilizam escalas verticais distintas; o detalhe
em (a) amplia os valores próximos de zero. Valores negativos foram
preservados conforme a implementação.

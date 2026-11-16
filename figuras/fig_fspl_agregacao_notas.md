# Figuras de FSPL e agregação cocanal

Gerador: `tools/generate_tcc_fspl_and_aggregation.py`. Executar na raiz do
repositório, com as dependências do SHARC disponíveis:

```powershell
python tools/generate_tcc_fspl_and_aggregation.py
```

## FSPL versus elevação

O cálculo importa `EARTH_RADIUS_M = 6378145` de
`sharc/satellite/ngso/constants.py`, a mesma constante usada pelo modelo
orbital e pelas transformações geométricas esféricas do SHARC.

Para a referência terrestre, foram mantidos 200 m de altitude do solo e
20 m de altura de antena do YAML-base da campanha 07. Portanto, o raio do
receptor é `r = R + 220 m`, e o raio orbital é `rs = R + h`.

A interseção entre a direção de observação com elevação `e` e a esfera
orbital fornece a distância oblíqua:

`d = sqrt(rs^2 - r^2 cos(e)^2) - r sin(e)`.

O script utiliza a forma algebricamente equivalente racionalizada. Não
substitui a distância oblíqua pela altitude orbital. A FSPL é obtida chamando
`PropagationFreeSpace.get_free_space_loss`, com frequência em MHz e distância
em metros: `20 log10(d_m) + 20 log10(f_MHz) - 27.55`. Isso equivale a
`32.45 + 20 log10(d_km) + 20 log10(f_MHz)`.

| Altitude orbital | Elevação | Distância oblíqua (km) | FSPL (dB) |
|---|---:|---:|---:|
| 340 km | 5° | 1625,595 | 163,339 |
| 340 km | 32° | 604,258 | 154,743 |
| 340 km | 90° | 339,780 | 149,743 |
| 525 km | 5° | 2142,034 | 165,735 |
| 525 km | 32° | 908,850 | 158,289 |
| 525 km | 90° | 524,780 | 153,518 |

A diferença entre 5° e 90° é de 13,596 dB em 340 km e de 12,217 dB em 525 km.
Usar antena a 40 m, mantendo a altitude do solo, altera essas curvas em menos
de 0,00052 dB no domínio avaliado; por isso não foram criadas curvas adicionais.
Isso se refere somente à FSPL, não ao clutter nem à interferência total.

As marcas de 5° e 32° são referências da configuração DC-MSS-IMT. O filtro
inicial usa a elevação a partir da referência terrestre; o atendimento usa
a elevação a partir da célula. Não são necessariamente o mesmo ângulo visto
do FS, nem restrições universais à recepção de interferência pelo FS. O
gráfico ilustra o efeito geométrico de uma elevação local genérica; não aplica
esses filtros às curvas nem representa a distribuição de snapshots.

Validações: fechamento da esfera orbital, reconstrução da elevação com
`sat_utils.calc_elevation` (erro máximo inferior a 7e-10 grau na grade
verificada, excluindo o zênite exato da inversão numérica), distância no
zênite e equivalência das expressões da FSPL em metros e quilômetros.
Nenhuma perda atmosférica, de clutter ou de polarização está incluída.

## Agregação de interferência

As entradas `I_j` são valores numéricos em dBm das contribuições já recebidas
no FS, não potências conduzidas de transmissão. As contribuições individuais
incorporam os ganhos, perdas e a integração espectral aplicáveis ao enlace.
As potências lineares `i_j` têm unidade mW.

Cada potência ativa é convertida por `i_j = 10^(I_j/10) mW`. O conjunto
`A` contém somente feixes cocanais ativos. O feixe 4 inativo é explicitamente
zero mW e não tem conector para o somador. **Zero dBm não significa inativo**:
zero dBm corresponderia a 1 mW. O ramo `n` representa um dos demais feixes
ativos; não é a quantidade de satélites visíveis.

O somador entrega `i_agg = sum(i_j, j em A)`, depois convertido para dBm.
O ruído não entra nesse somatório de interferência. Sua potência logarítmica
é subtraída de `I_agg,dBm` para obter a INR em dB. Esse encadeamento corresponde
ao cálculo em `sharc/cochannel_handover.py`, inclusive para a campanha de
desempenho quando o INR do FS orienta as decisões de handover.

O diagrama não contém números de um exemplo artificial. Os testes algébricos
internos confirmam a equivalência com `10 log10(i_agg/n_FS)`, o aumento de
3,0103 dB ao somar duas potências iguais e a contribuição nula de um feixe
inativo. Se não houver contribuição ativa, `i_agg = 0`; a conversão tem
limite `-infinito dBm` e a INR também é `-infinito dB` para ruído positivo.

## Arquivos e integridade

Os dois PNGs têm resolução de 450 dpi, fundo branco e não possuem título
geral. Os PDFs são vetoriais. Todos os arquivos gerados ficam em `figuras`.
`fig_fspl_elevacao_leo_curvas.csv` permite consultar os valores do gráfico.
`fig_fspl_agregacao_validacao.json` registra parâmetros, testes, versões,
commit e hashes dos arquivos consultados. As campanhas não foram executadas
nem modificadas; nenhum resultado existente foi utilizado como dado fictício.

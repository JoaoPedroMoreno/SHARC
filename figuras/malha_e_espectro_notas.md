# Figuras de LF e sobreposicao espectral

Gerador: `tools/generate_tcc_load_and_spectrum.py`.
Arquivos finais: `fig_malha_servico_ativacao.png` e
`fig_sobreposicao_espectral.png`, com SVGs e previews correspondentes.
Nenhum input, resultado ou modulo de simulacao foi modificado.

## Malha e atividade

Ilustracao conceitual, nao resultado da campanha. Os satelites usam os mesmos
assets Blender e as mesmas primitivas de feixes dos diagramas LATINCOM.
As letras A e B indicam a associacao da celula ao satelite. Celulas e
associacoes permanecem iguais nos dois paineis; somente a atividade muda.
As associacoes sao esquematicas: nao ha calculo orbital nesta figura.
Os pontos ocre representam UEs ilustrativos (dois por celula), conservados
nos dois paineis e tambem nas celulas inativas; nao reproduzem a quantidade
de usuarios configurada na campanha. LF sorteia cada feixe, nao a atividade
do satelite como um todo.

Os UEs usam deslocamentos aleatorios distintos em cada celula, verificados
dentro de seu hexagono. A celula destacada pelo contorno, associada ao satelite
A e identificada com a mesma letra A, aparece em seis snapshots
independentes. Essa sequencia e ilustrativa, nao uma trajetoria temporal.
Para demonstrar ambos os estados sem sugerir uma cota, a celula destacada
usa os valores ilustrativos [0.32, 0.74, 0.12, 0.41, 0.08, 0.62], com a mesma
regra u < LF. Essa sequencia foi construida para fins didaticos, nao extraida
da simulacao nem apresentada como amostra empirica. As demais celulas usam
o gerador pseudoaleatorio abaixo.
O sorteio usa `RandomState(838).rand(19, 6).T < LF`, reproduzindo a regra de
`StationFactory.sample_imt_base_station_active_mask`: um uniforme por feixe.
Os mesmos uniformes sao usados nos dois exemplos para isolar a mudanca de LF.
Isso nao significa que dois snapshots quaisquer tenham atividade aninhada.
Nao se impoe uma fracao exata nem se exibem totais como alvo de ativacao.
Os 19 candidatos representam celulas que ja passaram pelas restricoes
geometricas e de atendimento. A selecao inicial real usa a maior elevacao,
seguida do limiar de servico, em `topology_imt_mss_dc.py`.

Legenda sugerida: Representacao conceitual da malha de servico e da ativacao
probabilistica dos feixes. As letras A e B identificam os satelites associados;
os dois exemplos compartilham a geometria e o sorteio uniforme. O LF define
a probabilidade individual de ativacao, nao uma fracao fixa por snapshot.

## Espectro

Configuracao lida diretamente de
`sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml`:

- Canal DC-MSS-IMT: 2152,5 a 2157,5 MHz (5 MHz).
- Banda FS: 2140,5 a 2169,5 MHz (29 MHz).
- Frequencia central comum: 2155 MHz.
- `spectral_mask: MSS`, `spurious_emissions: -13` dBm/MHz.
- `enable_cochannel: true`, `enable_adjacent_channel: false`.
- `adjacent_ch_emissions: ACLR`, nao `SPECTRAL_MASK`.

A curva continua e obtida diretamente de `SpectralMaskMSS`, nao de uma curva
inventada ou ajustada. Para reproduzir a configuracao nominal, utiliza-se
42,8 dBm sem PBO. O grafico mostra a densidade absoluta em dBm/MHz:
35,8103 dBm/MHz em banda e piso espurio de -13 dBm/MHz. Nao e INR.
Um unico eixo sobrepoe a curva MSS completa e a faixa sombreada FS, sem
diferenciar o traco ou a cor entre a banda principal, OOB e dominio espurio.
O eixo vai de 2128 a 2182 MHz, deixando espaco visivel fora dos dois limites
da banda FS (2140,5 e 2169,5 MHz).
O grafico representa o canal nominal e nao os RBs individuais, a ocupacao
instantanea de usuarios ou um filtro FS medido. A banda FS e uma indicacao
de largura de banda, nao uma curva de seletividade. A faixa sombreada
delimita a janela equivalente do calculo cocanal. A integracao dos RBs nessa
janela equivale a `Simulation.calculate_bw_weights`.
Nao ha uma mascara continua de recepcao especificada no YAML. O ACS de
35 dB e um parametro escalar configurado, nao uma curva, e nao e aplicado
neste calculo cocanal. Desenha-lo como uma saia de filtro seria inventar
um modelo que esta campanha nao usa.

IMPORTANTE: a mascara MSS esta selecionada, mas suas caudas fora de banda
nao sao integradas nesta campanha cocanal. A rotina `CochannelHandover`
utiliza pesos de sobreposicao de banda para as contribuicoes interferentes.
O ruido do FS utiliza a largura de banda de recepcao de 29 MHz.
Mesmo habilitar o canal adjacente isoladamente nao selecionaria integracao
pela mascara, pois o modo de emissao adjacente atual e ACLR.

Substituicao sugerida para a frase sobre a figura no texto:

"A Figura~\ref{fig:sobreposicao_espectral} ilustra a disposicao cocanal das
bandas e, como referencia, a mascara MSS selecionada na configuracao.
Nesta campanha, as emissoes de canal adjacente estao desativadas; portanto,
as contribuicoes fora de banda dessa mascara nao entram no calculo da
interferencia."

Legenda sugerida: Sobreposicao entre o canal nominal DC-MSS-IMT de 5 MHz e
a banda de recepcao FS de 29 MHz, centrados em 2155 MHz. A curva continua
mostra a mascara MSS configurada para potencia nominal por feixe de 42,8 dBm;
suas emissoes fora de banda nao sao integradas na campanha cocanal.

## Validacao

O gerador verifica os limites das bandas, a configuracao cocanal, o nivel
normalizado em banda, as dimensoes e o posicionamento dos textos na figura.
`malha_e_espectro_validacao.json` registra os parametros e o sorteio ilustrativo.

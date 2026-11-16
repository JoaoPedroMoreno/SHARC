# Auditoria dos registros das campanhas 07 e 08

Data: 14/11/2026. Inspecao de codigo, configuracoes e arquivos existentes.
Nenhuma simulacao foi iniciada e nenhuma configuracao de producao foi alterada.

## Verificacao dos arquivos existentes

- 136 YAMLs reais da 08 conferidos contra o gerador, sem divergencias.
- 126 configuracoes da 07 com registros: 8 baseline, 71 PBO e 47 HO.
- 110 dessas configuracoes estavam marcadas como completas durante a leitura.
- Os 10 primeiros snapshots comprometidos de cada output foram examinados:
  1260 registros, sem falhas de sequencia/seeds, INR nao finito ou violacao do
  limite de trocas/nao aumento do INR.
- As configuracoes fisicas executadas desses 126 outputs correspondem as da 08.
- Reconstrucao do primeiro snapshot dos oito HO30: identidades de usuarios,
  celulas e associacoes coerentes; angulos/posicoes dos feixes ativos finitos;
  soma das contribuicoes igual ao agregado registrado em cada passo.
- Dois desses snapshots tiveram 26 trocas, com 27 estados reconstruidos cada;
  os demais seis nao tiveram trocas nesse primeiro snapshot.
- Nenhuma inconsistencia encontrada nessa amostra. Nao foi feita verificacao
  integral de todos os registros detalhados de todos os snapshots.

As 10 configuracoes ainda sem registros comprometidos no levantamento eram
525 km / FS40 m / LF50: HO5 e PBO10 a PBO90 km. A execucao em andamento pode
alterar essas contagens apos a auditoria. Nao foram removidos ou recriados outputs.

Evidencia estruturada: `tmp/audit_tcc_saved_fields_20261114.json`.

## Diagnostico

Os registros de INR e de geometria do handover da campanha 07 permitem
estudar a relacao entre a mitigacao e a posicao relativa ao receptor FS.
A campanha 08 esta preparada para registrar o desempenho FINAL dos usuarios,
mas sua exportacao compacta nao guarda toda a geometria necessaria para uma
analise angular autonoma. O reaproveitamento da geometria da 07 depende de
validacao do pareamento; para baseline/PBO, os registros detalhados foram
removidos/desabilitados por economia de armazenamento.

Nao foram encontrados outputs de producao da campanha 08 nos dois destinos
previstos (pasta local da campanha e D:/SHARC_outputs). Portanto, a validacao
da 08 abrange implementacao, inputs e testes automatizados, nao resultados
de uma campanha completa ja executada.

## Matriz da campanha de desempenho

136 inputs: 8 baseline, 48 handover e 80 PBO. Combinacoes:

- Altitude: 340 e 525 km.
- Altura FS: 20 e 40 m.
- LF: 20% e 50%.
- HO: limites de 5, 10, 15, 20, 25 e 30 trocas aceitas.
- PBO: 10 a 100 km, em passos de 10 km.
- 1000 snapshots por input, com calculo de desempenho habilitado.

Baseline corresponde a ausencia de mitigacao; nao ha necessidade de um
PBO0 separado para essa referencia. PBO e HO sao estrategias separadas na matriz.

## Campanha 07: INR e geometria do handover

`tcc2_snapshots.csv.gz` registra INR antes/depois, seeds, hashes da realizacao,
contadores de busca e trocas, motivos de parada e numero de feixes com PBO.
`tcc2_steps.csv.gz` registra INR e soma linear das contribuicoes em cada passo.

Nos casos HO, `tcc2_links.delta.jsonl.gz` (ou o formato CSV integral) permite
recuperar, por snapshot/passo/feixe/celula:

- `tx_offaxis_deg`: separacao entre apontamento do feixe e direcao do FS.
- `rx_offaxis_deg`: separacao entre apontamento do FS e direcao do satelite.
- Elevacao de servico da celula, azimute/elevacao do boresight e distancia satelite-FS.
- Posicao do satelite, latitude/longitude da celula e distancia a fronteira paraguaia.
- Associacao, atividade, potencia, ganhos, perdas e contribuicao interferente.

Os registros `events` e `candidates` permitem identificar decisoes, candidatos
avaliados e motivos de rejeicao. Candidatos rejeitados antes do calculo fisico
podem ter angulos fora do eixo e contribuicoes NaN: nao significa perda do
registro da rejeicao. Suas coordenadas e motivos sao registrados.

Os registros `users` preservam IDs, coordenadas e associacoes. Como a campanha
07 desabilita desempenho, campos de SINR/SNR nao sao medidas validas de desempenho.

O formato DELTA preserva os valores: sua leitura deve reconstruir o estado de
cada passo com `sharc.support.tcc2_detailed_records.read_detailed_rows`, e nao
interpretar apenas as linhas alteradas como se fossem toda a populacao.

## Campanha 08: desempenho

`tcc2_performance_users.csv.gz` salva uma linha FINAL por usuario/snapshot:

- SINR, SNR, INR intrassistemico; potencias de sinal, interferencia e ruido.
- Ganhos e perdas do enlace desejado; largura de banda alocada.
- Elevacao de servico no UE e distancia ao centro da celula.
- Atividade, atendimento, perda de servico e outage por SINR.
- Satelite inicial/final, identificadores e flag de reassociacao.
- Back-off aplicado e potencia transmitida.
- Proxies de eficiencia espectral e taxa atendida.

Usuarios inativos e sem atendimento nao sao removidos. Inativos nao devem ser
contados como demanda de taxa zero. As proxies nao equivalem a throughput de
pacotes, goodput, latencia ou BLER.

O desempenho e recalculado para a populacao apos a troca, incluindo os demais
usuarios afetados pela interferencia, e nao apenas o UE da celula reassociada.
Entretanto, apenas o ultimo estado individual e exportado. Os passos
intermediarios guardam INR e contadores agregados, nao SINR de cada UE.

## Lacunas para a analise solicitada

1. A 08 NAO exporta `tx_offaxis_deg`/`rx_offaxis_deg` em relacao ao FS,
   coordenadas UE/satelite/celula nem distancia a fronteira.
2. A 08 NAO exporta historico individual de desempenho apos cada troca.
   O efeito final e analisavel contra baseline; uma trajetoria de SINR por
   usuario ao longo de todas as trocas nao esta disponivel.
3. Para HO, geometria da 07 pode complementar os registros finais da 08,
   mas somente apos validar a correspondencia real das realizacoes.
4. Para baseline/PBO, nao se deve contar com tabelas detalhadas apagadas ou
   desabilitadas da 07 para suprir as lacunas geometricas da 08.
   Uma alternativa a exportar novamente e reaproveitar a geometria inicial
   (`step=0`) de um HO da 07 com a mesma realizacao, mas isso exige validar
   tambem a populacao, associacoes e geometria entre os tratamentos. Nao e
   suficiente juntar por numero do snapshot ou seed; esse cruzamento ainda
   nao foi validado com outputs de producao da 08.

## Ajuste recomendado, ainda nao implementado

Para tornar a analise autonoma, acrescentar a linha FINAL por UE da 08 os angulos TX/FS e RX/FS, coordenadas
UE/satelite, centro da celula e distancia a fronteira. Isso atenderia a analise
angular/posicional de PBO e HO sem restaurar exportacoes integrais em cada passo.
Se a prioridade for evitar qualquer duplicacao, implementar e validar primeiro
o cruzamento com a geometria da 07, incluindo o caso PBO descrito acima.
Se for preciso analisar a evolucao individual durante HO, definir tambem um
registro compacto de desempenho inicial e das mudancas relevantes; nao confundir
essa analise com comparar somente o estado final de cada limite de HO.

## Pareamento e interpretacao

O teste `validate_physics.py --check-pairing` compara hashes, seeds, decisoes e
INR entre o mesmo tratamento das campanhas 07 e 08. Seed igual, isoladamente,
nao comprova pareamento. Dentro da 08, `service_population_sha256` permite
checar a populacao entre baseline/PBO/HO sem exigir potencias iguais.

Relacionar por configuracao fisica, tratamento quando aplicavel, snapshot,
seed, celula e usuario/feixe. O satelite e um resultado da mitigacao, nao uma
chave fixa para juntar baseline e HO.

No PBO, o passo inicial ja incorpora o back-off: `inr_before_db` nao representa
um baseline sem PBO. Comparar com o cenario baseline correspondente.

Um limiar angular empirico pode ser investigado com esses dados, mas nao deve
ser apresentado como garantia universal: INR agrega varios feixes e depende
tambem de LF, potencia, propagacao e geometria. Avaliar casos rejeitados e nao
reassociados evita selecionar somente exemplos bem-sucedidos.

## Referencias no codigo

- `sharc/cochannel_handover.py:317`: metricas geometricas em relacao ao FS.
- `sharc/cochannel_handover.py:331`: candidatos e rejeicoes.
- `sharc/cochannel_handover.py:417`: desempenho e identidade dos usuarios.
- `sharc/cochannel_handover.py:466`: campos finais exportados pela 08.
- `sharc/cochannel_handover.py:501`: registros detalhados dos enlaces.
- `sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/generate.py`: matriz.
- `sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/validate_physics.py:68`: pareamento.

O teste existente `tests/test_tcc2_performance_campaign.py` passou nos oito
casos, incluindo preservacao de usuarios inativos/sem atendimento, consistencia
fisica da matriz e manutencao do comportamento legado da campanha 07.

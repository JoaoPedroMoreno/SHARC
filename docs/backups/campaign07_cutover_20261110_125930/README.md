# Registro da fila da campanha 07 no inicio das alteracoes da campanha 08

Marco: 10/11/2026, 12:59:30.574, UTC-03 (Brasilia).
Primeira alteracao compartilhada: parameters_imt_mss_dc.py, confirmado pelo
horario de modificacao que permaneceu inalterado desde o primeiro patch.
Auditoria dos arquivos: 10/11/2026, 13:15:58, UTC-03.

Reconstrucao baseada nos inputs atuais, logs de inicio/fim, manifestos dos
outputs em C e D e horarios de criacao dos processos Windows. Nao foi uma
captura da fila do sistema operacional feita exatamente no instante do patch.
Nao iniciar significa ausencia de output/log/processo observado; pressupoe que
nao houve tentativa anterior sem registro ou output apagado nesse intervalo.

## Resultado

Dos 96 inputs presentes no lote atual:

* 15 ja estavam concluidos antes do marco.
* 12 ja tinham iniciado antes do marco e continuavam em execucao na consulta.
* 69 ainda nao tinham iniciado: 24 HO e 45 PBO.
* Nenhum cenario foi identificado como iniciado depois do marco ate a consulta.

O ultimo processo de cenario ativo iniciou em 10/11/2026, 12:55:24:
`tcc2_SA_noPY_340km_FS40m_LF50_Azi90_HO5.yaml`.
Wrappers do venv e seus processos Python filhos foram agrupados pelo cenario;
nao foram contados como simulacoes distintas.

| Altitude | FS | LF | Ainda nao iniciados | Quantidade |
| --- | --- | --- | --- | --- |
| 340 km | 40 m | 50% | PBO10,20,30,40,50,60,70,80,90 km | 9 |
| 525 km | 20 m | 20% | HO5,10,15,20,25,30; PBO10 a 90 km, passo 10 km | 15 |
| 525 km | 20 m | 50% | HO5,10,15,20,25,30; PBO10 a 90 km, passo 10 km | 15 |
| 525 km | 40 m | 20% | HO5,10,15,20,25,30; PBO10 a 90 km, passo 10 km | 15 |
| 525 km | 40 m | 50% | HO5,10,15,20,25,30; PBO10 a 90 km, passo 10 km | 15 |

Nao confundir este total com todos os 136 cenarios da matriz: outros 40 inputs
ja estavam fora da fila deste lote por reutilizacao/preservacao de resultados.

## Conteudo deste backup

* `pending_input_names.txt`: nomes exatos dos 69 YAMLs.
* `pending_at_change.csv`: tabela dos 69 pendentes com parametros e SHA-256.
* `pending_inputs_at_change/`: copias byte a byte desses 69 YAMLs, com hashes verificados.
* `all_queue_status.csv`: classificacao dos 96 inputs do lote.
* `audit.json`: evidencias, caminhos de outputs, horarios e hashes.
* `processes_observed.json`: consulta dos processos, incluindo seus horarios de inicio.
* `context_at_audit/`: copias do base/generate/run/relatorio de geracao da 07 e
  dos tres arquivos compartilhados na versao existente NO MOMENTO DA AUDITORIA.
  O codigo compartilhado copiado ja inclui a opcao da campanha 08. NAO e um
  backup do codigo anterior ao patch, nem uma captura do codigo na memoria.

Os contadores de snapshots em audit.json sao da consulta, nao do instante do patch.
Os outputs pesados nao foram copiados. Nenhum input original, output ou processo
foi alterado, apagado, reiniciado ou interrompido por esta auditoria.

Este diretorio nao faz parte da fila executavel. Nao recoloque automaticamente
os 69 inputs na fila no futuro: alguns poderao ja ter terminado desde esta foto.

"""Format the already-derived preview; never reads or modifies simulation outputs."""
import csv
import heapq
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"sharc/campaigns/07_TCC2_DC_MSS_to_FS/plots/preview_completed_20261031"
s=json.loads((OUT/"summary.json").read_text())
with (OUT/"completed_metrics.csv").open(newline="") as f:
    metrics=list(csv.DictReader(f))
with (OUT/"forecast_cases.csv").open(newline="") as f:
    jobs=list(csv.DictReader(f))
slots=[]
scheduled=[]
for i,j in enumerate(j for j in jobs if j["status"]=="running"):
    hours=float(j["hours"])
    heapq.heappush(slots,(hours,i))
    scheduled.append((0.,hours,float(j["additional_gib"])))
for status in ("queued","interrupted"):
    for j in (j for j in jobs if j["status"]==status):
        start,i=heapq.heappop(slots)
        end=start+float(j["hours"])
        heapq.heappush(slots,(end,i))
        scheduled.append((start,end,float(j["additional_gib"])))
lo,hi=0.,max(end for start,end,size in scheduled)
for _ in range(60):
    mid=(lo+hi)/2
    used=sum(size*min(1.,max(0.,(mid-start)/(end-start))) for start,end,size in scheduled)
    if used<s["d_free_gib"]:
        lo=mid
    else:
        hi=mid
s["conditional_disk_full_hours_linear_model"]=hi
s["forecast_storage_by_treatment"]={tech:sum(float(j["additional_gib"]) for j in jobs if ("_HO" in j["scenario"])==(tech=="HO")) for tech in ("HO","PBO")}
(OUT/"summary.json").write_text(json.dumps(s,indent=2),encoding="utf-8")
text=["# Previa TCC2: resultados concluidos e capacidade", "",
      "Leitura de referencia: 31/10/2026, aproximadamente 00:45 (Brasilia).",
      "Analise somente de outputs existentes. Nenhuma simulacao foi iniciada, interrompida ou alterada.",
      "", "## Progresso", "",
      "Lote atual: 112 casos; 26 concluidos, 12 ativos, 70 na fila, 4 interrompidos.",
      "Os CSVs dos 26 concluidos confirmam 10000 snapshots consecutivos e INR finito.",
      "Com os 16 controles anteriores, sao 42 casos concluidos. Os oito HO30 antigos continuam parciais e fora da fila por solicitacao anterior.",
      f"Snapshots registrados no lote atual: {s['current_batch_recorded_snapshots']:,} / 1,120,000. Os parciais interrompidos nao sao checkpoints retomaveis.",
      "", "## Resultados", "",
      "INR20 = amostra ordenada ceil(0.8*N), sem interpolacao; M20 = -6 - INR20. CCDF = 1 - rank/N, como no script da campanha/GUI.",
      "Somente casos com 10000 snapshots entram nas figuras. Nao foi calculado IC/bootstrap nesta previa; M20 positivo indica atendimento pontual, nao conformidade sustentada por IC.",
      "Pareamento de todos os seis casos HO completos com baseline conferido por seeds e hashes de realizacao/enlaces iniciais.",
      "", "- 340 km, FS20, LF20: baseline INR20=-6.229 dB; HO5/10/15/20/25 INR20=-6.428 dB. Ganho no criterio: 0.198 dB.",
      "- No mesmo perfil, a excedencia de -6 dB cai de 18.91% para 16.36% (HO5) e 15.80% (HO25). Ha melhora, mas ganho marginal pequeno ao aumentar o limite.",
      "- O gatilho so atua acima de -6 dB; o percentil 80 ja estava abaixo desse limiar no baseline. Portanto, esta metrica pode saturar sem que as curvas inteiras sejam identicas. A figura CCDF mostra a cauda.",
      "- 340 km, FS20, LF20: PBO100 eleva M20 de +0.229 para +2.442 dB.",
      "- 340 km, FS20, LF50: PBO100 melhora INR20 de +3.434 para -3.381 dB, mas M20=-2.619 dB ainda fica abaixo do criterio. Nenhum PBO de 10 a 100 km desse perfil atende pontualmente.",
      "- 525 km, LF50: PBO100 tem M20=+0.677 dB (FS20) e +0.790 dB (FS40). Ainda nao ha novos casos de HO ou varredura PBO nessa altitude.",
      "- Nenhum HO LF50 do lote novo concluiu; nao extrapolar para LF50 a saturacao observada em LF20.",
      "", "## Tempo restante", "",
      f"Estimativa central: {s['automatic_queue_hours']:.0f} h adicionais, cerca de {s['automatic_queue_hours']/24:.1f} dias. Referencia aproximada: 06/11/2026.",
      "Faixa de planejamento: 4 a 9 dias adicionais (aproximadamente 04 a 09/11), NAO um intervalo estatistico de confianca.",
      "Condicoes: 12 workers, computador continuamente ligado, desempenho semelhante e espaco em disco suficiente. A fila atual nao refaz automaticamente os quatro casos interrompidos.",
      "A projecao com quatro reexecucoes completas inclui seu custo; elas cabem nos workers liberados antes do ultimo HO terminar no modelo estatico. Isso nao significa que vao reiniciar sozinhas.",
      "Taxas: tempo de cada execucao desde a criacao do output ate o ultimo snapshot dividido por N. Casos nao iniciados usam perfis equivalentes; HO525 usa a razao historica HO30 entre altitudes. As alturas nao observadas usam a outra altura no mesmo perfil. PBO525 usa a taxa historica ajustada pela relacao antigo/novo observada em 340 km.",
      "O intervalo curto entre as duas leituras serve apenas para confirmar progresso, nao determina a previsao central. Periodos de suspensao ou mudanca de carga podem distorcer a media historica.",
      "", "### Casos ativos", "", "| Cenario | Snapshots | Horas restantes aproximadas |", "|---|---:|---:|"]
for r in s["active_progress"]:
    text.append(f"| {r['scenario'].removeprefix('tcc2_SA_noPY_')} | {r['n']} | {r['remaining_hours']:.1f} |")
text += ["", "### Casos interrompidos", "", "Todos sao 340 km, FS40, LF20. Os logs de encerramento terminam em 30/10 as 21:40:23-24, sem causa registrada; nao havia processos ativos para esses inputs.",
         "Sem evidencia suficiente para atribuir a causa a disco, memoria, cancelamento manual ou erro de simulacao.", ""]
for r in s["interrupted"]:
    text.append(f"- {r['scenario'].split('Azi90_')[1]}: {r['n']} / 10000.")
text += ["", "## Espaco", "",
         f"Campanha no C: {s['storage_c_gib']:.1f} GiB. Campanha no D: {s['storage_d_gib']:.1f} GiB. Livre no D: {s['d_free_gib']:.1f} GiB.",
         f"Projecao adicional central: {s['estimated_additional_gib']:.0f} GiB, sendo {s['forecast_storage_by_treatment']['HO']:.0f} GiB HO e {s['forecast_storage_by_treatment']['PBO']:.0f} GiB PBO.",
         f"Campanha no D ao final: aproximadamente {s['storage_d_gib']+s['estimated_additional_gib']:.0f} GiB. Deficit central de espaco: {s['estimated_additional_gib']-s['d_free_gib']:.0f} GiB.",
         "Faixa exploratoria de espaco adicional: 465 a 996 GiB. Usa multiplicadores 0.7 e 1.5 da projecao central, nao limites estatisticos.",
         "A extrapolacao usa bytes por snapshot do perfil correspondente, ou proxy explicitado no CSV de previsao. Inclui os arquivos parciais existentes e novas reexecucoes completas dos quatro interrompidos, sem apagar nada.",
         f"Num modelo linear de escrita e agendamento, o D esgotaria em cerca de {hi:.0f} h ({hi/24:.1f} dias), ANTES de terminar. Este instante e especialmente incerto; depende de novas execucoes, do perfil de trocas e de outros usos do disco.",
         "Nao ha capacidade suficiente para prometer o termino com a gravacao atual. E necessario providenciar espaco adicional ou planejar uma reducao da duplicacao dos registros detalhados HO sem perder as variaveis de interesse. Nenhuma mudanca desse tipo foi aplicada.",
         "", "## Todos os pontos concluidos", "",
         "| Altitude | FS | LF | Tratamento | INR20 (dB) | M20 (dB) | P(INR > -6) |",
         "|---:|---:|---:|---|---:|---:|---:|"]
for r in metrics:
    text.append(f"| {r['altitude']} | {r['height']} | {r['lf']} | {r['mode']} | {float(r['inr20_db']):.3f} | {float(r['margin20_db']):.3f} | {float(r['exceedance_pct']):.2f}% |")
text += ["", "## Arquivos", "",
         "- margens_concluidos_340km.png/pdf: resumo de margem com lacunas explicitas.",
         "- ccdf_HO_340km_FS20_LF20.png/pdf: baseline e todos os limites HO completos.",
         "- ccdf_PBO_340km_FS20_LF20.png/pdf e ccdf_PBO_340km_FS20_LF50.png/pdf: varreduras completas.",
         "- completed_metrics.csv: pontos concluidos e caminhos das fontes.",
         "- progress.csv: situacao dos 112 inputs do lote.",
         "- forecast_cases.csv: projecao e fonte de extrapolacao para cada caso restante.",
         "- summary.json: parametros e resultados numericos do levantamento."]
(OUT/"relatorio_previa.md").write_text("\n".join(text)+"\n",encoding="utf-8")
print(json.dumps({"report":str(OUT/"relatorio_previa.md"),"conditional_disk_full_hours":hi},indent=2))

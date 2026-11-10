"""Read-only campaign audit; writes derived previews outside raw output roots."""
import csv
import gzip
import heapq
import json
import math
from pathlib import Path
import re
import runpy
from datetime import datetime, timedelta, timezone
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
OUT = CAMPAIGN / "plots/preview_completed_20261031"
OUT.mkdir(exist_ok=True, parents=True)
plot = runpy.run_path(str(CAMPAIGN / "Scripts/plot_system_inr_ccdf.py"))
A = json.loads((ROOT / "tmp/tcc2_progress_20261031_a.json").read_text(encoding="utf-8-sig"))
B = json.loads((ROOT / "tmp/tcc2_progress_20261031_b.json").read_text(encoding="utf-8-sig"))
RX = re.compile(r"tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(BASELINE|HO\d+|PBO\d+km)")
GIB = 2**30
def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
now = dt(B["sampled_utc"])
active = {RX.search(p["CommandLine"]).group(0) for p in A["processes"] if RX.search(p["CommandLine"])}
earlier = {r["scenario"]: r for r in A["entries"]}
inputs = [p.stem for p in (CAMPAIGN / "input").glob("*.yaml")]
records = {}
arrays = {}
metrics = []
for item in B["entries"]:
    row = dict(item)
    match = RX.fullmatch(row["scenario"])
    if not match:
        continue
    row["altitude"], row["height"], row["lf"] = map(int, match.groups()[:3])
    row["mode"] = match[4]
    row["new_batch"] = row["path"].lower().startswith("d:")
    row["key"] = (row["altitude"], row["height"], row["lf"], row["mode"])
    row["status"] = "complete" if row["complete"] else (
        "running" if row["scenario"] in active else "interrupted" if row["new_batch"] else "historical_partial")
    row["seconds_per_snapshot"] = (dt(row["updated"]) - dt(row["created"])).total_seconds() / row["n"]
    row["bytes_per_snapshot"] = row["bytes"] / row["n"]
    prev = earlier[row["scenario"]]
    seconds = (now - dt(A["sampled_utc"])).total_seconds()
    row["recent_snapshots"] = row["n"] - prev["n"]
    row["recent_seconds_per_snapshot"] = seconds / row["recent_snapshots"] if row["recent_snapshots"] > 0 else None
    row["remaining_hours_lifetime_rate"] = (10000-row["n"])*row["seconds_per_snapshot"]/3600
    values, accepted, seeds = [], [], []
    with gzip.open(Path(row["path"]) / "tcc2_snapshots.csv.gz", "rt", newline="") as f:
        for entry in csv.DictReader(f):
            sid = int(entry["snapshot_id"])
            assert sid == len(values)+1, (row["scenario"], sid)
            value = float(entry["inr_after_db"])
            assert np.isfinite(value)
            values.append(value)
            accepted.append(int(entry["accepted_changes"]))
            seeds.append(entry["secondary_seed"])
            if sid == row["n"]:
                break
    assert len(values) == row["n"], row["scenario"]
    row["csv_validated"] = True
    row["mean_accepted_changes"] = float(np.mean(accepted))
    row["inr20_db"] = float(np.sort(values)[math.ceil(.8*len(values))-1])
    row["margin20_db"] = -6-row["inr20_db"]
    row["exceedance_pct"] = float(np.mean(np.array(values)>-6)*100)
    records[row["scenario"]] = row
    if row["complete"]:
        assert row["n"] == row["target"] == 10000
        arrays[row["key"]] = np.array(values)
        metrics.append({k: row[k] for k in ("scenario", "altitude", "height", "lf", "mode", "n", "inr20_db", "margin20_db", "exceedance_pct", "mean_accepted_changes", "path")})
    print(row["status"], row["scenario"], row["n"], flush=True)

# Cross-run realization pairing for completed HO comparisons, using campaign logic.
pairing = []
for row in records.values():
    if row["complete"] and row["mode"].startswith("HO"):
        base = next(r for r in records.values() if r["key"] == (*row["key"][:3], "BASELINE"))
        _, ids = plot["paired_samples"]({"BASELINE": Path(base["path"]), row["mode"]: Path(row["path"])})
        assert len(ids) == 10000
        pairing.append(row["scenario"])

with (OUT / "completed_metrics.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
    writer.writeheader()
    writer.writerows(metrics)
status_rows = []
for scenario in inputs:
    row = records.get(scenario)
    status_rows.append(dict(scenario=scenario, status=row["status"] if row else "queued",
        snapshots=row["n"] if row else 0, gib=row["bytes"]/GIB if row else 0,
        seconds_per_snapshot=row["seconds_per_snapshot"] if row else None,
        recent_seconds_per_snapshot=row["recent_seconds_per_snapshot"] if row else None,
        mean_accepted_changes=row["mean_accepted_changes"] if row else None,
        source=row["path"] if row else ""))
with (OUT / "progress.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(status_rows[0]))
    writer.writeheader()
    writer.writerows(status_rows)

def reference(scenario, metric):
    """Measured same-profile rate, then documented orbital/limit proxy."""
    a,h,lf,mode = RX.fullmatch(scenario).groups()
    a,h,lf = int(a),int(h),int(lf)
    usable = [r for r in records.values() if r["n"]>=1000]
    exact = [r for r in usable if r["key"]==(a,h,lf,mode)]
    if exact:
        return exact[0][metric], "same scenario"
    candidates = [r for r in usable if r["altitude"]==a and r["lf"]==lf and r["mode"]==mode]
    if candidates:
        return median(r[metric] for r in candidates), "same altitude/LF/treatment, other FS height"
    if mode.startswith("PBO"):
        candidates = [r for r in usable if r["altitude"]==a and r["lf"]==lf and r["mode"].startswith("PBO")]
        fresh = [r for r in candidates if r["new_batch"]]
        value = median(r[metric] for r in fresh or candidates)
        if not fresh and metric == "seconds_per_snapshot":
            old340 = [r[metric] for r in usable if r["altitude"]==340 and r["lf"]==lf and r["mode"]=="PBO100km"]
            new340 = [r[metric] for r in usable if r["altitude"]==340 and r["lf"]==lf and r["mode"].startswith("PBO") and r["new_batch"]]
            value *= median(new340)/median(old340)
        return value, "same-altitude/LF PBO; historical time adjusted by measured 340-km batch ratio"
    # No new 525-km HO yet: transfer the measured 340-km limit, scaled by
    # the old HO30 same-height/LF ratio between altitudes. Not a confidence interval.
    assert a == 525 and mode.startswith("HO"), scenario
    proxy, _ = reference(scenario.replace("525km", "340km"), metric)
    lower = records[f"tcc2_SA_noPY_340km_FS{h}m_LF{lf}_Azi90_HO30"][metric]
    upper = records[f"tcc2_SA_noPY_525km_FS{h}m_LF{lf}_Azi90_HO30"][metric]
    return proxy*upper/lower, "340-km same-limit proxy scaled by historical 525/340 HO30 ratio"

predictions=[]
for row in status_rows:
    if row["status"]=="complete":
        continue
    time_rate,time_method=reference(row["scenario"], "seconds_per_snapshot")
    byte_rate,byte_method=reference(row["scenario"], "bytes_per_snapshot")
    # Interrupted runs cannot resume: budget a separate full rerun, keep old files.
    needed=10000-row["snapshots"] if row["status"]=="running" else 10000
    predictions.append(dict(scenario=row["scenario"],status=row["status"],
        hours=time_rate*needed/3600, additional_gib=max(0,byte_rate*10000/GIB-row["gib"]) if row["status"]=="running" else byte_rate*10000/GIB,
        time_method=time_method,space_method=byte_method))
slots=[p["hours"] for p in predictions if p["status"]=="running"]
assert len(slots)==12
heapq.heapify(slots)
queued = [p for p in predictions if p["status"]=="queued"]
for p in queued:
    heapq.heapreplace(slots,slots[0]+p["hours"])
automatic_hours=max(slots)
for p in predictions:
    if p["status"]=="interrupted":
        heapq.heapreplace(slots,slots[0]+p["hours"])
with (OUT / "forecast_cases.csv").open("w",newline="",encoding="utf-8") as f:
    writer=csv.DictWriter(f,fieldnames=list(predictions[0]))
    writer.writeheader();writer.writerows(predictions)

plt.rcParams.update({"font.family":"serif","font.size":11,"axes.titlesize":12,"legend.fontsize":9})
fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
lookup={r["key"]:r for r in records.values() if r["complete"]}
colors={(20,20):"#0072B2",(20,50):"#D55E00",(40,20):"#009E73",(40,50):"#CC79A7"}
for ax,tech,xs in zip(axes,("HO","PBO"),([0,5,10,15,20,25],[0,*range(10,101,10)])):
    for h,lf in colors:
        modes=["BASELINE" if x==0 else f"HO{x}" if tech=="HO" else f"PBO{x}km" for x in xs]
        if not any((340,h,lf,m) in lookup for m in modes[1:]):
            continue
        ys=[lookup[(340,h,lf,m)]["margin20_db"] if (340,h,lf,m) in lookup else np.nan for m in modes]
        ax.plot(xs,ys,marker="o" if h==20 else "s",markersize=5,color=colors[h,lf],
            linestyle="-" if lf==20 else "--",label=f"FS={h} m, LF={lf}%")
    ax.axhline(0,color="black",linestyle=":",linewidth=1.3,label="Criterio: M20 = 0 dB")
    ax.set_title("Handover" if tech=="HO" else "Power back-off de 10 dB")
    ax.set_xlabel("Limite de reassociacoes por snapshot" if tech=="HO" else "Faixa externa ao Paraguai (km)")
    ax.set_ylabel("M20 = -6 - INR20 (dB)")
    ax.set_xticks(xs)
    ax.grid(alpha=.25)
    ax.legend(loc="best")
fig.suptitle("DC-MSS System 3, 340 km | Casos concluidos: 10.000 snapshots",fontsize=14)
fig.text(.5,.015,"Estimativas pontuais, sem IC. Lacunas = casos nao concluidos; HO30 parcial nao incluido.",ha="center",fontsize=10)
fig.tight_layout(rect=(0,.05,1,.94))
for ext in ("png","pdf"):
    fig.savefig(OUT / f"margens_concluidos_340km.{ext}",dpi=220)
plt.close(fig)

for technique,lf in (("HO",20),("PBO",20),("PBO",50)):
    fig,ax=plt.subplots(figsize=(8,4.7))
    modes=["BASELINE"]+([f"HO{i}" for i in (5,10,15,20,25)] if technique=="HO" else [f"PBO{i}km" for i in range(10,101,10)])
    palette=plt.get_cmap("tab10")
    for i,mode in enumerate(modes):
        samples=arrays.get((340,20,lf,mode))
        if samples is None: continue
        x,y=plot["compute_ccdf"](samples)
        ax.plot(x,np.clip(y,1e-4,1),linewidth=1.4,color="#333333" if i==0 else palette((i-1)%10),label=mode)
    ax.plot([-6,-6],[.2,1],"k:",linewidth=1.4,label="-6 dB / 20%")
    ax.set(yscale="log",ylim=(1e-4,1),xlabel="INR (dB)",ylabel="CCDF",
        title=f"{technique} | System 3, 340 km, FS=20 m, LF={lf}%\n10.000 snapshots por curva")
    ax.grid(True,which="both",alpha=.25)
    ax.legend(ncol=2,fontsize=8)
    fig.tight_layout()
    for ext in ("png","pdf"):
        fig.savefig(OUT/f"ccdf_{technique}_340km_FS20_LF{lf}.{ext}",dpi=220)
    plt.close(fig)

counts={status:sum(r["status"]==status for r in status_rows) for status in ("complete","running","interrupted","queued")}
future=sum(p["additional_gib"] for p in predictions)
summary=dict(sampled_utc=B["sampled_utc"],sample_interval_seconds=(now-dt(A["sampled_utc"])).total_seconds(),
    current_batch_cases=len(inputs),current_batch_status=counts,
    current_batch_recorded_snapshots=sum(r["snapshots"] for r in status_rows),
    total_completed_cases=len(metrics),historical_partial_cases=8,
    completed_ho_pairing_verified=pairing,
    storage_c_gib=sum(r["bytes"] for r in records.values() if not r["new_batch"])/GIB,
    storage_d_gib=sum(r["bytes"] for r in records.values() if r["new_batch"])/GIB,
    d_free_gib=next(d["Free"] for d in B["disks"] if d["Name"]=="D")/GIB,
    estimated_additional_gib=future,planning_storage_range_gib=[.7*future,1.5*future],
    automatic_queue_hours=automatic_hours,with_four_manual_restarts_hours=max(slots),
    planning_time_range_hours=[.65*max(slots),1.5*max(slots)],
    nominal_finish_local=(now+timedelta(hours=max(slots))).astimezone(timezone(timedelta(hours=-3))).isoformat(),
    active_progress=[dict(scenario=r["scenario"],n=r["n"],recent_delta=r["recent_snapshots"],
        sec_per_snapshot=r["seconds_per_snapshot"],recent_sec_per_snapshot=r["recent_seconds_per_snapshot"],
        remaining_hours=r["remaining_hours_lifetime_rate"]) for r in records.values() if r["status"]=="running"],
    interrupted=[dict(scenario=r["scenario"],n=r["n"],updated=r["updated"]) for r in records.values() if r["status"]=="interrupted"],
    assumptions=["Static measured rates, 12 concurrent workers, uninterrupted execution and adequate disk space.",
        "Unstarted FS heights use same-altitude/LF/treatment proxy; 525-km HO uses historical orbital ratio.",
        "Interrupted cases need manual full reruns; no checkpoint/resume assumed.",
        "Planning ranges are sensitivity bands, not statistical confidence intervals.",
        "HO30 historical partial runs are preserved, excluded from complete-case figures and remaining batch forecast."])
(OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2),flush=True)

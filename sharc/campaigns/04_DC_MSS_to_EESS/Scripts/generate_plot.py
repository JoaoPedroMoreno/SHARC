"""Plots da campanha V2 risk-gated, usando somente runs completos."""
from pathlib import Path
import re
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CAMP = Path(__file__).resolve().parents[1]
OUT, PLOTS = CAMP/"output", CAMP/"plots"/"v2_risk_gate_5000"
N, LIMIT = 5000, -154.0
GUARD_BANDS = [5, 10, 60, 65, 70, 75, 80]
PAT = re.compile(r"system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_GB_(5|10|60|65|70|75|80)MHz_STRATEGY_V2_RISK_GATE_(\d{4}-\d{2}-\d{2})_(\d+)")

def nrows(p):
    with p.open("rb") as f: return sum(1 for _ in f)-1

def runs():
    found={}
    for d in OUT.iterdir():
        m=PAT.fullmatch(d.name) if d.is_dir() else None
        if not m: continue
        s=d/"interference_aware_handover_v2_snapshot.csv"
        y=d/"system_dl_interf_power_per_mhz.csv"
        if not s.is_file() or not y.is_file() or nrows(s)!=N or nrows(y)!=N: continue
        key=(int(m[1]),m[2],float(m[3]),int(m[4])); stamp=(m[5],int(m[6]))
        if key not in found or stamp>found[key][0]: found[key]=(stamp,d)
    if len(found)!=56: raise RuntimeError(f"Esperados 56 runs completos; encontrados {len(found)}")
    return {k:v[1] for k,v in found.items()}

def load(rs):
    frames={}; rows=[]
    for key,d in sorted(rs.items()):
        alt,eess,lf,gb=key; x=pd.read_csv(d/"interference_aware_handover_v2_snapshot.csv")
        ev=pd.read_csv(d/"interference_aware_handover_v2_events.csv")
        frames[key]=x; crit=x.critical_before.astype(bool); act=x.actuation_flag.astype(bool)
        acc=ev[ev.accepted.astype(bool)]
        loss=acc.current_service_elevation_deg-acc.selected_service_elevation_deg
        red=x.loc[act,"iagg_reduction_db"]
        rows.append(dict(altitude_km=alt,eess_system=eess,load_factor=lf,guard_band_mhz=gb,
          frequency_mhz=2197.5-gb,snapshots=len(x),
          p99_before=x.iagg_before_dbw_per_mhz.quantile(.99),p99_after=x.iagg_after_dbw_per_mhz.quantile(.99),
          exceed_before_pct=100*crit.mean(),exceed_after_pct=100*x.critical_after.astype(bool).mean(),
          gate_pct=100*x.gate_entered.astype(bool).mean(),handover_pct=100*act.mean(),
          handovers=int(x.reassigned_beams.sum()),became_compliant=int(x.became_compliant.astype(bool).sum()),
          rescued_pct=100*x.became_compliant.astype(bool).sum()/max(crit.sum(),1),
          reduction_median_db=red.median() if len(red) else 0,reduction_p90_db=red.quantile(.9) if len(red) else 0,
          c1_median=x.loc[crit,"concentration_c1"].median() if crit.any() else np.nan,
          c13_median=x.loc[crit,"concentration_c1_c3"].median() if crit.any() else np.nan,
          elevation_loss_median_deg=loss.median() if len(loss) else np.nan,
          elevation_loss_p90_deg=loss.quantile(.9) if len(loss) else np.nan,
          unresolved=int(x.unresolved_count.sum()),candidates=int(x.candidates_evaluated.sum()),run=d.name))
    return frames,pd.DataFrame(rows)

def save(fig,name):
    fig.tight_layout(); fig.savefig(PLOTS/(name+".png"),dpi=220,bbox_inches="tight"); fig.savefig(PLOTS/(name+".pdf"),bbox_inches="tight"); plt.close(fig)

SC=[(340,"B"),(340,"D"),(525,"B"),(525,"D")]
def facets(title):
    f,a=plt.subplots(2,2,figsize=(13,9),sharex=True); f.suptitle(title); return f,a

def metric(df,before,after,y,title,name,ref=None):
    f,a=facets(title)
    for ax,(alt,eess) in zip(a.flat,SC):
      for lf,c in [(.2,"tab:blue"),(.5,"tab:orange")]:
        q=df[(df.altitude_km==alt)&(df.eess_system==eess)&(df.load_factor==lf)].sort_values("guard_band_mhz")
        ax.plot(q.guard_band_mhz,q[before],"o-",color=c,label=f"LF {lf} before")
        ax.plot(q.guard_band_mhz,q[after],"s--",color=c,label=f"LF {lf} after")
      if ref is not None: ax.axhline(ref,color="black",lw=1)
      ax.set(title=f"{alt} km — EESS {eess}",xlabel="Guard band [MHz]",ylabel=y); ax.set_xticks(GUARD_BANDS); ax.legend(fontsize=8)
    save(f,name)

def ccdf(frames):
    f,a=plt.subplots(4,2,figsize=(14,17),sharex=True,sharey=True)
    colors=dict(zip(GUARD_BANDS,plt.cm.viridis(np.linspace(.04,.96,len(GUARD_BANDS)))))
    for row,(alt,eess) in enumerate(SC):
      for col,lf in enumerate([.2,.5]):
        ax=a[row,col]
        for gb in GUARD_BANDS:
          x=frames[(alt,eess,lf,gb)]
          for field,style,label in [("iagg_before_dbw_per_mhz","-","before"),("iagg_after_dbw_per_mhz","--","after")]:
            v=np.sort(x[field]); p=(N-np.arange(N))/N; ax.plot(v,p,style,color=colors[gb],lw=1.2,label=f"GB {gb} {label}")
        ax.axvline(LIMIT,color="black",lw=1); ax.axhline(.01,color="gray",lw=1); ax.set_yscale("log"); ax.set_ylim(1/N,1)
        ax.set(title=f"{alt} km — EESS {eess} — LF {lf}",xlabel="Iagg [dBW/MHz]",ylabel="CCDF"); ax.legend(fontsize=7,ncol=2)
    f.suptitle("CCDF before and after V2 risk-gated handover"); save(f,"01_ccdf_before_after")

def operational(df):
    f,a=facets("V2 handover and critical-snapshot rescue rates")
    for ax,(alt,eess) in zip(a.flat,SC):
      for lf,c in [(.2,"tab:blue"),(.5,"tab:orange")]:
        q=df[(df.altitude_km==alt)&(df.eess_system==eess)&(df.load_factor==lf)].sort_values("guard_band_mhz")
        ax.plot(q.guard_band_mhz,q.handover_pct,"o-",color=c,label=f"LF {lf} handover")
        ax.plot(q.guard_band_mhz,q.rescued_pct,"s--",color=c,label=f"LF {lf} rescued")
      ax.set(title=f"{alt} km — EESS {eess}",xlabel="Guard band [MHz]",ylabel="Percentage [%]"); ax.set_xticks(GUARD_BANDS); ax.legend(fontsize=8)
    save(f,"04_handover_and_rescue")

def combined(df,cols,labels,title,name,y):
    f,a=facets(title)
    for ax,(alt,eess) in zip(a.flat,SC):
      for lf,c in [(.2,"tab:blue"),(.5,"tab:orange")]:
        q=df[(df.altitude_km==alt)&(df.eess_system==eess)&(df.load_factor==lf)].sort_values("guard_band_mhz")
        ax.plot(q.guard_band_mhz,q[cols[0]],"o-",color=c,label=f"LF {lf} {labels[0]}"); ax.plot(q.guard_band_mhz,q[cols[1]],"s--",color=c,label=f"LF {lf} {labels[1]}")
      ax.set(title=f"{alt} km — EESS {eess}",xlabel="Guard band [MHz]",ylabel=y); ax.set_xticks(GUARD_BANDS); ax.legend(fontsize=8)
    save(f,name)

def main():
    plt.rcParams.update({"axes.grid":True,"grid.linestyle":":","grid.alpha":.4,"font.size":9}); PLOTS.mkdir(parents=True,exist_ok=True)
    rs=runs(); frames,df=load(rs); df.to_csv(PLOTS/"campaign_summary.csv",index=False)
    ccdf(frames)
    metric(df,"p99_before","p99_after","P99 [dBW/MHz]","P99 before and after V2","02_p99_before_after",LIMIT)
    metric(df,"exceed_before_pct","exceed_after_pct","Exceedance [%]","Exceedance of -154 dBW/MHz","03_exceedance_before_after",1)
    operational(df)
    combined(df,["reduction_median_db","elevation_loss_median_deg"],["reduction [dB]","elevation loss [deg]"],"Mitigation benefit and service cost","05_reduction_elevation","Median")
    q=df.copy(); q["c1_pct"]=100*q.c1_median; q["c13_pct"]=100*q.c13_median
    combined(q,["c1_pct","c13_pct"],["C1","C1:3"],"Critical interference concentration","06_concentration","Median concentration [%]")
    print(f"56/56 complete; plots: {PLOTS}"); print(df.to_string(index=False))

if __name__=="__main__": main()

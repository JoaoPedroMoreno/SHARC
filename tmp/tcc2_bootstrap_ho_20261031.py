"""Reuse the campaign-02 percentile bootstrap for completed TCC2 HO cases."""
import csv
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"sharc/campaigns/02_DC_MSS_to_FS 2/Script"))
from bootstrap_inr20_confidence import bootstrap_inr20_ci, classify_margin, DEFAULT_BOOTSTRAPS, BOOTSTRAP_SEED
OUT=ROOT/"sharc/campaigns/07_TCC2_DC_MSS_to_FS/plots/preview_completed_20261031"
with (OUT/"completed_metrics.csv").open(newline="") as f:
    cases=[r for r in csv.DictReader(f) if r["altitude"]=="340" and r["lf"]=="20" and (r["mode"]=="BASELINE" or r["mode"].startswith("HO"))]
cases.sort(key=lambda r:(int(r["height"]),0 if r["mode"]=="BASELINE" else int(r["mode"][2:])))
rng=np.random.default_rng(BOOTSTRAP_SEED)
report_path = OUT/"ho_bootstrap_classification.json"
results=json.loads(report_path.read_text()) if report_path.exists() else []
roots = [ROOT/"sharc/campaigns/07_TCC2_DC_MSS_to_FS/output", Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS")]
manifests = []
for root in roots:
    for path in root.glob("*/tcc2_manifest.json"):
        manifest = json.loads(path.read_text())
        if manifest.get("complete"):
            manifests.append((path.parent, manifest))
profiles = {m["scenario"].rsplit("_",1)[0] for p,m in manifests if m["scenario"].rsplit("_",1)[1].startswith("HO")}
seen = {r["scenario"] for r in results}
cases = [dict(scenario=m["scenario"], path=str(p)) for p,m in manifests
         if m["scenario"].rsplit("_",1)[0] in profiles
         and (m["scenario"].endswith("BASELINE") or m["scenario"].rsplit("_",1)[1].startswith("HO"))
         and m["scenario"] not in seen]
cases.sort(key=lambda r:r["scenario"])
for case in cases:
    source=Path(case["path"])/"system_inr.csv"
    with source.open(newline="") as f:
        values=np.array([float(r["samples"]) for r in csv.DictReader(f)])
    assert len(values)==10000 and np.isfinite(values).all()
    q,lo,hi=bootstrap_inr20_ci(values,n_bootstrap=DEFAULT_BOOTSTRAPS,rng=rng)
    result=dict(scenario=case["scenario"],n=len(values),bootstrap=DEFAULT_BOOTSTRAPS,seed=BOOTSTRAP_SEED,
        inr20=q,inr_ci_low=lo,inr_ci_high=hi,margin=-6-q,margin_ci_low=-6-hi,margin_ci_high=-6-lo,
        classification=classify_margin(-6-hi,-6-lo),source=str(source))
    results.append(result)
    print(json.dumps(result),flush=True)
report_path.write_text(json.dumps(results,indent=2))

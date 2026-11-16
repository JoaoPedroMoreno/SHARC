"""Metadata-only remaining-storage estimate; never reads large output contents."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from statistics import median
import time

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
OUTPUT = Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS")
GIB = 2**30
RX = re.compile(r'tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km)')


def key(name):
    m = RX.fullmatch(name)
    return (*map(int, m.groups()[:3]), m[4])


def read(path):
    for attempt in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            time.sleep(.1)


plan = read(CAMPAIGN / "input/generation_report.json")
prior = read(CAMPAIGN / "plots/preview_completed_20261031/storage_forecast_delta.json")
predictions = {r["scenario"]: r for r in prior["predictions"]}
names = [Path(f).stem for f in plan["generated"]]
current = {}
root_bytes = 0
for folder in OUTPUT.iterdir():
    if not folder.is_dir():
        continue
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    root_bytes += size
    manifest = folder / "tcc2_manifest.json"
    if not manifest.exists():
        continue
    m = read(manifest)
    name = m["scenario"]
    if name not in names:
        continue
    if name in current:
        raise ValueError(f"Duplicate output needs manual selection: {name}")
    n = m["completed_snapshots"]
    current[name] = dict(snapshots=n, bytes=size, complete=m["complete"], target=m["snapshots"], source=str(folder))

pbo_factors = [r["bytes"]/(predictions[name]["central_gib"]*GIB)
               for name, r in current.items() if "_PBO" in name and r["complete"]]
pbo_factor = median(pbo_factors) if pbo_factors else 1.
cases = []
for name in names:
    p = predictions[name]
    r = current.get(name)
    a, h, lf, mode = key(name)
    if r and r["complete"]:
        central = low = high = 0.
        status, method = "complete", "actual completed output"
    elif r and r["snapshots"] >= 200:
        projected = r["bytes"] / r["snapshots"] * r["target"] / GIB
        central = max(0., projected - r["bytes"]/GIB)
        low, high = .8*central, 1.5*central
        status, method = "active", "observed output bytes per committed snapshot"
    else:
        status = "active" if r else "queued"
        if mode.startswith("HO"):
            proxy = f"tcc2_SA_noPY_340km_FS{h}m_LF{lf}_Azi90_{mode}"
            measured = current[proxy]
            factor = measured["bytes"] / max(1, measured["snapshots"]) * measured["target"] / (
                predictions[proxy]["central_gib"] * GIB)
            method = "historical DELTA model calibrated by current same-height/LF/HO 340-km output"
        else:
            factor, method = pbo_factor, "historical compact PBO calibrated by current completed PBO"
        already = r["bytes"]/GIB if r else 0.
        central = max(0., p["central_gib"]*factor - already)
        low = max(0., min(p["low_gib"]*factor, .8*p["central_gib"]*factor) - already)
        high = max(0., max(p["high_gib"]*factor, 1.5*p["central_gib"]*factor) - already)
    cases.append(dict(scenario=name, status=status, technique="HO" if mode.startswith("HO") else "PBO",
                      additional_gib=central, additional_low_gib=low, additional_high_gib=high, method=method))

total, used, free = shutil.disk_usage("D:/")
central = sum(c["additional_gib"] for c in cases)
high = sum(c["additional_high_gib"] for c in cases)
summary = dict(sampled_at=datetime.now().astimezone().isoformat(),
               disk_total_gib=total/GIB, disk_used_gib=used/GIB, disk_free_gib=free/GIB,
               disk_free_decimal_gb=free/1e9, current_campaign_D_gib=root_bytes/GIB,
               counts=dict(Counter(c["status"] for c in cases)),
               additional_expected_gib=central, additional_high_gib=high,
               free_after_expected_gib=free/GIB-central, free_after_high_gib=free/GIB-high,
               margin_after_high_and_20gib_reserve=free/GIB-high-20,
               by_technique={mode:dict(additional_expected_gib=sum(c["additional_gib"] for c in cases if c["technique"]==mode),
                                      additional_high_gib=sum(c["additional_high_gib"] for c in cases if c["technique"]==mode))
                             for mode in ("HO", "PBO")},
               pbo_calibration=pbo_factor,
               caveats=["Campaign 07 remaining jobs only; no campaign-08 outputs included.",
                        "No other disk growth, duplicate reruns or decompression of detailed CSVs assumed.",
                        "High estimate is engineering sensitivity, not a guaranteed maximum.",
                        "525-km HO storage still extrapolated from previous DELTA benchmarks and current 340-km samples.",
                        "Active file sizes and committed counters are sampled non-atomically; small discrepancies possible."])
(ROOT / "tmp/tcc2_storage_20261110.json").write_text(json.dumps(dict(summary=summary,cases=cases,current=current),indent=2))
print(json.dumps(summary, indent=2))

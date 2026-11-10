"""Read-only ETA refresh: committed manifests, recent rates and historical proxies."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import heapq
import json
from pathlib import Path
import re
from statistics import median
import time

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
RX = re.compile(r'tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km|BASELINE)')


def key(s):
    m = RX.search(s)
    return (*map(int, m.groups()[:3]), m[4])


def read_json(path):
    for attempt in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            time.sleep(.1)


plan = read_json(CAMPAIGN / "input/generation_report.json")
scenarios = {Path(f).stem for f in plan["generated"]}
prior = read_json(ROOT / "tmp/tcc2_eta_20261109.json")
previous = {r["scenario"]: r for r in prior["records"]}
history = read_json(ROOT / "tmp/tcc2_progress_20261031_b.json")
hist = {key(r["scenario"]): r for r in history["entries"]}
now = datetime.now().astimezone()
records = {}
for folder in sorted(Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS").glob("output_*_2026-11-*")):
    path = folder / "tcc2_manifest.json"
    if not path.exists():
        continue
    m = read_json(path)
    if m["scenario"] not in scenarios:
        continue
    k = key(m["scenario"])
    if k in records:
        raise ValueError(f"Duplicate current result: {k}")
    n = m["completed_snapshots"]
    created, updated = folder.stat().st_ctime, path.stat().st_mtime
    if n <= 0:
        raise ValueError("Cannot estimate a zero-snapshot result")
    lifetime = (updated - created) / n
    r = dict(scenario=m["scenario"], n=n, target=m["snapshots"], complete=m["complete"],
             created=created, updated=updated, lifetime_seconds_per_snapshot=lifetime,
             current_seconds_per_snapshot=lifetime, age_seconds=now.timestamp()-updated,
             source=str(folder), rate_basis="since this scenario started")
    p = previous.get(m["scenario"])
    if p and n > p["n"] and updated - p["updated"] > 3600:
        r["advance_since_previous_sample"] = n - p["n"]
        r["recent_seconds_per_snapshot"] = (updated - p["updated"]) / (n - p["n"])
        if not m["complete"]:
            r["current_seconds_per_snapshot"] = r["recent_seconds_per_snapshot"]
            r["rate_basis"] = "advance since 2026-11-09 morning sample"
    records[k] = r


def historical(k):
    a, h, lf, mode = k
    r = hist.get(k)
    if r and r["n"] >= 1000:
        return (datetime.fromisoformat(r["updated"]) - datetime.fromisoformat(r["created"])).total_seconds()/r["n"]
    matches = [historical(kk) for kk, v in hist.items()
               if kk[0] == a and kk[2] == lf and kk[3] == mode and v["n"] >= 1000]
    if matches:
        return median(matches)
    if mode.startswith("PBO"):
        return median(historical(kk) for kk, v in hist.items()
                      if kk[0] == a and kk[2] == lf and kk[3].startswith("PBO") and v["n"] >= 1000)
    if a != 525:
        raise ValueError(f"No historical proxy: {k}")
    return historical((340, h, lf, mode)) * historical((525, h, lf, "HO30")) / historical((340, h, lf, "HO30"))


pbo_calibration = median([r["current_seconds_per_snapshot"] / historical(k)
                          for k, r in records.items() if k[3].startswith("PBO") and r["complete"]])


def forecast(recent=True, calibrate_pbo=True):
    jobs = []
    for filename in plan["generated"]:
        k = key(filename)
        a, h, lf, mode = k
        r = records.get(k)
        field = "current_seconds_per_snapshot" if recent else "lifetime_seconds_per_snapshot"
        if r:
            status = "complete" if r["complete"] else "active"
            rate, remaining = r[field], r["target"]-r["n"]
            method = r["rate_basis"] if recent else "lifetime"
        elif mode.startswith("HO"):
            # Same FS height/LF/HO limit, scaled by historical 525/340 costs.
            observed = records[(340, h, lf, mode)]
            rate = observed[field] * historical(k) / historical((340, h, lf, mode))
            status, remaining = "queued", 10000
            method = "current same-profile 340 km rate times historical altitude ratio"
        else:
            rate = historical(k) * (pbo_calibration if calibrate_pbo else 1.)
            status, remaining = "queued", 10000
            method = "historical PBO rate, calibrated by newly completed PBO" if calibrate_pbo else "historical PBO"
        jobs.append(dict(scenario=Path(filename).stem, status=status, seconds_per_snapshot=rate,
                         completed_snapshots=r["n"] if r else 0, remaining_snapshots=remaining,
                         remaining_hours=rate*remaining/3600, rate_basis=method))
    slots = [j["remaining_hours"] for j in jobs if j["status"] == "active"]
    if len(slots) != 12:
        raise ValueError(f"Recheck worker concurrency: found {len(slots)}")
    heapq.heapify(slots)
    for job in jobs:
        if job["status"] == "complete":
            finish = 0.
        elif job["status"] == "active":
            finish = job["remaining_hours"]
        else:
            start = heapq.heappop(slots)
            finish = start + job["remaining_hours"]
            heapq.heappush(slots, finish)
            job["expected_start_local"] = (now+timedelta(hours=start)).isoformat()
        job["expected_finish_local"] = (now+timedelta(hours=finish)).isoformat()
    return max(slots), jobs


hours, jobs = forecast()
variants = []
for recent, calibrate_pbo in ((True, False), (False, True), (False, False)):
    duration, _ = forecast(recent, calibrate_pbo)
    variants.append(dict(recent_rates=recent, calibrate_pbo=calibrate_pbo, remaining_hours=duration,
                         eta_local=(now+timedelta(hours=duration)).isoformat()))
low, high = .65*hours, 1.5*hours
summary = dict(sampled_at=now.isoformat(), counts=dict(Counter(j["status"] for j in jobs)),
               remaining_snapshots=sum(j["remaining_snapshots"] for j in jobs),
               remaining_hours=hours, remaining_days=hours/24,
               eta_local=(now+timedelta(hours=hours)).isoformat(),
               sensitivity_65_to_150pct=[(now+timedelta(hours=t)).isoformat() for t in (low, high)],
               previous_eta=prior["eta_local"], previous_sampled_at=prior["sampled_at"],
               advance_vs_previous_eta_hours=(datetime.fromisoformat(prior["eta_local"])-
                                             (now+timedelta(hours=hours))).total_seconds()/3600,
               pbo_calibration_factor=pbo_calibration,
               stale_active=[r["scenario"] for r in records.values() if not r["complete"] and r["age_seconds"]>600],
               variants=variants,
               assumptions=["Campaign 07 only; campaign 08 is not running or included.",
                            "12 concurrent workers, uninterrupted operation and adequate disk space.",
                            "Queue order from unchanged generation_report.json.",
                            "All 525-km jobs are still proxies, not measured in this batch.",
                            "Sensitivity range is a planning range, not a statistical confidence interval."])
result = dict(**summary, records=list(records.values()), jobs=jobs)
(ROOT / "tmp/tcc2_eta_20261110.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
for job in jobs:
    if job["status"] == "active":
        print(json.dumps(job))

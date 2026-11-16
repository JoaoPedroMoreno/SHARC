"""Read output metadata only; write a separate forecast, never simulation files."""
from collections import Counter
from datetime import datetime, timedelta
import heapq
import json
import os
from pathlib import Path
import re
import shutil
from statistics import median
import time

ROOT = Path(__file__).resolve().parents[1]
CAM = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
OUT = Path('D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS')
GIB = 2**30


def read(path):
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError:
            time.sleep(.1)
    raise ValueError(path)


def key(name):
    m = re.search(r'_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(.*)$', name)
    return int(m[1]), int(m[2]), int(m[3]), m[4]


def collect():
    records = []
    for folder in OUT.iterdir():
        path = folder / 'tcc2_manifest.json'
        if not folder.is_dir() or not path.exists():
            continue
        m = read(path)
        size = sum(f.stat().st_size for f in folder.iterdir() if f.is_file())
        n = m['completed_snapshots']
        created, updated = folder.stat().st_ctime, path.stat().st_mtime
        records.append(dict(scenario=m['scenario'], n=n, target=m['snapshots'],
                            complete=m['complete'], created=created, updated=updated,
                            bytes=size, source=str(folder),
                            lifetime_rate=(updated-created)/max(n, 1)))
    return records


plan = read(CAM / 'input/generation_report.json')
names = [Path(p).stem for p in plan['generated']]
assert set(names) == {p.stem for p in (CAM / 'input').glob('*.yaml')}
previous = {r['scenario']: r for r in read(ROOT / 'tmp/tcc2_eta_20261110.json')['records']}
records = collect()
current = {}
for r in records:
    name = r['scenario']
    if name in names:
        assert name not in current, f'Duplicate output: {name}'
        current[name] = r
now = datetime.now().astimezone()


def peers(name):
    a, h, lf, mode = key(name)
    return [r for r in current.values() if r['n'] >= 1000 and
            key(r['scenario'])[0] == a and key(r['scenario'])[2] == lf and
            (key(r['scenario'])[3] == mode if mode.startswith('HO') else
             key(r['scenario'])[3].startswith('PBO'))]


jobs = []
for name in names:
    r = current.get(name)
    matches = peers(name)
    status = 'queued' if r is None else 'complete' if r['complete'] else 'active'
    n, target, size = (r['n'], r['target'], r['bytes']) if r else (0, 10000, 0)
    if r and n >= 100:
        rate = r['lifetime_rate']
        basis = 'lifetime'
        old = previous.get(name)
        if old and n > old['n'] and not r['complete']:
            rate = (r['updated']-old['updated'])/(n-old['n'])
            basis = 'progress since November 10'
    else:
        assert matches, name
        rate = median(p['lifetime_rate'] for p in matches)
        basis = 'measured same altitude/LF/HO or PBO peers'
    bps = size/n if r and n >= 200 else median(p['bytes']/p['n'] for p in matches)
    remaining = 0 if status == 'complete' else target-n
    extra = max(0, bps*target-size) if remaining else 0
    jobs.append(dict(scenario=name, status=status, n=n, target=target,
                     seconds_per_snapshot=rate, basis=basis,
                     remaining_hours=remaining*rate/3600, remaining_snapshots=remaining,
                     current_gib=size/GIB, additional_gib=extra/GIB))

active = [j for j in jobs if j['status']=='active']
assert len(active)==12, 'Recheck the running process inventory'
slots = [j['remaining_hours'] for j in active]
heapq.heapify(slots)
for j in jobs:
    if j['status']=='queued':
        start = heapq.heappop(slots)
        finish = start+j['remaining_hours']
        heapq.heappush(slots, finish)
        j['start_in_hours'] = start
    else:
        finish = j['remaining_hours']
    j['finish_in_hours'] = finish
    j['estimated_finish'] = (now+timedelta(hours=finish)).isoformat()
hours = max(slots)
free = shutil.disk_usage('D:/').free/GIB
extra = sum(j['additional_gib'] for j in jobs)
summary = dict(sampled_at=now.isoformat(), counts=dict(Counter(j['status'] for j in jobs)),
               by_technique={mode:dict(Counter(j['status'] for j in jobs
                                if key(j['scenario'])[3].startswith(mode))) for mode in ('HO','PBO')},
               remaining_snapshots=sum(j['remaining_snapshots'] for j in jobs),
               remaining_hours=hours, eta=(now+timedelta(hours=hours)).isoformat(),
               planning_eta_range=[(now+timedelta(hours=hours*f)).isoformat() for f in (.75,1.3)],
               campaign_on_D_gib=sum(r['bytes'] for r in records)/GIB,
               disk_free_gib=free, additional_gib=extra,
               additional_planning_range_gib=[.8*extra,1.5*extra],
               free_after_central_gib=free-extra, free_after_high_gib=free-1.5*extra,
               stale_active=[r['scenario'] for r in current.values() if not r['complete'] and
                             now.timestamp()-r['updated']>600],
               preserved_incomplete_not_in_queue=[dict(scenario=r['scenario'], n=r['n']) for r in records
                                                 if not r['complete'] and r['scenario'] not in names],
               caveats=['Campaign 07 only, not the future performance campaign.',
                        '12 workers and uninterrupted operation assumed; rates can improve as the queue drains.',
                        'Planning ranges are sensitivity estimates, not statistical confidence intervals.',
                        'File sizes and committed snapshots sampled non-atomically.',
                        'No decompression, extra reruns or other disk growth included.'])
result = dict(summary=summary, jobs=jobs, records=records)
(ROOT / 'tmp/tcc2_forecast_20261114.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
print('REMAINING JOBS')
for job in jobs:
    if job['status']!='complete':
        print(json.dumps(job))

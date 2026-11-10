"""Refresh the read-only campaign forecast using overnight progress."""
from collections import Counter
from datetime import datetime, timedelta
import heapq
import json
from pathlib import Path
import re
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT/'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
RX=re.compile(r'tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km|BASELINE)')
def key(s):
    m=RX.search(s)
    return (*map(int,m.groups()[:3]),m[4])

plan=json.loads((CAMPAIGN/'input/generation_report.json').read_text())
scenarios={Path(f).stem for f in plan['generated']}
old=json.loads((ROOT/'tmp/tcc2_progress_20261031_b.json').read_text(encoding='utf-8-sig'))
hist={key(r['scenario']):r for r in old['entries']}
yesterday=json.loads((ROOT/'tmp/tcc2_live_b_20261108.json').read_text())
previous={r['scenario']:r for r in yesterday['records']}
now=datetime.now().astimezone()
records={}
for folder in sorted(Path('D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS').glob('output_*_2026-11-*')):
    path=folder/'tcc2_manifest.json'
    if not path.exists():
        continue
    m=json.loads(path.read_text())
    if m['scenario'] not in scenarios:
        continue
    k=key(m['scenario'])
    assert k not in records,'Duplicate current results need manual selection'
    n=m['completed_snapshots']
    created,updated=folder.stat().st_ctime,path.stat().st_mtime
    r=dict(scenario=m['scenario'],n=n,complete=m['complete'],updated=updated,
           seconds_per_snapshot=(updated-created)/n,source=str(folder))
    if m['scenario'] in previous:
        p=previous[m['scenario']]
        r['overnight_advance']=n-p['n']
        r['overnight_seconds_per_snapshot']=(updated-p['updated'])/(n-p['n'])
    if not m['complete']:
        assert now.timestamp()-updated<300,('Stale output',m['scenario'])
    records[k]=r

def historical(k):
    a,h,lf,mode=k
    r=hist.get(k)
    if r and r['n']>=1000:
        return (datetime.fromisoformat(r['updated'])-datetime.fromisoformat(r['created'])).total_seconds()/r['n']
    matches=[historical(kk) for kk,v in hist.items() if kk[0]==a and kk[2]==lf and kk[3]==mode and v['n']>=1000]
    if matches:
        return median(matches)
    if mode.startswith('PBO'):
        return median(historical(kk) for kk,v in hist.items() if kk[0]==a and kk[2]==lf and kk[3].startswith('PBO') and v['n']>=1000)
    assert a==525,k
    return historical((340,h,lf,mode))*historical((525,h,lf,'HO30'))/historical((340,h,lf,'HO30'))

jobs=[]
for f in plan['generated']:
    k=key(f)
    a,h,lf,mode=k
    r=records.get(k)
    if r:
        rate=r['seconds_per_snapshot']
        status='complete' if r['complete'] else 'active'
    elif mode.startswith('HO'):
        observed=records[(340,20,lf,mode)]
        rate=historical(k)*observed['seconds_per_snapshot']/historical((340,20,lf,mode))
        status='queued'
    else:
        rate=historical(k)
        status='queued'
    remaining=10000-r['n'] if r else 10000
    jobs.append(dict(scenario=Path(f).stem,status=status,seconds_per_snapshot=rate,
                     remaining_hours=rate*remaining/3600,
                     eta_local=(now+timedelta(seconds=rate*remaining)).isoformat() if status=='active' else None))
slots=[j['remaining_hours'] for j in jobs if j['status']=='active']
assert len(slots)==12
heapq.heapify(slots)
for j in jobs:
    if j['status']=='queued':
        heapq.heapreplace(slots,slots[0]+j['remaining_hours'])
hours=max(slots)
result=dict(sampled_at=now.isoformat(),counts=dict(Counter(j['status'] for j in jobs)),
    remaining_hours=hours,remaining_days=hours/24,eta_local=(now+timedelta(hours=hours)).isoformat(),
    planning_range_days=[.65*hours/24,1.5*hours/24],previous_eta=yesterday['forecast']['eta_local'],
    advance_vs_previous_eta_hours=(datetime.fromisoformat(yesterday['forecast']['eta_local'])-(now+timedelta(hours=hours))).total_seconds()/3600,
    records=list(records.values()),jobs=jobs,
    method='Same 12-worker scheduling model; overnight measured HO rates and historical 525/340 and PBO proxies. Range is sensitivity, not a confidence interval. Assumes uninterrupted operation.')
(ROOT/'tmp/tcc2_eta_20261109.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('jobs','records')},indent=2))
for j in jobs:
    if j['status']=='active':
        print(json.dumps(j))

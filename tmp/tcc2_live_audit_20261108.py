"""Read-only committed snapshot audit and provisional scheduling forecast."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path
import re
from statistics import median
import sys
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sharc.propagation.propagation_p619 import PropagationP619
CAMPAIGN = ROOT/'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
RX = re.compile(r'tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km|BASELINE)')

def key(s):
    m=RX.search(s)
    return (*map(int,m.groups()[:3]),m[4])

def sample():
    rows=[]
    paired={}
    for folder in sorted(Path('D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS').glob('*_2026-11-08_*')):
        path=folder/'tcc2_manifest.json'
        m=json.loads(path.read_text())
        cfg=yaml.safe_load((folder/'tcc2_executed_config.yaml').read_text())
        fs=cfg['single_earth_station']
        prop=PropagationP619(np.random.RandomState(0),season=fs['season'],**{k:fs['param_p619'][k] for k in
             ('earth_station_alt_m','earth_station_lat_deg','mean_clutter_height','below_rooftop')})
        lookup=prop.get_lookup_table_status(fs['frequency'])
        assert 'ACTIVE/OK' in lookup
        for name in ('sharc/propagation/propagation_p619.py','sharc/cochannel_handover.py','sharc/support/tcc2_detailed_records.py'):
            expected=m['code_sha256'].get(name.replace('/','\\'),m['code_sha256'].get(name))
            assert expected==hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), name
        assert m['detailed_record_format']=='DELTA' and m['ue_performance_calculated'] is False
        assert cfg['general']['output_dir'].replace('\\','/')=='D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS'
        n=m['completed_snapshots']
        committed=[]
        with gzip.open(folder/'tcc2_snapshots.csv.gz','rt',newline='') as stream:
            for row in csv.DictReader(stream):
                if len(committed)==n:
                    break
                assert int(row['snapshot_id'])==len(committed)+1
                before,after=float(row['inr_before_db']),float(row['inr_after_db'])
                assert math.isfinite(before) and math.isfinite(after) and after<=before+1e-8
                assert int(row['accepted_changes'])<=int(m['scenario'].rsplit('HO',1)[1])
                committed.append(row)
                if len(committed)==n:
                    break
        assert len(committed)==n
        for r in committed:
            pk=(*key(m['scenario'])[:3],r['snapshot_id'])
            fingerprint=tuple(r[k] for k in ('secondary_seed','realization_sha256','baseline_links_sha256','inr_before_db'))
            assert paired.setdefault(pk,fingerprint)==fingerprint,pk
        details=list(folder.glob('*.delta.jsonl.gz'))
        assert len(details)==2 and not (folder/'tcc2_links.csv.gz').exists() and not (folder/'tcc2_users.csv.gz').exists()
        rows.append(dict(scenario=m['scenario'],n=n,complete=m['complete'],
            created=folder.stat().st_ctime,updated=path.stat().st_mtime,
            bytes=sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
            lookup=lookup,format=m['detailed_record_format'],performance=False,
            mean_accepted= float(np.mean([int(r['accepted_changes']) for r in committed])),
            max_prediction_error=max(float(r['max_prediction_error_db']) for r in committed),
            stop_reasons=dict(Counter(r['stop_reason'] for r in committed))))
    return dict(time=datetime.now(timezone.utc).isoformat(),records=rows,checks='finite non-increasing INR, limits, pairing, runtime config/code, DELTA files')

parser=argparse.ArgumentParser()
parser.add_argument('label')
parser.add_argument('--previous',type=Path)
args=parser.parse_args()
current=sample()
out=ROOT/f'tmp/tcc2_live_{args.label}_20261108.json'
out.write_text(json.dumps(current,indent=2))
if args.previous:
    previous=json.loads(args.previous.read_text())
    earlier={r['scenario']:r for r in previous['records']}
    for r in current['records']:
        p=earlier[r['scenario']]
        r['advanced']=r['n']-p['n']
        assert r['advanced']>0, r['scenario']
        r['recent_seconds_per_snapshot']=(r['updated']-p['updated'])/r['advanced']
        r['lifetime_seconds_per_snapshot']=(r['updated']-r['created'])/r['n']
    old=json.loads((ROOT/'tmp/tcc2_progress_20261031_b.json').read_text(encoding='utf-8-sig'))
    hist={key(r['scenario']):r for r in old['entries']}
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
    active={key(r['scenario']):r for r in current['records']}
    plan=json.loads((CAMPAIGN/'input/generation_report.json').read_text())
    jobs=[]
    for f in plan['generated']:
        k=key(f)
        a,h,lf,mode=k
        if mode.startswith('HO'):
            observed=active[(340,20,lf,mode)]
            ratio=observed['lifetime_seconds_per_snapshot']/historical((340,20,lf,mode))
            rate=historical(k)*ratio
        else:
            rate=historical(k)
        remaining=10000-active[k]['n'] if k in active else 10000
        jobs.append(dict(scenario=f.removesuffix('.yaml'),active=k in active,seconds_per_snapshot=rate,hours=rate*remaining/3600))
    slots=[j['hours'] for j in jobs if j['active']]
    assert len(slots)==12
    heapq.heapify(slots)
    for j in jobs:
        if not j['active']:
            heapq.heapreplace(slots,slots[0]+j['hours'])
    hours=max(slots)
    current['forecast']=dict(remaining_hours=hours,days=hours/24,
        eta_local=(datetime.now().astimezone()+timedelta(hours=hours)).isoformat(),
        sensitivity_days=[.65*hours/24,1.5*hours/24],jobs=jobs,
        method='12-worker list scheduling; current HO lifetime rates calibrated by historical same-profile rates; PBO historical; short initial sample, not a confidence interval')
    out.write_text(json.dumps(current,indent=2))
print(json.dumps({k:v for k,v in current.items() if k!='forecast'},indent=2),flush=True)
if 'forecast' in current:
    print(json.dumps({k:v for k,v in current['forecast'].items() if k!='jobs'},indent=2),flush=True)

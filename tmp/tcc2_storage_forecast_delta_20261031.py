"""Storage-only forecast from historical byte inventories and test records."""
import csv
import gzip
import io
from itertools import groupby
import json
from pathlib import Path
import re
from statistics import median
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharc.support.tcc2_detailed_records import DeltaWriter

GIB = 2**30
RX = re.compile(r'tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(BASELINE|HO\d+|PBO\d+km)')
CAMPAIGN = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
plan = json.loads((CAMPAIGN / 'input/generation_report.json').read_text())
audit = json.loads((ROOT / 'tmp/tcc2_output_cleanup_20261031.json').read_text(encoding='utf-8-sig'))
old_cleanup = json.loads((ROOT / 'tmp/tcc2_baseline_pbo_cleanup_20261028.json').read_text(encoding='utf-8-sig'))

def key(text):
    m = RX.search(text)
    return (*map(int, m.groups()[:3]), m[4])

baseline_bytes = {}
for r in old_cleanup['Deleted']:
    if r['Mode'] == 'BASELINE':
        profile = key(r['Path'])[:3]
        baseline_bytes[profile] = baseline_bytes.get(profile, 0) + r['Bytes']

historical = {}
for r in audit['records']:
    detail = sum(f['bytes'] for f in r['files'] if f['path'].endswith(('tcc2_links.csv.gz', 'tcc2_users.csv.gz')))
    historical[key(r['scenario'])] = dict(n=r['snapshots'], detail=detail, other=r['bytes']-detail)

benchmarks = []
with tempfile.TemporaryDirectory(prefix='tcc2_delta_size_') as temp:
    for case in sorted((ROOT / 'tmp/tcc2_victim_only_validation_20261026').iterdir()):
        if not case.is_dir():
            continue
        for dataset in ('links', 'users'):
            source = case / 'victim_only' / f'tcc2_{dataset}.csv.gz'
            target = Path(temp) / f'{case.name}_{dataset}.delta.jsonl.gz'
            writer = DeltaWriter(target)
            sums = {t: dict(full=0, delta=0, frames=0) for t in ('initial', 'changes')}
            previous_size = 0
            first = True
            with gzip.open(source, 'rt', newline='') as stream:
                reader = csv.DictReader(stream)
                for common, group in groupby(reader, key=lambda r:(r['snapshot_id'],r['secondary_seed'],r['step'])):
                    rows = list(group)
                    buffer = io.StringIO(newline='')
                    full = csv.DictWriter(buffer, fieldnames=reader.fieldnames)
                    if first:
                        full.writeheader()
                    full.writerows(rows)
                    full_size = len(gzip.compress(buffer.getvalue().encode('utf-8')))
                    writer.write(rows)
                    size = target.stat().st_size
                    kind = 'initial' if int(common[2]) == 0 else 'changes'
                    sums[kind]['full'] += full_size
                    sums[kind]['delta'] += size-previous_size
                    sums[kind]['frames'] += 1
                    previous_size, first = size, False
            benchmarks.append(dict(case=case.name, dataset=dataset, sizes=sums))
            print('Benchmarked', case.name, dataset, flush=True)

initial_ratios = {}
for altitude in (340,525):
    for lf in (20,50):
        records = [r['sizes']['initial'] for r in benchmarks if key(r['case'])[0]==altitude and key(r['case'])[2]==lf]
        initial_ratios[altitude,lf] = sum(r['delta'] for r in records)/sum(r['full'] for r in records)
changes = [r['sizes']['changes'] for r in benchmarks if r['sizes']['changes']['frames']]
step_ratio = sum(r['delta'] for r in changes)/sum(r['full'] for r in changes)

def reference(k, field):
    a,h,lf,mode = k
    r = historical.get(k)
    if r and r['n'] >= 1000:
        return r[field]/r['n']*10000, 'same scenario'
    matches = [v[field]/v['n']*10000 for (aa,hh,ll,mm),v in historical.items()
               if aa==a and ll==lf and mm==mode and v['n']>=1000]
    if matches:
        return median(matches), 'same altitude/LF/mode, other FS height'
    if mode.startswith('PBO'):
        matches = [v[field]/v['n']*10000 for (aa,hh,ll,mm),v in historical.items()
                   if aa==a and ll==lf and mm.startswith('PBO') and v['n']>=1000]
        return median(matches), 'same altitude/LF, other PBO distances'
    assert a == 525
    lower, _ = reference((340,h,lf,mode),field)
    high30, _ = reference((525,h,lf,'HO30'),field)
    low30, _ = reference((340,h,lf,'HO30'),field)
    return lower*high30/low30, '340-km same limit scaled by historical 525/340 HO30 ratio'

predictions = []
for filename in plan['generated']:
    k = key(filename)
    a,h,lf,mode = k
    other, method = reference(k,'other')
    if mode.startswith('HO'):
        old_detail, method = reference(k,'detail')
        initial = baseline_bytes[k[:3]] * initial_ratios[a,lf]
        delta = max(0,old_detail-baseline_bytes[k[:3]]) * step_ratio
        central = initial + delta + other
        # Engineering sensitivity range, not a statistical confidence interval.
        low = .9*initial + .5*delta + .8*other
        high = 1.15*initial + 2*delta + 1.5*other
        old = old_detail+other
    else:
        initial, delta, central = 0,0,other
        low, high, old = .9*other,1.15*other,other
    predictions.append(dict(scenario=filename.removesuffix('.yaml'),technique='HO' if mode.startswith('HO') else 'PBO',
        central_gib=central/GIB,low_gib=low/GIB,high_gib=high/GIB,old_full_gib=old/GIB,
        initial_detail_gib=initial/GIB,changed_detail_gib=delta/GIB,other_gib=other/GIB,method=method))

totals = {}
for technique in ('HO','PBO','ALL'):
    rows = [r for r in predictions if technique=='ALL' or r['technique']==technique]
    totals[technique] = dict(cases=len(rows),**{f:sum(r[f] for r in rows) for f in ('central_gib','low_gib','high_gib','old_full_gib','initial_detail_gib','changed_detail_gib','other_gib')})
result = dict(totals=totals,initial_delta_full_ratio={f'{a}km_LF{lf}':v for (a,lf),v in initial_ratios.items()},
    changed_frame_delta_full_ratio=step_ratio,benchmarks=benchmarks,predictions=predictions,
    caveats=['All 96 inputs counted from zero snapshots.', 'Uses historical deleted-file byte inventories; no simulation is run.',
             'Delta calibration uses small existing physical-test samples; 525-km changed frames extrapolate from 340 km.',
             'Bounds are engineering sensitivity scenarios, not a confidence interval or guaranteed maximum.',
             'Excludes existing outputs, future user-performance campaigns, duplicate runs and full CSV re-expansion.'])
out = CAMPAIGN/'plots/preview_completed_20261031/storage_forecast_delta.json'
out.write_text(json.dumps(result,indent=2))
print(json.dumps({k:result[k] for k in ('totals','initial_delta_full_ratio','changed_frame_delta_full_ratio')},indent=2),flush=True)

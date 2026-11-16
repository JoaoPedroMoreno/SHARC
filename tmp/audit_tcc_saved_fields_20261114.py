"""Read-only campaign data audit. Does not run snapshots or modify outputs."""
from collections import Counter, defaultdict
import csv
import gzip
from itertools import product
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from sharc.support.tcc2_detailed_records import read_detailed_rows

CAM07 = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
CAM08 = ROOT / 'sharc/campaigns/08_TCC2_DC_MSS_performance'
sys.path.insert(0, str(CAM08 / 'Scripts'))
import generate as gen08
from validate_physics import physical_config


def read_json(path):
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError:
            time.sleep(.1)
    raise ValueError(path)


def csv_rows(folder, dataset):
    with gzip.open(folder / f'tcc2_{dataset}.csv.gz', 'rt', newline='', encoding='utf-8') as stream:
        yield from csv.DictReader(stream)


def header(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        if '.delta.' in path.name:
            return json.loads(next(stream))['columns']
        return next(csv.reader(stream))


report = {'scope': 'metadata and first 10 committed INR rows per output; detailed first-snapshot sampling; no simulation runs',
          'inputs08': [], 'outputs07': [], 'schemas': {}, 'errors': [], 'detailed_samples': []}
expected = {gen08.name(a, h, lf, mode): gen08.build(a, h, lf, mode)
            for a, h, lf, mode in product(gen08.SYSTEMS, gen08.FS_HEIGHTS, gen08.LOAD_FACTORS, gen08.MODES)}
files08 = list((CAM08 / 'input').glob('*.yaml'))
assert {p.stem for p in files08} == set(expected)
for path in files08:
    cfg = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert cfg == expected[path.stem], path
    report['inputs08'].append(path.stem)
report['outputs08_found'] = [str(p) for root in [CAM08 / 'output', Path('D:/SHARC_outputs/08_TCC2_DC_MSS_performance')]
                            for p in root.glob('*/tcc2_manifest.json')]
print('Actual 08 inputs verified:', len(files08), flush=True)
schemas = defaultdict(dict)
best = {}
for root in [CAM07 / 'output', Path('D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS')]:
    for path in sorted(root.glob('*/tcc2_manifest.json')):
        m = read_json(path)
        folder = path.parent
        name = m['scenario']
        if not name.startswith('tcc2_SA_noPY_'):
            continue
        n = m['completed_snapshots']
        if not n:
            continue
        mode = name.split('_Azi90_')[1]
        family = 'HO' if mode.startswith('HO') else 'PBO' if mode.startswith('PBO') else 'BASELINE'
        row = dict(scenario=name, family=family, n=n, complete=m['complete'], folder=str(folder),
                   performance=m['ue_performance_calculated'], files=[p.name for p in folder.iterdir() if p.is_file()],
                   rows_checked=0, nonfinite_inr=0, first_snapshot=None)
        try:
            for item in csv_rows(folder, 'snapshots'):
                number = int(item['snapshot_id'])
                assert number == row['rows_checked']+1, ('nonsequential', name, number)
                assert int(item['secondary_seed']) == m['secondary_seeds'][number-1]
                before, after = float(item['inr_before_db']), float(item['inr_after_db'])
                row['nonfinite_inr'] += not (math.isfinite(before) and math.isfinite(after))
                assert after <= before+1e-8, ('inr increase', name, number)
                assert int(item['accepted_changes']) <= (int(mode[2:]) if family=='HO' else 0)
                if number == 1:
                    row['first_snapshot'] = item
                row['rows_checked'] += 1
                if number == min(n, 10):
                    break
            assert row['rows_checked'] == min(n, 10)
            for data in ('snapshots', 'steps', 'events', 'candidates', 'links', 'users'):
                candidates = [folder/f'tcc2_{data}.csv.gz', folder/f'tcc2_{data}.delta.jsonl.gz']
                found = [p for p in candidates if p.exists()]
                assert len(found) <= 1
                if found:
                    columns = header(found[0])
                    schemas[family].setdefault(data, columns)
                    assert schemas[family][data] == columns, ('schema mismatch', name, data)
            if family == 'HO':
                assert any('tcc2_links.' in f for f in row['files'])
                assert any('tcc2_users.' in f for f in row['files'])
                assert 'tcc2_steps.csv.gz' in row['files']
            cfg08name = name.replace('tcc2_', 'tcc2_perf_', 1)
            cfg07path = folder/'tcc2_executed_config.yaml'
            if not cfg07path.exists():
                cfg07path = folder/(name+'.yaml')
            cfg07 = yaml.safe_load(cfg07path.read_text(encoding='utf-8'))
            row['physical_config_matches08'] = physical_config(cfg07) == physical_config(expected[cfg08name])
        except Exception as exc:
            report['errors'].append(dict(scenario=name, error=str(exc)))
        report['outputs07'].append(row)
        if len(report['outputs07']) % 10 == 0:
            print('Outputs sampled:', len(report['outputs07']), flush=True)
        if name not in best or n > best[name]['n']:
            best[name] = row

for row in best.values():
    if not row['scenario'].endswith('_HO30'):
        continue
    folder = Path(row['folder'])
    print('Reconstructing first snapshot:', row['scenario'], flush=True)
    count = int(row['first_snapshot']['accepted_changes'])
    steps = {}
    for item in csv_rows(folder, 'steps'):
        if int(item['snapshot_id']) != 1:
            break
        steps[int(item['step'])] = item
        if int(item['step']) == count:
            break
    links = defaultdict(dict)
    reader = read_detailed_rows(folder, 'links')
    for item in reader:
        if int(item['snapshot_id']) != 1:
            break
        links[int(item['step'])][int(item['beam_id'])] = item
    reader.close()
    assert set(links) == set(range(count+1)), row['scenario']
    first = links[0]
    for step, beams in links.items():
        assert set(beams) == set(first)
        power = sum(float(b['i_link_mw']) for b in beams.values())
        assert math.isclose(power, float(steps[step]['iagg_mw']), rel_tol=1e-10)
        for beam, item in beams.items():
            for field in ('cell_id', 'cell_lat', 'cell_lon', 'active'):
                assert item[field] == first[beam][field]
            if item['active'] == 'True':
                assert all(math.isfinite(float(item[f])) for f in ('tx_offaxis_deg', 'rx_offaxis_deg',
                           'satellite_x_m', 'satellite_y_m', 'satellite_z_m', 'distance_paraguay_border_km'))
    user_ids = defaultdict(set)
    users = read_detailed_rows(folder, 'users')
    for item in users:
        if int(item['snapshot_id']) != 1:
            break
        step, beam = int(item['step']), int(item['beam_id'])
        assert beam in links[step]
        assert item['cell_id'] == links[step][beam]['cell_id']
        assert item['satellite_id'] == links[step][beam]['satellite_id']
        user_ids[step].add(int(item['user_id']))
    users.close()
    assert set(user_ids) == set(links)
    assert all(ids == user_ids[0] for ids in user_ids.values())
    events = []
    for item in csv_rows(folder, 'events') if (folder/'tcc2_events.csv.gz').exists() else ():
        if int(item['snapshot_id']) != 1:
            break
        events.append(item)
    assert sum(e['accepted']=='True' for e in events) == count
    report['detailed_samples'].append(dict(scenario=row['scenario'], snapshot=1,
        accepted=count, steps=len(steps), cells=len(first), users=len(user_ids[0]),
        active_cells=sum(b['active']=='True' for b in first.values()),
        links_sum_matches_steps=True, users_and_cells_join=True,
        angles_and_positions_finite_for_active=True, event_columns=list(events[0]) if events else []))

report['schemas'] = dict(schemas)
summary = dict(input08_count=len(files08), input08_matrix={'BASELINE':8,'HO':48,'PBO':80},
               production08_outputs=len(report['outputs08_found']),
               output07_count=len(report['outputs07']), unique07_cases=len(best),
               output07_by_family=dict(Counter(r['family'] for r in best.values())),
               committed_snapshot_rows_checked=sum(r['rows_checked'] for r in report['outputs07']),
               nonfinite_inr_rows=sum(r['nonfinite_inr'] for r in report['outputs07']),
               complete07_count=sum(r['complete'] for r in best.values()),
               detailed_ho_snapshots_checked=len(report['detailed_samples']), errors=report['errors'],
               physical_config_mismatches=[r['scenario'] for r in best.values() if not r.get('physical_config_matches08')],
               missing07_cases=[name.replace('tcc2_perf_', 'tcc2_', 1) for name in expected
                                if name.replace('tcc2_perf_', 'tcc2_', 1) not in best])
report['summary'] = summary
(ROOT/'tmp/audit_tcc_saved_fields_20261114.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
print(json.dumps(report['detailed_samples'], indent=2))

"""Read-only result audit; writes only a separate JSON report."""
import csv
from collections import Counter, defaultdict
from datetime import datetime
import gzip
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import runpy

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS'
ROOTS = [CAMPAIGN / 'output', Path('D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS')]


def differences(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        result = []
        for k in sorted(a.keys() | b.keys()):
            result.extend(differences(a.get(k), b.get(k), path + '/' + k))
        return result
    return [] if a == b else [dict(path=path, expected=a, executed=b)]


def inspect(folder, expected, normalize):
    record = dict(folder=str(folder), drive=folder.drive, issues=[])
    try:
        m = json.loads((folder / 'tcc2_manifest.json').read_text(encoding='utf-8'))
        scenario = m['scenario']
        record.update(scenario=scenario, target=m.get('snapshots'),
                      committed=m.get('completed_snapshots'), complete=m.get('complete'),
                      git_commit=m.get('git_commit'), performance=m.get('ue_performance_calculated'),
                      updated=datetime.fromtimestamp((folder / 'tcc2_manifest.json').stat().st_mtime).isoformat())
        config_file = folder / 'tcc2_executed_config.yaml'
        raw = config_file.read_bytes()
        config = yaml.safe_load(raw)
        record['config_hash_valid'] = hashlib.sha256(raw).hexdigest() == m.get('executed_config_sha256')
        if not record['config_hash_valid']:
            record['issues'].append('executed_config_hash_mismatch')
        record['config_differences'] = differences(normalize(expected[scenario]), normalize(config)) if scenario in expected else []
        seeds = m.get('secondary_seeds', [])
        values = []
        sequential = finite = seed_match = True
        stops = Counter()
        with gzip.open(folder / 'tcc2_snapshots.csv.gz', 'rt', newline='') as f:
            for n, row in enumerate(csv.DictReader(f), 1):
                sequential &= int(row['snapshot_id']) == n
                before, after = float(row['inr_before_db']), float(row['inr_after_db'])
                finite &= math.isfinite(before) and math.isfinite(after)
                seed_match &= n <= len(seeds) and int(row['secondary_seed']) == seeds[n - 1]
                values.append(after)
                stops[row['stop_reason']] += 1
        with (folder / 'system_inr.csv').open(newline='') as f:
            inrs = [float(row['samples']) for row in csv.DictReader(f)]
        same = len(inrs) == len(values) and all(math.isclose(a, b, rel_tol=0, abs_tol=1e-9) for a, b in zip(inrs, values))
        record.update(snapshot_rows=len(values), inr_rows=len(inrs), sequential_ids=sequential,
                      finite_inr=finite and all(map(math.isfinite, inrs)), seed_match=seed_match,
                      inr_matches_snapshots=same, stop_reasons=dict(stops),
                      auxiliary_files={p.name: p.stat().st_size for p in folder.glob('tcc2*') if p.is_file()})
        for key in ['sequential_ids', 'finite_inr', 'seed_match', 'inr_matches_snapshots']:
            if not record[key]:
                record['issues'].append(key)
        if len(values) != m.get('completed_snapshots'):
            record['issues'].append('manifest_row_count_mismatch')
        record['validated_complete'] = (not record['issues'] and m.get('complete') is True
                                        and m.get('snapshots') == len(values) == 10000)
    except Exception as exc:
        record['issues'].append(type(exc).__name__ + ': ' + str(exc))
        record['validated_complete'] = False
    return record


def main():
    gen = runpy.run_path(str(CAMPAIGN / 'Scripts/generate.py'), run_name='audit_import_only')
    expected = {gen['name'](a, h, lf, mode): gen['build'](a, h, lf, mode)
                for a, h, lf, mode in product(gen['SYSTEMS'], gen['FS_HEIGHTS'], gen['LOAD_FACTORS'], gen['MODES'])}
    records = []
    for root in ROOTS:
        for folder in sorted(root.glob('output*')):
            if folder.is_dir():
                record = inspect(folder, expected, gen['comparable_config'])
                records.append(record)
                if len(records) % 20 == 0:
                    print('Checked', len(records), 'folders', flush=True)
    grouped = defaultdict(list)
    for r in records:
        grouped[r.get('scenario', r['folder'])].append(r)
    missing = sorted(set(expected) - set(grouped))
    incomplete = {k: [dict(folder=r['folder'], snapshots=r.get('snapshot_rows'), issues=r['issues']) for r in grouped[k]]
                  for k in expected if k in grouped and not any(r['validated_complete'] for r in grouped[k])}
    duplicates = {k: [r['folder'] for r in v] for k, v in grouped.items() if len(v) > 1}
    summary = dict(expected=len(expected), folders=len(records), missing=missing, incomplete=incomplete,
                   duplicates=duplicates, unexpected=sorted(set(grouped) - set(expected)),
                   complete_by_drive=dict(Counter(r['drive'] for r in records if r['validated_complete'])),
                   complete_by_mode=dict(Counter(r['scenario'].split('_')[-1] for r in records if r['validated_complete'])),
                   total_snapshot_rows=sum(r.get('snapshot_rows', 0) for r in records),
                   config_difference_paths=dict(Counter(d['path'] for r in records for d in r.get('config_differences', []))),
                   issues=[dict(folder=r['folder'], issues=r['issues']) for r in records if r['issues']])
    dest = ROOT / 'reports/tcc07_completion_20261116.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(dict(checked_at=datetime.now().astimezone().isoformat(), summary=summary, results=records), indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print('REPORT', dest)


if __name__ == '__main__':
    main()

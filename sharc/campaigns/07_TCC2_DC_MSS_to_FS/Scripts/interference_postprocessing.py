"""Shared read-only data/statistics helpers for the full campaign-07 matrix."""
import csv
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import yaml

CAMPAIGN = Path(__file__).resolve().parents[1]
HO = [5, 10, 15, 20, 25, 30]
PBO = list(range(10, 101, 10))
MODES = ['BASELINE'] + [f'HO{n}' for n in HO] + [f'PBO{n}km' for n in PBO]
PATTERN = re.compile(r'^output_tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(BASELINE|HO(?:5|10|15|20|25|30)|PBO(?:10|20|30|40|50|60|70|80|90|100)km)_\d{4}-\d{2}-\d{2}_\d+$')
SEED = 20260727
BOOTSTRAPS = 10000
VERSION = 'snapshot-percentile-bootstrap-v1'


def default_roots():
    cfg = yaml.safe_load((Path(__file__).with_name('base_input.yaml')).read_text(encoding='utf-8'))
    return list(dict.fromkeys([Path(cfg['general']['output_dir']), CAMPAIGN / 'output']))


def inventory(roots):
    found = {}
    for root in roots:
        for folder in sorted(root.glob('output_*')):
            match = PATTERN.fullmatch(folder.name)
            if not match:
                continue
            a, h, lf, mode = match.groups()
            key = (int(a), int(h), int(lf), mode)
            if key in found and found[key].resolve() != folder.resolve():
                raise ValueError(f'Duplicate scenario {key}: choose --output-root explicitly')
            found[key] = folder
    return dict(sorted(found.items(), key=lambda kv: (*kv[0][:3], MODES.index(kv[0][3]))))


def read_gzip_csv(path):
    # Read through EOF: CRC/truncation errors must not masquerade as complete data.
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class Case:
    key: tuple
    folder: Path
    manifest: dict
    values: np.ndarray
    fingerprint: str
    stops: Counter

    @property
    def n(self):
        return len(self.values)

    @property
    def partial(self):
        return not self.manifest.get('complete') or self.n != self.manifest['snapshots']


FIELDS = ['inr_before_db', 'inr_after_db', 'accepted_changes', 'examined_beams',
          'attempts', 'candidate_satellites_considered', 'evaluated_candidates',
          'active_pbo_beams', 'max_prediction_error_db']


def load_case(key, folder):
    manifest = json.loads((folder / 'tcc2_manifest.json').read_text(encoding='utf-8'))
    path = folder / 'tcc2_snapshots.csv.gz'
    values, stops = [], Counter()
    seeds = manifest['secondary_seeds']
    for count, row in enumerate(read_gzip_csv(path), 1):
        if int(row['snapshot_id']) != count or int(row['secondary_seed']) != seeds[count - 1]:
            raise ValueError(f'Invalid snapshot ID/seed: {folder}, row {count}')
        numbers = [float(row[field]) for field in FIELDS]
        if not all(map(math.isfinite, numbers)):
            raise ValueError(f'Nonfinite snapshot metrics: {folder}, row {count}')
        values.append(tuple(numbers))
        stops[row['stop_reason']] += 1
    if not values or len(values) != manifest['completed_snapshots']:
        raise ValueError(f'Manifest/snapshot count mismatch: {folder}')
    dtype = [(field, 'f8') for field in FIELDS]
    return Case(key, folder, manifest, np.array(values, dtype=dtype),
                hashlib.sha256(path.read_bytes()).hexdigest(), stops)


def empirical_q80(samples):
    x = np.asarray(samples, dtype=float)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError('Expected finite nonempty snapshot samples')
    return float(np.partition(x, math.ceil(.8 * x.size) - 1)[math.ceil(.8 * x.size) - 1])


def bootstrap_inr20_ci(samples, *, n_bootstrap, rng, confidence=.95, chunk_size=250):
    """Same resampling/quantile algorithm as campaign-02 bootstrap_inr20_ci."""
    x = np.asarray(samples, dtype=float)
    point = empirical_q80(x)
    if n_bootstrap < 1:
        raise ValueError('n_bootstrap must be positive')
    index = math.ceil(.8 * x.size) - 1
    estimates = []
    for start in range(0, n_bootstrap, chunk_size):
        indices = rng.integers(0, x.size, size=(min(chunk_size, n_bootstrap-start), x.size), endpoint=False)
        estimates.append(np.partition(x[indices], index, axis=1)[:, index])
    alpha = (1-confidence)/2
    low, high = np.quantile(np.concatenate(estimates), [alpha, 1-alpha])
    return point, float(low), float(high)


def classify(low, high):
    return 'compliant' if low >= 0 else 'non-compliant' if high < 0 else 'borderline'


def metrics(case, cache_dir, n_bootstrap=BOOTSTRAPS, seed=SEED):
    signature = dict(sha256=case.fingerprint, method=VERSION, resamples=n_bootstrap, seed=seed)
    path = cache_dir / ('_'.join(map(str, case.key)) + '.json')
    if path.exists():
        cached = json.loads(path.read_text())
        if cached['signature'] == signature:
            return dict(cached['metrics'], source=str(case.folder), partial=case.partial, snapshots=case.n)
    after = case.values['inr_after_db']
    if n_bootstrap:
        q, lo, hi = bootstrap_inr20_ci(after, n_bootstrap=n_bootstrap, rng=np.random.default_rng(seed))
    else:
        q, lo, hi = empirical_q80(after), math.nan, math.nan
    row = dict(altitude_km=case.key[0], fs_height_m=case.key[1], lf_pct=case.key[2], mode=case.key[3],
               snapshots=case.n, partial=case.partial, inr20_db=q, inr_ci_low_db=lo, inr_ci_high_db=hi,
               margin_db=-6-q, margin_ci_low_db=-6-hi, margin_ci_high_db=-6-lo,
               classification=classify(-6-hi, -6-lo) if n_bootstrap else 'not_evaluated',
               exceedance_pct=100*float(np.mean(after > -6)),
               inr20_before_db=empirical_q80(case.values['inr_before_db']),
               mean_snapshot_reduction_db=float(np.mean(case.values['inr_before_db']-after)),
               mean_accepted_changes=float(np.mean(case.values['accepted_changes'])),
               snapshots_with_handover_pct=100*float(np.mean(case.values['accepted_changes'] > 0)),
               mean_examined_beams=float(np.mean(case.values['examined_beams'])),
               mean_attempts=float(np.mean(case.values['attempts'])),
               mean_candidates=float(np.mean(case.values['candidate_satellites_considered'])),
               mean_evaluated_candidates=float(np.mean(case.values['evaluated_candidates'])),
               mean_active_pbo_beams=float(np.mean(case.values['active_pbo_beams'])),
               max_prediction_error_db=float(np.max(case.values['max_prediction_error_db'])),
               bootstrap_resamples=n_bootstrap, bootstrap_seed=seed, source=str(case.folder))
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(signature=signature, metrics=row), indent=2), encoding='utf-8')
    return row


def sustained(values):
    """First evaluated setting whose CI and all subsequent evaluated CIs support compliance."""
    for i, (setting, low) in enumerate(values):
        if all(math.isfinite(v) and v >= 0 for _, v in values[i:]):
            return setting
    return None


def style():
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'serif', 'font.size': 11, 'axes.labelsize': 12,
                         'legend.fontsize': 9, 'axes.spines.top': False,
                         'axes.spines.right': False, 'savefig.facecolor': 'white'})


def save_figure(fig, path, formats=('png',), dpi=350):
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        fig.savefig(path.with_suffix('.' + fmt), dpi=dpi, bbox_inches='tight')
    plt.close(fig)

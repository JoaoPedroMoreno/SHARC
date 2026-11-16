"""Focused tests for offline interference figures; no simulation is run."""
import ast
import csv
import gzip
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts'))
import interference_postprocessing as pp
from plot_interference_results import thresholds
from plot_handover_geometry import attach_links


class PostprocessingTests(unittest.TestCase):
    def test_bootstrap_matches_previous_method(self):
        path=ROOT/'sharc/campaigns/02_DC_MSS_to_FS 2/Script/bootstrap_inr20_confidence.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bootstrap_inr20_ci')
        scope=dict(np=np,math=math,EXCEEDANCE_PROBABILITY=.2,
                   inr_at_exceedance_probability=lambda x,p: pp.empirical_q80(x))
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),scope)
        data=np.random.default_rng(1).normal(size=177)
        expected=scope['bootstrap_inr20_ci'](data,n_bootstrap=503,rng=np.random.default_rng(99))
        actual=pp.bootstrap_inr20_ci(data,n_bootstrap=503,rng=np.random.default_rng(99))
        np.testing.assert_array_equal(actual,expected)

    def test_quantile_and_classification(self):
        self.assertEqual(pp.empirical_q80(np.arange(10)),7)
        self.assertEqual(pp.bootstrap_inr20_ci(np.full(20,-6.),n_bootstrap=20,rng=np.random.default_rng(4)),(-6.,-6.,-6.))
        self.assertEqual(pp.classify(0,.2),'compliant')
        self.assertEqual(pp.classify(-.2,0),'borderline')
        self.assertEqual(pp.classify(-.2,-.01),'non-compliant')
        with self.assertRaises(ValueError): pp.empirical_q80([1,np.nan])

    def test_sustained_nonmonotonic(self):
        self.assertEqual(pp.sustained([(0,-1),(10,.2),(20,-.1),(30,.3),(40,.1)]),30)
        self.assertIsNone(pp.sustained([(0,1),(10,-1)]))

    def test_matrix_names(self):
        self.assertEqual(len(pp.MODES)*2*2*2,136)
        for mode in pp.MODES:
            self.assertIsNotNone(pp.PATTERN.fullmatch(f'output_tcc2_SA_noPY_340km_FS20m_LF20_Azi90_{mode}_2026-11-16_01'))

    def test_partial_and_duplicate_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            manifest=dict(completed_snapshots=2,snapshots=10000,complete=False,secondary_seeds=[11,22])
            (p/'tcc2_manifest.json').write_text(json.dumps(manifest))
            rows=[dict(snapshot_id=i,secondary_seed=seed,stop_reason='DISABLED',**{f:0 for f in pp.FIELDS})
                  for i,seed in [(1,11),(2,22)]]
            def write():
                with gzip.open(p/'tcc2_snapshots.csv.gz','wt',newline='') as stream:
                    w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            write(); case=pp.load_case((340,20,20,'BASELINE'),p)
            self.assertTrue(case.partial); self.assertEqual(case.n,2)
            rows[1]['snapshot_id']=1;write()
            with self.assertRaises(ValueError): pp.load_case((340,20,20,'BASELINE'),p)

    def test_exact_before_after_link_steps(self):
        event=dict(accepted='True',accepted_count='2',current_satellite_idx='7',selected_satellite_idx='8',cell_id='42')
        events={(1,3):event}
        from plot_handover_geometry import LINK_FIELDS
        rows=[dict(snapshot_id=1,beam_id=3,step=step,satellite_id=sat,cell_id=42,
                   **{f:float(step) for f in LINK_FIELDS}) for step,sat in [(0,7),(1,7),(2,8)]]
        with patch('plot_handover_geometry.read_detailed_rows',return_value=iter(rows)):
            attach_links(Path('.'),events,None)
        self.assertEqual(event['before_rx_offaxis_deg'],1)
        self.assertEqual(event['after_rx_offaxis_deg'],2)


if __name__=='__main__': unittest.main()

"""Two real validation snapshots, outside campaign outputs; not a campaign run."""
import csv
import gc
import gzip
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import sys

import numpy as np

root = Path(__file__).resolve().parents[1]
scripts = root / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts"
sys.path.insert(0, str(scripts))
import generate
from sharc.cochannel_handover import xyz
from sharc.simulation_downlink import SimulationDownlink
from sharc.support.sharc_logger import SimulationLogger

output = root / "tmp" / ("tcc2_pbo_validation_" + datetime.now().strftime("%Y%m%dT%H%M%S%f"))
results = {}
for mode in ["BASELINE", "PBO100km"]:
    source = generate.CAMPAIGN / "input" / (generate.name(525, 40, .5, mode) + ".yaml")
    params = generate.load(source)
    params.general.num_snapshots = 1
    params.general.output_dir = str(output)
    SimulationLogger._global_output_dir = None
    sim = SimulationDownlink(params, str(source))
    sim.initialize()
    sim.snapshot(write_to_file=False, snapshot_number=1, seed=2182114437)
    sim.results.write_files(1)
    with gzip.open(Path(sim.results.output_directory) / "tcc2_links.csv.gz", "rt") as stream:
        links = [row for row in csv.DictReader(stream) if row["active"] == "True"]
    results[mode] = dict(record=sim.tcc2_last_snapshot, links=links,
                         ue=xyz(sim.ue).copy(), bs=xyz(sim.bs).copy(),
                         active=sim.bs.active.copy(), cells=sim.topology.beam_grid_idx.copy())
    print(mode, sim.tcc2_last_snapshot, flush=True)
    del sim
    gc.collect()

baseline, pbo = (results[m] for m in ["BASELINE", "PBO100km"])
for field in ["ue", "bs", "active", "cells"]:
    np.testing.assert_array_equal(baseline[field], pbo[field])
affected = 0
for a, b in zip(baseline["links"], pbo["links"]):
    assert a["beam_id"] == b["beam_id"]
    reduction = float(b["power_backoff_db"])
    assert reduction in [0., 10.]
    affected += reduction > 0
    np.testing.assert_allclose(float(b["tx_power_dbm"]), float(a["tx_power_dbm"]) - reduction, atol=1e-12)
    np.testing.assert_allclose(float(b["i_link_mw"]), float(a["i_link_mw"]) * 10 ** (-reduction / 10), rtol=1e-9)
assert affected > 0
assert affected < len(pbo["links"])
assert pbo["record"]["accepted_changes"] == 0
assert pbo["record"]["inr_after_db"] < baseline["record"]["inr_after_db"]
report = dict(passed=True, affected_active_beams=affected, active_beams=len(pbo["links"]),
              baseline_inr_db=baseline["record"]["inr_after_db"], pbo_inr_db=pbo["record"]["inr_after_db"],
              same_geometry_users_activity=True, exact_10db_on_affected_links=True)
(output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
plot_spec = importlib.util.spec_from_file_location("tcc2_plot", scripts / "plot_system_inr_ccdf.py")
plot = importlib.util.module_from_spec(plot_spec)
plot_spec.loader.exec_module(plot)
plot.plot(output, output / "plots")
print(json.dumps(report, indent=2))
print(output, flush=True)

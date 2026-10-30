"""Compare the optimized audit to snapshot 1 of the user's original run."""
import csv
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/output/output_tcc2_SA_noPY_340km_FS40m_LF50_Azi90_HO5_2026-10-25_01"
NEW = Path(__file__).parent / "physics_final/handover_physics"


def rows(folder, name):
    result = []
    with gzip.open(folder / f"tcc2_{name}.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if int(row["snapshot_id"]) != 1:
                break
            result.append(row)
    return result


report = {}
for name in ("snapshots", "steps", "events", "candidates", "users", "links"):
    before, after = rows(OLD, name), rows(NEW, name)
    assert len(before) == len(after), (name, len(before), len(after))
    errors = {}
    for index, (a, b) in enumerate(zip(before, after)):
        assert a.keys() == b.keys(), (name, "schema")
        for key in a:
            if a[key] == b[key]:
                continue
            try:
                x, y = float(a[key]), float(b[key])
            except ValueError:
                raise AssertionError((name, index, key, a[key], b[key]))
            if math.isnan(x) and math.isnan(y):
                continue
            assert math.isclose(x, y, rel_tol=0, abs_tol=1e-8), (name, index, key, x, y)
            errors[key] = max(errors.get(key, 0), abs(x - y))
    report[name] = dict(rows=len(before), max_abs_differences=errors)
result = dict(old=str(OLD), new=str(NEW), tolerance=1e-8, comparison=report)
(Path(__file__).parent / "comparison.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))

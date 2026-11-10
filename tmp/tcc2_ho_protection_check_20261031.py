"""Read paired before/after INR from committed HO LF50 snapshots only."""
import csv
import gzip
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parents[1]
roots = [root / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/output",
         Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS")]
report = []
for location in roots:
    for folder in sorted(location.glob("*LF50_Azi90_HO*")):
        manifest = json.loads((folder / "tcc2_manifest.json").read_text())
        n = manifest["completed_snapshots"]
        before, after = [], []
        rescued = 0
        with gzip.open(folder / "tcc2_snapshots.csv.gz", "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                assert int(row["snapshot_id"]) == len(before) + 1
                a,b = float(row["inr_before_db"]),float(row["inr_after_db"])
                assert math.isfinite(a) and math.isfinite(b)
                before.append(a)
                after.append(b)
                rescued += a > -6 and b <= -6
                if len(before) == n:
                    break
        assert len(before) == n
        index = math.ceil(.8*n)-1
        qb,qa = sorted(before)[index],sorted(after)[index]
        result=dict(scenario=manifest["scenario"],source=str(folder),n=n,
            complete=manifest["complete"],inr20_before_db=qb,inr20_after_db=qa,
            margin20_before_db=-6-qb,margin20_after_db=-6-qa,
            crossed_point_criterion=qb > -6 and qa <= -6,
            rescued_snapshots=rescued,exceedance_before_pct=100*sum(v>-6 for v in before)/n,
            exceedance_after_pct=100*sum(v>-6 for v in after)/n)
        report.append(result)
        print(json.dumps(result),flush=True)
(root / "tmp/tcc2_ho_protection_check_20261031.json").write_text(json.dumps(report,indent=2))

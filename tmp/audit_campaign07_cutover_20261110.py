"""Read-only campaign audit, writing a separate non-executable backup of inputs."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
BACKUP = ROOT / "docs/backups/campaign07_cutover_20261110_125930"
LOCAL = timezone(timedelta(hours=-3))
CUTOFF = datetime.fromisoformat("2026-11-10T12:59:30.574068-03:00")
NAME = re.compile(r"tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(HO\d+|PBO\d+km|BASELINE)")
SHARED = ["sharc/cochannel_handover.py", "sharc/simulation_downlink.py",
          "sharc/parameters/imt/parameters_imt_mss_dc.py"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    recorded_at = datetime.now(LOCAL).isoformat()
    process_records = json.loads((BACKUP / "processes_observed.json").read_text())["processes"]
    processes = defaultdict(list)
    for process in process_records:
        match = NAME.search(process.get("CommandLine") or "")
        if match:
            processes[match[0]].append(process)
    roots = [CAMPAIGN / "output", Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS")]
    outputs = defaultdict(list)
    warnings = []
    for root in roots:
        for folder in root.glob("output_tcc2_SA_noPY_*"):
            match = NAME.search(folder.name)
            if not folder.is_dir() or not match:
                continue
            manifest_path = folder / "tcc2_manifest.json"
            manifest = {}
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as error:
                    warnings.append(f"{manifest_path}: {error}")
            logs = []
            for log in folder.glob("simulation_*/simulation_log_*.yaml"):
                data = yaml.safe_load(log.read_text(encoding="utf-8"))
                run = data.get("run", {})
                logs.append(dict(path=str(log), started_at=run.get("started_at"), ended_at=run.get("ended_at")))
            outputs[match[0]].append(dict(
                folder=str(folder), folder_created_local=datetime.fromtimestamp(folder.stat().st_ctime, LOCAL).isoformat(),
                manifest_exists=manifest_path.exists(), snapshots_observed=manifest.get("completed_snapshots"),
                complete_observed=manifest.get("complete"), logs=logs))
    rows, pending = [], []
    for path in sorted((CAMPAIGN / "input").glob("*.yaml")):
        scenario = path.stem
        match = NAME.fullmatch(scenario)
        assert match, scenario
        evidence = outputs.get(scenario, [])
        starts = [datetime.fromisoformat(p["CreationDate"]) for p in processes.get(scenario, [])]
        ends = []
        for result in evidence:
            for log in result["logs"]:
                if log["started_at"]:
                    starts.append(datetime.fromisoformat(str(log["started_at"])).replace(tzinfo=LOCAL))
                if log["ended_at"]:
                    ends.append(datetime.fromisoformat(str(log["ended_at"])).replace(tzinfo=LOCAL))
        started_before = any(t < CUTOFF for t in starts)
        completed_before = any(t < CUTOFF for t in ends)
        created_before = any(datetime.fromisoformat(r["folder_created_local"]) < CUTOFF for r in evidence)
        if completed_before:
            status = "COMPLETED_BEFORE_CHANGE"
        elif started_before:
            status = "STARTED_BEFORE_CHANGE"
        elif created_before:
            status = "OUTPUT_EXISTED_BEFORE_CHANGE_START_TIME_UNVERIFIED"
        elif not starts and not evidence:
            status = "NOT_STARTED_AT_CHANGE_NO_OUTPUT_OR_PROCESS"
        elif starts and min(starts) >= CUTOFF:
            status = "STARTED_AFTER_CHANGE"
        else:
            status = "REVIEW_REQUIRED"
        row = dict(scenario=scenario, altitude_km=int(match[1]), fs_height_m=int(match[2]),
                   lf_pct=int(match[3]), treatment=match[4], status_at_change=status,
                   earliest_start=min(starts).isoformat() if starts else None,
                   ended_before_change=max((t for t in ends if t < CUTOFF), default=None),
                   current_process_ids=[p["ProcessId"] for p in processes.get(scenario, [])],
                   input=str(path), input_sha256=sha(path),
                   input_modified=datetime.fromtimestamp(path.stat().st_mtime, LOCAL).isoformat(),
                   outputs=evidence)
        if row["ended_before_change"]:
            row["ended_before_change"] = row["ended_before_change"].isoformat()
        rows.append(row)
        if status in {"NOT_STARTED_AT_CHANGE_NO_OUTPUT_OR_PROCESS", "STARTED_AFTER_CHANGE"}:
            pending.append(row)
    before = {row["input"]: row["input_sha256"] for row in rows}
    destination = BACKUP / "pending_inputs_at_change"
    destination.mkdir(exist_ok=False)
    for row in pending:
        source = Path(row["input"])
        target = destination / source.name
        shutil.copy2(source, target)
        assert sha(target) == row["input_sha256"]
    context_dir = BACKUP / "context_at_audit"
    context_dir.mkdir(exist_ok=False)
    context = []
    for rel in [*SHARED, "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml",
                "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/generate.py",
                "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/run_multiple_campaigns_mut_thread.py",
                "sharc/campaigns/07_TCC2_DC_MSS_to_FS/input/generation_report.json"]:
        source = ROOT / rel
        if not source.exists():
            continue
        target = context_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        context.append(dict(path=rel, sha256=sha(source),
                            modified=datetime.fromtimestamp(source.stat().st_mtime, LOCAL).isoformat()))
    assert before == {row["input"]: sha(Path(row["input"])) for row in rows}
    summary = dict(audit_time=recorded_at, change_cutoff=CUTOFF.isoformat(),
                   cutoff_evidence="First patch modified parameters_imt_mss_dc.py; unchanged mtime since that patch.",
                   queue_inputs=len(rows), status_counts=dict(Counter(r["status_at_change"] for r in rows)),
                   pending_at_change=len(pending),
                   pending_by_technique=dict(Counter("HO" if r["treatment"].startswith("HO") else "PBO" for r in pending)),
                   current_active_scenarios=len(processes),
                   started_after_cutoff=[r["scenario"] for r in rows if r["status_at_change"] == "STARTED_AFTER_CHANGE"],
                   warnings=warnings, context_files=context,
                   limitations=["Reconstructed after the fact, not an OS queue capture at the exact cutoff.",
                                "No-output/no-process status assumes no unrecorded failed attempt or deleted output.",
                                "Snapshot counts are from audit time, not reconstructed cutoff progress.",
                                "Context code is the disk version AFTER campaign-08 edits, not process memory or a pre-edit backup.",
                                "No outputs are copied, deleted, renamed, or regenerated; no simulations are started or stopped."])
    (BACKUP / "audit.json").write_text(json.dumps(dict(summary=summary, scenarios=rows), indent=2), encoding="utf-8")
    fields = ["scenario", "altitude_km", "fs_height_m", "lf_pct", "treatment", "status_at_change",
              "earliest_start", "ended_before_change", "input", "input_sha256"]
    for filename, records in (("all_queue_status.csv", rows), ("pending_at_change.csv", pending)):
        with (BACKUP / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
    (BACKUP / "pending_input_names.txt").write_text("\n".join(r["scenario"] + ".yaml" for r in pending) + "\n")
    groups = defaultdict(list)
    for r in pending:
        groups[(r["altitude_km"], r["fs_height_m"], r["lf_pct"])].append(r["treatment"])
    print(json.dumps(dict(summary=summary, groups=[dict(altitude=k[0], fs_height=k[1], lf=k[2], modes=v)
                                                 for k, v in sorted(groups.items())]), indent=2))


if __name__ == "__main__":
    main()

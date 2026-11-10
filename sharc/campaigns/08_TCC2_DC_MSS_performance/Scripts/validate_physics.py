"""Validate campaign inputs, cross-campaign pairing, or a small physics smoke test."""
import argparse
from copy import deepcopy
import csv
import gc
import gzip
import importlib.util
from itertools import product
import json
from pathlib import Path
import random
from unittest.mock import patch

from generate import CAMPAIGN, ROOT, SYSTEMS, FS_HEIGHTS, LOAD_FACTORS, MODES, build, load
import numpy as np
import yaml

SOURCE = ROOT / "sharc/campaigns/07_TCC2_DC_MSS_to_FS"
SOURCE_ROOTS = [SOURCE / "output", Path("D:/SHARC_outputs/07_TCC2_DC_MSS_to_FS")]


def physical_config(cfg):
    cfg = deepcopy(cfg)
    for key in ("num_snapshots", "output_dir", "output_dir_prefix", "overwrite_output"):
        cfg["general"].pop(key, None)
    cfg["imt"].pop("imt_dl_intra_sinr_calculation_disabled", None)
    ho = cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]
    for key in ("record_detailed_links_and_users", "detailed_record_format",
                "record_candidate_details", "performance_only_output"):
        ho.pop(key, None)
    return cfg


def check_inputs():
    spec = importlib.util.spec_from_file_location("campaign07_generate", SOURCE / "Scripts/generate.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    count = 0
    for altitude, height, lf, mode in product(SYSTEMS, FS_HEIGHTS, LOAD_FACTORS, MODES):
        cfg = build(altitude, height, lf, mode)
        assert physical_config(cfg) == physical_config(previous.build(altitude, height, lf, mode)), (
            altitude, height, lf, mode)
        assert cfg["general"]["num_snapshots"] == 1000
        assert cfg["imt"]["imt_dl_intra_sinr_calculation_disabled"] is False
        assert cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]["performance_only_output"]
        count += 1
    return dict(scenarios=count, physical_configs_equal_to_07=True,
                snapshots=1000, outputs=str(build(340, 20, .2, "BASELINE")["general"]["output_dir"]))


def read_snapshots(folder, limit=None):
    manifest = json.loads((folder / "tcc2_manifest.json").read_text(encoding="utf-8"))
    count = manifest["completed_snapshots"]
    if limit is not None:
        count = min(count, limit)
    rows = {}
    if not count:
        return rows
    with gzip.open(folder / "tcc2_snapshots.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            number = int(row["snapshot_id"])
            if number != len(rows) + 1:
                raise ValueError(f"Non-sequential snapshots: {folder}")
            rows[number] = row
            if number == count:
                break  # Do not read an uncommitted member of a running gzip file.
    if len(rows) != count:
        raise ValueError(f"Missing committed snapshots: {folder}")
    return rows


def compare_records(left, right):
    for key in ("snapshot_id", "secondary_seed", "realization_sha256", "baseline_links_sha256",
                "initial_top_k", "examined_beams", "attempts", "evaluated_candidates",
                "accepted_changes", "stop_reason", "active_pbo_beams"):
        if str(left[key]) != str(right[key]):
            raise ValueError(f"Pairing mismatch in {key}, snapshot {left['snapshot_id']}")
    for key in ("inr_before_db", "inr_after_db"):
        np.testing.assert_allclose(float(left[key]), float(right[key]), rtol=0, atol=1e-9)


def check_pairing(results):
    sources = {}
    for root in SOURCE_ROOTS:
        for path in root.glob("*/tcc2_manifest.json"):
            m = json.loads(path.read_text(encoding="utf-8"))
            sources.setdefault(m["scenario"], []).append((path.parent, m))
    report = []
    for path in sorted(results.glob("*/tcc2_manifest.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if not m.get("performance_only_output"):
            continue
        cfg = yaml.safe_load(path.with_name("tcc2_executed_config.yaml").read_text(encoding="utf-8"))
        old_name = m["scenario"].replace("tcc2_perf_", "tcc2_", 1)
        candidates = sorted(sources.get(old_name, []),
                            key=lambda item: item[1].get("completed_snapshots", 0), reverse=True)
        source = None
        for folder, old in candidates:
            old_cfg = yaml.safe_load((folder / "tcc2_executed_config.yaml").read_text(encoding="utf-8"))
            if physical_config(old_cfg) == physical_config(cfg) and old.get("completed_snapshots", 0):
                source = folder
                break
        row = dict(scenario=m["scenario"], output=str(path.parent), source=str(source) if source else None)
        if source is None:
            row.update(status="NO_MATCHING_07_RESULT", paired_snapshots=0)
        else:
            new_rows = read_snapshots(path.parent)
            old_rows = read_snapshots(source, len(new_rows))
            for number in old_rows:
                compare_records(old_rows[number], new_rows[number])
            row.update(status="PAIRED" if len(old_rows) == len(new_rows) and new_rows else "PARTIAL",
                       paired_snapshots=len(old_rows), available_08=len(new_rows))
        report.append(row)
    return report


def smoke(output):
    """Small sequential tests only; never writes into production outputs."""
    from sharc.simulation_downlink import SimulationDownlink
    from sharc.support.sharc_logger import SimulationLogger
    output = output.resolve()
    protected = [*(p.resolve() for p in SOURCE_ROOTS),
                 Path(build(340, 20, .2, "BASELINE")["general"]["output_dir"]).resolve()]
    if any(output == p or p in output.parents for p in protected):
        raise ValueError("Smoke tests cannot write inside production outputs")
    output.mkdir(parents=True, exist_ok=False)
    seed = random.Random(838).randint(1, 2**32 - 1)
    report = []
    for altitude, height, lf, mode in ((340, 20, .2, "BASELINE"),
                                     (340, 40, .5, "HO5"), (525, 20, .2, "PBO100km")):
        states = []
        for profile in ("reference", "performance"):
            folder = output / f"{altitude}_{height}_{lf}_{mode}" / profile
            folder.mkdir(parents=True)
            cfg = build(altitude, height, lf, mode)
            ho = cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"]
            ho["performance_only_output"] = profile == "performance"
            # Both calculate performance; compare exports against the existing path.
            ho["record_detailed_links_and_users"] = profile == "reference"
            ho["detailed_record_format"] = "FULL"
            cfg["general"].update(num_snapshots=1, output_dir=str(folder), overwrite_output=True)
            source = folder / "input.yaml"
            source.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            with patch.object(SimulationLogger, "_global_output_dir", None):
                sim = SimulationDownlink(load(source), str(source))
                sim.initialize()
                sim.snapshot(write_to_file=True, snapshot_number=1, seed=seed)
                record = dict(sim.tcc2_last_snapshot)
                directory = Path(sim.results.output_directory)
                states.append(dict(record=record, sinr=sim.ue.sinr.copy(), snr=sim.ue.snr.copy(),
                                   rng=sim.propagation_system.random_number_gen.get_state(), folder=directory,
                                   active=sim.ue.active.copy()))
                if profile == "performance":
                    assert not sim.results.imt_dl_sinr and not sim.results.imt_dl_selected_ue_metrics
                    assert not (directory / "system_inr.csv").exists()
                    assert not list(directory.glob("tcc2_links*"))
                    assert not list(directory.glob("tcc2_users*"))
                    assert not (directory / "tcc2_candidates.csv.gz").exists()
                    with gzip.open(directory / "tcc2_performance_users.csv.gz", "rt") as stream:
                        rows = list(csv.DictReader(stream))
                    assert len(rows) == sim.ue.num_stations
                    for user, row in enumerate(rows):
                        assert int(row["user_id"]) == user
                        assert row["active"] == str(bool(sim.ue.active[user]))
                        if sim.ue.active[user]:
                            np.testing.assert_equal(float(row["sinr_db"]), sim.ue.sinr[user])
                            np.testing.assert_equal(float(row["snr_db"]), sim.ue.snr[user])
                del sim
                gc.collect()
        a, b = states
        compare_records(a["record"], b["record"])
        np.testing.assert_array_equal(a["sinr"], b["sinr"])
        np.testing.assert_array_equal(a["snr"], b["snr"])
        np.testing.assert_equal(a["rng"], b["rng"])
        # Read one committed production-07 snapshot when this scenario exists.
        name07 = f"tcc2_SA_noPY_{altitude}km_FS{height}m_LF{int(lf*100)}_Azi90_{mode}"
        paired07 = None
        for root in SOURCE_ROOTS:
            for old in sorted(root.glob(f"output_{name07}_*/tcc2_manifest.json"), reverse=True):
                old_cfg = yaml.safe_load(old.with_name("tcc2_executed_config.yaml").read_text(encoding="utf-8"))
                if physical_config(old_cfg) != physical_config(cfg):
                    continue
                prior = read_snapshots(old.parent, 1)
                if prior:
                    compare_records(prior[1], b["record"])
                    paired07 = str(old.parent)
                    break
        report.append(dict(scenario=name07, export_only_exact=True, source07_paired=paired07,
                           accepted_changes=b["record"]["accepted_changes"],
                           users=len(b["active"]), active_users=int(b["active"].sum()),
                           compact_bytes=sum(p.stat().st_size for p in b["folder"].glob("tcc2_*.*"))))
        (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report[-1]), flush=True)
    assert any(r["accepted_changes"] for r in report), "Smoke test must exercise accepted HO"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", type=Path, help="Fresh scratch folder for six single-snapshot runs")
    parser.add_argument("--check-pairing", type=Path, help="Campaign-08 output root; read-only")
    args = parser.parse_args()
    print(json.dumps(check_inputs(), indent=2))
    if args.smoke:
        smoke(args.smoke)
    if args.check_pairing:
        print(json.dumps(check_pairing(args.check_pairing), indent=2))


if __name__ == "__main__":
    main()

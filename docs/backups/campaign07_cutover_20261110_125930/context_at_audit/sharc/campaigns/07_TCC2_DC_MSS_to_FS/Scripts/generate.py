"""Generate only pending TCC2 scenarios, preserving all simulation outputs."""
import argparse
import csv
from copy import deepcopy
import gzip
from itertools import product
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import yaml
from sharc.parameters.parameters import Parameters
from sharc.cochannel_handover import validate_configuration

CAMPAIGN = Path(__file__).resolve().parents[1]
BASE_FILE = Path(__file__).resolve().with_name("base_input.yaml")
SYSTEMS = {
    340: dict(n_planes=48, sats_per_plane=110, beam_radius_m=25803),
    525: dict(n_planes=28, sats_per_plane=120, beam_radius_m=39844),
}
FS_HEIGHTS = {
    20: dict(mean_clutter_height="low", below_rooftop=60),
    40: dict(mean_clutter_height="mid", below_rooftop=10),
}
LOAD_FACTORS = [0.2, 0.5]
HANDOVER_LIMITS = [5, 10, 15, 20, 25, 30]
PBO_DISTANCES_KM = list(range(10, 101, 10))
# Near-complete PBO samples are retained by request, without marking complete.
PRESERVE_PBO_ABOVE_SNAPSHOTS = 9000
HANDOVER_LIMIT = 30
HANDOVER_MODE = f"HO{HANDOVER_LIMIT}"
MODES = ["BASELINE", *[f"HO{n}" for n in HANDOVER_LIMITS],
         *[f"PBO{n}km" for n in PBO_DISTANCES_KM]]
GENERATED_NAME = re.compile(
    r"^tcc2_SA_noPY_(340|525)km_FS(20|40)m_LF(20|50)_Azi90_(BASELINE|HO\d+|PBO\d+km)\.yaml$")


def name(altitude, height, load, mode):
    return f"tcc2_SA_noPY_{altitude}km_FS{height}m_LF{int(load * 100)}_Azi90_{mode}"


def load_base():
    return yaml.safe_load(BASE_FILE.read_text(encoding="utf-8"))


def build(altitude, height, load, mode):
    if mode not in MODES:
        raise ValueError(f"Unknown treatment: {mode}")
    cfg = deepcopy(load_base())
    cfg["general"]["output_dir_prefix"] = "output_" + name(altitude, height, load, mode)
    imt = cfg["imt"]
    mss = imt["topology"]["mss_dc"]
    system = SYSTEMS[altitude]
    mss["beam_radius"] = system["beam_radius_m"]
    mss["orbits"][0].update(n_planes=system["n_planes"], sats_per_plane=system["sats_per_plane"],
                             perigee_alt_km=float(altitude), apogee_alt_km=float(altitude))
    imt["bs"].update(height=float(altitude * 1000), load_probability=load)
    enabled = mode.startswith("HO")
    # Disabled controls retain their original configuration for reproducibility.
    limit = int(mode[2:]) if enabled else 5
    mss["interference_aware_handover_v2"].update(
        enabled=enabled, top_k=limit, max_handovers_per_snapshot=limit,
        record_detailed_links_and_users=enabled)
    # The base contains the PBO geography; the other treatments disable only PBO.
    if not mode.startswith("PBO"):
        mss["power_control_zones"].update(zones=[], power_backoff_db=0.0)
    else:
        zones = mss["power_control_zones"]["zones"]
        zones[1]["geometry"]["from_countries"]["margin_from_border"] = -int(mode[3:-2])
    fs = cfg["single_earth_station"]
    fs["geometry"]["height"] = height
    fs["param_p619"].update(FS_HEIGHTS[height])
    return cfg


def load(path):
    params = Parameters()
    params.set_file_name(str(path))
    params.read_params()
    validate_configuration(params)
    return params


def comparable_config(cfg):
    cfg = deepcopy(cfg)
    cfg["general"].pop("output_dir", None)
    # Export verbosity does not change the simulated realization or INR.
    cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"].pop(
        "record_detailed_links_and_users", None)
    cfg["imt"]["topology"]["mss_dc"]["interference_aware_handover_v2"].pop(
        "detailed_record_format", None)
    return cfg


def result_inventory(results_dir):
    inventory = {}
    for path in sorted(results_dir.glob("*/tcc2_manifest.json"), reverse=True):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            config = yaml.safe_load(path.with_name("tcc2_executed_config.yaml").read_text(encoding="utf-8"))
            inventory.setdefault(manifest["scenario"], []).append((path.parent, manifest, config))
        except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
            print(f"Cannot reuse {path.parent.name}: {exc}")
    return inventory


def reusable_result(cfg, mode, inventory):
    scenario = cfg["general"]["output_dir_prefix"].removeprefix("output_")
    partial = None
    for folder, manifest, executed in inventory.get(scenario, []):
        if comparable_config(cfg) != comparable_config(executed):
            continue
        committed = manifest.get("completed_snapshots", 0)
        target = cfg["general"]["num_snapshots"]
        if not isinstance(committed, int) or committed <= 0 or committed > target:
            continue
        count = 0
        try:
            with gzip.open(folder / "tcc2_snapshots.csv.gz", "rt", newline="") as stream:
                for row in csv.DictReader(stream):
                    if int(row["snapshot_id"]) != count + 1 or not math.isfinite(float(row["inr_after_db"])):
                        break
                    count += 1
                    if count == committed:
                        break  # A running file can have an unfinished tail.
        except (OSError, EOFError, ValueError, KeyError):
            continue
        if count != committed:
            continue
        record = dict(scenario=scenario, source=str(folder), snapshots=count, target=target)
        if manifest.get("complete") is True and manifest.get("snapshots") == target and count == target:
            return dict(record, status="completed")
        if (mode.startswith("PBO") and count > PRESERVE_PBO_ABOVE_SNAPSHOTS
                and (partial is None or count > partial["snapshots"])):
            partial = dict(record, status="preserved_partial_by_request")
    return partial


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=CAMPAIGN / "input",
                        help="Write to a separate staging folder while the current campaign is running")
    parser.add_argument("--results-dir", type=Path, action="append",
                        help="Read-only results root; repeat for multiple roots. Default: local and base output_dir")
    args = parser.parse_args(argv)
    lookup = ROOT / "sharc/propagation/Dataset/FOZ_2155_200m.csv"
    if not lookup.is_file():
        raise FileNotFoundError(lookup)
    output = args.input_dir.resolve()
    destination = Path(load_base()["general"]["output_dir"]).resolve()
    results_dirs = list(dict.fromkeys(p.resolve() for p in (
        args.results_dir if args.results_dir is not None else [CAMPAIGN / "output", destination])))
    if any(output == root or root in output.parents
           for root in [(CAMPAIGN / "output").resolve(), destination, *results_dirs]):
        raise ValueError("Input generation must never write into simulation outputs")
    output.mkdir(parents=True, exist_ok=True)
    inventory = {}
    for root in results_dirs:
        for scenario, entries in result_inventory(root).items():
            inventory.setdefault(scenario, []).extend(entries)
    generated = set()
    skipped = []
    for altitude, height, lf, mode in product(SYSTEMS, FS_HEIGHTS, LOAD_FACTORS, MODES):
        path = output / (name(altitude, height, lf, mode) + ".yaml")
        cfg = build(altitude, height, lf, mode)
        existing = reusable_result(cfg, mode, inventory)
        if existing:
            skipped.append(existing)
            continue
        if path.resolve().parent != output or path.is_symlink():
            raise ValueError(f"Unexpected input path: {path}")
        path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        load(path)
        generated.add(path.name)
    # Remove only this generator's obsolete or skipped inputs, never outputs.
    for path in output.glob("*.yaml"):
        if GENERATED_NAME.fullmatch(path.name) and path.name not in generated:
            if path.resolve().parent != output.resolve():
                raise ValueError(f"Unexpected input path: {path}")
            path.unlink()
    report = dict(generated=sorted(generated), skipped=skipped,
                  output_dir=str(destination), results_dirs=[str(p) for p in results_dirs],
                  handover_limits=HANDOVER_LIMITS, pbo_distances_km=PBO_DISTANCES_KM,
                  preserve_pbo_above_snapshots=PRESERVE_PBO_ABOVE_SNAPSHOTS)
    (output / "generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{len(generated)} validated pending inputs in {output}. Output data untouched.")
    for status in ("completed", "preserved_partial_by_request"):
        print(f"Skipped {status}: {sum(r['status'] == status for r in skipped)}")


if __name__ == "__main__":
    main()

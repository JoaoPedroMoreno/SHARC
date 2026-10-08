"""Run the 32 Paraguay reference-guard-band scenarios with handover OFF.

This launcher does not edit campaign YAML files. It validates the immutable
reference inputs, filters out Colombia, and runs unchanged YAML files with a
memory-conscious level of parallelism. Progress and per-scenario logs are
written below tmp/; simulation CSVs use each YAML's original output_dir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
sys.path.append(str(VENV_SITE_PACKAGES))

import yaml


INPUT_DIR = REPO / "sharc" / "campaigns" / "04_DC_MSS_to_EESS" / "input"
OUTPUT_DIR = REPO / "sharc" / "campaigns" / "04_DC_MSS_to_EESS" / "output"
LOOKUP = REPO / "sharc" / "propagation" / "Dataset" / "FOZ_2117_200m.csv"
WRAPPER = REPO / "tmp" / "run_sharc_local.py"
EXPECTED_LOOKUP_BLOB = "88c97d4b2688f20eafee08ce7d14911906b0476c"
REFERENCE_COMMIT = "08b6e1e96fd75b67a86a1decda7e723b25d6d051"


def git_blob_hash(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_yaml(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    general = config["general"]
    imt = config["imt"]
    earth = config["single_earth_station"]
    mss = imt["topology"]["mss_dc"]

    assert general["seed"] == 157, (path, general["seed"])
    assert general["num_snapshots"] == 10000, (path, general["num_snapshots"])
    assert general["overwrite_output"] is False, path
    assert imt["frequency"] == 2117.5, (path, imt["frequency"])
    assert imt["bandwidth"] == 5, (path, imt["bandwidth"])
    assert imt["guard_band_ratio"] == 0.1, (path, imt["guard_band_ratio"])
    assert earth["channel_model"] == "P619", (path, earth["channel_model"])
    assert earth["param_p619"]["earth_station_lat_deg"] == -25.5549751, path
    assert earth["param_p619"]["earth_station_alt_m"] == 200, path
    assert imt["topology"]["central_latitude"] == -25.5549751, path
    assert imt["topology"]["central_longitude"] == -54.5746686, path
    assert imt["topology"]["central_altitude"] == 200, path

    handover = mss.get("interference_aware_handover", {})
    assert not bool(handover.get("enabled", False)), (path, handover)

    return {
        "file": str(path),
        "sha256": file_sha256(path),
        "seed": general["seed"],
        "snapshots": general["num_snapshots"],
        "output_prefix": general["output_dir_prefix"],
        "imt_frequency_mhz": imt["frequency"],
        "imt_bandwidth_mhz": imt["bandwidth"],
        "guard_band_ratio": imt["guard_band_ratio"],
        "eess_frequency_mhz": earth["frequency"],
        "eess_bandwidth_mhz": earth["bandwidth"],
        "load_probability": imt["bs"]["load_probability"],
        "handover_enabled": False,
    }


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.workers < 1:
        raise ValueError("--workers must be >= 1")

    lookup_blob = git_blob_hash(LOOKUP)
    if lookup_blob != EXPECTED_LOOKUP_BLOB:
        raise RuntimeError(
            f"Unexpected lookup blob {lookup_blob}; expected {EXPECTED_LOOKUP_BLOB}"
        )

    yaml_paths = sorted(INPUT_DIR.glob("*_P_Spu_*.yaml"))
    if len(yaml_paths) != 32:
        raise RuntimeError(f"Expected 32 Paraguay YAMLs, found {len(yaml_paths)}")

    scenarios = [validate_yaml(path) for path in yaml_paths]
    if args.validate_only:
        print(
            json.dumps(
                {
                    "scenario_count": len(scenarios),
                    "total_snapshots": sum(item["snapshots"] for item in scenarios),
                    "lookup_git_blob": lookup_blob,
                    "all_handover_off": all(
                        not item["handover_enabled"] for item in scenarios
                    ),
                },
                indent=2,
            )
        )
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir or REPO / "tmp" / f"paraguay_baseline_ho_off_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    log_dir = run_dir / "logs"
    log_dir.mkdir()

    manifest_path = run_dir / "manifest.json"
    lock = threading.Lock()
    manifest = {
        "status": "RUNNING",
        "started_at": datetime.now().isoformat(),
        "reference_campaign_commit": REFERENCE_COMMIT,
        "lookup_file": str(LOOKUP),
        "lookup_git_blob": lookup_blob,
        "workers": min(args.workers, len(yaml_paths)),
        "scenario_count": len(yaml_paths),
        "total_snapshots": sum(item["snapshots"] for item in scenarios),
        "output_dir": str(OUTPUT_DIR),
        "scenarios": scenarios,
        "completed": [],
        "failed": [],
    }
    write_json(manifest_path, manifest)

    def run_one(path: Path) -> dict:
        name = path.stem
        stdout_path = log_dir / f"{name}.stdout.log"
        sharc_log_path = log_dir / f"{name}.sharc.log"
        command = [
            sys.executable,
            "-u",
            str(WRAPPER),
            "-p",
            str(path),
            "-l",
            str(sharc_log_path),
        ]
        started = datetime.now()
        with stdout_path.open("w", encoding="utf-8") as stdout:
            completed = subprocess.run(
                command,
                cwd=REPO,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                text=True,
            )
        ended = datetime.now()
        return {
            "file": str(path),
            "name": name,
            "returncode": completed.returncode,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": (ended - started).total_seconds(),
            "stdout_log": str(stdout_path),
            "sharc_log": str(sharc_log_path),
        }

    with ThreadPoolExecutor(max_workers=manifest["workers"]) as executor:
        future_to_path = {executor.submit(run_one, path): path for path in yaml_paths}
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "file": str(path),
                    "name": path.stem,
                    "returncode": -1,
                    "error": repr(error),
                }
            with lock:
                target = "completed" if result["returncode"] == 0 else "failed"
                manifest[target].append(result)
                write_json(manifest_path, manifest)

    manifest["ended_at"] = datetime.now().isoformat()
    manifest["status"] = "COMPLETE" if not manifest["failed"] else "FAILED"
    write_json(manifest_path, manifest)
    return 0 if not manifest["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

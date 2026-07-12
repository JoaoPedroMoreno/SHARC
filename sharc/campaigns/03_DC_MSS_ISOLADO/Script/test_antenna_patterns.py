from __future__ import annotations

import csv
import math
import runpy
import shutil
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent
REPO_DIR = CAMPAIGN_DIR.parents[2]
SHARC_DIR = REPO_DIR / "sharc"
SITE_PACKAGES = REPO_DIR / ".venv" / "Lib" / "site-packages"

BASE_INPUT = CAMPAIGN_DIR / "input" / "dc_mss_isolado_Sys3_340km_FS20m_LF20.yaml"
TEST_INPUT_DIR = CAMPAIGN_DIR / "input" / "_antenna_tests"
OUTPUT_DIR = CAMPAIGN_DIR / "output"

SNAPSHOTS = 10
BASE_PREFIX = "output_dc_mss_isolado_anttest"

PATTERNS = {
    "taylor": {
        "pattern": "ITU-R-S.1528-Taylor",
        "s1528_extra": {},
        "array_extra": {},
    },
    "leo": {
        "pattern": "ITU-R-S.1528-LEO",
        "s1528_extra": {
            "antenna_l_s": -20.0,
            "antenna_3_dB_bw": 8.0,
            "far_out_side_lobe": 5.0,
        },
        "array_extra": {},
    },
    "section12": {
        "pattern": "ITU-R-S.1528-Section1.2",
        "s1528_extra": {
            "antenna_l_s": -20.0,
            "antenna_3_dB_bw": 8.0,
            "major_minor_axis_ratio": 1.0,
            "far_out_side_lobe": 5.0,
        },
        "array_extra": {},
    },
    "array": {
        "pattern": "ARRAY",
        "s1528_extra": {},
        "array_extra": {},
    },
    "array24": {
        "pattern": "ARRAY",
        "s1528_extra": {},
        "array_extra": {
            "n_rows": 24,
            "n_columns": 24,
        },
    },
}


def replace_scalar(lines: list[str], key: str, value: str, start: int = 0, end: int | None = None) -> None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        stripped = lines[index].lstrip()
        if not stripped.startswith(f"{key}:"):
            continue
        indent = lines[index][: len(lines[index]) - len(stripped)]
        comment = ""
        if "#" in stripped:
            _, comment = stripped.split("#", 1)
            comment = " #" + comment
        lines[index] = f"{indent}{key}: {value}{comment.rstrip()}"
        return
    raise KeyError(f"Key not found: {key}")


def find_line(lines: list[str], text: str, start: int = 0) -> int:
    for index in range(start, len(lines)):
        if text in lines[index]:
            return index
    raise KeyError(text)


def generate_test_inputs() -> list[Path]:
    TEST_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    template = BASE_INPUT.read_text(encoding="utf-8").splitlines()
    generated = []

    for token, cfg in PATTERNS.items():
        lines = template[:]
        replace_scalar(lines, "num_snapshots", str(SNAPSHOTS))
        replace_scalar(lines, "output_dir_prefix", f"{BASE_PREFIX}_{token}")

        bs_antenna_start = find_line(lines, "        antenna:", find_line(lines, "    bs:"))
        replace_scalar(lines, "pattern", cfg["pattern"], start=bs_antenna_start)

        s1528_start = find_line(lines, "            itu_r_s_1528:", bs_antenna_start)
        next_block = find_line(lines, "            array:", s1528_start)
        existing_keys = {line.strip().split(":", 1)[0] for line in lines[s1528_start + 1:next_block] if ":" in line}
        insert_at = next_block
        for key, value in cfg["s1528_extra"].items():
            if key in existing_keys:
                replace_scalar(lines, key, str(value), start=s1528_start, end=next_block)
            else:
                lines.insert(insert_at, f"                {key}: {value}")
                insert_at += 1

        array_start = find_line(lines, "            array:", bs_antenna_start)
        for key in ["n_rows", "n_columns"]:
            if key in cfg["array_extra"]:
                replace_scalar(lines, key, str(cfg["array_extra"][key]), start=array_start)

        out_path = TEST_INPUT_DIR / f"dc_mss_isolado_anttest_{token}.yaml"
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        generated.append(out_path)

    return generated


def run_simulation(param_file: Path) -> None:
    if str(REPO_DIR) in sys.path:
        sys.path.remove(str(REPO_DIR))
    sys.path.insert(0, str(REPO_DIR))
    if str(SHARC_DIR) in sys.path:
        sys.path.remove(str(SHARC_DIR))
    sys.path.insert(1, str(SHARC_DIR))
    if str(SITE_PACKAGES) not in sys.path:
        sys.path.append(str(SITE_PACKAGES))
    sys.argv = ["main_cli.py", "-p", str(param_file)]
    try:
        runpy.run_path(str(SHARC_DIR / "main_cli.py"), run_name="__main__")
    except TypeError as exc:
        if "log_path" not in str(exc) and "NoneType" not in str(exc):
            raise
        print("Aviso: simulacao finalizou, mas o logger falhou ao salvar o log final.")


def latest_output(prefix: str) -> Path:
    matches = [
        path for path in OUTPUT_DIR.iterdir()
        if path.is_dir()
        and path.name.startswith(prefix)
        and (path / "imt_dl_sinr.csv").exists()
        and (path / "imt_bs_antenna_gain.csv").exists()
    ]
    if not matches:
        raise FileNotFoundError(prefix)
    return max(matches, key=lambda path: path.stat().st_mtime)


def read_values(path: Path, field: str) -> list[float]:
    values = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        index = header.index(field) if field in header else 0
        for row in reader:
            if len(row) <= index:
                continue
            try:
                value = float(row[index])
            except ValueError:
                continue
            if math.isfinite(value):
                values.append(value)
    values.sort()
    return values


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    index = round((pct / 100.0) * (len(values) - 1))
    return values[index]


def summarize_output(token: str) -> dict[str, float | str | int]:
    folder = latest_output(f"{BASE_PREFIX}_{token}")
    summary: dict[str, float | str | int] = {"pattern": token, "folder": folder.name}
    for field in ["imt_bs_antenna_gain", "imt_dl_snr", "imt_dl_sinr", "imt_dl_tput"]:
        values = read_values(folder / f"{field}.csv", field)
        summary[f"{field}_p50"] = percentile(values, 50)
        summary[f"{field}_p95"] = percentile(values, 95)
        summary[f"{field}_n"] = len(values)
    return summary


def main() -> None:
    generated = generate_test_inputs()
    for param_file in generated:
        token = param_file.stem.replace("dc_mss_isolado_anttest_", "")
        prefix = f"{BASE_PREFIX}_{token}"
        try:
            latest_output(prefix)
            print(f"Pulando {param_file.name}: output valido ja existe.")
        except FileNotFoundError:
            print(f"Rodando {param_file.name}...")
            run_simulation(param_file)

    rows = [summarize_output(token) for token in PATTERNS]
    out_csv = CAMPAIGN_DIR / "plots" / "imt_performance" / "antenna_pattern_quick_test.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResumo salvo em: {out_csv}")
    print("pattern,gain_p50,snr_p50,sinr_p50,tput_p50,tput_p95")
    for row in rows:
        print(
            f"{row['pattern']},"
            f"{row['imt_bs_antenna_gain_p50']:.3f},"
            f"{row['imt_dl_snr_p50']:.3f},"
            f"{row['imt_dl_sinr_p50']:.3f},"
            f"{row['imt_dl_tput_p50']:.6f},"
            f"{row['imt_dl_tput_p95']:.6f}"
        )


if __name__ == "__main__":
    main()

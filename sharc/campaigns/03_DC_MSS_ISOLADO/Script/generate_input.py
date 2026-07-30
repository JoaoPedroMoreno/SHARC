from pathlib import Path
import re


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "base_input.yaml"
OUTPUT_DIR = BASE_DIR.parent / "input"

SYSTEM_NAME = "Sys3_340km"
N_PLANES = 48
ALTITUDE_KM = 340.0
SATS_PER_PLANE = 110
BEAM_RADIUS_M = 25803

LOAD_FACTORS = [0.2, 0.5]
POWER_BACKOFF_LEVELS_DB = [0.0, 5.0, 10.0, 15.0, 20.0]
AFFECTED_FRACTIONS = [0.05, 0.10, 0.15]
SERVED_COUNTRIES = ["Brazil"]


def scenario_name(
    load_factor: float,
    power_backoff_db: float,
    affected_fraction: float,
) -> str:
    load_percent = int(round(load_factor * 100))
    pbo_db = int(round(power_backoff_db))
    fraction_percent = int(round(affected_fraction * 100))
    return (
        f"dc_mss_isolado_{SYSTEM_NAME}_LF{load_percent}"
        f"_PBO{pbo_db}dB_F{fraction_percent:02d}pct"
    )


def build_scenarios() -> list[tuple[float, float, float]]:
    scenarios = []
    for load_factor in LOAD_FACTORS:
        scenarios.append((load_factor, 0.0, 0.0))
        for power_backoff_db in POWER_BACKOFF_LEVELS_DB:
            if power_backoff_db == 0.0:
                continue
            for affected_fraction in AFFECTED_FRACTIONS:
                scenarios.append(
                    (load_factor, power_backoff_db, affected_fraction))
    return scenarios


def cleanup_generated_inputs(output_dir: Path) -> None:
    for generated_file in output_dir.glob("dc_mss_isolado_*.yaml"):
        generated_file.unlink()


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def replace_scalar(line: str, key: str, value) -> tuple[str, bool]:
    pattern = rf"^(\s*(?:-\s*)?{re.escape(key)}:\s*)([^#\r\n]*?)(\s*(?:#.*)?$)"
    match = re.match(pattern, line)
    if not match:
        return line, False
    prefix, _, suffix = match.groups()
    value_text = "" if value is None else str(value)
    separator = " " if value_text and prefix.endswith(":") else ""
    return f"{prefix}{separator}{value_text}{suffix}", True


def replace_first_scalar(
    lines: list[str],
    key: str,
    value,
    *,
    start: int = 0,
    end: int | None = None,
) -> None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        updated, matched = replace_scalar(lines[index], key, value)
        if matched:
            lines[index] = updated
            return
    raise KeyError(f"Could not find key '{key}' in template")


def find_line(
    lines: list[str],
    pattern: str,
    *,
    start: int = 0,
    end: int | None = None,
) -> int:
    end = len(lines) if end is None else end
    regex = re.compile(pattern)
    for index in range(start, end):
        if regex.search(lines[index]):
            return index
    raise KeyError(f"Could not find pattern '{pattern}' in template")


def find_next_top_level_section(lines: list[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        if (
            lines[index].strip()
            and line_indent(lines[index]) == 0
            and not lines[index].lstrip().startswith("#")
        ):
            return index
    return len(lines)


def replace_country_name_blocks(
    lines: list[str],
    countries: list[str],
) -> None:
    index = 0
    while index < len(lines):
        if not re.match(r"^\s*country_names:\s*$", lines[index]):
            index += 1
            continue

        parent_indent = line_indent(lines[index])
        item_indent = parent_indent + 4
        insert_at = index + 1
        remove_until = insert_at

        while remove_until < len(lines):
            stripped = lines[remove_until].strip()
            if not stripped or line_indent(lines[remove_until]) <= parent_indent:
                break
            if stripped.startswith("-") or re.match(r"^#\s*-", stripped):
                remove_until += 1
                continue
            break

        lines[insert_at:remove_until] = [
            f"{' ' * item_indent}- {country}" for country in countries
        ]
        index = insert_at + len(countries)


def neutralize_geographic_power_backoff(
    lines: list[str],
    *,
    power_control_start: int,
    imt_end: int,
) -> None:
    for index in range(power_control_start, imt_end):
        if not re.match(r"^\s*-\s*power_backoff_db:\s*", lines[index]):
            continue
        lines[index], _ = replace_scalar(
            lines[index],
            "power_backoff_db",
            0.0,
        )


def update_template(
    template: str,
    *,
    output_prefix: str,
    load_factor: float,
    power_backoff_db: float,
    affected_fraction: float,
) -> str:
    lines = template.splitlines()

    imt_start = find_line(lines, r"^imt:\s*$")
    imt_end = find_next_top_level_section(lines, imt_start)
    topology_start = find_line(
        lines,
        r"^\s{4}topology:\s*$",
        start=imt_start,
        end=imt_end,
    )
    mss_dc_start = find_line(
        lines,
        r"^\s{8}mss_dc:\s*$",
        start=topology_start,
        end=imt_end,
    )
    power_control_start = find_line(
        lines,
        r"^\s*power_control_zones:\s*$",
        start=mss_dc_start,
        end=imt_end,
    )
    bs_start = find_line(
        lines,
        r"^\s{4}bs:\s*$",
        start=imt_start,
        end=imt_end,
    )
    ue_start = find_line(
        lines,
        r"^\s{4}ue:\s*$",
        start=bs_start,
        end=imt_end,
    )

    replace_first_scalar(lines, "output_dir_prefix", f"output_{output_prefix}")
    replace_first_scalar(
        lines,
        "interfered_with",
        "false",
        start=imt_start,
        end=imt_end,
    )
    replace_first_scalar(
        lines,
        "imt_dl_intra_sinr_calculation_disabled",
        "false",
        start=imt_start,
        end=imt_end,
    )

    replace_first_scalar(
        lines, "n_planes", N_PLANES, start=mss_dc_start, end=imt_end)
    replace_first_scalar(
        lines,
        "perigee_alt_km",
        ALTITUDE_KM,
        start=mss_dc_start,
        end=imt_end,
    )
    replace_first_scalar(
        lines,
        "apogee_alt_km",
        ALTITUDE_KM,
        start=mss_dc_start,
        end=imt_end,
    )
    replace_first_scalar(
        lines,
        "sats_per_plane",
        SATS_PER_PLANE,
        start=mss_dc_start,
        end=imt_end,
    )
    replace_first_scalar(
        lines,
        "beam_radius",
        BEAM_RADIUS_M,
        start=mss_dc_start,
        end=imt_end,
    )
    replace_first_scalar(
        lines,
        "mode",
        "ACTIVE_FRACTION",
        start=power_control_start,
        end=bs_start,
    )
    replace_first_scalar(
        lines,
        "power_backoff_db",
        float(power_backoff_db),
        start=power_control_start,
        end=bs_start,
    )
    replace_first_scalar(
        lines,
        "affected_fraction",
        float(affected_fraction),
        start=power_control_start,
        end=bs_start,
    )
    neutralize_geographic_power_backoff(
        lines,
        power_control_start=power_control_start,
        imt_end=bs_start,
    )

    replace_first_scalar(
        lines,
        "load_probability",
        load_factor,
        start=bs_start,
        end=ue_start,
    )
    replace_first_scalar(
        lines,
        "height",
        ALTITUDE_KM * 1000,
        start=bs_start,
        end=ue_start,
    )

    replace_country_name_blocks(lines, SERVED_COUNTRIES)
    return "\n".join(lines) + "\n"


def generate_inputs(
    template_path: Path = INPUT_FILE,
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = template_path.read_text(encoding="utf-8")
    cleanup_generated_inputs(output_dir)

    generated_paths = []
    for load_factor, power_backoff_db, affected_fraction in build_scenarios():
        name = scenario_name(
            load_factor,
            power_backoff_db,
            affected_fraction,
        )
        output_path = output_dir / f"{name}.yaml"
        output_path.write_text(
            update_template(
                template,
                output_prefix=name,
                load_factor=load_factor,
                power_backoff_db=power_backoff_db,
                affected_fraction=affected_fraction,
            ),
            encoding="utf-8",
        )
        generated_paths.append(output_path)

    return generated_paths


if __name__ == "__main__":
    generated = generate_inputs()
    print(f"{len(generated)} arquivos YAML gerados com sucesso.")

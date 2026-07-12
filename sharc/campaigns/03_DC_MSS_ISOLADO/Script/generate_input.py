from pathlib import Path
import re


base_dir = Path(__file__).resolve().parent
input_file = base_dir / "base_input.yaml"
output_dir = base_dir.parent / "input"
output_dir.mkdir(parents=True, exist_ok=True)

SYSTEMS = {
    "Sys3_340km": {
        "n_planes": 48,
        "alt_km": 340,
        "sats_per_plane": 110,
        "beam_radius_m": 23775,
    },
    "Sys3_525km": {
        "n_planes": 28,
        "alt_km": 525,
        "sats_per_plane": 120,
        "beam_radius_m": 36712,
    },
}

FS_HEIGHTS = {
    20: {
        "mean_clutter_height": "low",
        "below_rooftop": 60,
    },
    40: {
        "mean_clutter_height": "mid",
        "below_rooftop": 10,
    },
}

LOAD_FACTORS = [0.2, 0.5]
SERVED_COUNTRIES = ["Brazil"]


def scenario_name(system_name: str, fs_height_m: int, load_percent: int) -> str:
    return f"dc_mss_isolado_{system_name}_FS{fs_height_m}m_LF{load_percent}"


def cleanup_generated_inputs() -> None:
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


def replace_first_scalar(lines: list[str], key: str, value, *, start: int = 0, end: int | None = None) -> None:
    end = len(lines) if end is None else end
    for index in range(start, end):
        updated, matched = replace_scalar(lines[index], key, value)
        if matched:
            lines[index] = updated
            return
    raise KeyError(f"Could not find key '{key}' in template")


def find_line(lines: list[str], pattern: str, *, start: int = 0, end: int | None = None) -> int:
    end = len(lines) if end is None else end
    regex = re.compile(pattern)
    for index in range(start, end):
        if regex.search(lines[index]):
            return index
    raise KeyError(f"Could not find pattern '{pattern}' in template")


def find_next_top_level_section(lines: list[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        if lines[index].strip() and line_indent(lines[index]) == 0 and not lines[index].lstrip().startswith("#"):
            return index
    return len(lines)


def replace_country_name_blocks(lines: list[str], countries: list[str]) -> None:
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

        lines[insert_at:remove_until] = [f"{' ' * item_indent}- {country}" for country in countries]
        index = insert_at + len(countries)


def replace_power_backoff_values(lines: list[str], *, mss_dc_start: int, imt_end: int) -> None:
    power_control_start = find_line(lines, r"^\s*power_control_zones:\s*$", start=mss_dc_start, end=imt_end)
    matches = [
        index for index in range(power_control_start, imt_end)
        if re.match(r"^\s*-\s*power_backoff_db:\s*", lines[index])
    ]
    if len(matches) < 2:
        raise KeyError("Expected at least two power_backoff_db zones in template")
    lines[matches[0]], _ = replace_scalar(lines[matches[0]], "power_backoff_db", 0.0)
    lines[matches[1]], _ = replace_scalar(lines[matches[1]], "power_backoff_db", 0.0)


def replace_mss_border_margins(lines: list[str], *, mss_dc_start: int, imt_end: int) -> None:
    for index in range(mss_dc_start, imt_end):
        updated, matched = replace_scalar(lines[index], "margin_from_border", 0)
        if matched:
            lines[index] = updated


def update_template(template: str, *, output_prefix: str, system: dict, fs_height_m: int,
                    fs_params: dict, load_factor: float) -> str:
    lines = template.splitlines()

    imt_start = find_line(lines, r"^imt:\s*$")
    imt_end = find_next_top_level_section(lines, imt_start)
    topology_start = find_line(lines, r"^\s{4}topology:\s*$", start=imt_start, end=imt_end)
    mss_dc_start = find_line(lines, r"^\s{8}mss_dc:\s*$", start=topology_start, end=imt_end)
    bs_start = find_line(lines, r"^\s{4}bs:\s*$", start=imt_start, end=imt_end)
    ue_start = find_line(lines, r"^\s{4}ue:\s*$", start=bs_start, end=imt_end)

    fs_start = find_line(lines, r"^single_earth_station:\s*$")
    fs_end = find_next_top_level_section(lines, fs_start)
    fs_geometry_start = find_line(lines, r"^\s{2}geometry:\s*$", start=fs_start, end=fs_end)
    fs_antenna_start = find_line(lines, r"^\s{2}antenna:\s*$", start=fs_geometry_start, end=fs_end)
    param_p619_start = find_line(lines, r"^\s{2}param_p619:\s*$", start=fs_start, end=fs_end)

    replace_first_scalar(lines, "output_dir_prefix", f"output_{output_prefix}")
    replace_first_scalar(lines, "interfered_with", "false", start=imt_start, end=imt_end)
    replace_first_scalar(lines, "imt_dl_intra_sinr_calculation_disabled", "false", start=imt_start, end=imt_end)

    replace_first_scalar(lines, "n_planes", system["n_planes"], start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "perigee_alt_km", float(system["alt_km"]), start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "apogee_alt_km", float(system["alt_km"]), start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "sats_per_plane", system["sats_per_plane"], start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "beam_radius", system["beam_radius_m"], start=mss_dc_start, end=imt_end)
    replace_power_backoff_values(lines, mss_dc_start=mss_dc_start, imt_end=imt_end)
    replace_mss_border_margins(lines, mss_dc_start=mss_dc_start, imt_end=imt_end)

    replace_first_scalar(lines, "load_probability", load_factor, start=bs_start, end=ue_start)
    replace_first_scalar(lines, "height", float(system["alt_km"] * 1000), start=bs_start, end=ue_start)

    replace_first_scalar(lines, "height", fs_height_m, start=fs_geometry_start, end=fs_antenna_start)
    replace_first_scalar(lines, "mean_clutter_height", fs_params["mean_clutter_height"], start=param_p619_start, end=fs_end)
    replace_first_scalar(lines, "below_rooftop", fs_params["below_rooftop"], start=param_p619_start, end=fs_end)

    replace_country_name_blocks(lines, SERVED_COUNTRIES)
    return "\n".join(lines) + "\n"


template = input_file.read_text(encoding="utf-8")
cleanup_generated_inputs()

created = 0
for system_name, system in SYSTEMS.items():
    for fs_height_m, fs_params in FS_HEIGHTS.items():
        for load_factor in LOAD_FACTORS:
            load_percent = int(load_factor * 100)
            name = scenario_name(system_name, fs_height_m, load_percent)
            output_path = output_dir / f"{name}.yaml"
            output_path.write_text(
                update_template(
                    template,
                    output_prefix=name,
                    system=system,
                    fs_height_m=fs_height_m,
                    fs_params=fs_params,
                    load_factor=load_factor,
                ),
                encoding="utf-8",
            )
            created += 1

print(f"{created} arquivos YAML gerados com sucesso.")

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
        "margins_km": [25, 75],
    },
    "Sys3_525km": {
        "n_planes": 28,
        "alt_km": 525,
        "sats_per_plane": 120,
        "beam_radius_m": 36712,
        "margins_km": [40, 120],
    },
}

CASES = {
    "BR_AR_Paraguay": {
        "served_countries": ["Brazil", "Argentina"],
    },
    "SouthAmerica": {
        "served_countries": [
            "Brazil",
            "Argentina",
            "Uruguay",
            "Paraguay",
            "Bolivia",
            "Chile",
            "Peru",
        ],
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

LOAD_FACTORS = [0.1, 0.5]
AZIMUTHS_DEG = [90, 180]


def build_scenario_name(
    case_name: str,
    system_name: str,
    fs_height_m: int,
    load_percent: int,
    margin_km: int,
    azimuth_deg: int,
) -> str:
    return (
        f"dc_mss_to_fs_"
        f"{case_name}_"
        f"{system_name}_"
        f"FS{fs_height_m}m_"
        f"LF{load_percent}_"
        f"M{margin_km}km_"
        f"Azi{azimuth_deg}deg"
    )


def build_output_dir_prefix(
    case_name: str,
    system_name: str,
    fs_height_m: int,
    load_percent: int,
    margin_km: int,
    azimuth_deg: int,
) -> str:
    return f"output_{build_scenario_name(case_name, system_name, fs_height_m, load_percent, margin_km, azimuth_deg)}"


def cleanup_generated_inputs() -> None:
    for generated_file in output_dir.glob("dc_mss_to_fs_*.yaml"):
        generated_file.unlink()
    for generated_file in output_dir.glob("output_dc_mss_to_fs_*.yaml"):
        generated_file.unlink()


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def replace_scalar(line: str, key: str, value) -> tuple[str, bool]:
    pattern = rf"^(\s*(?:-\s*)?{re.escape(key)}:\s*)([^#\r\n]*?)(\s*(?:#.*)?$)"
    match = re.match(pattern, line)
    if not match:
        return line, False
    prefix, _, suffix = match.groups()
    return f"{prefix}{value}{suffix}", True


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
            if not stripped:
                break
            if line_indent(lines[remove_until]) <= parent_indent:
                break
            if stripped.startswith("-") or re.match(r"^#\s*-", stripped):
                remove_until += 1
                continue
            break

        replacement = [f"{' ' * item_indent}- {country}" for country in countries]
        lines[insert_at:remove_until] = replacement
        index = insert_at + len(replacement)


def replace_grid_margin(lines: list[str], margin_km: int, *, mss_dc_start: int, imt_end: int) -> None:
    grid_start = find_line(lines, r"^\s*grid_in_zone:\s*$", start=mss_dc_start, end=imt_end)
    from_countries_start = find_line(lines, r"^\s*from_countries:\s*$", start=grid_start, end=imt_end)
    replace_first_scalar(lines, "margin_from_border", margin_km, start=from_countries_start, end=imt_end)


def update_template(template: str, *, output_dir_prefix: str, system: dict, countries: list[str],
                    fs_height_m: int, fs_params: dict, load_factor: float,
                    margin_km: int, azimuth_deg: int) -> str:
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

    replace_first_scalar(lines, "output_dir_prefix", output_dir_prefix)

    replace_first_scalar(lines, "central_altitude", 200, start=topology_start, end=imt_end)
    replace_first_scalar(lines, "n_planes", system["n_planes"], start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "perigee_alt_km", float(system["alt_km"]), start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "apogee_alt_km", float(system["alt_km"]), start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "sats_per_plane", system["sats_per_plane"], start=mss_dc_start, end=imt_end)
    replace_first_scalar(lines, "beam_radius", system["beam_radius_m"], start=mss_dc_start, end=imt_end)
    replace_grid_margin(lines, margin_km, mss_dc_start=mss_dc_start, imt_end=imt_end)

    replace_first_scalar(lines, "load_probability", load_factor, start=bs_start, end=ue_start)
    replace_first_scalar(lines, "conducted_power", 42.8, start=bs_start, end=ue_start)
    replace_first_scalar(lines, "height", float(system["alt_km"] * 1000), start=bs_start, end=ue_start)

    replace_first_scalar(lines, "height", fs_height_m, start=fs_geometry_start, end=fs_antenna_start)
    replace_first_scalar(lines, "fixed", azimuth_deg, start=fs_geometry_start, end=fs_antenna_start)
    replace_first_scalar(lines, "frequency", 2155, start=fs_start, end=fs_end)
    replace_first_scalar(lines, "bandwidth", 29, start=fs_start, end=fs_end)
    replace_first_scalar(lines, "mean_clutter_height", fs_params["mean_clutter_height"], start=param_p619_start, end=fs_end)
    replace_first_scalar(lines, "below_rooftop", fs_params["below_rooftop"], start=param_p619_start, end=fs_end)

    replace_country_name_blocks(lines, countries)

    return "\n".join(lines) + "\n"


template = input_file.read_text(encoding="utf-8")
cleanup_generated_inputs()

for system_name, system in SYSTEMS.items():
    for case_name, case in CASES.items():
        for fs_height_m, fs_params in FS_HEIGHTS.items():
            for load_factor in LOAD_FACTORS:
                for margin_km in system["margins_km"]:
                    for azimuth_deg in AZIMUTHS_DEG:
                        load_percent = int(load_factor * 100)
                        countries = case["served_countries"]

                        name_file = build_scenario_name(
                            case_name, system_name, fs_height_m, load_percent, margin_km, azimuth_deg)
                        output_dir_prefix = build_output_dir_prefix(
                            case_name, system_name, fs_height_m, load_percent, margin_km, azimuth_deg)

                        output_path = output_dir / f"{name_file}.yaml"
                        output_path.write_text(
                            update_template(
                                template,
                                output_dir_prefix=output_dir_prefix,
                                system=system,
                                countries=countries,
                                fs_height_m=fs_height_m,
                                fs_params=fs_params,
                                load_factor=load_factor,
                                margin_km=margin_km,
                                azimuth_deg=azimuth_deg,
                            ),
                            encoding="utf-8",
                        )

print("Arquivos YAML gerados com sucesso!")

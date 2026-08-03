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
        "beam_radius_m": 25803,
        "margins_km": list(range(0, 101, 10)),
        "exclusion_radii_km": list(range(0, 101, 10)),
    },
    "Sys3_525km": {
        "n_planes": 28,
        "alt_km": 525,
        "sats_per_plane": 120,
        "beam_radius_m": 39844,
        "margins_km": list(range(0, 101, 10)),
        "exclusion_radii_km": list(range(0, 101, 10)),
    },
}

CASES = {
    "BR_AR_Paraguay": {
        "served_countries": ["Brazil", "Argentina"],
        "distance_mode": "POWER_BACKOFF",
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
        "distance_mode": "EXCLUSION_ZONE",
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
AZIMUTHS_DEG = [90]

# The victim FS is currently at geometry.location.fixed x=0, y=0, so this
# matches imt.topology.central_latitude/central_longitude in base_input.yaml.
EXCLUSION_ZONE_CENTER_LAT = -25.5549751
EXCLUSION_ZONE_CENTER_LON = -54.5746686


def build_scenario_name(
    case_name: str,
    system_name: str,
    fs_height_m: int,
    load_percent: int,
    distance_token: str,
    azimuth_deg: int,
) -> str:
    return (
        f"dc_mss_to_fs_"
        f"{case_name}_"
        f"{system_name}_"
        f"FS{fs_height_m}m_"
        f"LF{load_percent}_"
        f"{distance_token}_"
        f"Azi{azimuth_deg}deg"
    )


def build_output_dir_prefix(
    case_name: str,
    system_name: str,
    fs_height_m: int,
    load_percent: int,
    distance_token: str,
    azimuth_deg: int,
) -> str:
    return f"output_{build_scenario_name(case_name, system_name, fs_height_m, load_percent, distance_token, azimuth_deg)}"


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
    value_text = "" if value is None else str(value)
    separator = " " if value_text != "" and prefix.endswith(":") else ""
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


def replace_power_backoff_margin(lines: list[str], margin_km: int, *, mss_dc_start: int, imt_end: int) -> None:
    power_control_start = find_line(lines, r"^\s*power_control_zones:\s*$", start=mss_dc_start, end=imt_end)
    zone_zero_start = find_line(lines, r"^\s*-\s*power_backoff_db:\s*0(?:\.0)?\s*$", start=power_control_start, end=imt_end)
    from_countries_start = find_line(lines, r"^\s*from_countries:\s*$", start=zone_zero_start, end=imt_end)
    replace_first_scalar(lines, "margin_from_border", margin_km, start=from_countries_start, end=imt_end)


def replace_power_backoff_values(lines: list[str], border_backoff_db: float, *, mss_dc_start: int, imt_end: int) -> None:
    power_control_start = find_line(lines, r"^\s*power_control_zones:\s*$", start=mss_dc_start, end=imt_end)
    matches = []
    for index in range(power_control_start, imt_end):
        if re.match(r"^\s*-\s*power_backoff_db:\s*", lines[index]):
            matches.append(index)

    if len(matches) < 2:
        raise KeyError("Expected at least two power_backoff_db zones in template")

    lines[matches[0]], _ = replace_scalar(lines[matches[0]], "power_backoff_db", 0.0)
    lines[matches[1]], _ = replace_scalar(lines[matches[1]], "power_backoff_db", border_backoff_db)


def replace_grid_exclusion_zone(
    lines: list[str],
    *,
    enabled: bool,
    radius_km: int,
    center_lat: float,
    center_lon: float,
    mss_dc_start: int,
    imt_end: int,
) -> None:
    exclusion_start = find_line(lines, r"^\s*grid_exclusion_zone:\s*$", start=mss_dc_start, end=imt_end)
    circle_start = find_line(lines, r"^\s*circle:\s*$", start=exclusion_start, end=imt_end)

    replace_first_scalar(lines, "type", "CIRCLE" if enabled else "", start=exclusion_start, end=circle_start)
    replace_first_scalar(lines, "center_lat", center_lat, start=circle_start, end=imt_end)
    replace_first_scalar(lines, "center_lon", center_lon, start=circle_start, end=imt_end)
    replace_first_scalar(lines, "radius_km", radius_km if enabled else 0, start=circle_start, end=imt_end)


def update_template(template: str, *, output_dir_prefix: str, system: dict, countries: list[str],
                    fs_height_m: int, fs_params: dict, load_factor: float,
                    margin_km: int, azimuth_deg: int,
                    use_exclusion_zone: bool = False,
                    disable_power_backoff: bool = False) -> str:
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
    replace_grid_margin(lines, 0, mss_dc_start=mss_dc_start, imt_end=imt_end)
    replace_power_backoff_margin(lines, 0 if disable_power_backoff else margin_km, mss_dc_start=mss_dc_start, imt_end=imt_end)
    replace_power_backoff_values(lines, 0.0 if disable_power_backoff else 10.0, mss_dc_start=mss_dc_start, imt_end=imt_end)
    replace_grid_exclusion_zone(
        lines,
        enabled=use_exclusion_zone,
        radius_km=margin_km,
        center_lat=EXCLUSION_ZONE_CENTER_LAT,
        center_lon=EXCLUSION_ZONE_CENTER_LON,
        mss_dc_start=mss_dc_start,
        imt_end=imt_end,
    )

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
                distance_mode = case["distance_mode"]
                if distance_mode == "POWER_BACKOFF":
                    distances_km = system["margins_km"]
                    distance_prefix = "M"
                    use_exclusion_zone = False
                    disable_power_backoff = False
                elif distance_mode == "EXCLUSION_ZONE":
                    distances_km = system["exclusion_radii_km"]
                    distance_prefix = "EZ"
                    use_exclusion_zone = True
                    disable_power_backoff = True
                else:
                    distances_km = [0]
                    distance_prefix = "M"
                    use_exclusion_zone = False
                    disable_power_backoff = False

                for margin_km in distances_km:
                    distance_token = f"{distance_prefix}{margin_km}km"
                    effective_use_exclusion_zone = use_exclusion_zone and margin_km > 0
                    for azimuth_deg in AZIMUTHS_DEG:
                        load_percent = int(load_factor * 100)
                        countries = case["served_countries"]

                        name_file = build_scenario_name(
                            case_name, system_name, fs_height_m, load_percent, distance_token, azimuth_deg)
                        output_dir_prefix = build_output_dir_prefix(
                            case_name, system_name, fs_height_m, load_percent, distance_token, azimuth_deg)

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
                                use_exclusion_zone=effective_use_exclusion_zone,
                                disable_power_backoff=disable_power_backoff,
                            ),
                            encoding="utf-8",
                        )

print("Arquivos YAML gerados com sucesso!")

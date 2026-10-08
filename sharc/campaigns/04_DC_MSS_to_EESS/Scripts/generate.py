from __future__ import annotations

from copy import deepcopy
from itertools import product
from pathlib import Path
import math
import yaml


# ============================================================
# PATHS
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = SCRIPT_DIR.parent

BASE_FILE = SCRIPT_DIR / "base_input.yaml"
INPUT_DIR = CAMPAIGN_DIR / "input"
P619_DATASET_DIR = CAMPAIGN_DIR.parents[1] / "propagation" / "Dataset"

# O base nunca é sobrescrito.
# Se um YAML já existir, por segurança o gerador aborta.
OVERWRITE_EXISTING_INPUTS = False


# ============================================================
# MATRIZ DA PESQUISA
# ============================================================
#
# O baseline do documento é recriado por GB=80 MHz:
# DC-MSS fc=2117.5 MHz, canal 2115--2120 MHz.
#
# Esta matriz testa o efeito de:
#   1) separação espectral (guard band);
#   2) handover OFF/ON.
#
# Guard band aqui significa separação ENTRE AS BORDAS dos canais.
# NÃO confundir com imt.guard_band_ratio, que permanece em 0.1.
#
# EESS B e D têm borda inferior em 2200 MHz.
# DC-MSS tem BW = 5 MHz.
#
# Logo:
#   f_DC_center = 2200 - guard_band - 2.5
#
# Exemplos:
#   GB = 0 MHz  -> DC-MSS 2195–2200 MHz -> fc = 2197.5 MHz
#   GB = 80 MHz -> DC-MSS 2115–2120 MHz -> fc = 2117.5 MHz
#   GB = 10 MHz -> DC-MSS 2185–2190 MHz -> fc = 2187.5 MHz
#   GB = 5 MHz  -> DC-MSS 2190–2195 MHz -> fc = 2192.5 MHz
# ============================================================

ALTITUDES_KM = [340, 525]
EESS_SYSTEMS = ["EESS_B", "EESS_D"]
POSITIONS = ["P"]  # somente Paraguai
LOAD_FACTORS = [0.2, 0.5]

# Para isolar o efeito de guard band + handover, deixamos a
# mitigação geográfica antiga (OM=75 km) DESLIGADA.
OPERATIONAL_MARGINS_KM = [0]

# Caso principal do novo estudo: cobertura de toda a América do Sul.
# ATENÇÃO: "Colombia" pode aparecer na lista de países de cobertura SA,
# mas NÃO é gerada como posição da estação EESS. A única posição EESS é P = Paraguai.
# Para incluir também o antigo Case II, troque por ["SA", "BR_AR"].
COVERAGES = ["SA"]

# Pontos adicionais informativos: GB=10 ainda está na região plana de
# espúrios; GB=5 é o primeiro ponto na região variável da máscara.
GUARD_BANDS_MHZ = [10, 5]
NUM_SNAPSHOTS = 5000
DC_MSS_BANDWIDTH_MHZ = 5.0


# ============================================================
# PARÂMETROS DA CAMPANHA VALIDADA
# ============================================================

ALTITUDE_CONFIG = {
    340: {
        "n_planes": 48,
        "sats_per_plane": 110,
        "phasing_deg": 1.636,
        "beam_radius": 26195,
        "N_max_beam": 105,
        "bs_height_m": 340000,
    },
    525: {
        "n_planes": 28,
        "sats_per_plane": 120,
        "phasing_deg": 1.5,
        "beam_radius": 40448,
        "N_max_beam": 90,
        "bs_height_m": 525000,
    },
}

EESS_CONFIG = {
    "EESS_B": {
        "frequency": 2202.0,
        "bandwidth": 4.0,
        "noise_temperature": 190,
        "gain": 45.8,
        "diameter": 8.91,
    },
    "EESS_D": {
        "frequency": 2203.0,
        "bandwidth": 6.0,
        "noise_temperature": 120,
        "gain": 39.0,
        "diameter": 4.07,
    },
}

POSITION_CONFIG = {
    "P": {
        "name": "Paraguay",
        "latitude": -25.5549751,
        "longitude": -54.5746686,
        "altitude_m": 200,
    },
}

COVERAGE_CONFIG = {
    "SA": [
        "Argentina",
        "Bolivia",
        "Brazil",
        "Chile",
        "Colombia",
        "Ecuador",
        "Paraguay",
        "Peru",
        "Uruguay",
        "Venezuela",
        "Guyana",
        "Suriname",
    ],
    "BR_AR": [
        "Brazil",
        "Argentina",
    ],
}


# ============================================================
# HELPERS
# ============================================================

def fmt_number(value: float) -> str:
    """Usado apenas nos nomes dos arquivos."""
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", "p")


def load_base() -> dict:
    if not BASE_FILE.exists():
        raise FileNotFoundError(f"Base não encontrado: {BASE_FILE}")

    with BASE_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("base_input.yaml não contém um dicionário YAML válido.")

    return data


def calculate_dc_center_frequency(
    eess_frequency_mhz: float,
    eess_bandwidth_mhz: float,
    dc_bandwidth_mhz: float,
    guard_band_mhz: float,
) -> float:
    """
    Guard band = distância entre:
        borda superior do canal DC-MSS
        e
        borda inferior do canal EESS.
    """

    if guard_band_mhz < 0:
        raise ValueError("Guard band negativa criaria overlap/co-channel.")

    eess_lower_edge = eess_frequency_mhz - eess_bandwidth_mhz / 2.0

    dc_center = (
        eess_lower_edge
        - guard_band_mhz
        - dc_bandwidth_mhz / 2.0
    )

    dc_lower_edge = dc_center - dc_bandwidth_mhz / 2.0
    dc_upper_edge = dc_center + dc_bandwidth_mhz / 2.0

    # Faixa DC-MSS do estudo: 2110–2200 MHz
    if dc_lower_edge < 2110.0 or dc_upper_edge > 2200.0:
        raise ValueError(
            f"Canal DC-MSS fora de 2110–2200 MHz: "
            f"{dc_lower_edge:.3f}–{dc_upper_edge:.3f} MHz"
        )

    return dc_center


def expected_p619_lookup_path(dc_frequency_mhz: float) -> Path:
    """Return the exact filename convention used by PropagationP619."""
    return P619_DATASET_DIR / (
        f"FOZ_{int(float(dc_frequency_mhz))}_200m.csv"
    )


def validate_p619_lookup_tables() -> None:
    """Abort before writing inputs if any sweep lookup table is absent."""
    expected = [
        (
            2197.5 - float(guard_band_mhz),
            expected_p619_lookup_path(2197.5 - float(guard_band_mhz)),
        )
        for guard_band_mhz in GUARD_BANDS_MHZ
    ]
    missing = [(frequency, path) for frequency, path in expected
               if not path.is_file()]
    if missing:
        details = "\n".join(
            f"  - {frequency:.1f} MHz: {path.name}"
            for frequency, path in missing
        )
        raise FileNotFoundError(
            "Campanha não gerada: faltam lookup tables P.619 de FOZ:\n"
            f"{details}\n"
            "As tabelas não serão inventadas ou regeneradas automaticamente."
        )


def apply_altitude(cfg: dict, altitude_km: int) -> None:
    p = ALTITUDE_CONFIG[altitude_km]

    mss = cfg["imt"]["topology"]["mss_dc"]
    orbit = mss["orbits"][0]

    orbit["n_planes"] = p["n_planes"]
    orbit["perigee_alt_km"] = altitude_km
    orbit["apogee_alt_km"] = altitude_km
    orbit["sats_per_plane"] = p["sats_per_plane"]
    orbit["phasing_deg"] = p["phasing_deg"]

    mss["beam_radius"] = p["beam_radius"]
    mss["N_max_beam"] = p["N_max_beam"]

    cfg["imt"]["bs"]["height"] = p["bs_height_m"]


def apply_eess(cfg: dict, system_label: str) -> None:
    p = EESS_CONFIG[system_label]
    es = cfg["single_earth_station"]

    # Obrigatório para o handover implementado pelo Codex.
    # É mantido também com HO OFF para que os pares OFF/ON
    # difiram somente no campo "enabled".
    es["system_label"] = system_label

    es["frequency"] = p["frequency"]
    es["bandwidth"] = p["bandwidth"]
    es["noise_temperature"] = p["noise_temperature"]

    es["antenna"]["gain"] = p["gain"]
    es["antenna"]["itu_r_s_465"]["antenna_gain"] = p["gain"]
    es["antenna"]["itu_r_s_465"]["diameter"] = p["diameter"]


def apply_position(cfg: dict, position: str) -> None:
    p = POSITION_CONFIG[position]

    topo = cfg["imt"]["topology"]
    topo["central_latitude"] = p["latitude"]
    topo["central_longitude"] = p["longitude"]
    topo["central_altitude"] = p["altitude_m"]

    p619 = cfg["single_earth_station"]["param_p619"]
    p619["earth_station_lat_deg"] = p["latitude"]
    p619["earth_station_alt_m"] = p["altitude_m"]

    # geometry.location.fixed.x/y permanecem 0/0 porque a ES
    # continua sendo a origem do sistema local usado pela campanha.


def apply_coverage(cfg: dict, coverage: str) -> None:
    countries = list(COVERAGE_CONFIG[coverage])

    mss = cfg["imt"]["topology"]["mss_dc"]

    mss["sat_is_active_if"]["lat_long_inside_country"]["country_names"] = (
        list(countries)
    )

    grid_countries = (
        mss["beam_positioning"]
        ["service_grid"]
        ["grid_in_zone"]
        ["from_countries"]
    )
    grid_countries["country_names"] = list(countries)


def apply_operational_margin(cfg: dict, margin_km: int) -> None:
    # IMPORTANTE:
    # Isto é a antiga margem GEOGRÁFICA do estudo.
    # Não é guard band espectral.
    cfg["imt"]["topology"]["mss_dc"][
        "beam_positioning"
    ]["service_grid"]["grid_in_zone"]["from_countries"][
        "margin_from_border"
    ] = margin_km


def apply_handover(cfg: dict) -> None:
    ho = cfg["imt"]["topology"]["mss_dc"].setdefault(
        "interference_aware_handover",
        {},
    )

    # Sobrescrevemos explicitamente todos os campos do mecanismo
    # para não depender de defaults escondidos.
    ho["enabled"] = False
    ho["dc_mss_off_axis_limit_deg"] = 4.322755
    ho["eess_boundary"] = "S465_MAX_GAIN_REGION"
    ho["unresolved_policy"] = "KEEP_PRIMARY_AND_FLAG"
    ho["record_event_details"] = False

    # A estratégia V2 é independente do handover geométrico legado e fica
    # desligada em toda a matriz até a etapa experimental correspondente.
    v2 = cfg["imt"]["topology"]["mss_dc"].setdefault(
        "interference_aware_handover_v2", {},
    )
    v2["enabled"] = True
    v2["top_k"] = 3
    v2["min_reduction_db"] = 0.0
    v2["max_service_elevation_loss_deg"] = 90.0
    v2["max_handovers_per_snapshot"] = 1
    v2["trigger_mode"] = "RISK_GATED_TOP_K"
    v2["risk_gate_dbw_per_mhz"] = -154.0
    v2["record_candidate_details"] = False

    diagnostics = cfg["imt"]["topology"]["mss_dc"].setdefault(
        "interference_link_diagnostics", {},
    )
    diagnostics["enabled"] = False
    diagnostics["top_n"] = 10
    diagnostics["eess_position_label"] = "Paraguay"


def apply_guard_band(cfg: dict, guard_band_mhz: float) -> None:
    imt = cfg["imt"]
    es = cfg["single_earth_station"]

    dc_bw = float(imt["bandwidth"])
    if not math.isclose(dc_bw, DC_MSS_BANDWIDTH_MHZ, abs_tol=1e-12):
        raise ValueError(
            "A largura de banda DC-MSS deve permanecer fixa em 5 MHz; "
            f"base_input.yaml contém {dc_bw} MHz."
        )

    center = calculate_dc_center_frequency(
        eess_frequency_mhz=float(es["frequency"]),
        eess_bandwidth_mhz=float(es["bandwidth"]),
        dc_bandwidth_mhz=dc_bw,
        guard_band_mhz=float(guard_band_mhz),
    )

    # Somente a frequência do canal DC-MSS é deslocada.
    # NÃO alterar imt.guard_band_ratio: esse parâmetro possui
    # outro significado dentro do SHARC.
    imt["frequency"] = center

    # Todos os valores deste sweep são adjacent-band sem overlap.
    cfg["general"]["enable_adjacent_channel"] = True
    cfg["general"]["enable_cochannel"] = False


def validate_generated_config(
    cfg: dict,
    guard_band_mhz: float,
    eess_system: str,
) -> None:

    # HO
    ho = cfg["imt"]["topology"]["mss_dc"][
        "interference_aware_handover"
    ]

    assert ho["enabled"] is False
    assert math.isclose(
        float(ho["dc_mss_off_axis_limit_deg"]),
        4.322755,
        abs_tol=1e-12,
    )
    assert ho["eess_boundary"] == "S465_MAX_GAIN_REGION"
    assert ho["unresolved_policy"] == "KEEP_PRIMARY_AND_FLAG"
    v2 = cfg["imt"]["topology"]["mss_dc"][
        "interference_aware_handover_v2"]
    assert v2["enabled"] is True
    assert v2["trigger_mode"] == "RISK_GATED_TOP_K"
    assert math.isclose(float(v2["risk_gate_dbw_per_mhz"]), -154.0)
    assert math.isclose(float(v2["min_reduction_db"]), 0.0)
    assert math.isclose(float(v2["max_service_elevation_loss_deg"]), 90.0)
    assert int(v2["max_handovers_per_snapshot"]) == 1

    # EESS metadata
    assert cfg["single_earth_station"]["system_label"] == eess_system

    # Confirma a separação espectral real.
    dc_fc = float(cfg["imt"]["frequency"])
    dc_bw = float(cfg["imt"]["bandwidth"])
    assert math.isclose(
        dc_bw, DC_MSS_BANDWIDTH_MHZ, abs_tol=1e-12)

    es_fc = float(cfg["single_earth_station"]["frequency"])
    es_bw = float(cfg["single_earth_station"]["bandwidth"])

    dc_upper = dc_fc + dc_bw / 2.0
    es_lower = es_fc - es_bw / 2.0
    measured_gap = es_lower - dc_upper

    assert math.isclose(
        measured_gap,
        float(guard_band_mhz),
        abs_tol=1e-9,
    ), (
        f"Guard band incorreta: esperada={guard_band_mhz}, "
        f"obtida={measured_gap}"
    )

    # Este experimento não deve produzir overlap/co-channel.
    assert dc_upper <= es_lower + 1e-12
    assert math.isclose(
        dc_fc, 2197.5 - float(guard_band_mhz), abs_tol=1e-12)
    assert cfg["imt"]["spectral_mask"] == "MSS"
    assert cfg["imt"]["adjacent_ch_emissions"] == "SPECTRAL_MASK"
    assert cfg["general"]["enable_adjacent_channel"] is True
    assert cfg["general"]["enable_cochannel"] is False


def build_name(
    altitude_km: int,
    eess_system: str,
    coverage: str,
    position: str,
    margin_km: int,
    load_factor: float,
    guard_band_mhz: float,
) -> str:

    eess_short = eess_system.replace("EESS_", "")
    return (
        f"system_{altitude_km}km"
        f"_EESS_{eess_short}"
        f"_{coverage}"
        f"_{position}"
        f"_OM_{margin_km}"
        f"_lf_{load_factor}"
        f"_GB_{fmt_number(guard_band_mhz)}MHz"
        f"_STRATEGY_V2_RISK_GATE"
    )


def build_campaign_combinations() -> list[tuple]:
    """Build only the 16 additional V2 risk-gated cases (GB=10/5)."""
    shared_axes = (
        ALTITUDES_KM,
        EESS_SYSTEMS,
        COVERAGES,
        POSITIONS,
        OPERATIONAL_MARGINS_KM,
        LOAD_FACTORS,
    )
    combinations = list(product(*shared_axes, GUARD_BANDS_MHZ))
    assert len(combinations) == 16
    return combinations


# ============================================================
# GENERATION
# ============================================================

def main() -> None:
    base = load_base()
    # Esta verificação ocorre antes de criar diretórios ou escrever YAMLs.
    validate_p619_lookup_tables()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    combinations = build_campaign_combinations()

    generated = []

    for (
        altitude_km,
        eess_system,
        coverage,
        position,
        margin_km,
        load_factor,
        guard_band_mhz,
    ) in combinations:

        cfg = deepcopy(base)
        cfg["general"]["num_snapshots"] = NUM_SNAPSHOTS

        # Ordem deliberada:
        # 1) parâmetros físicos;
        # 2) EESS;
        # 3) geometria/cobertura;
        # 4) load;
        # 5) guard band;
        # 6) handover.
        apply_altitude(cfg, altitude_km)
        apply_eess(cfg, eess_system)
        apply_position(cfg, position)
        apply_coverage(cfg, coverage)
        apply_operational_margin(cfg, margin_km)

        cfg["imt"]["bs"]["load_probability"] = load_factor

        apply_guard_band(cfg, guard_band_mhz)
        apply_handover(cfg)

        name = build_name(
            altitude_km=altitude_km,
            eess_system=eess_system,
            coverage=coverage,
            position=position,
            margin_km=margin_km,
            load_factor=load_factor,
            guard_band_mhz=guard_band_mhz,
        )

        cfg["general"]["output_dir_prefix"] = name

        validate_generated_config(
            cfg=cfg,
            guard_band_mhz=guard_band_mhz,
            eess_system=eess_system,
        )

        output_file = INPUT_DIR / f"{name}.yaml"

        if output_file.exists() and not OVERWRITE_EXISTING_INPUTS:
            raise FileExistsError(
                f"{output_file} já existe. "
                "Nada foi sobrescrito. "
                "Apague/mova o arquivo ou habilite "
                "OVERWRITE_EXISTING_INPUTS conscientemente."
            )

        with output_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                cfg,
                f,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )

        # Reabre para detectar YAML inválido imediatamente.
        with output_file.open("r", encoding="utf-8") as f:
            yaml.safe_load(f)

        generated.append(output_file)

    print("=" * 72)
    print("CAMPANHA GERADA")
    print("=" * 72)
    print(f"Base: {BASE_FILE}")
    print(f"Diretório de inputs: {INPUT_DIR}")
    print(f"Total de YAMLs: {len(generated)}")
    print()
    print(
        f"{len(ALTITUDES_KM)} altitudes x "
        f"{len(EESS_SYSTEMS)} EESS x "
        f"{len(COVERAGES)} coberturas x "
        f"{len(POSITIONS)} posições x "
        f"{len(OPERATIONAL_MARGINS_KM)} OM x "
        f"{len(LOAD_FACTORS)} loads x "
        f"{len(GUARD_BANDS_MHZ)} guard bands"
    )
    print()
    print("Guard bands:", GUARD_BANDS_MHZ)
    print("Estratégia única: V2 RISK_GATED_TOP_K (16 inputs adicionais)")
    print()
    print("ATENÇÃO:")
    print("- imt.guard_band_ratio NÃO foi alterado.")
    print("- OM é margem geográfica; GB é separação espectral.")
    print("- Foram gerados somente GB=10 e GB=5 MHz.")
    print("- Nenhum arquivo base foi modificado.")


if __name__ == "__main__":
    main()

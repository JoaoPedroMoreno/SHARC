import importlib.util
from itertools import product
from pathlib import Path


GENERATOR = (Path(__file__).parents[1] / "sharc" / "campaigns" /
             "04_DC_MSS_to_EESS" / "Scripts" / "generate.py")
spec = importlib.util.spec_from_file_location("campaign04_generate", GENERATOR)
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


def test_campaign_matrix_has_exactly_144_inputs():
    combinations = generate.build_campaign_combinations()
    assert len(combinations) == 144
    assert sum(c[-1] == "BASELINE" for c in combinations) == 8
    assert sum(c[-1] == "V2" for c in combinations) == 136


def test_baseline_exists_only_at_80_mhz():
    combinations = generate.build_campaign_combinations()
    baseline = [c for c in combinations if c[-1] == "BASELINE"]
    assert {c[-2] for c in baseline} == {80}
    assert not any(c[-1] == "BASELINE" and c[-2] < 80
                   for c in combinations)


def test_guard_bands_frequency_and_fixed_five_mhz_bandwidth():
    assert generate.GUARD_BANDS_MHZ == list(range(80, -1, -5))
    for system in generate.EESS_SYSTEMS:
        eess = generate.EESS_CONFIG[system]
        for guard_band in generate.GUARD_BANDS_MHZ:
            center = generate.calculate_dc_center_frequency(
                eess["frequency"], eess["bandwidth"], 5.0, guard_band)
            assert center == 2197.5 - guard_band
    assert generate.DC_MSS_BANDWIDTH_MHZ == 5.0
    assert generate.load_base()["imt"]["bandwidth"] == 5


def test_p619_lookup_name_matches_implementation_convention():
    assert generate.expected_p619_lookup_path(2117.5).name == "FOZ_2117_200m.csv"
    assert generate.expected_p619_lookup_path(2197.5).name == "FOZ_2197_200m.csv"


def test_baseline_and_v2_differ_only_in_v2_enable_flag():
    base = generate.load_base()
    import copy
    baseline = copy.deepcopy(base)
    v2 = copy.deepcopy(base)
    generate.apply_handover(baseline, "BASELINE")
    generate.apply_handover(v2, "V2")
    b = baseline["imt"]["topology"]["mss_dc"]
    h = v2["imt"]["topology"]["mss_dc"]
    assert b["interference_aware_handover"]["enabled"] is False
    assert h["interference_aware_handover"]["enabled"] is False
    assert b["interference_aware_handover_v2"]["enabled"] is False
    assert h["interference_aware_handover_v2"]["enabled"] is True
    h["interference_aware_handover_v2"]["enabled"] = False
    assert b == h
    assert generate.NUM_SNAPSHOTS == 5000

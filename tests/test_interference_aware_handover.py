"""Tests for snapshot-based Interference-Aware Inter-Satellite Handover."""

import csv
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import numpy.testing as npt

from sharc.antenna.antenna_s1528 import AntennaS1528Taylor
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.parameters.antenna.parameters_antenna_s1528 import (
    ParametersAntennaS1528,
)
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.imt.parameters_imt_mss_dc import ParametersImtMssDc
from sharc.parameters.parameters_antenna_with_diameter import (
    ParametersAntennaWithDiameter,
)
from sharc.results import Results
from sharc.simulation_downlink import SimulationDownlink
from sharc.station_factory import StationFactory
from sharc.station_manager import StationManager
from sharc.support.sharc_geom import CoordinateSystem
from sharc.topology.interference_aware_handover import (
    calculate_eess_off_axis_deg,
    is_main_beam_to_main_beam,
    select_interference_aware_serving_satellites,
)
from sharc.topology.topology_imt_mss_dc import TopologyImtMssDc


DC_LIMIT_DEG = 4.322755


def make_s465(frequency_mhz=2202.0, diameter_m=8.91,
              gain_dbi=45.8):
    """Build the exact S.465 implementation used by campaign EESS systems."""
    return AntennaS465(ParametersAntennaWithDiameter(
        frequency=frequency_mhz,
        diameter=diameter_m,
        antenna_gain=gain_dbi,
    ))


def make_eess(
    *,
    azimuth_deg=0.0,
    elevation_deg=0.0,
    position=(0.0, 0.0, 0.0),
    antenna=None,
):
    """Create one realized EESS station without any random draw."""
    station = StationManager(1)
    station.geom.set_global_coords(
        np.array([position[0]]),
        np.array([position[1]]),
        np.array([position[2]]),
        azim=np.array([azimuth_deg]),
        elev=np.array([elevation_deg]),
    )
    station.antenna = np.array(
        [antenna if antenna is not None else make_s465()], dtype=object)
    return station


def selector_kwargs(candidate_positions, *, active=True, elevations=None,
                    eess_elevation_deg=0.0):
    """Return a one-cell selector fixture with stable candidate IDs."""
    if elevations is None:
        elevations = [80.0, 70.0, 60.0]
    return {
        "primary_satellite_indices": np.array([10]),
        "beam_grid_indices": np.array([0]),
        "active_mask": np.array([active]),
        "candidate_satellite_indices": np.array([10, 11, 12]),
        "candidate_elevations_deg": np.array([elevations]),
        "candidate_satellite_positions": np.asarray(
            candidate_positions, dtype=float),
        "cell_positions": np.array([[0.0, 0.0, 0.0]]),
        "eess_position": np.array([0.0, 0.0, 0.0]),
        "eess_boresight_azimuth_deg": 0.0,
        "eess_boresight_elevation_deg": eess_elevation_deg,
        "dc_mss_off_axis_limit_deg": DC_LIMIT_DEG,
        "eess_phi_min_deg": 1.5,
        "minimum_service_angle_deg": 5.0,
        "eess_system": "EESS_TEST",
    }


def make_synthetic_topology(
    candidate_positions,
    *,
    eess_elevation_deg=0.0,
    candidate_indices=None,
    candidate_elevations=None,
):
    """Create a one-row SERVICE_GRID topology without orbit generation."""
    if candidate_indices is None:
        candidate_indices = np.array([10, 11])
    if candidate_elevations is None:
        candidate_elevations = np.array([[80.0, 70.0]])
    candidate_positions = np.asarray(candidate_positions, dtype=float)
    params = ParametersImtMssDc(num_beams=1)
    params.beam_positioning.type = "SERVICE_GRID"
    params.beam_positioning.service_grid.minimum_service_angle = 5.0
    params.interference_aware_handover.enabled = True

    coordinate_system = CoordinateSystem()
    coordinate_system.set_reference(0.0, 0.0, 0.0)
    topology = TopologyImtMssDc(params, coordinate_system)
    topology.num_base_stations = 1
    topology.beam_grid_idx = np.array([0])
    topology.primary_satellite_idx = np.array([10])
    topology.serving_satellite_idx = np.array([10])
    topology.space_station_x = np.array([candidate_positions[0, 0]])
    topology.space_station_y = np.array([candidate_positions[0, 1]])
    topology.space_station_z = np.array([candidate_positions[0, 2]])
    topology.lat = np.array([1.0])
    topology.lon = np.array([2.0])
    topology.height = np.array([500000.0])
    topology.azimuth = np.array([180.0])
    topology.elevation = np.array([0.0])
    topology.beam_ground_elev_angles = np.array([80.0])
    topology.x = np.array([123.0])
    topology.y = np.array([456.0])
    topology.z = np.array([0.0])
    topology.power_backoff = np.array([7.0])
    topology.power_backoff_affected = np.array([True])
    topology.beam_grid_center_lon = np.array([-54.0])
    topology.beam_grid_center_lat = np.array([-25.0])
    topology.beam_grid_center_ecef = np.array([[1.0, 2.0, 3.0]])
    topology.beam_grid_center_enu = np.array([[0.0, 0.0, 0.0]])
    topology._service_grid_snapshot = {
        "beam_grid_indices": np.array([0]),
        "primary_satellite_indices": np.array([10]),
        "grid_longitudes": np.array([-54.0]),
        "grid_latitudes": np.array([-25.0]),
        "grid_positions_ecef": np.array([[1.0, 2.0, 3.0]]),
        "grid_positions_enu": np.array([[0.0, 0.0, 0.0]]),
        "candidate_satellite_indices": np.asarray(
            candidate_indices, dtype=int),
        "candidate_elevations_deg": np.asarray(
            candidate_elevations, dtype=float),
        "candidate_positions_enu": candidate_positions,
        "candidate_latitudes": np.arange(
            1.0, len(candidate_indices) + 1.0),
        "candidate_longitudes": np.arange(
            2.0, len(candidate_indices) + 2.0),
        "candidate_altitudes": np.arange(
            500000.0,
            500000.0 + 1000.0 * len(candidate_indices),
            1000.0,
        ),
    }
    return topology, make_eess(elevation_deg=eess_elevation_deg)


class TestInterferenceAwareHandover(unittest.TestCase):
    """Required tests A-M from the handover specification."""

    def test_configuration_defaults_and_nested_loading(self):
        params = ParametersImtMssDc()
        config = params.interference_aware_handover
        self.assertFalse(config.enabled)
        self.assertEqual(config.dc_mss_off_axis_limit_deg, DC_LIMIT_DEG)
        self.assertEqual(config.eess_boundary, "S465_MAX_GAIN_REGION")
        self.assertEqual(config.unresolved_policy, "KEEP_PRIMARY_AND_FLAG")
        self.assertFalse(config.record_event_details)

        params.load_subparameters("imt.topology.mss_dc", {
            "interference_aware_handover": {
                "enabled": True,
                "dc_mss_off_axis_limit_deg": 4.0,
                "eess_boundary": "s465_max_gain_region",
                "unresolved_policy": "keep_primary_and_flag",
                "record_event_details": True,
            },
        })
        config.validate("imt.topology.mss_dc.interference_aware_handover")
        self.assertTrue(config.enabled)
        self.assertEqual(config.dc_mss_off_axis_limit_deg, 4.0)
        self.assertEqual(config.eess_boundary, "S465_MAX_GAIN_REGION")
        self.assertEqual(config.unresolved_policy, "KEEP_PRIMARY_AND_FLAG")
        self.assertTrue(config.record_event_details)

    def test_enabled_configuration_requires_system_3_taylor(self):
        simulation = SimulationDownlink.__new__(SimulationDownlink)
        simulation.parameters = SimpleNamespace(
            imt=SimpleNamespace(
                topology=SimpleNamespace(
                    type="MSS_DC",
                    mss_dc=SimpleNamespace(
                        beam_positioning=SimpleNamespace(type="SERVICE_GRID"),
                        interference_aware_handover=SimpleNamespace(
                            enabled=True,
                        ),
                    ),
                ),
                bs=SimpleNamespace(
                    antenna=SimpleNamespace(pattern="OMNI"),
                ),
                interfered_with=False,
            ),
            general=SimpleNamespace(system="SINGLE_EARTH_STATION"),
            single_earth_station=SimpleNamespace(
                antenna=SimpleNamespace(pattern="ITU-R S.465"),
                system_label="EESS_B",
            ),
        )

        with self.assertRaisesRegex(ValueError, "System 3"):
            simulation._validate_interference_aware_handover_configuration()

        simulation.parameters.imt.bs.antenna.pattern = \
            "ITU-R-S.1528-Taylor"
        simulation.parameters.single_earth_station.system_label = ""
        with self.assertRaisesRegex(ValueError, "system_label"):
            simulation._validate_interference_aware_handover_configuration()

    def test_a_handover_disabled_preserves_original_assignment(self):
        topology, eess = make_synthetic_topology([
            [100.0, 0.0, 0.0],
            [0.0, 100.0, 0.0],
        ])
        topology.orbit_params.interference_aware_handover.enabled = False
        before = {
            name: deepcopy(getattr(topology, name))
            for name in [
                "beam_grid_idx",
                "serving_satellite_idx",
                "space_station_x",
                "space_station_y",
                "space_station_z",
                "azimuth",
                "elevation",
                "power_backoff",
            ]
        }

        result = topology.apply_interference_aware_handover(
            eess, np.array([True]), "EESS_B")

        self.assertIsNone(result)
        for name, expected in before.items():
            npt.assert_array_equal(getattr(topology, name), expected)

    def test_b_safe_primary_is_unchanged(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [0.0, 100.0, 0.0],
                [100.0, 0.0, 0.0],
                [0.0, -100.0, 0.0],
            ]))
        npt.assert_array_equal(outcome.serving_satellite_indices, [10])
        self.assertEqual(outcome.metrics["handover_trigger_count"], 0)

    def test_c_primary_main_main_second_candidate_safe(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ]))
        npt.assert_array_equal(outcome.serving_satellite_indices, [11])
        self.assertEqual(outcome.metrics["successful_handover_count"], 1)
        self.assertEqual(outcome.metrics["reassigned_fraction"], 1.0)
        self.assertEqual(outcome.metrics["unresolved_trigger_fraction"], 0.0)
        self.assertEqual(outcome.events[0].delta_elevation_deg, 10.0)

    def test_d_first_two_main_main_third_candidate_safe(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [200.0, 0.1, 0.0],
                [0.0, 100.0, 0.0],
            ]))
        npt.assert_array_equal(outcome.serving_satellite_indices, [12])
        self.assertEqual(outcome.events[0].target_satellite_idx, 12)

    def test_e_no_safe_candidate_keeps_primary_and_flags(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [200.0, 0.1, 0.0],
                [300.0, -0.1, 0.0],
            ]))
        npt.assert_array_equal(outcome.serving_satellite_indices, [10])
        npt.assert_array_equal(outcome.unresolved_mask, [True])
        self.assertEqual(
            outcome.events[0].outcome, "UNRESOLVED_KEEP_PRIMARY")
        self.assertEqual(outcome.events[0].target_satellite_idx, -1)
        self.assertEqual(outcome.metrics["unresolved_count"], 1)
        self.assertEqual(outcome.metrics["unresolved_trigger_fraction"], 1.0)

    def test_f_handover_preserves_same_cell_and_row(self):
        topology, eess = make_synthetic_topology([
            [100.0, 0.0, 0.0],
            [0.0, 100.0, 0.0],
        ])
        active_mask = np.array([True])
        immutable_before = {
            name: getattr(topology, name).copy()
            for name in [
                "beam_grid_idx",
                "beam_grid_center_lon",
                "beam_grid_center_lat",
                "beam_grid_center_ecef",
                "beam_grid_center_enu",
                "x", "y", "z",
                "power_backoff",
                "power_backoff_affected",
            ]
        }

        topology.apply_interference_aware_handover(
            eess, active_mask, "EESS_B")

        self.assertEqual(topology.num_base_stations, 1)
        npt.assert_array_equal(active_mask, [True])
        for name, expected in immutable_before.items():
            npt.assert_array_equal(getattr(topology, name), expected)
        npt.assert_array_equal(topology.serving_satellite_idx, [11])
        npt.assert_array_equal(topology.primary_satellite_idx, [10])
        npt.assert_array_equal(topology.space_station_x, [0.0])
        npt.assert_array_equal(topology.space_station_y, [100.0])
        npt.assert_array_equal(topology.space_station_z, [0.0])
        npt.assert_array_equal(topology.lat, [2.0])
        npt.assert_array_equal(topology.lon, [3.0])
        npt.assert_array_equal(topology.height, [501000.0])
        npt.assert_allclose(topology.azimuth, [-90.0], atol=1e-12)
        npt.assert_allclose(topology.elevation, [0.0], atol=1e-12)
        npt.assert_array_equal(topology.beam_ground_elev_angles, [70.0])

    def test_g_dc_mss_boundary_is_inclusive(self):
        just_inside = np.nextafter(DC_LIMIT_DEG, -np.inf)
        just_outside = np.nextafter(DC_LIMIT_DEG, np.inf)
        self.assertTrue(bool(is_main_beam_to_main_beam(
            just_inside, 0.0, DC_LIMIT_DEG, 1.5)))
        self.assertTrue(bool(is_main_beam_to_main_beam(
            DC_LIMIT_DEG, 0.0, DC_LIMIT_DEG, 1.5)))
        self.assertFalse(bool(is_main_beam_to_main_beam(
            just_outside, 0.0, DC_LIMIT_DEG, 1.5)))

    def test_h_system_b_uses_s465_phi_min(self):
        antenna = make_s465(2202.0, 8.91, 45.8)
        self.assertAlmostEqual(antenna.phi_min, 1.52906601589617)
        inside = np.nextafter(float(antenna.phi_min), -np.inf)
        outside = np.nextafter(float(antenna.phi_min), np.inf)
        self.assertTrue(bool(is_main_beam_to_main_beam(
            0.0, inside, DC_LIMIT_DEG, antenna.phi_min)))
        self.assertFalse(bool(is_main_beam_to_main_beam(
            0.0, antenna.phi_min, DC_LIMIT_DEG, antenna.phi_min)))
        self.assertFalse(bool(is_main_beam_to_main_beam(
            0.0, outside, DC_LIMIT_DEG, antenna.phi_min)))

    def test_i_system_d_uses_s465_phi_min(self):
        antenna = make_s465(2203.0, 4.07, 39.0)
        self.assertAlmostEqual(antenna.phi_min, 2.80946296198664)
        inside = np.nextafter(float(antenna.phi_min), -np.inf)
        outside = np.nextafter(float(antenna.phi_min), np.inf)
        self.assertTrue(bool(is_main_beam_to_main_beam(
            0.0, inside, DC_LIMIT_DEG, antenna.phi_min)))
        self.assertFalse(bool(is_main_beam_to_main_beam(
            0.0, antenna.phi_min, DC_LIMIT_DEG, antenna.phi_min)))
        self.assertFalse(bool(is_main_beam_to_main_beam(
            0.0, outside, DC_LIMIT_DEG, antenna.phi_min)))

    def test_j_s465_gain_is_unchanged_by_handover(self):
        antenna = make_s465()
        angles = np.array([
            0.0,
            np.nextafter(float(antenna.phi_min), -np.inf),
            antenna.phi_min,
            10.0,
            48.0,
            180.0,
        ])
        before = antenna.calculate_gain(off_axis_angle_vec=angles)
        select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ]))
        after = antenna.calculate_gain(off_axis_angle_vec=angles)
        npt.assert_array_equal(after, before)
        self.assertEqual(before[0], antenna.peak_gain)
        self.assertEqual(before[1], antenna.peak_gain)
        self.assertAlmostEqual(
            before[2], 32 - 25 * np.log10(antenna.phi_min))
        self.assertEqual(before[4], -10.0)

    def test_k_s1528_taylor_gain_is_unchanged_by_handover(self):
        antenna = AntennaS1528Taylor(ParametersAntennaS1528(
            frequency=2000.0,
            bandwidth=5.0,
            antenna_gain=34.1,
            slr=20.0,
            n_side_lobes=2,
            l_r=1.6,
            l_t=1.6,
        ))
        angles = np.array([0.0, 1.0, DC_LIMIT_DEG, 10.0])
        theta = np.array([0.0, 15.0, 45.0, 90.0])
        before = antenna.calculate_gain(
            off_axis_angle_vec=angles, theta_vec=theta)
        select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ]))
        after = antenna.calculate_gain(
            off_axis_angle_vec=angles, theta_vec=theta)
        npt.assert_array_equal(after, before)
        npt.assert_allclose(
            before,
            np.array([
                34.1,
                33.766944773420505,
                27.099998677098103,
                11.44855955442683,
            ]),
            rtol=0.0,
            atol=1e-12,
        )

    def test_l_rng_and_load_mask_are_reproducible(self):
        original_global_state = np.random.get_state()
        try:
            np.random.seed(91)
            detector_state = np.random.get_state()
            with (
                patch("numpy.random.default_rng",
                      side_effect=AssertionError("unexpected RNG call")),
                patch("numpy.random.RandomState",
                      side_effect=AssertionError("unexpected RNG call")),
                patch("numpy.random.rand",
                      side_effect=AssertionError("unexpected RNG call")),
                patch("numpy.random.random",
                      side_effect=AssertionError("unexpected RNG call")),
                patch("numpy.random.uniform",
                      side_effect=AssertionError("unexpected RNG call")),
            ):
                select_interference_aware_serving_satellites(
                    **selector_kwargs([
                        [100.0, 0.0, 0.0],
                        [0.0, 100.0, 0.0],
                        [0.0, -100.0, 0.0],
                    ]))
            state_after_detector = np.random.get_state()
            self.assertEqual(detector_state[0], state_after_detector[0])
            npt.assert_array_equal(
                detector_state[1], state_after_detector[1])
            self.assertEqual(
                detector_state[2:], state_after_detector[2:])
        finally:
            np.random.set_state(original_global_state)

        param = ParametersImt()
        param.topology.type = "MSS_DC"
        param.bs.load_probability = 0.4
        param.bs.antenna.pattern = "OMNI"
        param.bs.antenna.gain = 0.0
        num_beams = 5
        topology = SimpleNamespace(
            num_base_stations=num_beams,
            space_station_x=np.arange(num_beams, dtype=float),
            space_station_y=np.zeros(num_beams),
            space_station_z=np.full(num_beams, 500000.0),
            elevation=np.full(num_beams, -90.0),
            azimuth=np.zeros(num_beams),
            power_backoff=np.zeros(num_beams),
            power_backoff_affected=np.zeros(num_beams, dtype=bool),
            beam_ground_elev_angles=np.full(num_beams, 90.0),
        )

        legacy_rng = np.random.RandomState(157)
        legacy_bs = StationFactory.generate_imt_base_stations(
            param, param.bs.antenna.array, topology, legacy_rng)
        legacy_next = legacy_rng.uniform(size=4)

        handover_rng = np.random.RandomState(157)
        active_mask = StationFactory.sample_imt_base_station_active_mask(
            param, topology, handover_rng)
        handover_bs = StationFactory.generate_imt_base_stations(
            param,
            param.bs.antenna.array,
            topology,
            handover_rng,
            active_mask=active_mask,
        )
        handover_next = handover_rng.uniform(size=4)

        npt.assert_array_equal(legacy_bs.active, active_mask)
        npt.assert_array_equal(handover_bs.active, active_mask)
        npt.assert_array_equal(handover_next, legacy_next)

    def test_m_realized_eess_pointing_is_used(self):
        elevation_deg = 30.0
        radius = 100.0
        satellite = np.array([
            radius * np.cos(np.radians(elevation_deg)),
            0.0,
            radius * np.sin(np.radians(elevation_deg)),
        ])
        topology, eess = make_synthetic_topology(
            [satellite],
            eess_elevation_deg=elevation_deg,
            candidate_indices=np.array([10]),
            candidate_elevations=np.array([[80.0]]),
        )
        outcome = topology.apply_interference_aware_handover(
            eess, np.array([True]), "EESS_B")

        self.assertEqual(outcome.metrics["handover_trigger_count"], 1)
        self.assertAlmostEqual(
            outcome.events[0].primary_eess_off_axis_deg, 0.0)
        self.assertAlmostEqual(
            outcome.events[0].primary_dc_off_axis_deg, 0.0)

        # The same geometry with a different realized EESS pointing must
        # produce a different decision. No configured 90-degree assumption is
        # allowed to override the station geometry passed to the mechanism.
        topology_90, eess_90 = make_synthetic_topology(
            [satellite],
            eess_elevation_deg=90.0,
            candidate_indices=np.array([10]),
            candidate_elevations=np.array([[80.0]]),
        )
        outcome_90 = topology_90.apply_interference_aware_handover(
            eess_90, np.array([True]), "EESS_B")
        self.assertEqual(outcome_90.metrics["handover_trigger_count"], 0)

    def test_inactive_main_main_cell_is_not_evaluated(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ], active=False))

        npt.assert_array_equal(outcome.serving_satellite_indices, [10])
        self.assertEqual(outcome.metrics["active_beams_evaluated"], 0)
        self.assertEqual(outcome.metrics["handover_trigger_count"], 0)
        self.assertEqual(outcome.events, ())

    def test_candidate_below_minimum_service_angle_is_skipped(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ], elevations=[80.0, 4.999, 6.0]))

        npt.assert_array_equal(outcome.serving_satellite_indices, [12])
        self.assertEqual(outcome.events[0].target_satellite_idx, 12)

    def test_equal_elevation_candidates_keep_stable_order(self):
        outcome = select_interference_aware_serving_satellites(
            **selector_kwargs([
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, -100.0, 0.0],
            ], elevations=[80.0, 70.0, 70.0]))

        npt.assert_array_equal(outcome.serving_satellite_indices, [11])
        self.assertEqual(outcome.events[0].target_satellite_idx, 11)

    def test_eess_vector_formula_matches_existing_geometry_method(self):
        eess = make_eess(
            azimuth_deg=23.0,
            elevation_deg=37.0,
            position=(10.0, -20.0, 5.0),
        )
        candidates = StationManager(3)
        candidate_positions = np.array([
            [100.0, 20.0, 80.0],
            [-50.0, 70.0, 35.0],
            [10.0, -20.0, 150.0],
        ])
        candidates.geom.set_global_coords(
            candidate_positions[:, 0],
            candidate_positions[:, 1],
            candidate_positions[:, 2],
        )

        expected = eess.geom.get_off_axis_angle(candidates.geom)[0]
        actual = calculate_eess_off_axis_deg(
            np.array([10.0, -20.0, 5.0]),
            eess.geom.pointn_azim_global[0],
            eess.geom.pointn_elev_global[0],
            candidate_positions,
        )

        npt.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)


class TestInterferenceAwareHandoverResults(unittest.TestCase):
    """Structured instrumentation must be usable without per-beam logging."""

    def test_delayed_first_event_write_has_header_and_appends(self):
        event = {
            column: index
            for index, column in enumerate(
                Results.interference_aware_handover_event_columns)
        }
        with TemporaryDirectory() as temporary_directory:
            results = Results()
            results.output_directory = Path(temporary_directory)
            results.write_files(snapshot_number=10)

            results.interference_aware_handover_events.append(event)
            results.write_files(snapshot_number=20)
            results.interference_aware_handover_events.append(event)
            results.write_files(snapshot_number=30)

            path = Path(temporary_directory) / (
                "interference_aware_handover_events.csv")
            with path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)
            self.assertEqual(
                reader.fieldnames,
                Results.interference_aware_handover_event_columns,
            )
            self.assertEqual(len(rows), 2)

    def test_disabled_or_empty_results_do_not_create_handover_files(self):
        with TemporaryDirectory() as temporary_directory:
            results = Results()
            results.output_directory = Path(temporary_directory)
            results.write_files(snapshot_number=1)
            self.assertFalse((Path(temporary_directory) /
                              "interference_aware_handover_events.csv").exists())
            self.assertFalse((Path(temporary_directory) /
                              "interference_aware_handover_snapshot_metrics.csv").exists())

    def test_snapshot_summary_has_header_and_all_metrics(self):
        row = {
            column: index
            for index, column in enumerate(
                Results.interference_aware_handover_snapshot_metrics_columns)
        }
        with TemporaryDirectory() as temporary_directory:
            results = Results()
            results.output_directory = Path(temporary_directory)
            results.interference_aware_handover_snapshot_metrics.append(row)
            results.write_files(snapshot_number=1)

            path = Path(temporary_directory) / (
                "interference_aware_handover_snapshot_metrics.csv")
            with path.open(newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)
            self.assertEqual(
                reader.fieldnames,
                Results.interference_aware_handover_snapshot_metrics_columns,
            )
            self.assertEqual(len(rows), 1)

    def test_finalize_flushes_partial_handover_batch(self):
        with TemporaryDirectory() as temporary_directory:
            simulation = SimulationDownlink.__new__(SimulationDownlink)
            simulation.parameters = SimpleNamespace(
                imt=SimpleNamespace(
                    topology=SimpleNamespace(
                        type="MSS_DC",
                        mss_dc=SimpleNamespace(
                            interference_aware_handover=SimpleNamespace(
                                enabled=True,
                            ),
                        ),
                    ),
                ),
            )
            simulation.results = Results()
            simulation.results.output_directory = Path(temporary_directory)
            simulation.notify_observers = Mock()
            (
                simulation.results
                .interference_aware_handover_snapshot_metrics
                .append({
                    "snapshot_id": 1,
                    "active_beams_evaluated": 1,
                    "primary_main_main_count": 0,
                    "handover_trigger_count": 0,
                    "successful_handover_count": 0,
                    "unresolved_count": 0,
                    "reassigned_fraction": 0.0,
                    "unresolved_trigger_fraction": 0.0,
                })
            )

            simulation.finalize(snapshot_number=1)

            self.assertTrue((Path(temporary_directory) /
                             "interference_aware_handover_snapshot_metrics.csv")
                            .exists())
            simulation.notify_observers.assert_called_once()


if __name__ == "__main__":
    unittest.main()

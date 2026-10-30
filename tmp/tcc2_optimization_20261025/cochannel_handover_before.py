"""Opt-in TCC2 cocanal V2 physics and snapshot audit trail.

Each trial replays the baseline propagation RNG state on the same active rows.
This keeps clutter realizations paired and also recomputes P.619's existing
snapshot-wide atmospheric term. Candidate evaluation never advances the RNG.
"""
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from sharc.antenna.antenna_factory import AntennaFactory
from sharc.interference_aware_handover_v2 import CandidateEvaluation, run_inr_handover
from sharc.parameters.constants import BOLTZMANN_CONSTANT
from sharc.propagation.propagation_path import PropagationPath


def place_users_in_service_cells(simulation):
    """Re-anchor the existing hexagon draws at their actual service cells.

    SERVICE_GRID's legacy sector anchors are zero placeholders. Only the new
    cocanal mode uses this correction; no extra random numbers are consumed.
    """
    from pyproj import Geod
    from sharc.support.geometry import SimulatorGeometry
    s, t = simulation, simulation.topology
    old = s.ue.geom
    angle = np.radians(t.azimuth)
    radius = t.intersite_distance * 2 / 3
    # Undo the macrocell-sector offset, keeping the sampled hexagon offsets.
    east = old.x_global - t.x - radius * np.cos(angle)
    north = old.y_global - t.y - radius * np.sin(angle)
    distance = np.hypot(east, north)
    if np.any(distance > radius * (1 + 1e-10)):
        raise RuntimeError("Unexpected legacy UE sampler; cannot re-anchor safely")
    lon, lat, _ = Geod(ellps="WGS84").fwd(
        t.beam_grid_center_lon, t.beam_grid_center_lat,
        np.degrees(np.arctan2(east, north)), distance)
    cs = s.coordinate_system
    geometry = SimulatorGeometry(s.ue.num_stations, uses_local_coords=True,
                                 global_cs=(cs.ref_lat, cs.ref_long, cs.ref_alt))
    geometry.set_local_coord_sys(lat, lon, np.zeros_like(lat))
    geometry.set_local_coords(x=np.zeros_like(lat), y=np.zeros_like(lat),
                              z=np.full_like(lat, s.parameters.imt.ue.height),
                              azim=old.pointn_azim_global.copy(), elev=old.pointn_elev_global.copy())
    s.ue.geom = geometry
    s.ue.antenna = AntennaFactory.create_n_antennas(
        s.parameters.imt.ue.antenna, geometry.pointn_azim_global,
        geometry.pointn_elev_global, s.ue.num_stations)
    s._tcc2_ue_cell_distance_m = distance
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    s._tcc2_ue_up = np.column_stack(cs.ecef2enu(
        np.cos(lat_r) * np.cos(lon_r), np.cos(lat_r) * np.sin(lon_r),
        np.sin(lat_r), translate=0))


def validate_configuration(params):
    imt, general = params.imt, params.general
    cfg = imt.topology.mss_dc.interference_aware_handover_v2
    if (not general.enable_cochannel or general.enable_adjacent_channel
            or imt.interfered_with or general.system != "SINGLE_EARTH_STATION"
            or imt.topology.mss_dc.beam_positioning.type != "SERVICE_GRID"):
        raise ValueError("COCHANNEL_INR requires SERVICE_GRID downlink into one earth station, cochannel only")
    if imt.ue.k != 1 or imt.ue.k_m != 1:
        raise ValueError("Initial COCHANNEL_INR implementation requires k=k_m=1")
    if imt.ue.distribution_type != "UNIFORM_IN_CELL" or imt.ue.antenna.array.element_pattern != "FIXED":
        raise ValueError("COCHANNEL_INR requires the validated uniform-in-cell, fixed UE element")
    if imt.channel_model != "FSPL" or params.single_earth_station.channel_model != "P619":
        raise ValueError("COCHANNEL_INR currently validates FSPL service links and P619 victim links")
    if imt.bs.antenna.pattern != "ITU-R-S.1528-Taylor":
        raise ValueError("COCHANNEL_INR requires the validated cell-centred Taylor antenna")
    if imt.imt_dl_intra_sinr_calculation_disabled:
        raise ValueError("COCHANNEL_INR requires intra-IMT SINR calculation")
    if cfg.enabled and cfg.max_handovers_per_snapshot > cfg.top_k:
        raise ValueError("max_handovers_per_snapshot cannot exceed top_k")
    if imt.topology.mss_dc.interference_aware_handover.enabled:
        raise ValueError("COCHANNEL_INR cannot combine legacy handover")
    pbo = imt.topology.mss_dc.power_control_zones
    has_pbo = pbo.power_backoff_db != 0 or any(z.power_backoff_db for z in pbo.zones)
    if has_pbo and (cfg.enabled or pbo.mode != "GEOGRAPHIC"):
        raise ValueError("COCHANNEL_INR supports geographic PBO as a separate treatment, not combined with HO")


def digest_arrays(values):
    h = hashlib.sha256()
    for value in values:
        array = np.ascontiguousarray(value)
        h.update(str((array.dtype.str, array.shape)).encode())
        h.update(array.tobytes())
    return h.hexdigest()


def xyz(station):
    return np.column_stack((station.geom.x_global, station.geom.y_global, station.geom.z_global))


class CochannelHandover:
    def __init__(self, simulation):
        self.s = simulation
        self.t = simulation.topology
        self.cfg = simulation.parameters.imt.topology.mss_dc.interference_aware_handover_v2
        self.output = Path(simulation.results.output_directory)
        self.snapshot = simulation._current_snapshot_id
        self.seed = simulation._current_snapshot_seed
        self.active = np.flatnonzero(simulation.bs.active)
        self.noise = 10 * np.log10(BOLTZMANN_CONSTANT * float(simulation.param_system.noise_temperature)
                                 * float(simulation.param_system.bandwidth) * 1e6 * 1e3)
        self.random_state = simulation.propagation_system.random_number_gen.get_state()
        self.forecasts = {}
        self.candidate_rows = []
        self.errors_db = []
        self.initial_mask = None
        self.initial_served = None
        self.metric_cache = None
        self.distances = self.border_distances()

    def write(self, name, rows):
        if not rows:
            return
        path = self.output / f"tcc2_{name}.csv.gz"
        exists = path.exists()
        with gzip.open(path, "at", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            if not exists:
                writer.writeheader()
            writer.writerows(rows)

    def common(self):
        return dict(snapshot_id=self.snapshot, secondary_seed=self.seed)

    def record_standalone_manifest(self):
        """Keep provenance when the standard SHARC CLI is used."""
        import subprocess
        import sys
        import yaml
        s = self.s
        path = self.output / "tcc2_manifest.json"
        cache = getattr(s, "_tcc2_standalone_manifests", {})
        key = str(path)
        if key not in cache:
            if path.exists():  # Do not overwrite a manifest owned by another caller.
                return
            root = Path(__file__).resolve().parents[1]
            source = Path(s.parameters_filename)
            executed = yaml.safe_load(source.read_text(encoding="utf-8"))
            executed["general"].update(num_snapshots=s.parameters.general.num_snapshots,
                                        output_dir=s.parameters.general.output_dir)
            config_path = self.output / "tcc2_executed_config.yaml"
            config_path.write_text(yaml.safe_dump(executed, sort_keys=False), encoding="utf-8")
            def sha(file):
                return hashlib.sha256(file.read_bytes()).hexdigest()
            def git(*args):
                try:
                    return subprocess.check_output(["git", *args], cwd=root, text=True,
                                                   stderr=subprocess.DEVNULL).strip()
                except (OSError, subprocess.CalledProcessError):
                    return "unavailable"
            cache[key] = dict(
                runner="standard_sharc", mode=self.cfg.max_handovers_per_snapshot if self.cfg.enabled else 0,
                snapshots=s.parameters.general.num_snapshots, master_seed=s.parameters.general.seed,
                input=str(source), input_sha256=sha(source), executed_config_sha256=sha(config_path),
                scenario=source.stem,
                code_sha256={str(p.relative_to(root)): sha(p) for p in sorted((root / "sharc").rglob("*.py"))},
                git_commit=git("rev-parse", "HEAD"), git_status=git("status", "--porcelain"),
                python=sys.version, secondary_seeds=[], completed_snapshots=0, complete=False,
                pairing="within_snapshot_before_after; no cross-run pairing check",
                resource_capacity=self.cfg.max_active_beams_per_satellite)
            lookup = root / "sharc/propagation/Dataset/FOZ_2155_200m.csv"
            cache[key]["lookup_sha256"] = sha(lookup) if lookup.is_file() else None
            s._tcc2_standalone_manifests = cache
        manifest = cache[key]
        manifest["secondary_seeds"].append(self.seed)
        manifest["completed_snapshots"] = self.snapshot
        manifest["complete"] = self.snapshot == manifest["snapshots"]
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def border_distances(self):
        import shapely
        from shapely.ops import transform
        from pyproj import Transformer
        from sharc.parameters.imt.parameters_grid import ParametersZone
        from sharc.support.sharc_geom import get_lambert_equal_area_crs
        if not hasattr(self.s, "_tcc2_border"):
            zone = ParametersZone(type="FROM_COUNTRIES")
            zone.from_countries.country_names = ["Paraguay"]
            zone.from_countries.margin_from_border = 0
            zone.validate("tcc2.border")
            project = Transformer.from_crs("EPSG:4326", get_lambert_equal_area_crs(zone._polygon),
                                           always_xy=True).transform
            self.s._tcc2_border = (project, transform(project, zone._polygon).boundary)
        project, boundary = self.s._tcc2_border
        x, y = project(self.t.beam_grid_center_lon, self.t.beam_grid_center_lat)
        return shapely.distance(shapely.points(x, y), boundary) / 1000

    def sync_geometry(self):
        s, t = self.s, self.t
        s.bs.geom.set_global_coords(t.space_station_x, t.space_station_y,
                                   t.space_station_z, elev=t.elevation)
        s.bs.geom.set_local_coords(azim=t.azimuth)
        s.bs.antenna = AntennaFactory.create_n_antennas(
            s.parameters.imt.bs.antenna, s.bs.geom.pointn_azim_global,
            s.bs.geom.pointn_elev_global, s.bs.num_stations)
        # Taylor beams are cell-centred; add_beam metadata does not steer them.
        for row in self.active:
            s.bs.antenna[row].add_beam(t.azimuth[row], 90 - t.elevation[row])
        s.paths_between_imt_and_sys = PropagationPath.create_default(s.system, s.bs)

    def physical(self):
        s = self.s
        if not len(self.active):
            return {}
        rng = s.propagation_system.random_number_gen
        saved = rng.get_state()
        rng.set_state(self.random_state)
        try:
            coupling = s.calculate_coupling_loss_system_imt(s.system, s.bs, True)
        finally:
            rng.set_state(saved)
        mask = s.paths_between_imt_and_sys.mask.copy()
        if self.initial_mask is None:
            self.initial_mask = mask
        elif not np.array_equal(mask, self.initial_mask):
            raise RuntimeError("Handover changed propagation path population; RNG replay would not be paired")
        s.coupling_loss_imt_system = coupling
        self.metric_cache = (
            s.bs.geom.get_off_axis_angle(s.system.geom)[:, 0],
            s.system.geom.get_off_axis_angle(s.bs.geom)[0],
            s.system.geom.get_3d_distance_to(s.bs.geom)[0])
        powers = {}
        for row in self.active:
            users = s.link[row]
            weights = s.calculate_bw_weights(s.ue.bandwidth[users], s.ue.center_freq[users],
                                             s.param_system.bandwidth, s.param_system.frequency)
            received = weights * 10 ** (0.1 * (s.bs.tx_power[row] - coupling[row, 0]))
            powers[int(row)] = float(np.sum(received)) if mask[0, row] else 0.0
        if not all(np.isfinite(v) and v >= 0 for v in powers.values()):
            raise RuntimeError("Nonfinite cocanal contribution")
        return powers

    def metrics(self, row):
        s = self.s
        return dict(
            satellite_id=int(self.t.serving_satellite_idx[row]),
            service_elevation_deg=float(self.t.beam_ground_elev_angles[row]),
            tx_power_dbm=float(s.bs.tx_power[row][0]),
            tx_offaxis_deg=float(self.metric_cache[0][row]),
            rx_offaxis_deg=float(self.metric_cache[1][row]),
            tx_gain_dbi=float(s.imt_system_antenna_gain[0, row]),
            rx_gain_dbi=float(s.system_imt_antenna_gain[0, row]),
            path_loss_db=float(s.imt_system_path_loss[0, row]),
            coupling_loss_db=float(s.coupling_loss_imt_system[row, 0]),
            slant_range_m=float(self.metric_cache[2][row]))

    def evaluate(self, row):
        t = self.t
        state = t._service_grid_snapshot
        cell = t.beam_grid_idx[row]
        original = int(t.serving_satellite_idx[row])
        elevation = float(t.beam_ground_elev_angles[row])
        minimum = t.orbit_params.beam_positioning.service_grid.minimum_service_angle
        capacity = self.cfg.max_active_beams_per_satellite
        result = []
        for column, satellite in enumerate(state["candidate_satellite_indices"]):
            satellite = int(satellite)
            if satellite == original:
                continue
            target_elevation = float(state["candidate_elevations_deg"][cell, column])
            occupancy = int(np.sum(t.serving_satellite_idx[self.active] == satellite))
            delta = state["candidate_positions_enu"][column] - xyz(self.s.ue)[row]
            user_elevation = float(np.degrees(np.arcsin(np.clip(
                np.dot(delta, self.s._tcc2_ue_up[row]) / np.linalg.norm(delta), -1, 1))))
            reason = "EVALUATED"
            if target_elevation < minimum:
                reason = "SERVICE_ELEVATION"
            elif elevation - target_elevation > self.cfg.max_service_elevation_loss_deg:
                reason = "ELEVATION_LOSS"
            elif capacity is not None and occupancy >= capacity:
                reason = "SATELLITE_CAPACITY"
            elif user_elevation < minimum:
                reason = "USER_SERVICE_ELEVATION"
            entry = dict(**self.common(), beam_id=row, cell_id=int(cell), candidate_satellite=satellite,
                         service_elevation_deg=target_elevation, active_beams_at_target=occupancy,
                         user_elevation_deg=user_elevation,
                         candidate_x_m=float(state["candidate_positions_enu"][column, 0]),
                         candidate_y_m=float(state["candidate_positions_enu"][column, 1]),
                         candidate_z_m=float(state["candidate_positions_enu"][column, 2]),
                         tx_power_dbm=float(self.s.bs.tx_power[row][0]),
                         reason=reason, i_link_mw=np.nan, iagg_mw=np.nan,
                         tx_gain_dbi=np.nan, rx_gain_dbi=np.nan, path_loss_db=np.nan,
                         coupling_loss_db=np.nan, tx_offaxis_deg=np.nan, rx_offaxis_deg=np.nan)
            if reason == "EVALUATED":
                try:
                    t.reassign_service_grid_rows([row], [satellite])
                    self.sync_geometry()
                    powers = self.physical()
                    physical = self.metrics(row)
                    self.forecasts[row, satellite] = powers
                    result.append(CandidateEvaluation(satellite, target_elevation, powers[row]))
                    entry.update(i_link_mw=powers[row], iagg_mw=sum(powers.values()))
                    for key in ("tx_gain_dbi", "rx_gain_dbi", "path_loss_db", "coupling_loss_db",
                                "tx_offaxis_deg", "rx_offaxis_deg"):
                        entry[key] = physical[key]
                finally:
                    t.reassign_service_grid_rows([row], [original])
                    self.sync_geometry()
            self.candidate_rows.append(entry)
        return result

    def apply(self, row, decision):
        before = sum(self.current_powers.values())
        forecast = self.forecasts[row, decision.selected_satellite_idx]
        if sum(forecast.values()) >= before:
            return None
        self.t.reassign_service_grid_rows([row], [decision.selected_satellite_idx])
        self.sync_geometry()
        recalculated = self.physical()
        np.testing.assert_allclose(list(recalculated.values()), list(forecast.values()), rtol=1e-11, atol=0)
        error = 10 * np.log10(sum(recalculated.values()) / sum(forecast.values()))
        self.errors_db.append(float(error))
        self.current_powers = recalculated
        self.performance()
        return recalculated

    def performance(self):
        s = self.s
        s.bs_to_ue_phi, s.bs_to_ue_theta = s.bs.geom.get_global_pointing_vector_to(s.ue.geom)
        s.intra_imt_paths = PropagationPath.create_default(s.ue, s.bs)
        s.coupling_loss_imt = s.calculate_intra_imt_coupling_loss(s.ue, s.bs)
        s.calculate_sinr()

    def record_step(self, step, powers):
        s, t = self.s, self.t
        total = sum(powers.values())
        inr = float(10 * np.log10(total) - self.noise) if total else -np.inf
        delta = xyz(s.bs) - xyz(s.ue)
        user_elevations = np.degrees(np.arcsin(np.clip(
            np.einsum("ij,ij->i", delta, s._tcc2_ue_up) / np.linalg.norm(delta, axis=1), -1, 1)))
        minimum = t.orbit_params.beam_positioning.service_grid.minimum_service_angle
        rows = []
        served = np.zeros(s.ue.num_stations, dtype=bool)
        for user in range(s.ue.num_stations):
            beam = user  # configuration explicitly requires k=k_m=1
            active = bool(s.ue.active[user])
            elev = float(user_elevations[user])
            sinr = float(s.ue.sinr[user]) if active else np.nan
            # Availability and SINR outage are distinct, and neither drops users.
            served[user] = active and elev >= minimum and np.isfinite(sinr)
            outage = active and (not served[user] or sinr < s.parameters.imt.downlink.sinr_min)
            rows.append(dict(**self.common(), step=step, user_id=user, beam_id=beam,
                             cell_id=int(t.beam_grid_idx[beam]), satellite_id=int(t.serving_satellite_idx[beam]),
                             active=active, served=bool(served[user]), sinr_outage=bool(outage),
                             service_lost=bool(self.initial_served is not None and self.initial_served[user] and not served[user]),
                             sinr_db=sinr, snr_db=float(s.ue.snr[user]) if active else np.nan,
                             rx_power_dbm=float(s.ue.rx_power[user]) if active else np.nan,
                             interference_dbm=float(s.ue.rx_interference[user]) if active else np.nan,
                             desired_tx_gain_dbi=float(s.imt_bs_antenna_gain[beam, user]) if active else np.nan,
                             desired_rx_gain_dbi=float(s.imt_ue_antenna_gain[beam, user]) if active else np.nan,
                             desired_path_loss_db=float(s.path_loss_imt[beam, user]) if active else np.nan,
                             desired_coupling_loss_db=float(s.coupling_loss_imt[beam, user]) if active else np.nan,
                             service_elevation_deg=elev, ue_x_m=float(s.ue.geom.x_global[user]),
                             distance_to_cell_center_m=float(s._tcc2_ue_cell_distance_m[user]),
                             ue_y_m=float(s.ue.geom.y_global[user]), ue_z_m=float(s.ue.geom.z_global[user]),
                             allocated_bandwidth_mhz=float(s.ue.bandwidth[user]) if active else np.nan,
                             noise_dbm=float(s.ue.thermal_noise[user]) if active else np.nan))
        if self.initial_served is None:
            self.initial_served = served.copy()
        self.write("users", rows)
        beams = []
        # All cell identities, including inactive cells, remain visible.
        for row in range(s.bs.num_stations):
            values = self.metrics(row) if row in powers else dict(
                satellite_id=int(t.serving_satellite_idx[row]),
                service_elevation_deg=float(t.beam_ground_elev_angles[row]),
                tx_power_dbm=np.nan, tx_offaxis_deg=np.nan, rx_offaxis_deg=np.nan,
                tx_gain_dbi=np.nan, rx_gain_dbi=np.nan, path_loss_db=np.nan,
                coupling_loss_db=np.nan, slant_range_m=np.nan)
            beams.append(dict(**self.common(), step=step, beam_id=row, cell_id=int(t.beam_grid_idx[row]),
                              active=bool(s.bs.active[row]), i_link_mw=powers.get(row, 0.0),
                              power_backoff_db=float(t.power_backoff[row]),
                              cell_lat=float(t.beam_grid_center_lat[row]), cell_lon=float(t.beam_grid_center_lon[row]),
                              distance_paraguay_border_km=float(self.distances[row]),
                              satellite_x_m=float(t.space_station_x[row]), satellite_y_m=float(t.space_station_y[row]),
                              satellite_z_m=float(t.space_station_z[row]),
                              boresight_azimuth_deg=float(t.azimuth[row]), boresight_elevation_deg=float(t.elevation[row]),
                              **values))
        self.write("links", beams)
        self.write("steps", [dict(**self.common(), step=step, inr_db=inr, iagg_mw=total,
                                  noise_dbm=float(self.noise), active_users=int(s.ue.active.sum()),
                                  served_users=int(served.sum()), lost_users=int(np.sum(self.initial_served & ~served)),
                                  sinr_outage_users=sum(r["sinr_outage"] for r in rows))])

    def run(self):
        s, t = self.s, self.t
        preserved = digest_arrays([xyz(s.ue), s.ue.active, s.bs.active, t.beam_grid_idx,
                                    t.beam_grid_center_enu, *[s.link[r] for r in self.active]])
        capacity = self.cfg.max_active_beams_per_satellite
        if capacity is not None and len(self.active):
            if np.unique(t.serving_satellite_idx[self.active], return_counts=True)[1].max() > capacity:
                raise ValueError("Initial highest-elevation assignment exceeds the specified satellite capacity")
        pairing = digest_arrays([xyz(s.bs), xyz(s.ue), xyz(s.system), s.bs.active,
                                 s.ue.active, s.ue.indoor, s.ue.bandwidth[s.ue.active], s.ue.center_freq[s.ue.active],
                                 t.beam_grid_idx, t.beam_grid_center_enu, t.primary_satellite_idx,
                                 t._service_grid_snapshot["candidate_positions_enu"],
                                 s.system.geom.pointn_azim_global, s.system.geom.pointn_elev_global,
                                 *[s.bs.tx_power[r] for r in self.active],
                                 *[s.link[r] for r in self.active]])
        self.current_powers = self.physical()
        baseline_powers = dict(self.current_powers)
        performance_hash = digest_arrays([s.ue.sinr[s.ue.active], s.ue.snr[s.ue.active]])
        # Consume exactly one ordinary baseline propagation draw per snapshot.
        if len(self.active):
            s.calculate_coupling_loss_system_imt(s.system, s.bs, True)
        before = 10 * np.log10(sum(baseline_powers.values())) - self.noise if baseline_powers else -np.inf
        self.record_step(0, baseline_powers)
        result = run_inr_handover(
            config=self.cfg, link_powers=baseline_powers, noise_dbm=self.noise,
            cell_ids=t.beam_grid_idx,
            current_satellite=lambda row: int(t.serving_satellite_idx[row]),
            current_elevation=lambda row: float(t.beam_ground_elev_angles[row]),
            evaluate=self.evaluate, apply=self.apply, record_step=self.record_step)
        # Restore final physical arrays after rejected trials as well.
        final = self.physical()
        np.testing.assert_allclose(list(final.values()), list(result["powers"].values()), rtol=1e-11, atol=0)
        total = sum(final.values())
        s.system.rx_interference = np.array([10 * np.log10(total) if total else -np.inf])
        s.system.thermal_noise = np.array([self.noise])
        s.system.inr = s.system.rx_interference - s.system.thermal_noise
        self.write("candidates", self.candidate_rows)
        self.write("events", [dict(**self.common(), **d) for d in result["decisions"]])
        record = dict(**self.common(), realization_sha256=pairing,
                      initial_performance_sha256=performance_hash,
                      baseline_links_sha256=digest_arrays([list(baseline_powers.values())]),
                      inr_before_db=float(before), inr_after_db=float(s.system.inr[0]),
                      initial_top_k=json.dumps(result["initial_top_k"]),
                      examined_beams=result["examined_beams"], attempts=result["attempts"],
                      candidate_satellites_considered=len(self.candidate_rows),
                      evaluated_candidates=result["evaluated_candidates"], accepted_changes=result["accepted_changes"],
                      stop_reason=result["stop_reason"],
                      active_pbo_beams=int(np.count_nonzero(t.power_backoff[self.active])),
                      max_prediction_error_db=max(map(abs, self.errors_db), default=0.0))
        if preserved != digest_arrays([xyz(s.ue), s.ue.active, s.bs.active, t.beam_grid_idx,
                                        t.beam_grid_center_enu, *[s.link[r] for r in self.active]]):
            raise AssertionError("Handover changed users, activity or service-cell identities")
        s.tcc2_last_snapshot = record
        self.write("snapshots", [record])
        self.record_standalone_manifest()

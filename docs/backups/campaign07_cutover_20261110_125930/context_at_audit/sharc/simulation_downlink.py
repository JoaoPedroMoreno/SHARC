# -*- coding: utf-8 -*-
"""
Created on Wed Jan 11 19:06:41 2017

@author: edgar
"""

import numpy as np
import math
import warnings
import hashlib

from sharc.simulation import Simulation
from sharc.parameters.parameters import Parameters
from sharc.station_factory import StationFactory
from sharc.station_manager import StationManager
from sharc.antenna.antenna_factory import AntennaFactory
from sharc.support.enumerations import StationType
from sharc.parameters.constants import BOLTZMANN_CONSTANT, SPEED_OF_LIGHT
from sharc.propagation.propagation_path import PropagationPath
from sharc.interference_link_diagnostics import select_diagnostic_links
from sharc.interference_aware_handover_v2 import (
    CandidateEvaluation, choose_minimum_interference_target,
    replace_link_power_linear, select_triggered_links,
    should_enter_risk_gate,
)

warn = warnings.warn


class SimulationDownlink(Simulation):
    """
    Implements the flowchart of simulation downlink method
    """
    _PBO_RANDOM_STREAM_ID = 0x50424F

    def __init__(self, parameters: Parameters, parameter_file: str):
        """Initialize the SimulationDownlink with parameters and parameter file.

        Parameters
        ----------
        parameters : Parameters
            Simulation parameters object.
        parameter_file : str
            Path to the parameter file.
        """
        super().__init__(parameters, parameter_file)
        self.interference_aware_handover_outcome = None
        self._validate_interference_aware_handover_configuration()
        self._validate_interference_link_diagnostics_configuration()
        self._validate_interference_aware_handover_v2_configuration()
        self._validate_operational_risk_diagnostics_configuration()

    def _validate_operational_risk_diagnostics_configuration(self):
        if self.parameters.imt.topology.type != "MSS_DC":
            return
        cfg = self.parameters.imt.topology.mss_dc.operational_risk_diagnostics
        if not cfg.enabled:
            return
        if self.parameters.imt.topology.mss_dc.beam_positioning.type != "SERVICE_GRID":
            raise ValueError("Operational-risk diagnostics require SERVICE_GRID")
        if self.parameters.general.system != "SINGLE_EARTH_STATION":
            raise ValueError(
                "Operational-risk diagnostics require one earth station")
        if self.parameters.imt.interfered_with:
            raise ValueError(
                "Operational-risk diagnostics require DC-MSS as interferer")
        if (not self.parameters.general.enable_adjacent_channel
                or self.parameters.general.enable_cochannel):
            raise ValueError(
                "Operational-risk diagnostics currently require adjacent-only operation")
        if self.parameters.imt.adjacent_ch_emissions != "SPECTRAL_MASK":
            raise ValueError(
                "Operational-risk diagnostics require SPECTRAL_MASK")
        if self.parameters.single_earth_station.adjacent_ch_reception != "OFF":
            raise ValueError(
                "Operational-risk diagnostics require EESS ACS OFF")
        if self.parameters.imt.ue.k != 1:
            raise ValueError("Operational-risk diagnostics require imt.ue.k = 1")

    def _validate_interference_aware_handover_v2_configuration(self):
        if self.parameters.imt.topology.type != "MSS_DC":
            return
        cfg = self.parameters.imt.topology.mss_dc.interference_aware_handover_v2
        if cfg.evaluation_mode == "COCHANNEL_INR":
            from sharc.cochannel_handover import validate_configuration
            validate_configuration(self.parameters)
            return
        if not cfg.enabled:
            return
        if self.parameters.imt.topology.mss_dc.beam_positioning.type != "SERVICE_GRID":
            raise ValueError("Handover V2 requires SERVICE_GRID")
        if self.parameters.imt.interfered_with or self.parameters.general.enable_cochannel:
            raise ValueError("Handover V2 supports adjacent DC-MSS -> EESS only")
        if not self.parameters.general.enable_adjacent_channel:
            raise ValueError("Handover V2 requires adjacent-channel calculation")
        if self.parameters.imt.adjacent_ch_emissions != "SPECTRAL_MASK":
            raise ValueError("Handover V2 requires the configured spectral mask")
        if self.parameters.single_earth_station.adjacent_ch_reception != "OFF":
            raise ValueError("Handover V2 currently requires EESS ACS OFF")
        if self.parameters.imt.ue.k != 1:
            raise ValueError("Handover V2 requires imt.ue.k = 1")

    def _handover_v2_enabled(self):
        config = getattr(
            self.parameters.imt.topology.mss_dc,
            "interference_aware_handover_v2", None)
        return (self.parameters.imt.topology.type == "MSS_DC" and
                config is not None and config.enabled)

    def _operational_risk_diagnostics_enabled(self):
        config = getattr(
            self.parameters.imt.topology.mss_dc,
            "operational_risk_diagnostics", None)
        return (
            self.parameters.imt.topology.type == "MSS_DC"
            and config is not None and config.enabled
        )

    def _validate_interference_aware_handover_configuration(self) -> None:
        """Fail fast for unsupported handover/system combinations."""
        if self.parameters.imt.topology.type != "MSS_DC":
            return
        config = (
            self.parameters.imt.topology.mss_dc
            .interference_aware_handover
        )
        if not config.enabled:
            return
        if (
            self.parameters.imt.topology.mss_dc.beam_positioning.type
            != "SERVICE_GRID"
        ):
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover requires "
                "SERVICE_GRID")
        if self.parameters.general.system != "SINGLE_EARTH_STATION":
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover requires "
                "general.system = SINGLE_EARTH_STATION")
        if self.parameters.single_earth_station.antenna.pattern != "ITU-R S.465":
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover requires "
                "the implemented ITU-R S.465 EESS antenna")
        if self.parameters.imt.bs.antenna.pattern != "ITU-R-S.1528-Taylor":
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover currently "
                "supports DC-MSS System 3 with ITU-R-S.1528-Taylor")
        if self.parameters.single_earth_station.system_label not in {
            "EESS_B", "EESS_D",
        }:
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover requires "
                "single_earth_station.system_label = EESS_B or EESS_D")
        if self.parameters.imt.interfered_with:
            raise ValueError(
                "Interference-Aware Inter-Satellite Handover currently "
                "supports DC-MSS interference into EESS")

    def _validate_interference_link_diagnostics_configuration(self) -> None:
        """Restrict diagnostics to the physically audited campaign path."""
        if self.parameters.imt.topology.type != "MSS_DC":
            return
        config = (
            self.parameters.imt.topology.mss_dc
            .interference_link_diagnostics
        )
        if not config.enabled:
            return
        if (
            self.parameters.imt.topology.mss_dc.beam_positioning.type
            != "SERVICE_GRID"
        ):
            raise ValueError(
                "Interference link diagnostics require SERVICE_GRID")
        if self.parameters.general.system != "SINGLE_EARTH_STATION":
            raise ValueError(
                "Interference link diagnostics require one earth station")
        if self.parameters.imt.interfered_with:
            raise ValueError(
                "Interference link diagnostics require DC-MSS as interferer")
        if self.parameters.general.enable_cochannel:
            raise ValueError(
                "Initial interference link diagnostics support adjacent-only "
                "DC-MSS -> EESS scenarios")
        if not self.parameters.general.enable_adjacent_channel:
            raise ValueError(
                "Interference link diagnostics require adjacent channel")
        if self.parameters.imt.adjacent_ch_emissions != "SPECTRAL_MASK":
            raise ValueError(
                "Interference link diagnostics require SPECTRAL_MASK")
        if self.parameters.single_earth_station.adjacent_ch_reception != "OFF":
            raise ValueError(
                "Initial interference link diagnostics require EESS adjacent "
                "channel reception OFF")
        if self.parameters.imt.ue.k != 1:
            raise ValueError(
                "Initial interference link diagnostics require imt.ue.k = 1")

    def _interference_link_diagnostics_enabled(self) -> bool:
        return (
            self.parameters.imt.topology.type == "MSS_DC"
            and self.parameters.imt.topology.mss_dc
            .interference_link_diagnostics.enabled
        )

    def snapshot(self, *args, **kwargs):
        """Run a simulation snapshot for the downlink scenario.

        Parameters
        ----------
        *args : tuple
            Positional arguments (unused).
        **kwargs : dict
            Keyword arguments, must include 'write_to_file', 'snapshot_number', and 'seed'.
        """
        write_to_file = kwargs["write_to_file"]
        snapshot_number = kwargs["snapshot_number"]
        seed = kwargs["seed"]
        self._current_snapshot_id = int(snapshot_number)
        self._current_snapshot_seed = int(seed)

        if self._interference_link_diagnostics_enabled():
            self._diagnostic_snapshot_id = int(snapshot_number)
            self._diagnostic_secondary_seed = int(seed)
        if self._handover_v2_enabled():
            self._v2_snapshot_id = int(snapshot_number)
            self._v2_secondary_seed = int(seed)
        if self._operational_risk_diagnostics_enabled():
            self._operational_risk_snapshot_id = int(snapshot_number)
            self._operational_risk_secondary_seed = int(seed)

        random_number_gen = np.random.RandomState(seed)

        # In case of hotspots, base stations coordinates have to be calculated
        # on every snapshot. Anyway, let topology decide whether to calculate
        # or not
        num_stations_before = self.topology.num_base_stations

        self.topology.calculate_coordinates(random_number_gen)

        if num_stations_before != self.topology.num_base_stations:
            self.initialize_topology_dependant_variables()

        handover_enabled = (
            self.parameters.imt.topology.type == "MSS_DC"
            and self.parameters.imt.topology.mss_dc
            .interference_aware_handover.enabled
        )
        self.interference_aware_handover_outcome = None

        if handover_enabled:
            # Preserve the legacy RNG sequence: this is exactly the load draw
            # formerly made by generate_imt_base_stations, before the EESS
            # azimuth/elevation draws.
            active_mask = (
                StationFactory.sample_imt_base_station_active_mask(
                    self.parameters.imt,
                    self.topology,
                    random_number_gen,
                )
            )
            self.system = StationFactory.generate_system(
                self.parameters, self.topology, random_number_gen,
                coordinate_system=self.coordinate_system
            )
            self.interference_aware_handover_outcome = (
                self.topology.apply_interference_aware_handover(
                    self.system,
                    active_mask,
                    self.parameters.single_earth_station.system_label,
                )
            )
            self.bs = StationFactory.generate_imt_base_stations(
                self.parameters.imt,
                self.parameters.imt.bs.antenna.array,
                self.topology,
                random_number_gen,
                active_mask=active_mask,
            )
            self.apply_mss_dc_power_backoff(seed)
        else:
            # Keep the original path and call order unchanged when disabled.
            self.bs = StationFactory.generate_imt_base_stations(
                self.parameters.imt,
                # TODO: remove this:
                self.parameters.imt.bs.antenna.array,
                self.topology, random_number_gen,
            )
            self.apply_mss_dc_power_backoff(seed)
            self.system = StationFactory.generate_system(
                self.parameters, self.topology, random_number_gen,
                coordinate_system=self.coordinate_system
            )

        # Create IMT user equipments
        self.ue = StationFactory.generate_imt_ue(
            self.parameters.imt,
            # TODO: remove this:
            self.parameters.imt.ue.antenna.array,
            self.topology, random_number_gen,
        )

        if (self.parameters.imt.topology.type == "MSS_DC"
                and self.parameters.imt.topology.mss_dc.interference_aware_handover_v2.evaluation_mode == "COCHANNEL_INR"):
            from sharc.cochannel_handover import place_users_in_service_cells
            place_users_in_service_cells(self)

        if self.parameters.imt.interfered_with:
            self.paths_between_imt_and_sys = PropagationPath.create_default(
                self.system,
                self.ue,
            )
        else:
            self.paths_between_imt_and_sys = PropagationPath.create_default(
                self.system,
                self.bs,
            )

        self.intra_imt_paths = PropagationPath.create_default(
            self.ue,
            self.bs,
        )

        # self.plot_scenario()

        self.connect_ue_to_bs()
        self.select_ue(random_number_gen)
        self.scheduler()
        self.power_control()

        if self.parameters.imt.interfered_with:
            # Execute this piece of code if the other system generates
            # interference into IMT

            # Calculate coupling loss after beams are created
            self.coupling_loss_imt = self.calculate_intra_imt_coupling_loss(
                self.ue, self.bs,
            )
            self.calculate_sinr()
            self.calculate_sinr_ext()
        else:
            # Execute this piece of code if IMT generates interference into
            # the other system

            # If the intra SINR calculation is disabled, we do not calculate
            # the SINR for the IMT UEs, but we still calculate the external
            # interference.
            if not self.parameters.imt.imt_dl_intra_sinr_calculation_disabled:
                self.coupling_loss_imt = self.calculate_intra_imt_coupling_loss(
                    self.ue, self.bs,
                )
                self.calculate_sinr()
            self.calculate_external_interference()

        self.collect_results(write_to_file, snapshot_number)

    @staticmethod
    def select_active_beams_for_pbo(
        active_beams: np.ndarray,
        affected_fraction: float,
        snapshot_seed: int,
    ) -> tuple[np.ndarray, float]:
        """Select a deterministic nested fraction of active beams for PBO."""
        if affected_fraction < 0.0 or affected_fraction > 1.0:
            raise ValueError("affected_fraction needs to be in [0, 1]")

        active_beams = np.asarray(active_beams, dtype=bool)
        active_ids = np.flatnonzero(active_beams)
        affected_mask = np.zeros_like(active_beams, dtype=bool)
        if active_ids.size == 0:
            return affected_mask, 0.0

        seed_sequence = np.random.SeedSequence([
            int(snapshot_seed),
            SimulationDownlink._PBO_RANDOM_STREAM_ID,
        ])
        pbo_random_number_gen = np.random.default_rng(seed_sequence)
        ranked_active_ids = pbo_random_number_gen.permutation(active_ids)
        num_affected = int(np.floor(
            affected_fraction * active_ids.size + 0.5))
        affected_mask[ranked_active_ids[:num_affected]] = True

        realized_fraction = num_affected / active_ids.size
        return affected_mask, realized_fraction

    def apply_mss_dc_power_backoff(self, snapshot_seed: int) -> None:
        """Apply configured MSS-DC PBO after the active-beam draw."""
        if self.parameters.imt.topology.type != "MSS_DC":
            return

        power_control = self.parameters.imt.topology.mss_dc.power_control_zones
        active_beams = np.asarray(self.bs.active, dtype=bool)
        num_active = int(np.count_nonzero(active_beams))

        if power_control.mode == "ACTIVE_FRACTION":
            selected_mask, selected_fraction = (
                self.select_active_beams_for_pbo(
                    active_beams,
                    power_control.affected_fraction,
                    snapshot_seed,
                )
            )
            applied_mask = (
                selected_mask & (power_control.power_backoff_db > 0.0)
            )
            effective_backoff = np.where(
                applied_mask,
                power_control.power_backoff_db,
                0.0,
            )

            self.bs.tx_power = (
                self.parameters.imt.bs.conducted_power
                * np.ones(self.bs.num_stations)
                - effective_backoff
            )
            self.topology.power_backoff = effective_backoff
            self.topology.power_backoff_affected = applied_mask
            self.topology.requested_affected_fraction = (
                power_control.affected_fraction)
            self.topology.realized_affected_fraction = (
                selected_fraction
                if power_control.power_backoff_db > 0.0 else 0.0
            )
            return

        geographic_mask = np.asarray(
            self.topology.power_backoff_affected,
            dtype=bool,
        )
        self.topology.requested_affected_fraction = np.nan
        self.topology.realized_affected_fraction = (
            np.count_nonzero(geographic_mask & active_beams) / num_active
            if num_active else 0.0
        )

    def finalize(self, *args, **kwargs):
        """
        Finalize the simulation and notify observers with the results.

        Parameters
        ----------
        *args : tuple
            Positional arguments (unused).
        **kwargs : dict
            Keyword arguments (unused).
        """
        handover_enabled = (
            self.parameters.imt.topology.type == "MSS_DC"
            and self.parameters.imt.topology.mss_dc
            .interference_aware_handover.enabled
        )
        if (handover_enabled or self._handover_v2_enabled()
                or self._interference_link_diagnostics_enabled()):
            # Model writes every ten snapshots. Flush a partial final batch so
            # structured handover/diagnostic rows are not lost in short runs.
            self.results.write_files(kwargs["snapshot_number"])
        self.notify_observers(source=__name__, results=self.results)

    def power_control(self):
        """
        Apply downlink power control algorithm to distribute power among selected UEs.
        """
        # Currently, the maximum transmit power of the base station is equaly
        # divided among the selected UEs
        total_power = self.bs.tx_power \
            + self.bs_power_gain
        tx_power = total_power - 10 * math.log10(self.parameters.imt.ue.k)
        # calculate transmit powers to have a structure such as
        # {bs_1: [pwr_1, pwr_2,...], ...}, where bs_1 is the base station id,
        # pwr_1 is the transmit power from bs_1 to ue_1, pwr_2 is the transmit
        # power from bs_1 to ue_2, etc
        # NOTE: Re-writing bs.tx_power here as dict
        bs_active = np.where(self.bs.active)[0]
        self.bs.tx_power = dict(
            [(bs, tx_power[bs] * np.ones(self.parameters.imt.ue.k)) for bs in bs_active])

        # Update the spectral mask
        if self.adjacent_channel:
            # FIXME: assumes all BS have same total power
            max_tx_power = self.parameters.imt.bs.conducted_power + self.bs_power_gain
            self.bs.spectral_mask.set_mask(p_tx=max_tx_power)

    def calculate_sinr(self):
        """
        Calculates the downlink SINR for each UE.
        """
        bs_active = np.where(self.bs.active)[0]
        ue_k = self.parameters.imt.ue.k

        # paths that actually exist and should make signal or interf
        ue_to_bs_path_mask = self.intra_imt_paths.mask
        # since bs tx_power is dict, we get it to array for easier use
        bs_tx_power_per_beam_array = np.array([
            self.bs.tx_power[k] if k in self.bs.tx_power
            else np.full(ue_k, -np.inf)
            for k in range(self.bs.num_stations)
        ])
        for bs in bs_active:
            ue = self.link[bs]
            self.ue.rx_power[ue] = self.bs.tx_power[bs] - \
                self.coupling_loss_imt[bs, ue]
            for ui in ue:
                # base stations that have links/paths to ue
                bs_interf = np.where(ue_to_bs_path_mask[ui])[0]
                # remove serving bs to get interferrers
                bs_interf = bs_interf[bs_interf != bs]
                # get each base station power per beam
                interf_tx_pow = bs_tx_power_per_beam_array[bs_interf]
                # get UE RB index
                ue_rb_beam_idx = int(self.bs_to_ue_beam_rbs[ui])
                if ue_rb_beam_idx >= interf_tx_pow.shape[1]:
                    ue_rb_beam_idx = 0
                # only overlapping RB interf power is considered
                interf_tx_pow = interf_tx_pow[:, ue_rb_beam_idx]
                # coupling loss already considers only the overlapping beam
                # from BS
                interference = interf_tx_pow - \
                    self.coupling_loss_imt[bs_interf, ui]

                # sum 1e-50 so that rx_interference >= -500
                self.ue.rx_interference[ui] = 10 * np.log10(
                    np.sum(np.power(10, 0.1 * interference)) + 1e-50
                )

        # Thermal noise in dBm
        self.ue.thermal_noise = \
            10 * math.log10(BOLTZMANN_CONSTANT * self.parameters.imt.noise_temperature * 1e3) + \
            10 * np.log10(self.ue.bandwidth * 1e6) + \
            self.ue.noise_figure

        self.ue.total_interference = \
            10 * np.log10(
                np.power(10, 0.1 * self.ue.rx_interference) +
                np.power(10, 0.1 * self.ue.thermal_noise),
            )

        self.ue.sinr = self.ue.rx_power - self.ue.total_interference
        self.ue.snr = self.ue.rx_power - self.ue.thermal_noise

    def calculate_sinr_ext(self):
        """
        Calculates the downlink SINR and INR for each UE taking into account the
        interference that is generated by the other system into IMT system.
        """
        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_emissions != "OFF"
        ):
            self.coupling_loss_imt_system = self.calculate_coupling_loss_system_imt(
                self.system,
                self.ue,
                is_co_channel=True,
            )
        if self.adjacent_channel:
            self.coupling_loss_imt_system_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system,
                    self.ue,
                    is_co_channel=False,
                )

        # applying a bandwidth scaling factor since UE transmits on a portion
        # of the satellite's bandwidth
        ue_interferer_paths = self.paths_between_imt_and_sys.mask.T

        # All UEs are active on an active BS
        bs_active = np.where(self.bs.active)[0]
        for bs in bs_active:
            for ue in self.link[bs]:
                # NOTE: ue is a scalar
                system_interfering = np.where(ue_interferer_paths[ue])[0]

                # Get the weight factor for the system overlaping bandwidth in each
                # UE band.
                weights = self.calculate_bw_weights(
                    self.ue.bandwidth[ue],
                    self.ue.center_freq[ue],
                    float(self.param_system.bandwidth),
                    float(self.param_system.frequency),
                )

                in_band_interf_power = np.array(-500.)
                if self.co_channel:
                    # Inteferer transmit power in dBm over the overlapping band
                    # (MHz) with UEs.
                    if self.overlapping_bandwidth > 0:
                        with warnings.catch_warnings():
                            warnings.filterwarnings(
                                "ignore",
                                category=RuntimeWarning,
                                message="divide by zero encountered in log10",
                            )
                            in_band_interf_power = \
                                self.system.tx_power_density[system_interfering] + 10 * np.log10(
                                    self.ue.bandwidth[ue] * 1e6
                                ) + 10 * np.log10(weights) - \
                                self.coupling_loss_imt_system[ue, :][system_interfering]

                oob_power = np.resize(-500., 1)
                if self.adjacent_channel:
                    # emissions outside of tx bandwidth and inside of rx bw
                    # due to oob emissions on tx side
                    tx_oob = np.ones_like(system_interfering) * -500.

                    # emissions outside of rx bw and inside of tx bw
                    # due to non ideal filtering on rx side
                    # will be the same for all UE's, only considering
                    rx_oob = np.ones_like(system_interfering) * -500.

                    # TODO: M.2101 states that:
                    # "The ACIR value should be calculated based on per UE allocated number of resource blocks"

                    # should we actually implement that for ACS since the receiving
                    # filter is fixed?

                    # or maybe ignore ACS altogether (ACS = inf)? If we consider only allocated RB, it makes
                    # no sense to use ACS.
                    # At the same time, ignoring ACS doesn't seem correct since the interference
                    # could DECREASE when it would make sense for it to increase.
                    # e.g. adjacent systems -> slightly co-channel with ACS = inf
                    # should interfer ^        less than this ^

                    if self.parameters.imt.adjacent_ch_reception == "ACS":
                        if self.overlapping_bandwidth:
                            if getattr(self, "_acs_warned"):
                                warn(
                                    "You're trying to use ACS on a partially overlapping band "
                                    "with UEs.\n\tVerify the code implements the behavior you expect!!"
                                )
                                self._acs_warned = True
                        non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                        acs_dB = self.parameters.imt.ue.adjacent_ch_selectivity

                        # NOTE: only the power not overlapping is attenuated by ACS
                        # tx_pow_adj_lin = PSD * non_overlap_imt_bw
                        # rx_oob = tx_pow_adj_lin / acs
                        rx_oob[::] = self.system.tx_power_density[system_interfering] + \
                            10 * np.log10(non_overlap_sys_bw * 1e6) - acs_dB
                    elif self.parameters.imt.adjacent_ch_reception == "OFF":
                        pass
                    else:
                        raise ValueError(
                            f"No implementation for parameters.imt.adjacent_ch_reception == {
                                self.parameters.imt.adjacent_ch_reception}")

                    # for tx oob we accept ACLR and spectral mask
                    if self.param_system.adjacent_ch_emissions == "SPECTRAL_MASK":
                        ue_bws = self.ue.bandwidth[ue]
                        center_freqs = self.ue.center_freq[ue]

                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore",
                                                    category=RuntimeWarning,
                                                    message="divide by zero encountered in log10")
                            tx_oob[::] = self.system.spectral_mask.power_calc(
                                center_freqs,
                                ue_bws
                            ) - 30
                    elif self.param_system.adjacent_ch_emissions == "ACLR":
                        # consider ACLR only over non co-channel RBs
                        # This should diminish some of the ACLR interference
                        # in a way that make sense
                        non_overlap_imt_bw = self.ue.bandwidth[ue] * (1. - weights)
                        # NOTE: approximated equal to IMT bw
                        measurement_bw = self.param_system.bandwidth
                        aclr_dB = self.param_system.adjacent_ch_leak_ratio

                        if self.parameters.imt.bandwidth - self.overlapping_bandwidth > measurement_bw:
                            # NOTE: ACLR defines total leaked power over a fixed measurement bandwidth.
                            # If the victim bandwidth is wider, you’re assuming the same leakage
                            # profile extends beyond the ACLR-defined region, which may overestimate interference
                            # FIXME: if the victim bw fully contains tx bw, then
                            # EACH region should be <= measurement_bw
                            warn(
                                "Using System ACLR into IMT, but ACLR measurement bw is "
                                f"{measurement_bw} while the IMT bw is bigger ({self.parameters.imt.bandwidth}).\n"
                                "Are you sure you intend to apply the same ACLR to the entire IMT bw?"
                            )

                        # tx_oob_in_measurement = (tx_pow_lin / aclr)
                        # => approx. PSD = (tx_pow_lin / aclr) / measurement_bw
                        # approximated received tx_oob = PSD * non_overlap_imt_bw
                        tx_oob[::] = self.system.tx_power_density[system_interfering] + 60 - \
                            aclr_dB + 10 * np.log10(
                                non_overlap_imt_bw)
                    elif self.param_system.adjacent_ch_emissions == "OFF":
                        pass
                    else:
                        raise ValueError(
                            f"No implementation for param_system.adjacent_ch_emissions == {
                                self.param_system.adjacent_ch_emissions}")

                    if self.param_system.adjacent_ch_emissions != "OFF":
                        tx_oob = tx_oob - self.coupling_loss_imt_system[ue, system_interfering]

                    rx_oob = rx_oob - self.coupling_loss_imt_system_adjacent[ue, system_interfering]

                    # Out of band power
                    # sum linearly power leaked into band and power received in the
                    # adjacent band
                    oob_power = 10 * np.log10(
                        10 ** (0.1 * tx_oob) + 10 ** (0.1 * rx_oob)
                    )
                # Total external interference into the UE in dBm
                ue_ext_int = 10 * np.log10(
                    np.power(10, 0.1 * in_band_interf_power) +
                    np.power(10, 0.1 * oob_power))

                # Sum all the interferers for each UE
                self.ue.ext_interference[ue] = 10 * \
                    np.log10(np.sum(np.power(10, 0.1 * ue_ext_int), axis=0)) + 30

                self.ue.sinr_ext[ue] = \
                    self.ue.rx_power[ue] - (10 * np.log10(np.power(10, 0.1 * self.ue.total_interference[ue]) +
                                                          np.power(10, 0.1 * (self.ue.ext_interference[ue]))))

                # Calculate INR in dB
                self.ue.thermal_noise[ue] = \
                    10 * np.log10(BOLTZMANN_CONSTANT * self.parameters.imt.noise_temperature * 1e3) + \
                    10 * np.log10(self.ue.bandwidth[ue] * 1e6) + self.parameters.imt.ue.noise_figure

                self.ue.inr[ue] = self.ue.ext_interference[ue] - \
                    self.ue.thermal_noise[ue]

            # Calculate PFD at the UE
            self.calculate_system_to_imt_pfd(self.ue)

    def _evaluate_v2_candidate(self, beam_row, satellite_idx, tx_oob_dbm):
        """Evaluate one eligible satellite with the normal SHARC link model."""
        state = self.topology._service_grid_snapshot
        candidates = np.asarray(state["candidate_satellite_indices"])
        columns = np.flatnonzero(candidates == satellite_idx)
        if columns.size != 1:
            raise ValueError("V2 target is not an eligible SERVICE_GRID satellite")
        column = int(columns[0])
        grid_idx = int(self.topology.beam_grid_idx[beam_row])
        position = state["candidate_positions_enu"][column]
        cell = state["grid_positions_enu"][grid_idx]
        vector = cell - position
        distance = np.linalg.norm(vector)
        azimuth = np.degrees(np.arctan2(vector[1], vector[0]))
        elevation = np.degrees(np.arcsin(vector[2] / distance))

        candidate = StationManager(1)
        candidate.station_type = StationType.IMT_BS
        candidate.is_space_station = True
        candidate.active[:] = True
        candidate.geom.set_global_coords(
            np.array([position[0]]), np.array([position[1]]),
            np.array([position[2]]), elev=np.array([elevation]))
        candidate.geom.set_local_coords(azim=np.array([azimuth]))
        candidate.antenna = AntennaFactory.create_n_antennas(
            self.parameters.imt.bs.antenna,
            candidate.geom.pointn_azim_global,
            candidate.geom.pointn_elev_global, 1)
        candidate.bandwidth[:] = self.parameters.imt.bandwidth
        candidate.center_freq[:] = self.parameters.imt.frequency

        saved_path = self.paths_between_imt_and_sys
        propagation_rng = getattr(
            self.propagation_system, "random_number_gen", None)
        propagation_rng_state = (
            propagation_rng.get_state()
            if propagation_rng is not None
            and hasattr(propagation_rng, "get_state") else None)
        saved_attrs = {
            name: getattr(self, name, None) for name in (
                "imt_system_path_loss", "system_imt_antenna_gain",
                "imt_system_antenna_gain_adjacent")}
        physical = {}
        try:
            self.paths_between_imt_and_sys = PropagationPath.create_default(
                self.system, candidate)
            coupling = self.calculate_coupling_loss_system_imt(
                self.system, candidate, is_co_channel=False)
            i_linear = float(np.sum(np.power(
                10.0, 0.1 * (tx_oob_dbm - coupling))))
            tx_offaxis = float(
                candidate.geom.get_off_axis_angle(self.system.geom)[0, 0])
            rx_offaxis = float(
                self.system.geom.get_off_axis_angle(candidate.geom)[0, 0])
            interferer_azimuth, interferer_polar = (
                self.system.geom.get_global_pointing_vector_to(candidate.geom))
            g_rx = float(np.asarray(
                self.system_imt_antenna_gain).reshape(-1)[0])
            g_tx = float(np.asarray(
                self.imt_system_antenna_gain_adjacent).reshape(-1)[0])
            g_tx_peak = float(candidate.antenna[0].peak_gain)
            g_rx_peak = float(self.system.antenna[0].peak_gain)
            tx_power_dbm = float(np.asarray(
                self.bs.tx_power[beam_row]).reshape(-1)[0])
            physical = {
                "eess_elevation_deg": float(90.0 - interferer_polar[0, 0]),
                "interferer_azimuth_from_eess_deg": float(
                    interferer_azimuth[0, 0]),
                "tx_offaxis_deg": tx_offaxis,
                "rx_offaxis_deg": rx_offaxis,
                "g_tx_dbi": g_tx,
                "g_rx_dbi": g_rx,
                "tx_gain_drop_db": g_tx_peak - g_tx,
                "rx_gain_drop_db": g_rx_peak - g_rx,
                "joint_gain_suppression_db": (
                    g_tx_peak - g_tx + g_rx_peak - g_rx),
                "path_loss_db": float(np.asarray(
                    self.imt_system_path_loss).reshape(-1)[0]),
                "spectral_coupling_db": float(tx_oob_dbm - tx_power_dbm),
                "coupling_loss_db": float(np.asarray(coupling).reshape(-1)[0]),
                "tx_peak_gain_dbi": g_tx_peak,
                "rx_peak_gain_dbi": g_rx_peak,
                "tx_conducted_power_dbm": tx_power_dbm,
                "tx_spectral_power_dbm": float(tx_oob_dbm),
            }
        finally:
            self.paths_between_imt_and_sys = saved_path
            if propagation_rng_state is not None:
                propagation_rng.set_state(propagation_rng_state)
            for name, value in saved_attrs.items():
                setattr(self, name, value)
        return CandidateEvaluation(
            satellite_idx=int(satellite_idx),
            service_elevation_deg=float(
                state["candidate_elevations_deg"][grid_idx, column]),
            i_link_linear_mw=i_linear,
            satellite_enu_x_m=float(position[0]),
            satellite_enu_y_m=float(position[1]),
            satellite_enu_z_m=float(position[2]),
            satellite_latitude_deg=float(
                state["candidate_latitudes"][column]),
            satellite_longitude_deg=float(
                state["candidate_longitudes"][column]),
            satellite_altitude_m=float(
                state["candidate_altitudes"][column]),
            tx_boresight_azimuth_deg=float(azimuth),
            tx_boresight_elevation_deg=float(elevation),
            **physical)

    @staticmethod
    def _stable_int_array_hash(values) -> str:
        """Return a platform-independent identity hash for invariance checks."""
        array = np.asarray(values, dtype="<i8")
        return hashlib.sha256(array.tobytes()).hexdigest()

    def _prepare_operational_risk_diagnostics(
        self, *, bs_active, link_powers, aggregate_linear_mw,
        tx_spectral_power_dbm,
    ):
        """Capture realized pre-V2 link geometry without changing simulation state."""
        cfg = self.parameters.imt.topology.mss_dc.operational_risk_diagnostics
        bandwidth_mhz = float(self.system.bandwidth[0])
        aggregate_dbw_mhz = (
            10.0 * np.log10(aggregate_linear_mw) - 30.0
            - 10.0 * np.log10(bandwidth_mhz)
            if aggregate_linear_mw > 0.0 else -np.inf)
        v2_config = getattr(
            self.parameters.imt.topology.mss_dc,
            "interference_aware_handover_v2", None)
        risk_threshold = float(getattr(
            v2_config, "risk_gate_dbw_per_mhz", -154.0))
        ranked_rows = select_triggered_links(
            link_powers, cfg.record_top_k, "ORACLE_TOP_K")
        rank_by_row = {int(row): rank for rank, row in enumerate(ranked_rows, 1)}

        # These are the exact angular routines used by the antenna-gain path.
        tx_offaxis = self.bs.geom.get_off_axis_angle(self.system.geom)[:, 0]
        rx_offaxis = self.system.geom.get_off_axis_angle(self.bs.geom)[0]
        interferer_azimuth, interferer_polar = (
            self.system.geom.get_global_pointing_vector_to(self.bs.geom))
        interferer_elevation = 90.0 - interferer_polar[0]

        n_bs = self.bs.num_stations
        k = self.parameters.imt.ue.k
        path_loss = np.asarray(self.imt_system_path_loss).reshape(
            self.system.num_stations, n_bs, k)
        gain_rx = np.asarray(self.system_imt_antenna_gain).reshape(
            self.system.num_stations, n_bs, k)
        gain_tx = np.asarray(
            self.imt_system_antenna_gain_adjacent).reshape(
                n_bs, k, self.system.num_stations)
        coupling = np.asarray(self.coupling_loss_imt_system_adjacent)
        state = self.topology._service_grid_snapshot
        p619 = self.parameters.single_earth_station.param_p619
        eess_az = float(self.system.geom.pointn_azim_global[0])
        eess_el = float(self.system.geom.pointn_elev_global[0])
        az_rad = np.radians(eess_az)
        el_rad = np.radians(eess_el)
        eess_boresight = (
            float(np.cos(el_rad) * np.cos(az_rad)),
            float(np.cos(el_rad) * np.sin(az_rad)),
            float(np.sin(el_rad)),
        )
        eess_common = {
            "eess_latitude_deg": float(p619.earth_station_lat_deg),
            "eess_longitude_deg": float(
                self.parameters.imt.topology.central_longitude),
            "eess_altitude_m": float(p619.earth_station_alt_m),
            "eess_enu_x_m": float(self.system.geom.x_global[0]),
            "eess_enu_y_m": float(self.system.geom.y_global[0]),
            "eess_enu_z_m": float(self.system.geom.z_global[0]),
            "eess_pointing_azimuth_deg": eess_az,
            "eess_pointing_elevation_deg": eess_el,
            "eess_boresight_x": eess_boresight[0],
            "eess_boresight_y": eess_boresight[1],
            "eess_boresight_z": eess_boresight[2],
        }
        guard_band_mhz = max(
            0.0,
            (float(self.param_system.frequency) - bandwidth_mhz / 2.0)
            - (float(self.parameters.imt.frequency)
               + float(self.parameters.imt.bandwidth) / 2.0))
        scenario_common = {
            "snapshot_id": self._operational_risk_snapshot_id,
            "secondary_seed": self._operational_risk_secondary_seed,
            "master_seed": int(self.parameters.general.seed),
            "eess_system": self.parameters.single_earth_station.system_label,
            "load_factor": float(self.parameters.imt.bs.load_probability),
            "guard_band_mhz": guard_band_mhz,
            "dc_mss_center_frequency_mhz": float(self.parameters.imt.frequency),
            "dc_mss_bandwidth_mhz": float(self.parameters.imt.bandwidth),
        }
        g_rx_peak = float(self.system.antenna[0].peak_gain)
        additional_loss = float(
            self.parameters.imt.bs.ohmic_loss + self.polarization_loss)
        records = []
        for row in ranked_rows:
            row = int(row)
            grid_idx = int(self.topology.beam_grid_idx[row])
            i_linear = float(link_powers[row])
            i_dbw_mhz = (
                10.0 * np.log10(i_linear) - 30.0
                - 10.0 * np.log10(bandwidth_mhz)
                if i_linear > 0.0 else -np.inf)
            g_tx = float(gain_tx[row, 0, 0])
            g_rx = float(gain_rx[0, row, 0])
            g_tx_peak = float(self.bs.antenna[row].peak_gain)
            tx_power = float(np.asarray(
                self.bs.tx_power[row]).reshape(-1)[0])
            cell_ecef = np.asarray(state["grid_positions_ecef"][grid_idx])
            cell_enu = np.asarray(state["grid_positions_enu"][grid_idx])
            record = {
                **scenario_common,
                **eess_common,
                "rank_in_snapshot": rank_by_row[row],
                "beam_row_idx": row,
                "beam_grid_idx": grid_idx,
                "service_cell_id": grid_idx,
                "primary_satellite_idx": int(
                    self.topology.primary_satellite_idx[row]),
                "serving_satellite_idx": int(
                    self.topology.serving_satellite_idx[row]),
                "individual_i_linear_mw": i_linear,
                "individual_i_dbw_per_mhz": i_dbw_mhz,
                "fraction_of_iagg_linear": (
                    i_linear / aggregate_linear_mw
                    if aggregate_linear_mw > 0.0 else 0.0),
                "iagg_before_linear_mw": float(aggregate_linear_mw),
                "iagg_before_dbw_per_mhz": aggregate_dbw_mhz,
                "critical_before_flag": aggregate_dbw_mhz > risk_threshold,
                "altitude_km": float(self.topology.height[row]) / 1000.0,
                "satellite_latitude_deg": float(self.topology.lat[row]),
                "satellite_longitude_deg": float(self.topology.lon[row]),
                "satellite_altitude_m": float(self.topology.height[row]),
                "satellite_enu_x_m": float(self.bs.geom.x_global[row]),
                "satellite_enu_y_m": float(self.bs.geom.y_global[row]),
                "satellite_enu_z_m": float(self.bs.geom.z_global[row]),
                "service_cell_latitude_deg": float(
                    state["grid_latitudes"][grid_idx]),
                "service_cell_longitude_deg": float(
                    state["grid_longitudes"][grid_idx]),
                "service_cell_ecef_x_m": float(cell_ecef[0]),
                "service_cell_ecef_y_m": float(cell_ecef[1]),
                "service_cell_ecef_z_m": float(cell_ecef[2]),
                "service_cell_enu_x_m": float(cell_enu[0]),
                "service_cell_enu_y_m": float(cell_enu[1]),
                "service_cell_enu_z_m": float(cell_enu[2]),
                "tx_boresight_azimuth_deg": float(
                    self.bs.geom.pointn_azim_global[row]),
                "tx_boresight_elevation_deg": float(
                    self.bs.geom.pointn_elev_global[row]),
                "tx_offaxis_to_eess_deg": float(tx_offaxis[row]),
                "rx_offaxis_from_eess_boresight_deg": float(rx_offaxis[row]),
                "eess_to_satellite_azimuth_deg": float(
                    interferer_azimuth[0, row]),
                "eess_to_satellite_elevation_deg": float(
                    interferer_elevation[row]),
                "service_elevation_deg": float(
                    self.topology.beam_ground_elev_angles[row]),
                "tx_gain_toward_eess_dbi": g_tx,
                "tx_peak_gain_dbi": g_tx_peak,
                "tx_gain_drop_db": g_tx_peak - g_tx,
                "rx_gain_from_interferer_dbi": g_rx,
                "rx_peak_gain_dbi": g_rx_peak,
                "rx_gain_drop_db": g_rx_peak - g_rx,
                "joint_gain_suppression_db": (
                    g_tx_peak - g_tx + g_rx_peak - g_rx),
                "path_loss_db": float(path_loss[0, row, 0]),
                "coupling_loss_db": float(coupling[row, 0]),
                "additional_loss_db": additional_loss,
                "tx_conducted_power_dbm": tx_power,
                "tx_spectral_power_dbm": float(tx_spectral_power_dbm),
                "tx_spectral_psd_dbm_per_mhz": (
                    float(tx_spectral_power_dbm)
                    - 10.0 * np.log10(bandwidth_mhz)),
                "spectral_coupling_db": float(
                    tx_spectral_power_dbm - tx_power),
            }
            records.append(record)

        active_rows = np.asarray(bs_active, dtype=np.int64)
        serving_before = np.asarray(
            self.topology.serving_satellite_idx[active_rows], dtype=np.int64)
        return {
            "topk": records,
            "by_row": {record["beam_row_idx"]: record for record in records},
            "scenario": scenario_common,
            "eess": eess_common,
            "aggregate_before_linear_mw": float(aggregate_linear_mw),
            "aggregate_before_dbw_per_mhz": aggregate_dbw_mhz,
            "risk_threshold_dbw_per_mhz": risk_threshold,
            "active_beam_count": int(active_rows.size),
            "active_beam_rows_sha256": self._stable_int_array_hash(active_rows),
            "serving_satellite_ids_before_sha256": (
                self._stable_int_array_hash(serving_before)),
        }

    def _finalize_operational_risk_diagnostics(self, aggregate_after_linear_mw):
        """Emit passive rows after V2 while retaining the pre-V2 geometry."""
        context = self._operational_risk_context
        cfg = self.parameters.imt.topology.mss_dc.operational_risk_diagnostics
        bandwidth_mhz = float(self.system.bandwidth[0])
        after_dbw = (
            10.0 * np.log10(aggregate_after_linear_mw) - 30.0
            - 10.0 * np.log10(bandwidth_mhz)
            if aggregate_after_linear_mw > 0.0 else -np.inf)
        v2 = getattr(self, "_v2_last_snapshot_record", None) or {}
        ranked_powers = [
            row["individual_i_linear_mw"] for row in context["topk"]]
        before = context["aggregate_before_linear_mw"]
        c1 = ranked_powers[0] / before if ranked_powers and before > 0 else 0.0
        c13 = sum(ranked_powers[:3]) / before if before > 0 else 0.0
        top1 = context["topk"][0] if context["topk"] else {}

        if cfg.record_top_k:
            self.results.operational_risk_topk.extend(context["topk"])
        if cfg.record_snapshot_summary:
            snapshot = {
                **context["scenario"], **context["eess"],
                "altitude_km": top1.get("altitude_km", np.nan),
                "active_beam_count": context["active_beam_count"],
                "active_beam_rows_sha256": context["active_beam_rows_sha256"],
                "serving_satellite_ids_before_sha256": (
                    context["serving_satellite_ids_before_sha256"]),
                "iagg_before_linear_mw": before,
                "iagg_after_linear_mw": float(aggregate_after_linear_mw),
                "iagg_before_dbw_per_mhz": (
                    context["aggregate_before_dbw_per_mhz"]),
                "iagg_after_dbw_per_mhz": after_dbw,
                "critical_before_flag": (
                    context["aggregate_before_dbw_per_mhz"]
                    > context["risk_threshold_dbw_per_mhz"]),
                "compliant_after_flag": (
                    after_dbw <= context["risk_threshold_dbw_per_mhz"]),
                "risk_gate_triggered": bool(v2.get("gate_entered", False)),
                "handover_performed": bool(v2.get("actuation_flag", False)),
                "handover_count": int(v2.get("reassigned_beams", 0)),
                "candidates_evaluated": int(v2.get("candidates_evaluated", 0)),
                "unresolved_count": int(v2.get("unresolved_count", 0)),
                "concentration_c1": c1,
                "concentration_c1_c3": c13,
            }
            top1_map = {
                "top1_beam_row_idx": "beam_row_idx",
                "top1_beam_grid_idx": "beam_grid_idx",
                "top1_service_cell_id": "service_cell_id",
                "top1_serving_satellite_idx": "serving_satellite_idx",
                "top1_i_link_linear_mw": "individual_i_linear_mw",
                "top1_i_link_dbw_per_mhz": "individual_i_dbw_per_mhz",
                "top1_satellite_latitude_deg": "satellite_latitude_deg",
                "top1_satellite_longitude_deg": "satellite_longitude_deg",
                "top1_satellite_altitude_m": "satellite_altitude_m",
                "top1_satellite_enu_x_m": "satellite_enu_x_m",
                "top1_satellite_enu_y_m": "satellite_enu_y_m",
                "top1_satellite_enu_z_m": "satellite_enu_z_m",
                "top1_service_cell_latitude_deg": "service_cell_latitude_deg",
                "top1_service_cell_longitude_deg": "service_cell_longitude_deg",
                "top1_tx_offaxis_deg": "tx_offaxis_to_eess_deg",
                "top1_rx_offaxis_deg": "rx_offaxis_from_eess_boresight_deg",
                "top1_eess_to_satellite_azimuth_deg": (
                    "eess_to_satellite_azimuth_deg"),
                "top1_eess_to_satellite_elevation_deg": (
                    "eess_to_satellite_elevation_deg"),
                "top1_service_elevation_deg": "service_elevation_deg",
                "top1_tx_gain_dbi": "tx_gain_toward_eess_dbi",
                "top1_rx_gain_dbi": "rx_gain_from_interferer_dbi",
                "top1_joint_gain_suppression_db": (
                    "joint_gain_suppression_db"),
                "top1_path_loss_db": "path_loss_db",
                "top1_coupling_loss_db": "coupling_loss_db",
                "top1_tx_spectral_power_dbm": "tx_spectral_power_dbm",
                "top1_spectral_coupling_db": "spectral_coupling_db",
            }
            snapshot.update({out: top1.get(source, np.nan)
                             for out, source in top1_map.items()})
            self.results.operational_risk_snapshots.append(snapshot)

        if cfg.record_handover_events:
            event_sources = getattr(self, "_operational_v2_event_sources", [])
            for source in event_sources:
                decision = source["decision"]
                current = source["current"] or {}
                target = source["target"]
                target_values = target or CandidateEvaluation(
                    satellite_idx=-1, service_elevation_deg=np.nan,
                    i_link_linear_mw=np.nan)
                current_i_dbw = current.get("individual_i_dbw_per_mhz", np.nan)
                target_i_dbw = (
                    10.0 * np.log10(target_values.i_link_linear_mw) - 30.0
                    - 10.0 * np.log10(bandwidth_mhz)
                    if target is not None and target_values.i_link_linear_mw > 0
                    else np.nan)
                row = {
                    **context["scenario"], **context["eess"],
                    "rank_in_snapshot": source["rank"],
                    "beam_row_idx": decision.beam_row_idx,
                    "beam_grid_idx": current.get("beam_grid_idx", -1),
                    "service_cell_id": current.get("service_cell_id", -1),
                    "accepted": decision.accepted,
                    "unresolved": not decision.accepted,
                    "reason": decision.reason,
                    "candidates_evaluated": len(decision.candidates),
                    "current_satellite_idx": decision.current_satellite_idx,
                    "target_satellite_idx": (
                        target_values.satellite_idx if target is not None else -1),
                    "current_i_linear_mw": decision.current_i_linear_mw,
                    "target_i_linear_mw": (
                        target_values.i_link_linear_mw
                        if target is not None else np.nan),
                    "current_i_dbw_per_mhz": current_i_dbw,
                    "target_i_dbw_per_mhz": target_i_dbw,
                    "predicted_reduction_db": decision.predicted_reduction_db,
                    "service_elevation_loss_deg": (
                        current.get("service_elevation_deg", np.nan)
                        - target_values.service_elevation_deg),
                    "delta_rx_offaxis_deg": (
                        target_values.rx_offaxis_deg
                        - current.get("rx_offaxis_from_eess_boresight_deg", np.nan)),
                    "delta_tx_offaxis_deg": (
                        target_values.tx_offaxis_deg
                        - current.get("tx_offaxis_to_eess_deg", np.nan)),
                    "delta_joint_gain_suppression_db": (
                        target_values.joint_gain_suppression_db
                        - current.get("joint_gain_suppression_db", np.nan)),
                    "iagg_before_linear_mw": before,
                    "iagg_after_linear_mw": float(aggregate_after_linear_mw),
                    "iagg_before_dbw_per_mhz": (
                        context["aggregate_before_dbw_per_mhz"]),
                    "iagg_after_dbw_per_mhz": after_dbw,
                    "current_service_elevation_deg": current.get(
                        "service_elevation_deg", np.nan),
                    "target_service_elevation_deg": (
                        target_values.service_elevation_deg),
                    "current_tx_offaxis_deg": current.get(
                        "tx_offaxis_to_eess_deg", np.nan),
                    "target_tx_offaxis_deg": target_values.tx_offaxis_deg,
                    "current_rx_offaxis_deg": current.get(
                        "rx_offaxis_from_eess_boresight_deg", np.nan),
                    "target_rx_offaxis_deg": target_values.rx_offaxis_deg,
                    "current_tx_gain_dbi": current.get(
                        "tx_gain_toward_eess_dbi", np.nan),
                    "target_tx_gain_dbi": target_values.g_tx_dbi,
                    "current_rx_gain_dbi": current.get(
                        "rx_gain_from_interferer_dbi", np.nan),
                    "target_rx_gain_dbi": target_values.g_rx_dbi,
                    "current_tx_peak_gain_dbi": current.get(
                        "tx_peak_gain_dbi", np.nan),
                    "target_tx_peak_gain_dbi": target_values.tx_peak_gain_dbi,
                    "current_rx_peak_gain_dbi": current.get(
                        "rx_peak_gain_dbi", np.nan),
                    "target_rx_peak_gain_dbi": target_values.rx_peak_gain_dbi,
                    "current_joint_gain_suppression_db": current.get(
                        "joint_gain_suppression_db", np.nan),
                    "target_joint_gain_suppression_db": (
                        target_values.joint_gain_suppression_db),
                    "current_path_loss_db": current.get("path_loss_db", np.nan),
                    "target_path_loss_db": target_values.path_loss_db,
                    "current_coupling_loss_db": current.get(
                        "coupling_loss_db", np.nan),
                    "target_coupling_loss_db": target_values.coupling_loss_db,
                    "current_tx_gain_drop_db": current.get(
                        "tx_gain_drop_db", np.nan),
                    "target_tx_gain_drop_db": target_values.tx_gain_drop_db,
                    "current_rx_gain_drop_db": current.get(
                        "rx_gain_drop_db", np.nan),
                    "target_rx_gain_drop_db": target_values.rx_gain_drop_db,
                    "current_tx_spectral_power_dbm": current.get(
                        "tx_spectral_power_dbm", np.nan),
                    "target_tx_spectral_power_dbm": (
                        target_values.tx_spectral_power_dbm),
                    "current_spectral_coupling_db": current.get(
                        "spectral_coupling_db", np.nan),
                    "target_spectral_coupling_db": (
                        target_values.spectral_coupling_db),
                    "current_eess_to_satellite_azimuth_deg": current.get(
                        "eess_to_satellite_azimuth_deg", np.nan),
                    "target_eess_to_satellite_azimuth_deg": (
                        target_values.interferer_azimuth_from_eess_deg),
                    "current_eess_to_satellite_elevation_deg": current.get(
                        "eess_to_satellite_elevation_deg", np.nan),
                    "target_eess_to_satellite_elevation_deg": (
                        target_values.eess_elevation_deg),
                    "current_tx_boresight_azimuth_deg": current.get(
                        "tx_boresight_azimuth_deg", np.nan),
                    "target_tx_boresight_azimuth_deg": (
                        target_values.tx_boresight_azimuth_deg),
                    "current_tx_boresight_elevation_deg": current.get(
                        "tx_boresight_elevation_deg", np.nan),
                    "target_tx_boresight_elevation_deg": (
                        target_values.tx_boresight_elevation_deg),
                    "current_satellite_latitude_deg": current.get(
                        "satellite_latitude_deg", np.nan),
                    "current_satellite_longitude_deg": current.get(
                        "satellite_longitude_deg", np.nan),
                    "current_satellite_altitude_m": current.get(
                        "satellite_altitude_m", np.nan),
                    "current_satellite_enu_x_m": current.get(
                        "satellite_enu_x_m", np.nan),
                    "current_satellite_enu_y_m": current.get(
                        "satellite_enu_y_m", np.nan),
                    "current_satellite_enu_z_m": current.get(
                        "satellite_enu_z_m", np.nan),
                    "target_satellite_latitude_deg": (
                        target_values.satellite_latitude_deg),
                    "target_satellite_longitude_deg": (
                        target_values.satellite_longitude_deg),
                    "target_satellite_altitude_m": target_values.satellite_altitude_m,
                    "target_satellite_enu_x_m": target_values.satellite_enu_x_m,
                    "target_satellite_enu_y_m": target_values.satellite_enu_y_m,
                    "target_satellite_enu_z_m": target_values.satellite_enu_z_m,
                }
                for key in (
                    "service_cell_latitude_deg", "service_cell_longitude_deg",
                    "service_cell_ecef_x_m", "service_cell_ecef_y_m",
                    "service_cell_ecef_z_m", "service_cell_enu_x_m",
                    "service_cell_enu_y_m", "service_cell_enu_z_m",
                ):
                    row[key] = current.get(key, np.nan)
                self.results.operational_risk_handover_events.append(row)

        if cfg.record_candidate_details:
            for source in getattr(self, "_operational_v2_event_sources", []):
                decision = source["decision"]
                current = source["current"] or {}
                for order, candidate in enumerate(decision.candidates, 1):
                    self.results.operational_risk_candidates.append({
                        **context["scenario"],
                        "beam_row_idx": decision.beam_row_idx,
                        "beam_grid_idx": current.get("beam_grid_idx", -1),
                        "service_cell_id": current.get("service_cell_id", -1),
                        "current_satellite_idx": decision.current_satellite_idx,
                        "candidate_satellite_idx": candidate.satellite_idx,
                        "candidate_order": order,
                        "selected_flag": (
                            decision.accepted and candidate.satellite_idx
                            == decision.selected_satellite_idx),
                        "candidate_i_linear_mw": candidate.i_link_linear_mw,
                        "candidate_service_elevation_deg": (
                            candidate.service_elevation_deg),
                        "candidate_tx_offaxis_deg": candidate.tx_offaxis_deg,
                        "candidate_rx_offaxis_deg": candidate.rx_offaxis_deg,
                        "candidate_tx_gain_dbi": candidate.g_tx_dbi,
                        "candidate_rx_gain_dbi": candidate.g_rx_dbi,
                        "candidate_tx_gain_drop_db": candidate.tx_gain_drop_db,
                        "candidate_rx_gain_drop_db": candidate.rx_gain_drop_db,
                        "candidate_joint_gain_suppression_db": (
                            candidate.joint_gain_suppression_db),
                        "candidate_path_loss_db": candidate.path_loss_db,
                        "candidate_coupling_loss_db": candidate.coupling_loss_db,
                        "candidate_spectral_coupling_db": (
                            candidate.spectral_coupling_db),
                        "candidate_tx_spectral_power_dbm": (
                            candidate.tx_spectral_power_dbm),
                        "candidate_satellite_latitude_deg": (
                            candidate.satellite_latitude_deg),
                        "candidate_satellite_longitude_deg": (
                            candidate.satellite_longitude_deg),
                        "candidate_satellite_altitude_m": (
                            candidate.satellite_altitude_m),
                        "candidate_satellite_enu_x_m": candidate.satellite_enu_x_m,
                        "candidate_satellite_enu_y_m": candidate.satellite_enu_y_m,
                        "candidate_satellite_enu_z_m": candidate.satellite_enu_z_m,
                    })

    def _apply_interference_aware_handover_v2(
        self, link_powers, aggregate_linear_mw, tx_oob_dbm):
        """Rank links, evaluate exact alternatives and apply accepted changes."""
        cfg = self.parameters.imt.topology.mss_dc.interference_aware_handover_v2
        aggregate_before = float(aggregate_linear_mw)
        bandwidth_mhz = float(self.system.bandwidth[0])
        before_dbw_mhz = (
            10.0 * np.log10(aggregate_before) - 30.0
            - 10.0 * np.log10(bandwidth_mhz)
            if aggregate_before > 0.0 else -np.inf)
        gate_entered = should_enter_risk_gate(
            cfg.trigger_mode, before_dbw_mhz,
            cfg.risk_gate_dbw_per_mhz)
        rows = (
            select_triggered_links(
                link_powers, cfg.top_k,
                "ORACLE_TOP_K" if cfg.trigger_mode == "RISK_GATED_TOP_K"
                else cfg.trigger_mode)
            if gate_entered else []
        )
        ranked_powers = sorted(link_powers.values(), reverse=True)
        concentration_c1 = (
            ranked_powers[0] / aggregate_before
            if ranked_powers and aggregate_before > 0.0 else 0.0)
        concentration_c1_c3 = (
            sum(ranked_powers[:3]) / aggregate_before
            if ranked_powers and aggregate_before > 0.0 else 0.0)
        state = self.topology._service_grid_snapshot
        minimum = (self.parameters.imt.topology.mss_dc.beam_positioning
                   .service_grid.minimum_service_angle)
        accepted = 0
        decisions = []
        event_rows = []
        operational_sources = []
        operational_context = getattr(
            self, "_operational_risk_context", {"by_row": {}})
        rank_by_row = {int(row): rank for rank, row in enumerate(rows, 1)}
        for row in rows:
            if accepted >= cfg.max_handovers_per_snapshot:
                break
            grid_idx = int(self.topology.beam_grid_idx[row])
            current_sat = int(self.topology.serving_satellite_idx[row])
            candidate_values = []
            for column, sat_idx in enumerate(state["candidate_satellite_indices"]):
                service_elevation = float(
                    state["candidate_elevations_deg"][grid_idx, column])
                if service_elevation < minimum or int(sat_idx) == current_sat:
                    continue
                candidate_values.append(self._evaluate_v2_candidate(
                    row, int(sat_idx), tx_oob_dbm))
            decision = choose_minimum_interference_target(
                beam_row_idx=int(row), current_satellite_idx=current_sat,
                current_service_elevation_deg=float(
                    self.topology.beam_ground_elev_angles[row]),
                current_i_linear_mw=float(link_powers[row]),
                candidates=candidate_values,
                min_reduction_db=cfg.min_reduction_db,
                max_service_elevation_loss_deg=(
                    cfg.max_service_elevation_loss_deg))
            decisions.append(decision)
            selected_elevation = np.nan
            if decision.accepted:
                selected_elevation = next(
                    candidate.service_elevation_deg
                    for candidate in decision.candidates
                    if candidate.satellite_idx == decision.selected_satellite_idx
                )
            selected_candidate = next((
                candidate for candidate in decision.candidates
                if decision.accepted
                and candidate.satellite_idx == decision.selected_satellite_idx
            ), None)
            operational_sources.append({
                "rank": rank_by_row[int(row)],
                "decision": decision,
                "current": operational_context["by_row"].get(int(row)),
                "target": selected_candidate,
            })
            event_rows.append({
                "snapshot_id": self._v2_snapshot_id,
                "secondary_seed": self._v2_secondary_seed,
                "rank_in_snapshot": rank_by_row[int(row)],
                "beam_row_idx": int(row),
                "beam_grid_idx": int(self.topology.beam_grid_idx[row]),
                "current_satellite_idx": current_sat,
                "selected_satellite_idx": decision.selected_satellite_idx,
                "current_service_elevation_deg": float(
                    self.topology.beam_ground_elev_angles[row]),
                "selected_service_elevation_deg": selected_elevation,
                "candidates_evaluated": len(decision.candidates),
                "current_i_linear_mw": decision.current_i_linear_mw,
                "selected_i_linear_mw": decision.selected_i_linear_mw,
                "predicted_reduction_db": decision.predicted_reduction_db,
                "accepted": decision.accepted,
                "unresolved": not decision.accepted,
                "reason": decision.reason,
            })
            if not decision.accepted:
                continue
            aggregate_linear_mw = replace_link_power_linear(
                aggregate_linear_mw, link_powers[row],
                decision.selected_i_linear_mw)
            link_powers[row] = decision.selected_i_linear_mw
            self.topology.reassign_service_grid_rows(
                [row], [decision.selected_satellite_idx])
            accepted += 1

        if accepted:
            self.bs.geom.set_global_coords(
                self.topology.space_station_x, self.topology.space_station_y,
                self.topology.space_station_z, elev=self.topology.elevation)
            self.bs.geom.set_local_coords(azim=self.topology.azimuth)
            self.bs.antenna = AntennaFactory.create_n_antennas(
                self.parameters.imt.bs.antenna,
                self.bs.geom.pointn_azim_global,
                self.bs.geom.pointn_elev_global, self.bs.num_stations)
        self.interference_aware_handover_v2_decisions = decisions
        after_dbw_mhz = (
            10.0 * np.log10(aggregate_linear_mw) - 30.0
            - 10.0 * np.log10(bandwidth_mhz)
            if aggregate_linear_mw > 0.0 else -np.inf)
        aggregate_reduction_db = (
            10.0 * np.log10(aggregate_before / aggregate_linear_mw)
            if aggregate_before > 0.0 and aggregate_linear_mw > 0.0
            else 0.0)
        snapshot_record = {
            "snapshot_id": self._v2_snapshot_id,
            "secondary_seed": self._v2_secondary_seed,
            "top_k_links_examined": len(decisions),
            "actuation_flag": accepted > 0,
            "reassigned_beams": accepted,
            "candidates_evaluated": sum(
                len(decision.candidates) for decision in decisions),
            "unresolved_count": sum(
                not decision.accepted for decision in decisions),
            "risk_gate_dbw_per_mhz": cfg.risk_gate_dbw_per_mhz,
            "gate_entered": gate_entered,
            "critical_before": before_dbw_mhz > cfg.risk_gate_dbw_per_mhz,
            "critical_after": after_dbw_mhz > cfg.risk_gate_dbw_per_mhz,
            "became_compliant": (
                before_dbw_mhz > cfg.risk_gate_dbw_per_mhz
                and after_dbw_mhz <= cfg.risk_gate_dbw_per_mhz),
            "concentration_c1": concentration_c1,
            "concentration_c1_c3": concentration_c1_c3,
            "iagg_before_linear_mw": aggregate_before,
            "iagg_after_linear_mw": float(aggregate_linear_mw),
            "iagg_before_dbw_per_mhz": before_dbw_mhz,
            "iagg_after_dbw_per_mhz": after_dbw_mhz,
            "iagg_reduction_db": aggregate_reduction_db,
            "top1_link_reassigned": any(
                row["rank_in_snapshot"] == 1 and row["accepted"]
                for row in event_rows),
        }
        self._v2_last_snapshot_record = snapshot_record
        self._operational_v2_event_sources = operational_sources
        self.results.interference_aware_handover_v2_snapshots.append(
            snapshot_record)
        self.results.interference_aware_handover_v2_events.extend(event_rows)
        return aggregate_linear_mw

    def calculate_external_interference(self):
        """
        Calculates interference that IMT system generates on other system
        """
        if (self.parameters.imt.topology.type == "MSS_DC"
                and self.parameters.imt.topology.mss_dc.interference_aware_handover_v2
                .evaluation_mode == "COCHANNEL_INR"):
            from sharc.cochannel_handover import CochannelHandover
            CochannelHandover(self).run()
            return
        if self.co_channel or (
            self.adjacent_channel and self.param_system.adjacent_ch_reception != "OFF"
        ):
            self.coupling_loss_imt_system = self.calculate_coupling_loss_system_imt(
                self.system, self.bs, is_co_channel=True, )
        if self.adjacent_channel:
            self.coupling_loss_imt_system_adjacent = \
                self.calculate_coupling_loss_system_imt(
                    self.system,
                    self.bs,
                    is_co_channel=False,
                )

        # applying a bandwidth scaling factor since UE transmits on a portion
        # of the interfered systems bandwidth
        # calculate interference only from active UE's
        pow_coch = -np.inf
        # These are in dB. Turn to zero linear.
        tx_oob = -np.inf
        rx_oob = -np.inf

        bs_active = np.where(self.bs.active)[0]
        # this implm assumes some parameters will be same for all interferring BS's
        frst_bs = bs_active[0]
        if self.co_channel:
            ue = self.link[frst_bs]
            weights = self.calculate_bw_weights(
                self.ue.bandwidth[ue],
                self.ue.center_freq[ue],
                self.param_system.bandwidth,
                self.param_system.frequency,
            )

        if self.adjacent_channel:
            # Calculate how much power is emitted in the adjacent channel:
            if self.parameters.imt.adjacent_ch_emissions == "SPECTRAL_MASK":
                # The unwanted emission is calculated in terms of TRP (after
                # antenna). In SHARC implementation, ohmic losses are already
                # included in coupling loss. Then, care has to be taken;
                # otherwise ohmic loss will be included twice.
                tx_oob = self.bs.spectral_mask.power_calc(
                    self.param_system.frequency,
                    self.system.bandwidth) + self.parameters.imt.bs.ohmic_loss

            elif self.parameters.imt.adjacent_ch_emissions == "ACLR":
                non_overlap_sys_bw = self.param_system.bandwidth - self.overlapping_bandwidth
                # NOTE: approximated equal to IMT bw
                measurement_bw = self.parameters.imt.bandwidth
                aclr_dB = self.parameters.imt.bs.adjacent_ch_leak_ratio

                if non_overlap_sys_bw > measurement_bw:
                    # NOTE: ACLR defines total leaked power over a fixed measurement bandwidth.
                    # If the victim bandwidth is wider, you’re assuming the same leakage
                    # profile extends beyond the ACLR-defined region, which may overestimate interference
                    # FIXME: if the victim bw fully contains tx bw, then
                    # EACH region should be <= measurement_bw
                    warn(
                        "Using IMT ACLR into system, but ACLR measurement bw is "
                        f"{measurement_bw} while the system bw is bigger ({non_overlap_sys_bw}).\n"
                        "Are you sure you intend to apply ACLR to the entire system bw?"
                    )

                # tx_oob_in_measurement = (tx_pow_lin / aclr)
                # => approx. PSD = (tx_pow_lin / aclr) / measurement_bw
                # approximated received tx_oob = PSD * non_overlap_sys_bw
                # NOTE: we don't get total power, but power per beam
                # because later broadcast will sum this tx_oob `k` times
                tx_oob = self.bs.tx_power[frst_bs] - aclr_dB + 10 * np.log10(
                    non_overlap_sys_bw / measurement_bw
                )
            elif self.parameters.imt.adjacent_ch_emissions == "OFF":
                pass
            else:
                raise ValueError(
                    f"No implementation for self.parameters.imt.adjacent_ch_emissions == {
                        self.parameters.imt.adjacent_ch_emissions}")

            # Calculate how much power is received in the adjacent channel
            if self.param_system.adjacent_ch_reception == "ACS":
                non_overlap_imt_bw = self.parameters.imt.bandwidth - self.overlapping_bandwidth
                tx_bw = self.parameters.imt.bandwidth
                acs_dB = self.param_system.adjacent_ch_selectivity

                # NOTE: only the power not overlapping is attenuated by ACS
                # PSD = tx_pow_lin / tx_bw
                # tx_pow_adj_lin = PSD * non_overlap_imt_bw
                # rx_oob = tx_pow_adj_lin / acs
                rx_oob = self.bs.tx_power[frst_bs] + 10 * np.log10(
                    non_overlap_imt_bw / tx_bw
                ) - acs_dB
            elif self.param_system.adjacent_ch_reception == "OFF":
                if self.parameters.imt.adjacent_ch_emissions == "OFF":
                    raise ValueError(
                        "parameters.imt.adjacent_ch_emissions and parameters.imt.adjacent_ch_reception"
                        " cannot be both set to \"OFF\"")
            else:
                raise ValueError(
                    f"No implementation for self.param_system.adjacent_ch_reception == {
                        self.param_system.adjacent_ch_reception}")

        if self.system.num_stations > 1:
            raise NotImplementedError(
                "Implementation does not support victim system with more than 1 active station"
            )

        rx_interference = 0
        diagnostics_enabled = self._interference_link_diagnostics_enabled()
        v2_enabled = self._handover_v2_enabled()
        operational_enabled = self._operational_risk_diagnostics_enabled()
        link_interference_linear_mw = {} if (
            diagnostics_enabled or v2_enabled or operational_enabled) else None
        bs_interferer_paths = self.paths_between_imt_and_sys.mask.T
        for bs in bs_active:
            system_interfering = np.where(bs_interferer_paths[bs])[0]
            active_beams = [
                i for i in range(
                    bs *
                    self.parameters.imt.ue.k, (bs + 1) *
                    self.parameters.imt.ue.k,
                )
            ]
            if self.co_channel:
                pow_coch = 10 * np.log10(
                    weights * np.power(
                        10,
                        0.1 * self.bs.tx_power[bs],
                    ),
                )
                rx_interference += np.sum(
                    10 ** (0.1 * (pow_coch - self.coupling_loss_imt_system[active_beams, system_interfering]))
                )

            if self.adjacent_channel:
                # oob_power per beam
                # NOTE: we only consider one beam since all beams should have gain
                # of a single element for IMT, and as such the coupling loss should be the
                # same for all beams
                adj_loss = self.coupling_loss_imt_system_adjacent[np.ix_(active_beams, system_interfering)]

                # FIXME: for more than 1 sys
                # NOTE: sharc impl already doesn't really work with n_sys > 1
                # so more would have to be fixed before this
                assert np.all(adj_loss == adj_loss.flat[0])

                tx_oob_s = tx_oob - adj_loss[0, :]
                if self.param_system.adjacent_ch_reception != "OFF":
                    rx_oob_s = rx_oob - self.coupling_loss_imt_system[active_beams, system_interfering]
                else:
                    rx_oob_s = -np.inf

                # Out of band power
                # sum linearly power leaked into band and power received in the
                # adjacent band
                oob_power = 10 * np.log10(
                    10 ** (0.1 * tx_oob_s) + 10 ** (0.1 * rx_oob_s)
                )

                # System rx interference
                if diagnostics_enabled or v2_enabled or operational_enabled:
                    adjacent_link_power_linear_mw = np.sum(
                        np.power(10, 0.1 * oob_power)
                    )
                    rx_interference += adjacent_link_power_linear_mw
                    link_interference_linear_mw[int(bs)] = float(
                        adjacent_link_power_linear_mw)
                else:
                    # Preserve the baseline expression exactly when disabled.
                    rx_interference += np.sum(
                        np.power(10, 0.1 * oob_power)
                    )

        # Diagnostics describe the unmitigated physical links.  Collect them
        # before V2 mutates serving-satellite geometry and link powers.
        if diagnostics_enabled:
            self._collect_interference_link_diagnostics(
                bs_active=bs_active,
                link_interference_linear_mw=link_interference_linear_mw,
                aggregate_linear_mw=float(rx_interference),
                tx_spectral_power_dbm=float(np.asarray(tx_oob).reshape(-1)[0]),
            )

        if operational_enabled:
            self._operational_risk_context = (
                self._prepare_operational_risk_diagnostics(
                    bs_active=bs_active,
                    link_powers=link_interference_linear_mw,
                    aggregate_linear_mw=float(rx_interference),
                    tx_spectral_power_dbm=float(
                        np.asarray(tx_oob).reshape(-1)[0]),
                ))
            self._operational_v2_event_sources = []
            self._v2_last_snapshot_record = None

        if v2_enabled:
            rx_interference = self._apply_interference_aware_handover_v2(
                link_interference_linear_mw, float(rx_interference),
                float(np.asarray(tx_oob).reshape(-1)[0]))

        if operational_enabled:
            self._finalize_operational_risk_diagnostics(
                float(rx_interference))

        # Total received interference - dBW
        self.system.rx_interference = 10 * np.log10(rx_interference)
        # calculate N
        self.system.thermal_noise = \
            10 * math.log10(BOLTZMANN_CONSTANT * self.system.noise_temperature * 1e3) + \
            10 * math.log10(self.param_system.bandwidth * 1e6)

        # Calculate INR at the system - dBm
        self.system.inr = np.array(
            [self.system.rx_interference - self.system.thermal_noise],
        )

        # Calculate PFD at the system
        # TODO: generalize this a bit more if needed
        if hasattr(
                self.system.antenna[0],
                "effective_area") and self.system.num_stations == 1:
            self.system.pfd = 10 * \
                np.log10(
                    10**(self.system.rx_interference / 10) /
                    self.system.antenna[0].effective_area,
                )

    def _collect_interference_link_diagnostics(
        self, *, bs_active: np.ndarray,
        link_interference_linear_mw: dict[int, float],
        aggregate_linear_mw: float,
        tx_spectral_power_dbm: float,
    ) -> None:
        """Record exact top contributors without changing interference math."""
        config = self.parameters.imt.topology.mss_dc.interference_link_diagnostics
        bandwidth_mhz = float(self.param_system.bandwidth)
        aggregate_dbw_mhz = (
            10.0 * np.log10(aggregate_linear_mw) - 30.0
            - 10.0 * np.log10(bandwidth_mhz))
        v2_config = getattr(
            self.parameters.imt.topology.mss_dc,
            "interference_aware_handover_v2", None)
        risk_threshold = float(getattr(
            v2_config, "risk_gate_dbw_per_mhz", -154.0))
        tx_offaxis = self.bs.geom.get_off_axis_angle(self.system.geom)[:, 0]
        rx_offaxis = self.system.geom.get_off_axis_angle(self.bs.geom)[0]
        interferer_azimuth, interferer_polar = (
            self.system.geom.get_global_pointing_vector_to(self.bs.geom))
        interferer_elevation = 90.0 - interferer_polar[0]

        n_bs = self.bs.num_stations
        k = self.parameters.imt.ue.k
        path_loss = np.asarray(self.imt_system_path_loss).reshape(
            self.system.num_stations, n_bs, k)
        gain_rx = np.asarray(self.system_imt_antenna_gain).reshape(
            self.system.num_stations, n_bs, k)
        gain_tx = np.asarray(
            self.imt_system_antenna_gain_adjacent).reshape(
                n_bs, k, self.system.num_stations)
        event_by_row = {
            int(event["beam_row_idx"]): event for event in getattr(
                self.topology, "interference_aware_handover_events", [])}
        triggered = np.asarray(getattr(
            self.topology, "interference_aware_handover_triggered",
            np.zeros(n_bs, dtype=bool)), dtype=bool)
        successful = np.asarray(getattr(
            self.topology, "interference_aware_handover_successful",
            np.zeros(n_bs, dtype=bool)), dtype=bool)
        unresolved = np.asarray(getattr(
            self.topology, "interference_aware_handover_unresolved",
            np.zeros(n_bs, dtype=bool)), dtype=bool)

        p619 = self.parameters.single_earth_station.param_p619
        g_rx_peak = float(self.system.antenna[0].peak_gain)
        guard_band_mhz = max(
            0.0,
            (float(self.param_system.frequency) - bandwidth_mhz / 2.0)
            - (float(self.parameters.imt.frequency)
               + float(self.parameters.imt.bandwidth) / 2.0))
        additional_loss_db = float(
            self.parameters.imt.bs.ohmic_loss + self.polarization_loss)
        records = []
        for bs_value in bs_active:
            bs = int(bs_value)
            i_linear_mw = link_interference_linear_mw[bs]
            i_dbm = float(10.0 * np.log10(i_linear_mw))
            i_dbw_mhz = (
                i_dbm - 30.0 - 10.0 * np.log10(bandwidth_mhz))
            g_tx = float(gain_tx[bs, 0, 0])
            g_rx = float(gain_rx[0, bs, 0])
            g_tx_peak = float(self.bs.antenna[bs].peak_gain)
            tx_drop = g_tx_peak - g_tx
            rx_drop = g_rx_peak - g_rx
            event = event_by_row.get(bs, {})
            tx_power_dbm = float(np.asarray(
                self.bs.tx_power[bs]).reshape(-1)[0])
            geometric_score_db = (
                g_tx + g_rx - float(path_loss[0, bs, 0]))
            records.append({
                "snapshot_id": self._diagnostic_snapshot_id,
                "secondary_seed": self._diagnostic_secondary_seed,
                "beam_row_idx": bs,
                "beam_grid_idx": int(self.topology.beam_grid_idx[bs]),
                "service_cell_id": int(self.topology.beam_grid_idx[bs]),
                "primary_satellite_idx": int(
                    self.topology.primary_satellite_idx[bs]),
                "serving_satellite_idx": int(
                    self.topology.serving_satellite_idx[bs]),
                "target_satellite_idx": int(
                    event.get("target_satellite_idx", -1)),
                "guard_band_mhz": guard_band_mhz,
                "altitude_km": float(self.topology.height[bs]) / 1000.0,
                "load_factor": float(self.parameters.imt.bs.load_probability),
                "eess_system": self.parameters.single_earth_station.system_label,
                "eess_position_label": config.eess_position_label,
                "eess_latitude_deg": float(p619.earth_station_lat_deg),
                "eess_longitude_deg": float(
                    self.parameters.imt.topology.central_longitude),
                "eess_altitude_m": float(p619.earth_station_alt_m),
                "eess_local_x_m": float(self.system.geom.x_global[0]),
                "eess_local_y_m": float(self.system.geom.y_global[0]),
                "eess_local_z_m": float(self.system.geom.z_global[0]),
                "trigger_flag": bool(triggered[bs]),
                "handover_flag": bool(successful[bs]),
                "unresolved_flag": bool(unresolved[bs]),
                "i_link_linear_mw": i_linear_mw,
                "i_link_dbw_per_mhz": i_dbw_mhz,
                "i_agg_linear_mw": aggregate_linear_mw,
                "i_agg_dbw_per_mhz": aggregate_dbw_mhz,
                "risk_threshold_dbw_per_mhz": risk_threshold,
                "iagg_exceeds_risk_threshold": (
                    aggregate_dbw_mhz > risk_threshold),
                "tx_offaxis_to_eess_deg": float(tx_offaxis[bs]),
                "g_tx_toward_eess_dbi": g_tx,
                "g_tx_peak_dbi": g_tx_peak,
                "tx_gain_drop_from_peak_db": tx_drop,
                "service_cell_lat_deg": float(
                    self.topology.beam_grid_center_lat[bs]),
                "service_cell_lon_deg": float(
                    self.topology.beam_grid_center_lon[bs]),
                "satellite_elevation_from_service_cell_deg": float(
                    self.topology.beam_ground_elev_angles[bs]),
                "rx_offaxis_from_eess_boresight_deg": float(rx_offaxis[bs]),
                "eess_boresight_azimuth_deg": float(
                    self.system.geom.pointn_azim_global[0]),
                "eess_boresight_elevation_deg": float(
                    self.system.geom.pointn_elev_global[0]),
                "interferer_azimuth_from_eess_deg": float(
                    interferer_azimuth[0, bs]),
                "interferer_elevation_from_eess_deg": float(
                    interferer_elevation[bs]),
                "g_rx_from_interferer_dbi": g_rx,
                "g_rx_peak_dbi": g_rx_peak,
                "rx_gain_drop_from_peak_db": rx_drop,
                "joint_gain_suppression_db": tx_drop + rx_drop,
                "path_loss_db": float(path_loss[0, bs, 0]),
                "spectral_coupling_db": tx_spectral_power_dbm - tx_power_dbm,
                "tx_conducted_power_dbm": tx_power_dbm,
                "tx_spectral_power_dbm": tx_spectral_power_dbm,
                "tx_spectral_psd_dbm_per_mhz": (
                    tx_spectral_power_dbm - 10.0 * np.log10(bandwidth_mhz)),
                "additional_loss_db": additional_loss_db,
                "geometric_coupling_score_db": geometric_score_db,
                "full_coupling_score_dbm": i_dbm,
                "full_coupling_score_dbw_per_mhz": i_dbw_mhz,
            })

        selected, summary = select_diagnostic_links(
            records, aggregate_linear_mw, config.top_n)
        self.results.interference_link_diagnostics.extend(selected)
        summary.update({
            "snapshot_id": self._diagnostic_snapshot_id,
            "secondary_seed": self._diagnostic_secondary_seed,
            "i_agg_dbw_per_mhz": aggregate_dbw_mhz,
            "risk_threshold_dbw_per_mhz": risk_threshold,
            "iagg_exceeds_risk_threshold": (
                aggregate_dbw_mhz > risk_threshold),
        })
        self.results.interference_link_snapshot_summaries.append(summary)

    def collect_results(self, write_to_file: bool, snapshot_number: int):
        """
        Collect and store results for the current downlink simulation snapshot.

        Args:
            write_to_file (bool): Whether to write results to file.
            snapshot_number (int): The current snapshot number.
        """
        if (self.parameters.imt.topology.type == "MSS_DC"
                and getattr(self.parameters.imt.topology.mss_dc.interference_aware_handover_v2,
                            "performance_only_output", False)):
            # The opt-in performance campaign streams identified UE rows itself.
            # Do not duplicate them or the campaign-07 victim/link samples in RAM/CSV.
            if write_to_file:
                self.results.write_files(snapshot_number)
                self.notify_observers(source=__name__, results=self.results)
            return
        if (
            self.parameters.imt.topology.type == "MSS_DC"
            and self.parameters.imt.topology.mss_dc
            .interference_aware_handover.enabled
        ):
            metrics = self.topology.interference_aware_handover_metrics
            if metrics is None:
                raise RuntimeError(
                    "Handover is enabled but snapshot metrics are missing")
            snapshot_metrics = {"snapshot_id": snapshot_number}
            snapshot_metrics.update(metrics)
            self.results.interference_aware_handover_snapshot_metrics.append(
                snapshot_metrics)

            if (
                self.parameters.imt.topology.mss_dc
                .interference_aware_handover.record_event_details
            ):
                for event in self.topology.interference_aware_handover_events:
                    event_with_snapshot = {"snapshot_id": snapshot_number}
                    event_with_snapshot.update(event)
                    self.results.interference_aware_handover_events.append(
                        event_with_snapshot)

        if not self.parameters.imt.interfered_with and np.any(self.bs.active):
            self.results.system_inr.extend(self.system.inr.flatten())
            self.results.system_dl_interf_power.extend(
                self.system.rx_interference.flatten(),
            )
            self.results.system_dl_interf_power_per_mhz.extend(
                self.system.rx_interference.flatten() - 10 * math.log10(self.system.bandwidth),
            )
            # TODO: generalize this a bit more if needed (same conditional as
            # above)
            if hasattr(
                    self.system.antenna[0],
                    "effective_area") and self.system.num_stations == 1:
                self.results.system_pfd.extend([self.system.pfd])

        if self.parameters.imt.interfered_with:
            self.add_system_imt_interaction_attr_to_results(
                "DL",
                self.coupling_loss_imt_system.T,
                "sys_to_imt_coupling_loss",
            )
            self.add_system_imt_interaction_attr_to_results(
                "DL",
                self.system_imt_pfd,
                "imt_dl_pfd",
            )

        self.add_system_imt_interaction_attr_to_results("DL", "system_imt_antenna_gain")
        if len(self.imt_system_antenna_gain):
            self.add_system_imt_interaction_attr_to_results("DL", "imt_system_antenna_gain")

        if len(self.imt_system_antenna_gain_adjacent):
            self.add_system_imt_interaction_attr_to_results("DL", "imt_system_antenna_gain_adjacent")

        self.add_system_imt_interaction_attr_to_results("DL", "imt_system_path_loss")
        if self.param_system.channel_model == "HDFSS":
            self.add_system_imt_interaction_attr_to_results("DL", "imt_system_build_entry_loss")
            self.add_system_imt_interaction_attr_to_results("DL", "imt_system_diffraction_loss")

        bs_active = np.where(self.bs.active)[0]

        for bs in bs_active:
            ue = self.link[bs]

            #############################################
            # Experimental PFD calculation at UE based on received power
            if self.parameters.imt.ue.antenna.pattern == "ARRAY":
                Gr = self.parameters.imt.ue.antenna.array.element_max_g
                if self.parameters.imt.ue.antenna.array.element_pattern != "FIXED":
                    raise NotImplementedError("PFD with non-FIXED element pattern is not implemented")
            elif self.parameters.imt.ue.antenna.pattern != "OMNI":
                raise NotImplementedError("This antenna pattern is not implemented for PFD calc")
            else:
                Gr = self.parameters.imt.ue.antenna.gain

            # TODO: check if also remove polarization_loss
            L = self.parameters.imt.ue.ohmic_loss \
                + self.parameters.imt.ue.body_loss
            wavelen = SPEED_OF_LIGHT / (self.parameters.imt.frequency * 1e6)
            # self.ue.ext_interference[ue] is already without noise
            # and after coupling loss
            # WARNING: overwriting stuff
            # self.ue.ext_interference is in dBm
            self.ue.pfd_external_aggregated[ue] = self.ue.ext_interference[ue] - 30 - Gr + L - \
                10 * np.log10(wavelen**2 / (4 * np.pi)) - 10 * np.log10(self.ue.bandwidth[ue])
            #############################################

            if not self.parameters.imt.imt_dl_intra_sinr_calculation_disabled:
                self.results.imt_path_loss.extend(self.path_loss_imt[bs, ue])
                self.results.imt_coupling_loss.extend(
                    self.coupling_loss_imt[bs, ue],
                )

                self.results.imt_bs_antenna_gain.extend(
                    self.imt_bs_antenna_gain[bs, ue],
                )
                self.results.imt_ue_antenna_gain.extend(
                    self.imt_ue_antenna_gain[bs, ue],
                )

                tput = self.calculate_imt_tput(
                    self.ue.sinr[ue],
                    self.parameters.imt.downlink.sinr_min,
                    self.parameters.imt.downlink.sinr_max,
                    self.parameters.imt.downlink.attenuation_factor,
                )
                self.results.imt_dl_tput.extend(tput.tolist())
                power_backoff_db = 0.0
                beam_affected_by_pbo = False
                if (
                    hasattr(self.topology, "power_backoff")
                    and self.topology.power_backoff is not None
                ):
                    power_backoff_db = float(self.topology.power_backoff[bs])
                if (hasattr(self.topology, "power_backoff_affected")
                        and self.topology.power_backoff_affected is not None):
                    beam_affected_by_pbo = bool(
                        self.topology.power_backoff_affected[bs])
                else:
                    beam_affected_by_pbo = bool(power_backoff_db != 0.0)

                for idx, ue_id in enumerate(ue):
                    self.results.imt_dl_selected_ue_metrics.append({
                        "snapshot_id": snapshot_number,
                        "ue_id": int(ue_id),
                        "beam_id": int(bs),
                        "beam_active": bool(self.bs.active[bs]),
                        "beam_affected_by_pbo": beam_affected_by_pbo,
                        "power_backoff_db": power_backoff_db,
                        "tx_power_dbm": float(self.bs.tx_power[bs][idx]),
                        "sinr_db": float(self.ue.sinr[ue_id]),
                        "snr_db": float(self.ue.snr[ue_id]),
                        "spectral_efficiency_proxy": float(tput[idx]),
                        "requested_affected_fraction": float(
                            self.topology.requested_affected_fraction),
                        "realized_affected_fraction": float(
                            self.topology.realized_affected_fraction),
                    })

            # Results for IMT-SYSTEM
            if self.parameters.imt.interfered_with:  # IMT suffers interference
                tput_ext = self.calculate_imt_tput(
                    self.ue.sinr_ext[ue],
                    self.parameters.imt.downlink.sinr_min,
                    self.parameters.imt.downlink.sinr_max,
                    self.parameters.imt.downlink.attenuation_factor,
                )
                self.results.imt_dl_tput_ext.extend(tput_ext.tolist())
                self.results.imt_dl_sinr_ext.extend(
                    self.ue.sinr_ext[ue].tolist(),
                )
                self.results.imt_dl_inr.extend(self.ue.inr[ue].tolist())

                self.results.imt_dl_interf_power.extend(
                    (self.ue.ext_interference[ue] - 30).tolist(),
                )

            self.results.imt_dl_tx_power.extend(self.bs.tx_power[bs].tolist())

            if not self.parameters.imt.imt_dl_intra_sinr_calculation_disabled:
                self.results.imt_dl_sinr.extend(self.ue.sinr[ue].tolist())
                self.results.imt_dl_snr.extend(self.ue.snr[ue].tolist())

        if write_to_file:
            self.results.write_files(snapshot_number)
            self.notify_observers(source=__name__, results=self.results)

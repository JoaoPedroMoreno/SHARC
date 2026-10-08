# -*- coding: utf-8 -*-
"""
Created on Thu Mar 23 08:47:46 2017

@author: edgar
"""

import glob
import os
import datetime
import re
import pathlib
import pandas as pd
from shutil import copy
from sharc.support.sharc_logger import SimulationLogger


class SampleList(list):
    """
    This class only exists so that no list property can be confused with a SampleList
    """


class Results(object):
    """Handle the output of the simulator"""

    imt_dl_selected_ue_metrics_columns = [
        "snapshot_id",
        "ue_id",
        "beam_id",
        "beam_active",
        "beam_affected_by_pbo",
        "power_backoff_db",
        "tx_power_dbm",
        "sinr_db",
        "snr_db",
        "spectral_efficiency_proxy",
        "requested_affected_fraction",
        "realized_affected_fraction",
    ]

    interference_aware_handover_snapshot_metrics_columns = [
        "snapshot_id",
        "active_beams_evaluated",
        "primary_main_main_count",
        "handover_trigger_count",
        "successful_handover_count",
        "unresolved_count",
        "reassigned_fraction",
        "unresolved_trigger_fraction",
    ]

    interference_aware_handover_event_columns = [
        "snapshot_id",
        "beam_row_idx",
        "beam_grid_idx",
        "primary_satellite_idx",
        "target_satellite_idx",
        "final_satellite_idx",
        "primary_elevation_deg",
        "target_elevation_deg",
        "delta_elevation_deg",
        "primary_dc_off_axis_deg",
        "primary_eess_off_axis_deg",
        "target_dc_off_axis_deg",
        "target_eess_off_axis_deg",
        "eess_phi_min_deg",
        "eess_system",
        "outcome",
    ]

    interference_link_diagnostic_columns = [
        "snapshot_id", "secondary_seed", "beam_row_idx", "beam_grid_idx",
        "service_cell_id", "primary_satellite_idx", "serving_satellite_idx",
        "target_satellite_idx", "guard_band_mhz", "altitude_km",
        "load_factor", "eess_system", "eess_position_label",
        "eess_latitude_deg", "eess_longitude_deg", "eess_altitude_m", "eess_local_x_m",
        "eess_local_y_m", "eess_local_z_m", "trigger_flag",
        "handover_flag", "unresolved_flag", "i_link_linear_mw",
        "i_link_dbw_per_mhz", "i_agg_linear_mw",
        "i_agg_dbw_per_mhz", "risk_threshold_dbw_per_mhz",
        "iagg_exceeds_risk_threshold", "rank_in_snapshot",
        "fraction_of_iagg_linear", "fraction_top1", "fraction_top3",
        "fraction_top5", "fraction_top10", "tx_offaxis_to_eess_deg",
        "g_tx_toward_eess_dbi", "g_tx_peak_dbi",
        "tx_gain_drop_from_peak_db", "service_cell_lat_deg",
        "service_cell_lon_deg", "satellite_elevation_from_service_cell_deg",
        "rx_offaxis_from_eess_boresight_deg",
        "eess_boresight_azimuth_deg", "eess_boresight_elevation_deg",
        "interferer_azimuth_from_eess_deg",
        "interferer_elevation_from_eess_deg", "g_rx_from_interferer_dbi",
        "g_rx_peak_dbi", "rx_gain_drop_from_peak_db",
        "joint_gain_suppression_db", "path_loss_db",
        "spectral_coupling_db", "tx_conducted_power_dbm",
        "tx_spectral_power_dbm", "tx_spectral_psd_dbm_per_mhz",
        "additional_loss_db", "geometric_coupling_score_db",
        "full_coupling_score_dbm", "full_coupling_score_dbw_per_mhz",
    ]

    interference_link_snapshot_summary_columns = [
        "snapshot_id", "secondary_seed", "active_links_evaluated",
        "recorded_links", "i_agg_linear_mw", "i_agg_dbm",
        "i_agg_dbw_per_mhz", "sum_i_link_linear_mw",
        "sum_error_linear_mw", "fraction_top1", "fraction_top3",
        "fraction_top5", "fraction_top10", "risk_threshold_dbw_per_mhz",
        "iagg_exceeds_risk_threshold",
    ]

    interference_aware_handover_v2_snapshot_columns = [
        "snapshot_id", "secondary_seed", "top_k_links_examined",
        "actuation_flag", "reassigned_beams", "candidates_evaluated",
        "unresolved_count", "risk_gate_dbw_per_mhz", "gate_entered",
        "critical_before", "critical_after", "became_compliant",
        "concentration_c1", "concentration_c1_c3", "iagg_before_linear_mw",
        "iagg_after_linear_mw", "iagg_before_dbw_per_mhz",
        "iagg_after_dbw_per_mhz", "iagg_reduction_db",
        "top1_link_reassigned",
    ]

    interference_aware_handover_v2_event_columns = [
        "snapshot_id", "secondary_seed", "rank_in_snapshot",
        "beam_row_idx", "beam_grid_idx", "current_satellite_idx",
        "selected_satellite_idx", "current_service_elevation_deg",
        "selected_service_elevation_deg", "candidates_evaluated",
        "current_i_linear_mw", "selected_i_linear_mw",
        "predicted_reduction_db", "accepted", "unresolved", "reason",
    ]

    operational_risk_snapshot_columns = [
        "snapshot_id", "secondary_seed", "master_seed", "altitude_km",
        "eess_system", "load_factor", "guard_band_mhz",
        "dc_mss_center_frequency_mhz", "dc_mss_bandwidth_mhz",
        "active_beam_count", "active_beam_rows_sha256",
        "serving_satellite_ids_before_sha256", "eess_latitude_deg",
        "eess_longitude_deg", "eess_altitude_m", "eess_enu_x_m",
        "eess_enu_y_m", "eess_enu_z_m", "eess_pointing_azimuth_deg",
        "eess_pointing_elevation_deg", "eess_boresight_x",
        "eess_boresight_y", "eess_boresight_z", "iagg_before_linear_mw",
        "iagg_after_linear_mw", "iagg_before_dbw_per_mhz",
        "iagg_after_dbw_per_mhz", "critical_before_flag",
        "compliant_after_flag", "risk_gate_triggered",
        "handover_performed", "handover_count", "candidates_evaluated",
        "unresolved_count", "concentration_c1", "concentration_c1_c3",
        "top1_beam_row_idx", "top1_beam_grid_idx", "top1_service_cell_id",
        "top1_serving_satellite_idx", "top1_i_link_linear_mw",
        "top1_i_link_dbw_per_mhz", "top1_satellite_latitude_deg",
        "top1_satellite_longitude_deg", "top1_satellite_altitude_m",
        "top1_satellite_enu_x_m", "top1_satellite_enu_y_m",
        "top1_satellite_enu_z_m", "top1_service_cell_latitude_deg",
        "top1_service_cell_longitude_deg", "top1_tx_offaxis_deg",
        "top1_rx_offaxis_deg", "top1_eess_to_satellite_azimuth_deg",
        "top1_eess_to_satellite_elevation_deg",
        "top1_service_elevation_deg", "top1_tx_gain_dbi",
        "top1_rx_gain_dbi", "top1_joint_gain_suppression_db",
        "top1_path_loss_db", "top1_coupling_loss_db",
        "top1_tx_spectral_power_dbm", "top1_spectral_coupling_db",
    ]

    operational_risk_topk_columns = [
        "snapshot_id", "secondary_seed", "master_seed", "rank_in_snapshot",
        "beam_row_idx", "beam_grid_idx", "service_cell_id",
        "primary_satellite_idx", "serving_satellite_idx",
        "individual_i_linear_mw", "individual_i_dbw_per_mhz",
        "fraction_of_iagg_linear", "iagg_before_linear_mw",
        "iagg_before_dbw_per_mhz", "critical_before_flag",
        "eess_system", "altitude_km", "load_factor", "guard_band_mhz",
        "dc_mss_center_frequency_mhz", "dc_mss_bandwidth_mhz",
        "eess_latitude_deg", "eess_longitude_deg", "eess_altitude_m",
        "eess_enu_x_m", "eess_enu_y_m", "eess_enu_z_m",
        "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
        "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
        "satellite_latitude_deg", "satellite_longitude_deg",
        "satellite_altitude_m", "satellite_enu_x_m", "satellite_enu_y_m",
        "satellite_enu_z_m", "service_cell_latitude_deg",
        "service_cell_longitude_deg", "service_cell_ecef_x_m",
        "service_cell_ecef_y_m", "service_cell_ecef_z_m",
        "service_cell_enu_x_m", "service_cell_enu_y_m",
        "service_cell_enu_z_m", "tx_boresight_azimuth_deg",
        "tx_boresight_elevation_deg", "tx_offaxis_to_eess_deg",
        "rx_offaxis_from_eess_boresight_deg",
        "eess_to_satellite_azimuth_deg", "eess_to_satellite_elevation_deg",
        "service_elevation_deg", "tx_gain_toward_eess_dbi",
        "tx_peak_gain_dbi", "tx_gain_drop_db",
        "rx_gain_from_interferer_dbi", "rx_peak_gain_dbi",
        "rx_gain_drop_db", "joint_gain_suppression_db", "path_loss_db",
        "coupling_loss_db", "additional_loss_db", "tx_conducted_power_dbm",
        "tx_spectral_power_dbm", "tx_spectral_psd_dbm_per_mhz",
        "spectral_coupling_db",
    ]

    operational_risk_handover_event_columns = [
        "snapshot_id", "secondary_seed", "master_seed", "rank_in_snapshot",
        "beam_row_idx", "beam_grid_idx", "service_cell_id", "accepted",
        "unresolved", "reason", "candidates_evaluated",
        "current_satellite_idx", "target_satellite_idx",
        "current_i_linear_mw", "target_i_linear_mw",
        "current_i_dbw_per_mhz", "target_i_dbw_per_mhz",
        "predicted_reduction_db", "service_elevation_loss_deg",
        "delta_rx_offaxis_deg", "delta_tx_offaxis_deg",
        "delta_joint_gain_suppression_db", "iagg_before_linear_mw",
        "iagg_after_linear_mw", "iagg_before_dbw_per_mhz",
        "iagg_after_dbw_per_mhz", "current_service_elevation_deg",
        "target_service_elevation_deg", "current_tx_offaxis_deg",
        "target_tx_offaxis_deg", "current_rx_offaxis_deg",
        "target_rx_offaxis_deg", "current_tx_gain_dbi",
        "target_tx_gain_dbi", "current_rx_gain_dbi", "target_rx_gain_dbi",
        "current_tx_peak_gain_dbi", "target_tx_peak_gain_dbi",
        "current_rx_peak_gain_dbi", "target_rx_peak_gain_dbi",
        "current_joint_gain_suppression_db",
        "target_joint_gain_suppression_db", "current_path_loss_db",
        "target_path_loss_db", "current_coupling_loss_db",
        "target_coupling_loss_db", "current_tx_gain_drop_db",
        "target_tx_gain_drop_db", "current_rx_gain_drop_db",
        "target_rx_gain_drop_db", "current_tx_spectral_power_dbm",
        "target_tx_spectral_power_dbm", "current_spectral_coupling_db",
        "target_spectral_coupling_db", "current_eess_to_satellite_azimuth_deg",
        "target_eess_to_satellite_azimuth_deg",
        "current_eess_to_satellite_elevation_deg",
        "target_eess_to_satellite_elevation_deg",
        "current_tx_boresight_azimuth_deg", "target_tx_boresight_azimuth_deg",
        "current_tx_boresight_elevation_deg",
        "target_tx_boresight_elevation_deg", "current_satellite_latitude_deg",
        "current_satellite_longitude_deg", "current_satellite_altitude_m",
        "current_satellite_enu_x_m", "current_satellite_enu_y_m",
        "current_satellite_enu_z_m", "target_satellite_latitude_deg",
        "target_satellite_longitude_deg", "target_satellite_altitude_m",
        "target_satellite_enu_x_m", "target_satellite_enu_y_m",
        "target_satellite_enu_z_m", "service_cell_latitude_deg",
        "service_cell_longitude_deg", "service_cell_ecef_x_m",
        "service_cell_ecef_y_m", "service_cell_ecef_z_m",
        "service_cell_enu_x_m", "service_cell_enu_y_m",
        "service_cell_enu_z_m", "eess_latitude_deg", "eess_longitude_deg",
        "eess_altitude_m", "eess_enu_x_m", "eess_enu_y_m", "eess_enu_z_m",
        "eess_pointing_azimuth_deg", "eess_pointing_elevation_deg",
        "eess_boresight_x", "eess_boresight_y", "eess_boresight_z",
    ]

    operational_risk_candidate_columns = [
        "snapshot_id", "secondary_seed", "master_seed", "beam_row_idx",
        "beam_grid_idx", "service_cell_id", "current_satellite_idx",
        "candidate_satellite_idx", "candidate_order", "selected_flag",
        "candidate_i_linear_mw", "candidate_service_elevation_deg",
        "candidate_tx_offaxis_deg", "candidate_rx_offaxis_deg",
        "candidate_tx_gain_dbi", "candidate_rx_gain_dbi",
        "candidate_tx_gain_drop_db", "candidate_rx_gain_drop_db",
        "candidate_joint_gain_suppression_db", "candidate_path_loss_db",
        "candidate_coupling_loss_db", "candidate_spectral_coupling_db",
        "candidate_tx_spectral_power_dbm", "candidate_satellite_latitude_deg",
        "candidate_satellite_longitude_deg", "candidate_satellite_altitude_m",
        "candidate_satellite_enu_x_m", "candidate_satellite_enu_y_m",
        "candidate_satellite_enu_z_m",
    ]

    # This should always be true for 1st samples flush
    overwrite_sample_files = True

    def __init__(self):
        # Transmit power density [dBm/Hz]
        self.imt_ul_tx_power_density = SampleList()
        self.imt_ul_tx_power = SampleList()
        # SINR [dB]
        self.imt_ul_sinr_ext = SampleList()
        # SINR [dB]
        self.imt_ul_sinr = SampleList()
        # SNR [dB]
        self.imt_ul_snr = SampleList()
        self.imt_ul_inr = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_ul_tput_ext = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_ul_tput = SampleList()
        # System to IMT interference power [dB] - UL
        self.imt_ul_interf_power = SampleList()

        self.imt_path_loss = SampleList()
        self.imt_coupling_loss = SampleList()
        # Antenna gain [dBi]
        self.imt_bs_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_ue_antenna_gain = SampleList()

        # Antenna gain [dBi]
        self.system_imt_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_system_antenna_gain = SampleList()
        # Antenna gain [dBi]
        self.imt_system_antenna_gain_adjacent = SampleList()

        # Path Loss [dB]
        self.imt_system_path_loss = SampleList()
        # Building entry loss [dB]
        self.imt_system_build_entry_loss = SampleList()
        # System diffraction loss [dB]
        self.imt_system_diffraction_loss = SampleList()
        # System to IMT coupling loss
        self.sys_to_imt_coupling_loss = SampleList()

        self.imt_dl_tx_power_density = SampleList()
        # Transmit power [dBm]
        self.imt_dl_tx_power = SampleList()
        # SINR [dB]
        self.imt_dl_sinr_ext = SampleList()
        # SINR [dB]
        self.imt_dl_sinr = SampleList()
        # SNR [dB]
        self.imt_dl_snr = SampleList()
        # I/N [dB]
        self.imt_dl_inr = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_dl_tput_ext = SampleList()
        # Throughput [bits/s/Hz]
        self.imt_dl_tput = SampleList()
        # System to IMT interference power [dB] - DL
        self.imt_dl_interf_power = SampleList()

        # PFD at the IMT receiver [dBW/m²/MHz]
        self.imt_dl_pfd = SampleList()
        self.imt_dl_aggregated_pfd = SampleList()
        self.imt_ul_pfd = SampleList()

        self.system_ul_coupling_loss = SampleList()
        self.system_ul_interf_power = SampleList()
        # Interference Power [dBm]

        self.system_dl_coupling_loss = SampleList()
        self.system_dl_interf_power = SampleList()
        # Interference Power [dBm/MHz]
        # NOTE: this may not be what you want for a correct
        # protection criteria analysis since it is
        # a mean value. If you have both cochannel
        # and adjacent channel, the adjacent channel interference
        # will always drag the mean down
        self.system_dl_interf_power_per_mhz = SampleList()
        self.system_ul_interf_power_per_mhz = SampleList()

        self.system_inr = SampleList()
        self.system_pfd = SampleList()
        self.system_rx_interf = SampleList()
        self.imt_dl_selected_ue_metrics = []
        self.interference_aware_handover_snapshot_metrics = []
        self.interference_aware_handover_events = []
        self.interference_link_diagnostics = []
        self.interference_link_snapshot_summaries = []
        self.interference_aware_handover_v2_snapshots = []
        self.interference_aware_handover_v2_events = []
        self.operational_risk_snapshots = []
        self.operational_risk_topk = []
        self.operational_risk_handover_events = []
        self.operational_risk_candidates = []
        self._structured_files_initialized = set()

        self.__sharc_dir = pathlib.Path(__file__).parent.resolve()

    def prepare_to_write(
        self,
        parameters_filename: str,
        overwrite_output: bool,
        output_dir="output",
        output_dir_prefix="output",
    ):
        """Prepare the output directory and filenames for writing results.

        Parameters
        ----------
        parameters_filename : str
            Name of the parameters file.
        overwrite_output : bool
            Whether to overwrite existing output.
        output_dir : str, optional
            Parent output directory. Default is "output".
        output_dir_prefix : str, optional
            Prefix for output directory. Default is "output".
        """
        self.output_dir_parent = output_dir

        if not overwrite_output:
            today = datetime.date.today()

            results_number = 1
            results_dir_head = (
                output_dir_prefix + "_" + today.isoformat() + "_" + "{:02n}"
            )
            self.create_dir(results_number, results_dir_head)
            copy(parameters_filename, self.output_directory)

        else:
            self.output_directory = self.__sharc_dir / self.output_dir_parent
            try:
                os.makedirs(self.output_directory)
            except FileExistsError:
                pass
        SimulationLogger.set_output_dir(self.output_directory)

        return self

    def create_dir(self, results_number: int, dir_head: str):
        """Creates the output directory if it doesn't exist.

        Parameters
        ----------
        results_number : int
            Increment used in directory name
        dir_head : str
            Directory name prefix

        Returns
        -------
        str
            output directory name
        """

        dir_head_complete = (
            self.__sharc_dir /
            self.output_dir_parent /
            dir_head.format(results_number))

        try:
            os.makedirs(dir_head_complete)
            self.output_directory = dir_head_complete
        except FileExistsError:
            self.create_dir(results_number + 1, dir_head)

    def get_relevant_attributes(self):
        """
        Returns the attributes that are used for storing samples
        """
        self_dict = self.__dict__

        results_relevant_attr_names = list(
            filter(
                lambda x: isinstance(
                    getattr(
                        self,
                        x),
                    SampleList),
                self_dict))

        return results_relevant_attr_names

    def _write_structured_rows(
        self,
        filename: str,
        rows: list[dict],
        columns: list[str],
    ) -> None:
        """Write a structured CSV with an independent first-write state."""
        if not rows:
            return
        file_path = os.path.join(self.output_directory, filename)
        first_write = filename not in self._structured_files_initialized
        pd.DataFrame(rows, columns=columns).to_csv(
            file_path,
            mode="w" if first_write else "a",
            index=False,
            header=first_write,
        )
        self._structured_files_initialized.add(filename)

    def write_files(self, snapshot_number: int):
        """Writes the sample data to the output file

        Parameters
        ----------
        snapshot_number : int
            Current snapshot number
        """
        results_relevant_attr_names = self.get_relevant_attributes()
        for attr_name in results_relevant_attr_names:
            file_path = os.path.join(
                self.output_directory,
                attr_name + ".csv",
            )
            samples = getattr(self, attr_name)
            if len(samples) == 0:
                continue
            df = pd.DataFrame({"samples": samples})
            if self.overwrite_sample_files:
                df.to_csv(file_path, mode="w", index=False)
            else:
                df.to_csv(file_path, mode="a", index=False, header=False)
            setattr(self, attr_name, SampleList())

        if self.imt_dl_selected_ue_metrics:
            file_path = os.path.join(
                self.output_directory,
                "imt_dl_selected_ue_metrics.csv",
            )
            df = pd.DataFrame(
                self.imt_dl_selected_ue_metrics,
                columns=self.imt_dl_selected_ue_metrics_columns,
            )
            if self.overwrite_sample_files:
                df.to_csv(file_path, mode="w", index=False)
            else:
                df.to_csv(file_path, mode="a", index=False, header=False)
            self.imt_dl_selected_ue_metrics = []

        self._write_structured_rows(
            "interference_aware_handover_snapshot_metrics.csv",
            self.interference_aware_handover_snapshot_metrics,
            self.interference_aware_handover_snapshot_metrics_columns,
        )
        self.interference_aware_handover_snapshot_metrics = []

        self._write_structured_rows(
            "interference_aware_handover_events.csv",
            self.interference_aware_handover_events,
            self.interference_aware_handover_event_columns,
        )
        self.interference_aware_handover_events = []

        self._write_structured_rows(
            "interference_link_diagnostics.csv",
            self.interference_link_diagnostics,
            self.interference_link_diagnostic_columns,
        )
        self.interference_link_diagnostics = []

        self._write_structured_rows(
            "interference_link_snapshot_summary.csv",
            self.interference_link_snapshot_summaries,
            self.interference_link_snapshot_summary_columns,
        )
        self.interference_link_snapshot_summaries = []

        self._write_structured_rows(
            "interference_aware_handover_v2_snapshot.csv",
            self.interference_aware_handover_v2_snapshots,
            self.interference_aware_handover_v2_snapshot_columns,
        )
        self.interference_aware_handover_v2_snapshots = []

        self._write_structured_rows(
            "interference_aware_handover_v2_events.csv",
            self.interference_aware_handover_v2_events,
            self.interference_aware_handover_v2_event_columns,
        )
        self.interference_aware_handover_v2_events = []

        self._write_structured_rows(
            "operational_risk_snapshot.csv",
            self.operational_risk_snapshots,
            self.operational_risk_snapshot_columns,
        )
        self.operational_risk_snapshots = []

        self._write_structured_rows(
            "operational_risk_topk.csv",
            self.operational_risk_topk,
            self.operational_risk_topk_columns,
        )
        self.operational_risk_topk = []

        self._write_structured_rows(
            "operational_risk_handover_events.csv",
            self.operational_risk_handover_events,
            self.operational_risk_handover_event_columns,
        )
        self.operational_risk_handover_events = []

        self._write_structured_rows(
            "operational_risk_candidates.csv",
            self.operational_risk_candidates,
            self.operational_risk_candidate_columns,
        )
        self.operational_risk_candidates = []

        if self.overwrite_sample_files:
            self.overwrite_sample_files = False

    @staticmethod
    def load_many_from_dir(
        root_dir: str,
        *,
        only_latest=True,
        only_samples: list[str] = None,
        filter_fn=None,
    ) -> list["Results"]:
        """
        Load multiple Results objects from a directory containing output folders.

        Args:
            root_dir (str): The root directory to search for output folders.
            only_latest (bool, optional): If True, only load the most recent output for each prefix. Defaults to True.
            only_samples (list[str], optional): List of sample names to load. If None, load all samples. Defaults to None.
            filter_fn (callable, optional): Function to filter output directories. Defaults to None.

        Returns:
            list[Results]: A list of loaded Results objects.
        """
        output_dirs = sorted(list(glob.glob(f"{root_dir}/output_*")))

        if len(output_dirs) == 0:
            print("[WARNING]: Results.load_many_from_dir did not find any results")

        if only_latest:
            output_dirs = Results.get_most_recent_outputs_for_each_prefix(
                output_dirs)

        if filter_fn:
            output_dirs = filter(filter_fn, output_dirs)

        all_res = []
        for output_dir in output_dirs:
            res = Results()
            res.load_from_dir(output_dir, only_samples=only_samples)
            all_res.append(res)

        return all_res

    def load_from_dir(
            self,
            abs_path: str,
            *,
            only_samples: list[str] = None) -> "Results":
        """
        Load results from a specified directory, optionally loading only specified samples.

        Args:
            abs_path (str): Absolute path to the output directory.
            only_samples (list[str], optional): List of sample names to load. If None, load all samples. Defaults to None.

        Returns:
            Results: The Results object with loaded data.
        """
        self.output_directory = abs_path

        self_dict = self.__dict__
        if only_samples is not None:
            results_relevant_attr_names = only_samples
        else:
            results_relevant_attr_names = filter(
                lambda x: isinstance(getattr(self, x), SampleList), self_dict
            )

        for attr_name in results_relevant_attr_names:
            file_path = os.path.join(abs_path, f"{attr_name}.csv")
            if os.path.exists(file_path):
                try:
                    # Try reading the .csv file using pandas with different
                    # delimiters
                    try:
                        data = pd.read_csv(file_path, delimiter=",")
                    except pd.errors.ParserError:
                        data = pd.read_csv(file_path, delimiter=";")

                    # Ensure the data has exactly one column
                    if data.shape[1] != 1:
                        raise Exception(
                            f"The file with samples of {attr_name} should have a single column.", )

                    # Remove rows that do not contain valid numeric values
                    data = data.apply(pd.to_numeric, errors="coerce").dropna()

                    # Ignore if there is no data
                    if data.empty:
                        continue
                    # Check if there is enough data to load results from.

                    setattr(self, attr_name, SampleList(data.to_numpy()[:, 0]))

                except Exception as e:
                    print(e)
                    raise Exception(
                        f"Error processing the sample file ({attr_name}.csv) for {attr_name}: {e}")

        return self

    @staticmethod
    def get_most_recent_outputs_for_each_prefix(
            dirnames: list[str]) -> list[str]:
        """
        Get the most recent output directory for each output prefix.

        Args:
            dirnames (list[str]): A list of output directory names.

        Returns:
            list[str]: A list containing the most recent output dirname for each output_prefix.
        """
        res = {}

        for dirname in dirnames:
            prefix, date, id = Results.get_prefix_date_and_id(dirname)
            res.setdefault(
                prefix, {
                    "date": date, "id": id, "dirname": dirname})
            if date > res[prefix]["date"]:
                res[prefix]["date"] = date
                res[prefix]["id"] = id
                res[prefix]["dirname"] = dirname
            if date == res[prefix]["date"] and id > res[prefix]["id"]:
                res[prefix]["id"] = id
                res[prefix]["dirname"] = dirname

        return list(map(lambda x: x["dirname"], res.values()))

    @staticmethod
    def get_prefix_date_and_id(dirname: str) -> tuple[str, str, str]:
        """
        Extract the prefix, date, and id from a directory name.

        Args:
            dirname (str): The directory name to parse.

        Returns:
            tuple: A tuple containing the prefix, date, and id as strings.
        """
        mtch = re.search(
            "(.*)(20[2-9][0-9]-[0-1][0-9]-[0-3][0-9])_([0-9]{2})",
            dirname)
        prefix, date, id = mtch.group(1), mtch.group(2), mtch.group(3)
        return prefix, date, id

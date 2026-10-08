# Parameters for the IMT MSS-DC topology.
from dataclasses import dataclass, field
import numpy as np
import typing
from pathlib import Path

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_orbit import ParametersOrbit
from sharc.parameters.imt.parameters_grid import (
    ParametersSatelliteWithServiceGrid,
    ParametersSelectActiveSatellite,
    ParametersZone,
)

SHARC_ROOT_DIR = (Path(__file__) / ".." / ".." / ".." / "..").resolve()


@dataclass
class ParametersSectorPositioning(ParametersBase):
    """Dataclass for sector positioning parameters in the IMT MSS-DC topology."""

    @dataclass
    class ParametersSectorValue(ParametersBase):
        @dataclass
        class ParametersSectorValueDistribution(ParametersBase):
            min: float = None
            max: float = None

        __ALLOWED_TYPES = [
            "FIXED",
            "~U(MIN,MAX)",
            "~SQRT(U(0,1))*MAX",
        ]
        # # this distribution can be used when you wish to have a uniform area distribution
        # # over the area of a cone base (circle)
        # # uniform dist over area of circle is sqrt(U(0,1))*max_radius for radius dist
        # "~ATAN(SQRT(U(0,1))*TAN(MAX))",
        type: typing.Literal[
            "FIXED",
            "~U(MIN,MAX)",
            "~SQRT(U(0,1))*MAX",
        ] = "FIXED"

        MIN_VALUE: float = None
        MAX_VALUE: float = None

        fixed: float = 0.0
        distribution: ParametersSectorValueDistribution = field(
            default_factory=ParametersSectorValueDistribution)

        def validate(self, ctx):
            """
            Validate the sector value parameters.

            Ensures that the type and value constraints are satisfied for the sector value.

            Parameters
            ----------
            ctx : str
                Context string for error messages.
            """
            if self.type not in self.__ALLOWED_TYPES:
                raise ValueError(
                    f"{ctx}.type = {
                        self.type} is not one of the accepted values:\n{
                        self.__ALLOWED_TYPES}")
            match self.type:
                case "FIXED":
                    if not (
                        isinstance(
                            self.fixed,
                            float) or isinstance(
                            self.fixed,
                            int)):
                        raise ValueError(f"{ctx}.fixed must be a number")
                    if self.MIN_VALUE is not None:
                        if self.fixed < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.fixed must be at least {
                                    self.MIN_VALUE}")
                    if self.MAX_VALUE is not None:
                        if self.fixed > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.fixed must be at least {
                                    self.MAX_VALUE}")
                case "~U(MIN,MAX)":
                    if not (
                        isinstance(
                            self.distribution.min,
                            float) or isinstance(
                            self.distribution.max,
                            int)):
                        raise ValueError(
                            f"{ctx}.distribution.min must be a number")

                    if not (
                        isinstance(
                            self.distribution.max,
                            float) or isinstance(
                            self.distribution.max,
                            int)):
                        raise ValueError(
                            f"{ctx}.distribution.max must be a number")

                    if self.distribution.max <= self.distribution.min:
                        raise ValueError(
                            f"{ctx}.distribution.max must be bigger than {ctx}.distribution.max")

                    if self.MIN_VALUE is not None:
                        if self.distribution.min < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.min must be at least {
                                    self.MIN_VALUE}")
                        if self.distribution.max < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.max must be at least {
                                    self.MIN_VALUE}")

                    if self.MAX_VALUE is not None:
                        if self.distribution.min > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.min must be at least {
                                    self.MAX_VALUE}")
                        if self.distribution.max > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.max must be at least {
                                    self.MAX_VALUE}")
                case _:
                    raise NotImplementedError(
                        f"No validation implemented for {ctx}.type = {
                            self.type}")

    __ALLOWED_TYPES = [
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
        "SERVICE_GRID",
    ]

    type: typing.Literal[
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
        "SERVICE_GRID",
    ] = "ANGLE_FROM_SUBSATELLITE"

    # theta is the off axis angle from satellite nadir
    angle_from_subsatellite_theta: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue())

    # phi completes polar coordinates
    # equivalent to "azimuth" from subsatellite in earth plane
    angle_from_subsatellite_phi: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(
            MIN_VALUE=-180.0, MAX_VALUE=180.0))

    # distance from subsatellite. Substitutes theta
    distance_from_subsatellite: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(
            MIN_VALUE=0.0))

    service_grid: ParametersSatelliteWithServiceGrid = field(
        default_factory=ParametersSatelliteWithServiceGrid)

    def validate(self, ctx):
        """
        Validate the sector positioning parameters.

        Ensures that the type and nested parameters are valid for the sector positioning configuration.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        if self.type not in self.__ALLOWED_TYPES:
            raise ValueError(
                f"{ctx}.type = {
                    self.type} is not one of the accepted values:\n{
                    self.__ALLOWED_TYPES}")
        match self.type:
            case "ANGLE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(
                    f"{ctx}.angle_from_subsatellite_theta")
                self.angle_from_subsatellite_phi.validate(
                    f"{ctx}.angle_from_subsatellite_phi")
            case "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(
                    f"{ctx}.angle_from_subsatellite_theta")
            case "SERVICE_GRID":
                self.service_grid.validate(f"{ctx}.service_grid")
            case _:
                raise NotImplementedError(
                    f"No validation implemented for {ctx}.type = {self.type}"
                )


@dataclass
class ParametersPowerControlZone(ParametersBase):
    """Dataclass for a power control zone in the IMT MSS-DC topology."""
    geometry: ParametersZone = field(default_factory=ParametersZone)
    power_backoff_db: float = None


@dataclass
class ParametersPowerControl(ParametersBase):
    """Dataclass for power control parameters in the IMT MSS-DC topology."""
    zones: list[ParametersPowerControlZone] = field(
        default_factory=lambda: [ParametersPowerControlZone()])
    mode: typing.Literal["GEOGRAPHIC", "ACTIVE_FRACTION"] = "GEOGRAPHIC"
    power_backoff_db: float = 0.0
    affected_fraction: float = 1.0

    def validate(self, ctx):
        """
        Validate the power control parameters.
        """
        super().validate(ctx)
        self.mode = self.mode.upper()
        if self.mode not in ["GEOGRAPHIC", "ACTIVE_FRACTION"]:
            raise ValueError(
                f"{ctx}.mode must be GEOGRAPHIC or ACTIVE_FRACTION")
        if not isinstance(self.power_backoff_db, (float, int)):
            raise ValueError(f"{ctx}.power_backoff_db needs to be a number")
        if self.power_backoff_db < 0.0:
            raise ValueError(f"{ctx}.power_backoff_db needs to be non-negative")
        self.power_backoff_db = float(self.power_backoff_db)
        if not isinstance(self.affected_fraction, (float, int)):
            raise ValueError(f"{ctx}.affected_fraction needs to be a number")
        if self.affected_fraction < 0.0 or self.affected_fraction > 1.0:
            raise ValueError(f"{ctx}.affected_fraction needs to be in [0, 1]")
        self.affected_fraction = float(self.affected_fraction)
        for i in range(len(self.zones)):
            self.zones[i].geometry.validate(ctx + f"zones.{i}.geometry")
            if not isinstance(self.zones[i].power_backoff_db, (float, int)):
                self.zones[i].power_backoff_db = 0.0  # Default to 0 dB if not set - we make sure it's not applied later.
            else:
                self.zones[i].power_backoff_db = float(
                    self.zones[i].power_backoff_db)


@dataclass
class ParametersInterferenceAwareHandover(ParametersBase):
    """Snapshot-based Interference-Aware Inter-Satellite Handover settings."""

    enabled: bool = False
    dc_mss_off_axis_limit_deg: float = 4.322755
    eess_boundary: typing.Literal[
        "S465_MAX_GAIN_REGION",
    ] = "S465_MAX_GAIN_REGION"
    unresolved_policy: typing.Literal[
        "KEEP_PRIMARY_AND_FLAG",
    ] = "KEEP_PRIMARY_AND_FLAG"
    record_event_details: bool = False

    def validate(self, ctx: str):
        """Validate supported detector and unresolved-event policies."""
        if not isinstance(self.enabled, bool):
            raise ValueError(f"{ctx}.enabled must be a boolean")
        if isinstance(self.dc_mss_off_axis_limit_deg, bool) or not isinstance(
            self.dc_mss_off_axis_limit_deg, (int, float)
        ):
            raise ValueError(
                f"{ctx}.dc_mss_off_axis_limit_deg must be a number")
        if not 0.0 <= self.dc_mss_off_axis_limit_deg <= 180.0:
            raise ValueError(
                f"{ctx}.dc_mss_off_axis_limit_deg must be in [0, 180]")
        self.dc_mss_off_axis_limit_deg = float(
            self.dc_mss_off_axis_limit_deg)
        if not isinstance(self.eess_boundary, str):
            raise ValueError(f"{ctx}.eess_boundary must be a string")
        self.eess_boundary = self.eess_boundary.upper()
        if self.eess_boundary != "S465_MAX_GAIN_REGION":
            raise ValueError(
                f"{ctx}.eess_boundary only supports "
                "S465_MAX_GAIN_REGION")
        if not isinstance(self.unresolved_policy, str):
            raise ValueError(f"{ctx}.unresolved_policy must be a string")
        self.unresolved_policy = self.unresolved_policy.upper()
        if self.unresolved_policy != "KEEP_PRIMARY_AND_FLAG":
            raise ValueError(
                f"{ctx}.unresolved_policy only supports "
                "KEEP_PRIMARY_AND_FLAG")
        if not isinstance(self.record_event_details, bool):
            raise ValueError(
                f"{ctx}.record_event_details must be a boolean")


@dataclass
class ParametersInterferenceLinkDiagnostics(ParametersBase):
    """Optional per-link diagnostics; never participates in decisions."""

    enabled: bool = False
    top_n: int = 10
    eess_position_label: str = ""

    def validate(self, ctx: str):
        if not isinstance(self.enabled, bool):
            raise ValueError(f"{ctx}.enabled must be a boolean")
        if isinstance(self.top_n, bool) or not isinstance(self.top_n, int):
            raise ValueError(f"{ctx}.top_n must be an integer")
        if self.top_n < 1:
            raise ValueError(f"{ctx}.top_n must be at least 1")
        if not isinstance(self.eess_position_label, str):
            raise ValueError(
                f"{ctx}.eess_position_label must be a string")


@dataclass
class ParametersInterferenceAwareHandoverV2(ParametersBase):
    """Interference-ranked serving-satellite handover research strategy."""

    enabled: bool = False
    top_k: int = 3
    min_reduction_db: float = 0.0
    max_service_elevation_loss_deg: float = 90.0
    max_handovers_per_snapshot: int = 1
    trigger_mode: typing.Literal[
        "ORACLE_TOP_K", "RISK_GATED_TOP_K", "GEOMETRIC_RULE"
    ] = "ORACLE_TOP_K"
    risk_gate_dbw_per_mhz: float = -154.0
    record_candidate_details: bool = False

    def validate(self, ctx: str):
        if not isinstance(self.enabled, bool):
            raise ValueError(f"{ctx}.enabled must be a boolean")
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int):
            raise ValueError(f"{ctx}.top_k must be an integer")
        if self.top_k < 1:
            raise ValueError(f"{ctx}.top_k must be at least 1")
        for name in [
            "min_reduction_db", "max_service_elevation_loss_deg"
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{ctx}.{name} must be a number")
            if value < 0.0:
                raise ValueError(f"{ctx}.{name} must be non-negative")
            setattr(self, name, float(value))
        if (isinstance(self.max_handovers_per_snapshot, bool)
                or not isinstance(self.max_handovers_per_snapshot, int)):
            raise ValueError(
                f"{ctx}.max_handovers_per_snapshot must be an integer")
        if self.max_handovers_per_snapshot < 1:
            raise ValueError(
                f"{ctx}.max_handovers_per_snapshot must be at least 1")
        if not isinstance(self.trigger_mode, str):
            raise ValueError(f"{ctx}.trigger_mode must be a string")
        self.trigger_mode = self.trigger_mode.upper()
        if self.trigger_mode not in {
            "ORACLE_TOP_K", "RISK_GATED_TOP_K", "GEOMETRIC_RULE"
        }:
            raise ValueError(
                f"{ctx}.trigger_mode must be ORACLE_TOP_K, "
                "RISK_GATED_TOP_K or GEOMETRIC_RULE")
        if (isinstance(self.risk_gate_dbw_per_mhz, bool)
                or not isinstance(self.risk_gate_dbw_per_mhz, (int, float))):
            raise ValueError(
                f"{ctx}.risk_gate_dbw_per_mhz must be a number")
        self.risk_gate_dbw_per_mhz = float(self.risk_gate_dbw_per_mhz)
        if self.enabled and self.trigger_mode == "GEOMETRIC_RULE":
            raise ValueError(
                f"{ctx}.GEOMETRIC_RULE is reserved until empirical "
                "thresholds are configured")
        if not isinstance(self.record_candidate_details, bool):
            raise ValueError(
                f"{ctx}.record_candidate_details must be a boolean")


@dataclass
class ParametersOperationalRiskDiagnostics(ParametersBase):
    """Passive snapshot/link instrumentation for operational-risk research."""

    enabled: bool = False
    record_snapshot_summary: bool = True
    record_top_k: int = 3
    record_handover_events: bool = True
    record_candidate_details: bool = False

    def validate(self, ctx: str):
        for name in (
            "enabled", "record_snapshot_summary", "record_handover_events",
            "record_candidate_details",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{ctx}.{name} must be a boolean")
        if (isinstance(self.record_top_k, bool)
                or not isinstance(self.record_top_k, int)):
            raise ValueError(f"{ctx}.record_top_k must be an integer")
        if self.record_top_k < 1:
            raise ValueError(f"{ctx}.record_top_k must be at least 1")


@dataclass
class ParametersImtMssDc(ParametersBase):
    """Dataclass for the IMT MSS-DC topology parameters."""
    section_name: str = "imt_mss_dc"

    nested_parameters_enabled = True

    # MSS_D2D system name
    name: str = "SystemA"

    # Orbit parameters
    orbits: list[ParametersOrbit] = field(
        default_factory=lambda: [ParametersOrbit()])

    # Number of beams
    num_beams: int = 19

    # Maximum number of beams used by System 3 OOB normalization. Campaigns
    # with the OOB antenna disabled retain this value as inert metadata.
    N_max_beam: int = 100

    # Beam radius in meters
    # The beam radius should be calculated based on the Antenna Pattern used
    # for IMT Space Stations
    beam_radius: float = 36516.0

    power_control_zones: ParametersPowerControl = field(
        default_factory=ParametersPowerControl)

    interference_aware_handover: ParametersInterferenceAwareHandover = field(
        default_factory=ParametersInterferenceAwareHandover)

    interference_link_diagnostics: ParametersInterferenceLinkDiagnostics = field(
        default_factory=ParametersInterferenceLinkDiagnostics)

    interference_aware_handover_v2: ParametersInterferenceAwareHandoverV2 = field(
        default_factory=ParametersInterferenceAwareHandoverV2)

    operational_risk_diagnostics: ParametersOperationalRiskDiagnostics = field(
        default_factory=ParametersOperationalRiskDiagnostics)

    sat_is_active_if: ParametersSelectActiveSatellite = field(
        default_factory=ParametersSelectActiveSatellite)

    beam_positioning: ParametersSectorPositioning = field(
        default_factory=ParametersSectorPositioning)

    def propagate_parameters(self):
        """
        Propagate relevant parameters from the top-level configuration to nested parameter objects.

        Ensures that the service grid's beam radius and country-related parameters are set based on the main configuration.
        """
        if self.beam_positioning.service_grid.beam_radius is None:
            self.beam_positioning.service_grid.beam_radius = self.beam_radius

        self.beam_positioning.service_grid.load_from_active_sat_conditions(
            self.sat_is_active_if,
        )

    def validate(self, ctx: str):
        """
        Validate the IMT MSS DC parameters for correctness.

        Parameters
        ----------
        ctx : str
            Context string for error messages.

        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        # Now do the sanity check for some parameters
        if self.num_beams not in [1, 7, 19]:
            raise ValueError(
                f"{ctx}.num_beams: Invalid number of sectors {
                    self.num_sectors}")

        if self.beam_radius <= 0:
            raise ValueError(
                f"{ctx}.beam_radius: cell_radius must be greater than 0, but is {
                    self.cell_radius}")
        else:
            self.cell_radius = self.beam_radius
            self.intersite_distance = np.sqrt(3) * self.cell_radius

        self.propagate_parameters()

        if (
            self.interference_aware_handover.enabled
            and self.beam_positioning.type != "SERVICE_GRID"
        ):
            raise ValueError(
                f"{ctx}.interference_aware_handover requires "
                "beam_positioning.type = SERVICE_GRID")

        if (
            self.interference_aware_handover_v2.enabled
            and self.beam_positioning.type != "SERVICE_GRID"
        ):
            raise ValueError(
                f"{ctx}.interference_aware_handover_v2 requires "
                "beam_positioning.type = SERVICE_GRID")
        if (self.interference_aware_handover.enabled
                and self.interference_aware_handover_v2.enabled):
            raise ValueError(
                f"{ctx}: legacy and V2 handover cannot be enabled together")

        super().validate(ctx)

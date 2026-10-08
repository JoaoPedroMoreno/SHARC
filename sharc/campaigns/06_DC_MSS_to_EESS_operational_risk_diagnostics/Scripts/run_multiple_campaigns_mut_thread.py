from sharc.run_multiple_campaigns_mut_thread import run_campaign_re


run_campaign_re(
    "06_DC_MSS_to_EESS_operational_risk_diagnostics",
    r"^operational_risk_(340|525)km_EESS_(B|D)_SA_P_OM_0_"
    r"lf_(0\.2|0\.5)_GB_(80|75|70|65|60|10)MHz_V2_RISK_GATE\.yaml$",
)

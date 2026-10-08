from sharc.run_multiple_campaigns_mut_thread import run_campaign_re

# Set the campaign name
# The name of the campaign to run. This should match the name of the
# campaign directory.
name_campaign = "04_DC_MSS_to_EESS"

# Run the campaigns
# This function will execute the campaign with the given name.
# It will look for the campaign directory under the specified name and
# start the necessary processes.
run_campaign_re(
    name_campaign,
    r"^system_(340|525)km_EESS_(B|D)_SA_P_OM_0_lf_(0\.2|0\.5)_"
    r"GB_(10|5)MHz_STRATEGY_V2_RISK_GATE\.yaml$",
)

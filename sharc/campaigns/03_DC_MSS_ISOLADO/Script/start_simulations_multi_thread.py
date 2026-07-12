import os

from sharc.run_multiple_campaigns_mut_thread import run_campaign


os.environ["SHARC_FORCE_IMT_BS_TO_UE_MAIN_BEAM"] = "1"
run_campaign("03_DC_MSS_ISOLADO")

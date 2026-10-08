# Final scientific figure manifest

All numerical figures were regenerated from completed campaign outputs; no new
Monte Carlo snapshots were executed. The final-performance set contains 56 runs
(5,000 snapshots each), and the operational-geometry set contains 48 complete
runs. The EESS pointing is **realized per snapshot from the configured uniform
azimuth/elevation distributions**; it is not physically fixed. Figures 1, 7 and
8 therefore use the realized pointing stored for each snapshot, under the
operational interpretation that instantaneous pointing could be shared through
cooperative/self-reporting coordination.

The common scenario label is `altitude-EESS-load`, e.g. `340-B-0.5`.
Safe means `Iagg,before <= -154 dBW/MHz`; critical means
`Iagg,before > -154 dBW/MHz`.

## Fig. 1 - `fig01_scenario_reassociation`

- **Scientific purpose:** show the real South-American geometry and same-cell
  inter-satellite reassociation for a representative successful GB=10 event.
- **Script/source:** `scripts/01_scenario_reassociation.py` orchestrates
  `source/blender/render_fig01_article.py` and
  `source/blender/compose_fig01_article.py`; the Blender source is saved as
  `source/blender/fig01_scenario_reassociation.blend`. Natural Earth country
  geometry comes from `sharc/data/countries`, and the realized geometry comes
  from `operational_risk_handover_events.csv`.
- **Filter/selection:** accepted GB=10 events; minimum normalized absolute
  deviation from the event medians of predicted reduction and service-elevation
  loss.
- **Representative event:** scenario `525-D-0.5`, snapshot `3415`, serving
  satellite `1334`, target satellite `1576`, predicted reduction `48.629964 dB`,
  service-elevation loss `68.338098 deg`.
- **Processed data:** `data/fig01_representative_event.csv` and
  `representative_snapshot.txt`.
- **Final size/type:** 3600 x 2100 px PNG, designed for double-column use.
- **Final PNG:** `final/fig01_scenario_reassociation.png` (600 dpi).
- **Suggested caption:** *Simulated coexistence geometry and interference-aware
  inter-satellite reassociation. (a) Representative event from the final
  DC-MSS-EESS campaign. (b) Reassociation of the same service cell from the
  serving satellite to an eligible target producing lower interference toward
  the EESS earth station; the realized EESS pointing is assumed available
  through cooperative information sharing.*

## Fig. 2 - `fig02_spectral_mask`

- **Scientific purpose:** explain the spectral discontinuity between GB=10 and
  GB=5 MHz.
- **Script/source:** `scripts/02_spectral_mask.py`; the production
  `SpectralMaskMSS` implementation instantiated with channel bandwidth 5 MHz,
  campaign TX power 42.8 dBm and spurious level -13 dBm/MHz.
- **Datasets/scenarios:** deterministic mask values for fc=2187.5 and 2192.5 MHz;
  EESS B (2200-2204 MHz) and D (2200-2206 MHz).
- **Metric:** spectral mask value returned by SHARC at each frequency.
- **Processed data:** `data/fig02_data.csv`.
- **Final size/type:** 7.1 x 3.05 in, double-column.
- **Final PNG:** `final/fig02_spectral_mask.png` (600 dpi).
- **Suggested caption:** *Implemented DC-MSS spectral mask for GB=10 and GB=5
  MHz. At GB=10 MHz the EESS bands remain on the -13 dBm/MHz spurious floor,
  whereas at GB=5 MHz they enter the transition region of the implemented mask.*

## Fig. 3 - `fig03_v2_flowchart`

- **Scientific purpose:** document the exact risk-gated V2 decision flow.
- **Script/source:** `scripts/03_v2_flowchart.py`; final V2 configuration
  (`RISK_GATED_TOP_K`, threshold -154 dBW/MHz, K=3, one reassociation maximum).
- **Metric definitions:** all individual contributions and aggregate updates are
  in linear power; the service cell is preserved.
- **Final size/type:** 7.1 x 3.2 in, double-column.
- **Final PNG:** `final/fig03_v2_flowchart.png` (600 dpi).
- **Suggested caption:** *Risk-gated interference-aware inter-satellite
  reassociation used in the final campaign. Candidate interference is evaluated
  for the same service cell and the aggregate is updated in linear power.*

## Fig. 4 - `fig04_exceedance_gb10_gb5`

- **Scientific purpose:** compare empirical protection-criterion exceedance
  before and after V2 at GB=10 and GB=5 MHz.
- **Script/source:** `scripts/04_exceedance.py`;
  `interference_aware_handover_v2_snapshot.csv` from 16 completed final runs.
- **Scenarios/filter:** all eight altitude/EESS/load scenarios; GB in {10, 5};
  5,000 paired snapshots per run.
- **Metric:** `100 * mean(Iagg > -154 dBW/MHz)` using before/after values from
  the same Monte Carlo realization.
- **Processed data:** `data/fig04_data.csv`.
- **Final size/type:** 7.1 x 3.35 in, double-column.
- **Final PNG:** `final/fig04_exceedance_gb10_gb5.png` (600 dpi).
- **Suggested caption:** *Empirical exceedance probability before and after V2
  for GB=10 and GB=5 MHz. Markers are paired within the same 5,000-snapshot
  realization; the dashed line denotes the 1% protection criterion.*

## Fig. 5 - `fig05_mitigation_behavior`

- **Scientific purpose:** quantify mitigation magnitude and how often V2 acts.
- **Script/source:** `scripts/05_mitigation_behavior.py`;
  `interference_aware_handover_v2_snapshot.csv` from the same 16 runs as Fig. 4.
- **Metrics:** median `Iagg,before - Iagg,after` in dB only over acted snapshots;
  activation rate is the fraction of all snapshots with reassignment.
- **Processed data:** `data/fig05_data.csv`.
- **Final size/type:** 7.1 x 3.25 in, double-column.
- **Final PNG:** `final/fig05_mitigation_behavior.png` (600 dpi).
- **Suggested caption:** *Median aggregate-interference reduction in acted
  snapshots and V2 activation rate. V2 acts on rare events at GB=10 MHz but on a
  much larger fraction of realizations at GB=5 MHz.*

## Fig. 6 - `fig06_service_elevation_loss`

- **Scientific purpose:** expose the service-quality cost of mitigation.
- **Script/source:** `scripts/06_service_cost.py`;
  `interference_aware_handover_v2_events.csv` from eight GB=10 runs.
- **Filter:** accepted handover events only.
- **Metric:** current service elevation minus selected-target service elevation,
  in degrees. The dashed 90-degree line is the campaign constraint.
- **Processed data:** `data/fig06_data.csv`.
- **Final size/type:** 3.5 x 3.45 in, single-column.
- **Final PNG:** `final/fig06_service_elevation_loss.png` (600 dpi).
- **Suggested caption:** *Distribution of service-elevation loss for accepted
  V2 reassociations at GB=10 MHz. Boxes show median and interquartile range; the
  campaign allowed losses up to 90 degrees.*

## Fig. 7 - `fig07_risk_features`

- **Scientific purpose:** identify geometric variables that distinguish safe and
  critical snapshots at the mask breakpoint.
- **Script/source:** `scripts/07_risk_features.py`; snapshot summary and rank-1
  link from `operational_risk_snapshot.csv` and `operational_risk_topk.csv` in
  eight operational GB=10 runs.
- **Sample:** 40,000 snapshots: 39,533 safe and 467 critical.
- **Features evaluated:** RX off-axis, TX off-axis, joint antenna suppression,
  interferer elevation from EESS, service elevation and path loss.
- **Selection:** pooled and per-scenario rank AUC, direction consistency and
  operational interpretability. The two selected variables are joint antenna
  suppression (median per-scenario oriented AUC 0.9996) and RX off-axis
  (0.9584); both have the same risk direction in all eight scenarios.
- **Pooling:** all samples are used for statistics; deterministic subsampling is
  used only for visible scatter points. Per-scenario results are retained in
  `data/fig07_feature_stats.csv`.
- **Processed data:** `data/fig07_data.csv` and
  `data/fig07_feature_stats.csv`.
- **Final size/type:** 7.1 x 3.15 in, double-column.
- **Final PNG:** `final/fig07_risk_features.png` (600 dpi).
- **Suggested caption:** *Distributions of the two strongest operationally
  interpretable risk features at GB=10 MHz. Safe and critical snapshots are
  defined from `Iagg,before` relative to -154 dBW/MHz; the displayed separation
  is consistent in direction across all eight scenarios.*

## Fig. 8 - `fig08_operational_risk_curve`

- **Scientific purpose:** estimate critical-interference risk from an observable
  geometric quantity without using instantaneous aggregate interference as the
  operational input.
- **Script/source:** `scripts/08_operational_risk_curve.py`; same 40,000 GB=10
  snapshots as Fig. 7.
- **Feature choice:** joint antenna suppression, because it had the best stable
  scenario-balanced discrimination; it requires realized EESS pointing plus
  DC-MSS geometry and antenna models.
- **Pooling/binning:** ten global quantile bins; risk is first computed per
  scenario and then averaged with equal scenario weight. Error bars are 95%
  stratified-bootstrap intervals (2,000 replicates); the shaded region is the
  inter-scenario IQR. Each bin contains about 4,000 snapshots and all eight
  scenarios.
- **Processed data:** `data/fig08_bins.csv`.
- **Final size/type:** 3.5 x 3.05 in, single-column.
- **Final PNG:** `final/fig08_operational_risk_curve.png` (600 dpi).
- **Suggested caption:** *Scenario-balanced empirical exceedance risk versus
  rank-1 joint antenna suppression at GB=10 MHz. Error bars show 95% stratified
  bootstrap intervals and shading shows the inter-scenario IQR. The metric uses
  realized EESS pointing assumed available through cooperative coordination.*

## Audit and QA

- Campaign audit: `data_audit.csv` generated by `scripts/01_audit_campaign.py`.
- Pointing result: configured as `UNIFORM_DIST` in azimuth and elevation and
  stored as realized values per snapshot; no figure describes it as physically
  fixed.
- Final PNGs were visually inspected at their intended single- or double-column
  dimensions. The figure scripts export only 600-dpi PNG files so that the
  Overleaf project does not need to process the heavier PDF/SVG versions.

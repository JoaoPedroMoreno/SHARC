# Campaign 08: TCC2 UE performance

Same physical scenario matrix as campaign 07, with 1000 snapshots per input.
The complete matrix has 136 inputs: 8 BASELINE, 48 HO (5/10/15/20/25/30),
and 80 PBO (10/20/.../100 km). Both altitudes, FS heights and LFs are retained.
No campaign-07 inputs or outputs are modified. Outputs go to
`D:/SHARC_outputs/08_TCC2_DC_MSS_performance`, with overwrite disabled.

## Workflow

From the repository root, using the existing SHARC virtual environment:

```powershell
.venv/Scripts/python.exe sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/generate.py
.venv/Scripts/python.exe sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/run_multiple_campaigns_mut_thread.py
```

The generator reads its own `Scripts/base_input.yaml`. It generates the entire
matrix, not merely the inputs still pending in campaign 07. Re-running it skips
completed matching performance outputs, never victim-only outputs from 07.
Do not regenerate the pending input queue while its runner is active.
The standard launcher uses the same CPU-count concurrency as the other campaigns;
performance calculation needs substantially more RAM than victim-only runs.
Prefer to finish campaign 07 before launching this batch.

## What is computed and saved

`imt_dl_intra_sinr_calculation_disabled: false` enables the existing UE calculations.
`performance_only_output: true` changes exports only, not geometry, powers, the
HO objective, candidate selection or stopping conditions. The FS INR must still
be calculated because the original HO is triggered and selected by that metric.
The FS remains a receiver, not an interfering transmitter into the UEs.

* `tcc2_performance_users.csv.gz`: one FINAL row per sampled UE per snapshot.
  Includes IDs, final and primary satellite, activity, availability, SINR outage,
  service loss during HO, PBO power, reassociation flag, SINR/SNR/intra-INR,
  signal/interference/noise powers, allocated bandwidth, service elevation,
  desired-link gains/losses, and the SHARC spectral-efficiency proxy.
* `tcc2_steps.csv.gz`: compact per-step counts (active/served/lost/outage UEs)
  and FS INR. No repeated per-user tables after every handover.
* `tcc2_snapshots.csv.gz`: seeds, realization hashes, HO counts/stop reasons and
  before/after FS INR, kept solely as lightweight pairing/audit evidence.
* `tcc2_executed_config.yaml`, `tcc2_manifest.json`: configuration, code hashes,
  seeds, lookup hash and committed snapshot count. Standard topology/log metadata
  can also be written by SHARC.

No repeated victim-link tables, candidate tables, HO event tables, full geometry
tables or duplicated flat INR/SINR/UE CSVs are exported by this profile. Campaign
07 remains the source for the 10000-snapshot interference and HO audit results.
Do not treat the 1000-snapshot audit INR as a replacement for that analysis.

## Interpretation and pairing

* Activity is scheduling/load, not outage. Keep inactive rows for identity checks,
  but do not include them as zero-performance demand in UE CDFs or outage rates.
* `served` means active, meeting the configured service elevation and having a
  finite SINR. It is NOT a packet-delivery guarantee. `sinr_outage` additionally
  tests the configured downlink minimum SINR (currently -10 dB).
* Active unserved users are retained. `service_lost` compares final availability
  against the initial state of THAT run. PBO is already applied at step 0; compare
  its final users with the separate campaign-08 baseline to measure PBO impact.
* `spectral_efficiency_proxy_bps_hz` uses SHARC's existing clipped Shannon mapping,
  even for a measured active UE below the service elevation. Filter/report service
  availability explicitly. `served_rate_proxy_mbps` multiplies that proxy by the
  allocated MHz and is zero for active unserved UEs; inactive values are NaN.
  Neither metric is packet throughput, goodput, BLER or a temporal handover rate.
* Baseline and mitigated UE rows join by scenario altitude/FS height/LF,
  snapshot_id, secondary_seed, cell_id and user_id. Satellite is an outcome, NOT
  a join key. For HO, also report reassigned versus other active UEs; for PBO,
  separate back-off-affected and unaffected UEs. An FS height can change HO even
  though the FS height is not a direct service-link parameter.
* The 838 master seed produces the same first 1000 secondary seeds as campaign
  07's 10000 runs. Seed equality alone is not proof of pairing: compare the
  snapshot hashes, baseline powers, accepted swaps and final INR as well.
* `service_population_sha256` excludes transmit powers and can check the sampled
  user/cell/activity population across baseline/PBO/HO within campaign 08.
  Snapshot `realization_sha256` includes powers; compare it between 07 and 08
  for the SAME treatment, or between baseline and HO, not baseline versus PBO.
* Resample snapshots, not independent pooled UE rows, for snapshot-level uncertainty.

Read-only post-run validation (reports missing campaign-07 counterparts honestly):

```powershell
.venv/Scripts/python.exe sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/validate_physics.py --check-pairing D:/SHARC_outputs/08_TCC2_DC_MSS_performance
```

Optional real-physics smoke test, ONLY when resources are available. It executes
six isolated single-snapshot tests, compares the existing full exporter against
the new compact exporter, and checks available campaign-07 first snapshots.
It never starts the complete campaign or writes into production output folders:

```powershell
.venv/Scripts/python.exe sharc/campaigns/08_TCC2_DC_MSS_performance/Scripts/validate_physics.py --smoke tmp/tcc2_performance_smoke
```

The smoke folder must not already exist. The original 2155-MHz carrier / 2000-MHz
Taylor pattern parameter distinction is deliberately preserved, as are the beam
radii, noise, antenna gains, frequencies, power control and HO thresholds.

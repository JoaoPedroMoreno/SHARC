# Figure Regeneration Report

Date: 2026-07-27

## Updated Outputs

- `figuras/fluxograma_sharc_ieee.png` and `.pdf`
  - Redrawn deterministically from `tools/generate_fluxograma_sharc_ieee.py`.
  - Text changed from `10000 snapshots` to `10 000 snapshots`.
  - Title and ten workflow steps preserved.

- `figuras/geometria_interferencia.png`
  - Regenerated from `sharc/campaigns/02_DC_MSS_to_FS 2/Script/plot_dc_mss_fs_interference_geometry_blender.py`.
  - Panel captions preserved as `(A) Regional coverage` and `(B) Cross-border spillover`.
  - Added larger `FS receiver` labels.
  - No `triple border` text remains.

- `figuras/system_inr_ccdf_margin_explainer_BR_AR_Paraguay_Sys3_525km_FS40m_M0km_M60km.png` and `.pdf`
  - Regenerated from `plot_system_inr_ccdf_margin_explainer.py`.
  - Legend uses `D_border=0 km` and `D_border=60 km`.
  - Axes use `INR (dB)` and `Exceedance probability`.
  - The 20% line and -6 dB FS criterion are annotated.

- `figuras/margem_zona_exclusao_bootstrap_final.png` and `.pdf`
  - Generated from `plot_bootstrap_margin_figures.py`.
  - Includes 95% bootstrap confidence intervals.
  - CSV exported as `figuras/margem_zona_exclusao_bootstrap_final.csv`.

- `figuras/margem_power_backoff_bootstrap_final.png` and `.pdf`
  - Generated from `plot_bootstrap_margin_figures.py`.
  - Includes 95% bootstrap confidence intervals.
  - CSV exported as `figuras/margem_power_backoff_bootstrap_final.csv`.

## Bootstrap Settings

- Bootstrap resamples: `B = 10 000`.
- Bootstrap seed: `20260727`.
- Classification rule:
  - `supported compliant`: margin CI lower >= 0.
  - `supported non-compliant`: margin CI upper < 0.
  - `borderline`: CI crosses zero.

## Critical Data Availability Note

The available SHARC output files currently contain `4000` original INR samples per scenario, not `10 000`.
Therefore, the bootstrap was performed with `B = 10 000` resamples using the `4000` original `system_inr.csv` values available for each scenario.
No samples were duplicated or fabricated.

## Bootstrap Summary

All scenarios:

- supported compliant: 68
- borderline: 6
- supported non-compliant: 102

Exclusion zone:

- total points: 88
- supported compliant: 18
- borderline: 1
- supported non-compliant: 69

Power back-off:

- total points: 88
- supported compliant: 50
- borderline: 5
- supported non-compliant: 33

## First Supported-Compliant Distances

Exclusion zone:

- 340 km, LF 20%, FS 20 m: 90 km
- 340 km, LF 20%, FS 40 m: 90 km
- 340 km, LF 50%, FS 20 m: not compliant up to 100 km
- 340 km, LF 50%, FS 40 m: not compliant up to 100 km
- 525 km, LF 20%, FS 20 m: 50 km
- 525 km, LF 20%, FS 40 m: 50 km
- 525 km, LF 50%, FS 20 m: 100 km
- 525 km, LF 50%, FS 40 m: 100 km

Power back-off:

- 340 km, LF 20%, FS 20 m: 20 km
- 340 km, LF 20%, FS 40 m: 10 km
- 340 km, LF 50%, FS 20 m: not compliant up to 100 km
- 340 km, LF 50%, FS 40 m: not compliant up to 100 km
- 525 km, LF 20%, FS 20 m: 0 km
- 525 km, LF 20%, FS 40 m: 0 km
- 525 km, LF 50%, FS 20 m: 70 km
- 525 km, LF 50%, FS 40 m: 60 km

These values match the expected current conclusions. No automatic warning was triggered for a change in the first supported-compliant distances.

## LaTeX Compilation

Compilation was not performed because no `.tex` file was found under `C:\GitHub\SHARC`, and the search outside the workspace was denied by the filesystem permissions. Also, `pdflatex` was not found in the active command path.

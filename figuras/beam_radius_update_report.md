# Beam-radius campaign update report

Date: 2026-08-09

## Scope and provenance

- NEW source of truth: 176 output directories under `sharc/campaigns/02_DC_MSS_to_FS 2/output`.
- NEW completeness: 176/176 scenarios contain `system_inr.csv`, each with 10,000 snapshot-level samples.
- NEW beam radii: 88 scenarios use 25,803 m at 340 km and 88 use 39,844 m at 525 km.
- OLD comparison source: the versioned pre-correction bootstrap summary at `HEAD:sharc/campaigns/02_DC_MSS_to_FS 2/plots/bootstrap_inr20/bootstrap_inr20_all_scenarios.csv`.
- OLD data availability: the old snapshot-level CSVs are no longer present in the workspace. The OLD summary contains 4,000 samples per scenario.
- Statistical method retained exactly: empirical 80th percentile for INR exceeded in 20% of snapshots; percentile bootstrap with B=10,000; bootstrap seed 20260727; 95% CI; CI-based classification.

Important limitation: because OLD has 4,000 samples per scenario and NEW has 10,000, the comparison measures the combined campaign change. It cannot attribute every difference exclusively to beam radius without the old raw snapshot-level CSVs.

## A) Regenerated figures

The three paper figures that directly depend on campaign outputs were regenerated in PNG and PDF at 600 dpi:

1. `figuras/system_inr_ccdf_margin_explainer_BR_AR_Paraguay_Sys3_525km_FS40m_M0km_M60km.png` and `.pdf`.
2. `figuras/margem_zona_exclusao_bootstrap_final.png` and `.pdf`.
3. `figuras/margem_power_backoff_bootstrap_final.png` and `.pdf`.

The flowchart, conceptual geometry, mitigation illustrations, and S.1528 antenna-pattern figures do not depend on the numerical simulation outputs and did not require regeneration.

## B) OLD vs NEW summary

| Classification | OLD | NEW | Change |
|---|---:|---:|---:|
| Compliant | 68 | 84 | +16 |
| Borderline | 6 | 3 | -3 |
| Non-compliant | 102 | 89 | -13 |
| Total | 176 | 176 | 0 |

By technique:

| Technique | Dataset | Compliant | Borderline | Non-compliant |
|---|---|---:|---:|---:|
| Exclusion zone | OLD | 18 | 1 | 69 |
| Exclusion zone | NEW | 26 | 1 | 61 |
| Power back-off | OLD | 50 | 5 | 33 |
| Power back-off | NEW | 58 | 2 | 28 |

Across all 176 paired points, NEW-OLD M20 is positive at every point. The mean change is +0.781 dB, the median is +0.733 dB, and the range is +0.360 to +1.634 dB. The mean INR20 CI half-width decreased from 0.157 dB to 0.107 dB.

The complete point-level comparison, including OLD/NEW INR20, M20, both CIs, classifications, and deltas, is in `figuras/beam_radius_comparison/beam_radius_old_vs_new_all_points.csv`.

## C) Points that changed classification

Nineteen of 176 points changed classification. No point moved in an unfavorable direction.

| Technique | Alt. | LF | FS | Distance | OLD M20 | OLD class | NEW M20 | NEW class |
|---|---:|---:|---:|---:|---:|---|---:|---|
| Exclusion zone | 340 | 20 | 20 | 70 | -0.374 | non-compliant | +0.323 | compliant |
| Exclusion zone | 340 | 20 | 20 | 80 | -0.088 | non-compliant | +0.578 | compliant |
| Exclusion zone | 340 | 20 | 40 | 70 | -0.283 | non-compliant | +0.403 | compliant |
| Exclusion zone | 340 | 20 | 40 | 80 | -0.003 | borderline | +0.673 | compliant |
| Exclusion zone | 525 | 50 | 20 | 80 | -0.616 | non-compliant | +0.088 | compliant |
| Exclusion zone | 525 | 50 | 20 | 90 | -0.258 | non-compliant | +0.382 | compliant |
| Exclusion zone | 525 | 50 | 40 | 70 | -0.685 | non-compliant | +0.004 | borderline |
| Exclusion zone | 525 | 50 | 40 | 80 | -0.513 | non-compliant | +0.184 | compliant |
| Exclusion zone | 525 | 50 | 40 | 90 | -0.159 | non-compliant | +0.483 | compliant |
| Power back-off | 340 | 20 | 20 | 0 | -0.479 | non-compliant | +0.372 | compliant |
| Power back-off | 340 | 20 | 20 | 10 | +0.171 | borderline | +0.936 | compliant |
| Power back-off | 340 | 20 | 40 | 0 | -0.388 | non-compliant | +0.437 | compliant |
| Power back-off | 525 | 50 | 20 | 30 | -0.680 | non-compliant | -0.014 | borderline |
| Power back-off | 525 | 50 | 20 | 40 | -0.228 | non-compliant | +0.575 | compliant |
| Power back-off | 525 | 50 | 20 | 50 | -0.010 | borderline | +0.747 | compliant |
| Power back-off | 525 | 50 | 20 | 60 | +0.164 | borderline | +0.896 | compliant |
| Power back-off | 525 | 50 | 40 | 30 | -0.590 | non-compliant | +0.083 | borderline |
| Power back-off | 525 | 50 | 40 | 40 | -0.118 | borderline | +0.655 | compliant |
| Power back-off | 525 | 50 | 40 | 50 | +0.063 | borderline | +0.841 | compliant |

CI crossing changes:

- Newly borderline: exclusion zone, 525 km/LF50/FS40/70 km; power back-off, 525 km/LF50/FS20/30 km; power back-off, 525 km/LF50/FS40/30 km.
- No longer borderline: exclusion zone, 340 km/LF20/FS40/80 km; power back-off, 340 km/LF20/FS20/10 km; power back-off, 525 km/LF50/FS20/50 and 60 km; power back-off, 525 km/LF50/FS40/40 and 50 km. All six became compliant.

## D) First CI-supported compliant distances

`Supported` means the lower bound of the M20 95% bootstrap CI is non-negative.

| Technique | Altitude | LF | FS height | Old supported distance | New supported distance | Changed? |
|---|---:|---:|---:|---|---|---|
| Exclusion zone | 340 | 20 | 20 | 90 km | 70 km | Yes |
| Exclusion zone | 340 | 20 | 40 | 90 km | 70 km | Yes |
| Exclusion zone | 340 | 50 | 20 | >100 km / non-compliant within evaluated range | >100 km / non-compliant within evaluated range | No |
| Exclusion zone | 340 | 50 | 40 | >100 km / non-compliant within evaluated range | >100 km / non-compliant within evaluated range | No |
| Exclusion zone | 525 | 20 | 20 | 50 km | 50 km | No |
| Exclusion zone | 525 | 20 | 40 | 50 km | 50 km | No |
| Exclusion zone | 525 | 50 | 20 | 100 km | 80 km | Yes |
| Exclusion zone | 525 | 50 | 40 | 100 km | 80 km | Yes |
| Power back-off | 340 | 20 | 20 | 20 km | 0 km | Yes |
| Power back-off | 340 | 20 | 40 | 10 km | 0 km | Yes |
| Power back-off | 340 | 50 | 20 | >100 km / non-compliant within evaluated range | >100 km / non-compliant within evaluated range | No |
| Power back-off | 340 | 50 | 40 | >100 km / non-compliant within evaluated range | >100 km / non-compliant within evaluated range | No |
| Power back-off | 525 | 20 | 20 | 0 km | 0 km | No |
| Power back-off | 525 | 20 | 40 | 0 km | 0 km | No |
| Power back-off | 525 | 50 | 20 | 70 km | 40 km | Yes |
| Power back-off | 525 | 50 | 40 | 60 km | 40 km | Yes |

## E) New borderline count

There are 3 NEW borderline points, down from 6:

1. Exclusion zone, 525 km, LF50, FS40, 70 km: M20 = +0.004 dB, CI95% [-0.016, +0.025] dB.
2. Power back-off, 525 km, LF50, FS20, 30 km: M20 = -0.014 dB, CI95% [-0.153, +0.137] dB.
3. Power back-off, 525 km, LF50, FS40, 30 km: M20 = +0.083 dB, CI95% [-0.051, +0.233] dB.

## F) Conclusions that remain valid

- Both mitigation sweeps improve M20 as distance increases.
- The 340 km, LF50 configurations remain non-compliant through 100 km under both techniques.
- No universal mitigation distance exists across all evaluated cases.
- The 20 m and 40 m curves remain close; the data still show weak sensitivity to the two FS height/clutter configurations.
- The fixed 10 dB power-back-off rule is not universally sufficient.
- For exclusion zone at 525 km/LF20, the first supported-compliant distance remains 50 km.
- For power back-off at 525 km/LF20, the unmitigated 0 km points remain compliant.

## G) Conclusions that changed

- Exclusion zone at 340 km/LF20 reaches supported compliance at 70 km, not 90 km.
- Exclusion zone at 525 km/LF50 reaches supported compliance at 80 km, not 100 km.
- Power back-off at 340 km/LF20 is already supported compliant at 0 km for both FS heights. The paper can no longer claim that a 10 km strip causes the transition to compliance.
- Power back-off at 525 km/LF50 is borderline at 30 km and supported compliant at 40 km for both FS heights, rather than requiring approximately 50-70 km.
- The NEW margins are systematically more favorable: all 176 NEW-OLD M20 differences are positive. This is large enough to change the article's quantitative coordination-distance statements.

## H-I) Exact LaTeX excerpts requiring updates and suggested replacements

Audited source: `C:\Users\joaop\Downloads\Latincom_paper_revised_review.tex`. The source was not edited.

### Abstract, line 70

Exact current excerpt:

> The power back-off is effective for the low-load $340~\mathrm{km}$ case with a narrow strip and improves the high-load $525~\mathrm{km}$ case, which approaches compliance only after a substantially wider strip.

Suggested replacement:

> In the corrected campaign, the low-load $340~\mathrm{km}$ power-back-off cases are already compliant at the unmitigated point, whereas the high-load $525~\mathrm{km}$ cases are borderline at $30~\mathrm{km}$ and become compliant at $40~\mathrm{km}$. The high-load $340~\mathrm{km}$ cases remain non-compliant throughout the tested range. Geographic exclusion yields compliance at $70~\mathrm{km}$ for the low-load $340~\mathrm{km}$ cases and at $80~\mathrm{km}$ for the high-load $525~\mathrm{km}$ cases, but not within $100~\mathrm{km}$ for the high-load $340~\mathrm{km}$ cases.

### System parameters, line 209

Exact current excerpt:

```latex
Individual-beam radius, $R_{\mathrm{beam}}$ & $23.77~\mathrm{km}$ & $36.71~\mathrm{km}$ \\ \hline
```

Suggested replacement:

```latex
Individual-beam radius, $R_{\mathrm{beam}}$ & $25.803~\mathrm{km}$ & $39.844~\mathrm{km}$ \\ \hline
```

### FS clutter configuration, lines 228-229 and 252

Exact current excerpts:

```latex
Clutter profile at $20~\mathrm{m}$ & \texttt{below\_rooftop} \\ \hline
Clutter profile at $40~\mathrm{m}$ & \texttt{above\_rooftop} \\ \hline
```

> Local clutter loss is separately represented using Recommendation ITU-R P.2108-0 \cite{ref32} for the two nominal tower-height profiles.

These are not the actual YAML settings. Suggested table rows:

```latex
P.2108 environment at $20~\mathrm{m}$ & Low-rise; $60\%$ below-rooftop probability \\ \hline
P.2108 environment at $40~\mathrm{m}$ & Mid-rise; $10\%$ below-rooftop probability \\ \hline
```

Suggested prose replacement:

> Local clutter loss is separately represented using Recommendation ITU-R P.2108-0 \cite{ref32}. The $20~\mathrm{m}$ and $40~\mathrm{m}$ FS configurations use low-rise and mid-rise mean-clutter-height profiles, respectively, with below-rooftop probabilities of $60\%$ and $10\%$.

### Exclusion-zone implementation, line 259

Exact current excerpt:

> For Scenario~1, any active beam whose ground-centre position falls within a radius $R_{\mathrm{ez}}$ of the victim receiver is muted in the simulation.

Suggested replacement, matching the SHARC implementation:

> For Scenario~1, service-grid candidate points within a radius $R_{\mathrm{ez}}$ of the victim receiver are removed before beam placement; consequently, no DC-MSS service beam is pointed toward a target point inside the exclusion circle.

### Classification rule, line 293

Exact current excerpt:

> A non-negative value indicates compliance with the adopted threshold; a negative value gives the remaining deficit.

Suggested replacement:

> A scenario is classified as supported compliant when the lower bound of the $95\%$ bootstrap confidence interval of $M_{20}$ is non-negative, supported non-compliant when its upper bound is negative, and borderline when the interval crosses zero.

### Exclusion-zone figure reference and caption, lines 298-299

Exact current reference:

```latex
\centerline{\includegraphics[width=\columnwidth]{figuras/margem_zona_exclusao.pdf}}
```

Suggested replacement:

```latex
\centerline{\includegraphics[width=\columnwidth]{figuras/margem_zona_exclusao_bootstrap_final.pdf}}
\caption{Protection margin as a function of exclusion-zone radius. Error bars denote $95\%$ percentile-bootstrap confidence intervals; supported compliance requires the lower confidence bound to be non-negative.}
```

### Exclusion-zone results, line 305

Exact current paragraph:

> For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=20\%$, the unmitigated margin is $-13.1~\mathrm{dB}$. The margin improves to $-4.9~\mathrm{dB}$ at $30~\mathrm{km}$ and to $-0.8~\mathrm{dB}$ at $60~\mathrm{km}$. The corresponding low-load curve becomes compliant only near the upper portion of the evaluated range. Under $\mathrm{LF}=50\%$, however, the $340~\mathrm{km}$ curve remains negative at $100~\mathrm{km}$, with a plotted margin of approximately $-3.3~\mathrm{dB}$. Therefore, no sufficient exclusion radius is identified for that case within the tested interval.

Suggested replacement:

> For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=20\%$, the unmitigated $M_{20}$ ranges from $-12.33$ to $-12.23~\mathrm{dB}$ for the two FS heights. It improves to $-3.78$ to $-3.71~\mathrm{dB}$ at $30~\mathrm{km}$ and to $-0.23$ to $-0.14~\mathrm{dB}$ at $60~\mathrm{km}$. Both FS-height cases become supported compliant at $70~\mathrm{km}$. Under $\mathrm{LF}=50\%$, the $340~\mathrm{km}$ cases remain non-compliant at $100~\mathrm{km}$, with $M_{20}$ between $-2.62$ and $-2.55~\mathrm{dB}$.

### Exclusion-zone high-load 525 km result, line 307

Exact current excerpt:

> For the $525~\mathrm{km}$ high-load case, the curve reaches a small positive margin near $100~\mathrm{km}$ (approximately $+0.14~\mathrm{dB}$ in the reported data).

Suggested replacement:

> For the $525~\mathrm{km}$ high-load cases, the $70~\mathrm{km}$ points are non-compliant or borderline, while both FS-height configurations become supported compliant at $80~\mathrm{km}$, with $M_{20}=+0.088$ and $+0.184~\mathrm{dB}$ and strictly positive $95\%$ confidence intervals.

### Power-back-off figure reference and caption, lines 312-313

Exact current reference:

```latex
\centerline{\includegraphics[width=\columnwidth]{figuras/margem_power_backoff.pdf}}
```

Suggested replacement:

```latex
\centerline{\includegraphics[width=\columnwidth]{figuras/margem_power_backoff_bootstrap_final.pdf}}
\caption{Protection margin as a function of border-strip width under a fixed $10~\mathrm{dB}$ conducted-power back-off. Error bars denote $95\%$ percentile-bootstrap confidence intervals; supported compliance requires the lower confidence bound to be non-negative.}
```

### Power-back-off low-load 340 km result, line 320

Exact current paragraph:

> For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=20\%$, the unmitigated deficit of $-0.47~\mathrm{dB}$ changes to a small positive margin of approximately $+0.17~\mathrm{dB}$ when the back-off is applied over a $10~\mathrm{km}$ border strip. This confirms that a narrow strip is sufficient for this specific low-load case.

Suggested replacement:

> For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=20\%$, both FS-height cases are already supported compliant at the unmitigated point, with $M_{20}=+0.372$ and $+0.437~\mathrm{dB}$. Increasing the border strip to $10~\mathrm{km}$ raises the margins to $+0.936$ and $+1.008~\mathrm{dB}$; therefore, this configuration does not establish a minimum non-zero strip width.

### Power-back-off high-load results, line 322

Exact current paragraph:

> The high-load results are substantially less favorable. For the $525~\mathrm{km}$ configuration with $\mathrm{LF}=50\%$, the plotted baseline margin is approximately $-7.6~\mathrm{dB}$, remains negative at $10~\mathrm{km}$, and approaches the compliance boundary only around a $50~\mathrm{km}$ strip. For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=50\%$, the margin remains approximately $-3.3~\mathrm{dB}$ even at $100~\mathrm{km}$.

Suggested replacement:

> The high-load results are less favorable. For the $525~\mathrm{km}$ configuration with $\mathrm{LF}=50\%$, the baseline $M_{20}$ ranges from $-6.91$ to $-6.82~\mathrm{dB}$ and remains between $-2.74$ and $-2.63~\mathrm{dB}$ at $10~\mathrm{km}$. Both $30~\mathrm{km}$ points are borderline, and both FS-height cases become supported compliant at $40~\mathrm{km}$, with $M_{20}=+0.575$ and $+0.655~\mathrm{dB}$. For the $340~\mathrm{km}$ configuration with $\mathrm{LF}=50\%$, the $100~\mathrm{km}$ margins remain negative, between $-2.24$ and $-2.16~\mathrm{dB}$.

### FS-height sensitivity, line 326

Exact current excerpt requiring removal of the unresolved implementation caveat:

> This issue should be verified in the propagation implementation and, if the curves remain coincident, discussed as a weak sensitivity rather than as a dominant shielding effect.

Suggested replacement:

> Across the evaluated points, the $20~\mathrm{m}$ and $40~\mathrm{m}$ curves remain close. The corrected campaign therefore supports only a weak sensitivity to the two combined FS height and probabilistic P.2108 clutter configurations.

### Conclusion, lines 344 and 346

Exact current excerpt:

> A fixed $10~\mathrm{dB}$ border power back-off is more effective for some cross-border configurations. It achieves compliance with a narrow strip in the low-load $340~\mathrm{km}$ case and brings the high-load $525~\mathrm{km}$ case close to compliance only with a wider strip of approximately $50~\mathrm{km}$.

Suggested replacement:

> Geographic beam exclusion improves the FS margin, reaching supported compliance at $70~\mathrm{km}$ for the low-load $340~\mathrm{km}$ cases, at $50~\mathrm{km}$ for the low-load $525~\mathrm{km}$ cases, and at $80~\mathrm{km}$ for the high-load $525~\mathrm{km}$ cases. The high-load $340~\mathrm{km}$ cases remain non-compliant through $100~\mathrm{km}$. Under fixed $10~\mathrm{dB}$ border power back-off, the low-load cases are already compliant at the unmitigated point, while the high-load $525~\mathrm{km}$ cases become supported compliant at $40~\mathrm{km}$. The high-load $340~\mathrm{km}$ cases remain non-compliant throughout the tested range. Thus, neither technique yields a universal coordination distance across all evaluated configurations.

### Future work, line 348

Exact current excerpt:

> Future work should verify the spectral-bandwidth mapping, perform azimuth and location sweeps, quantify Monte Carlo uncertainty, release complete simulation configurations, and include the service-side cost of each mitigation mechanism.

Because bootstrap uncertainty is now quantified, suggested replacement:

> Future work should verify the spectral-bandwidth mapping, perform azimuth and location sweeps, extend the uncertainty assessment through convergence tests and independent simulation seeds, release complete simulation configurations, and include the service-side cost of each mitigation mechanism.

## Supporting files

- `figuras/beam_radius_comparison/beam_radius_comparison_report.md`: detailed numerical audit.
- `figuras/beam_radius_comparison/beam_radius_old_vs_new_all_points.csv`: all 176 OLD/NEW pairs.
- `figuras/beam_radius_comparison/beam_radius_classification_changes.csv`: the 19 changed points.
- `figuras/beam_radius_comparison/beam_radius_supported_distances.csv`: requested 16-row distance table.
- `figuras/beam_radius_comparison/bootstrap_inr20_old_snapshot.csv`: immutable copy of the OLD versioned summary used in the comparison.


# Beam-radius correction: OLD vs NEW

## Provenance and method

- OLD source: `C:\GitHub\SHARC\figuras\beam_radius_comparison\bootstrap_inr20_old_snapshot.csv`.
- NEW source: `C:\GitHub\SHARC\sharc\campaigns\02_DC_MSS_to_FS 2\plots\bootstrap_inr20\bootstrap_inr20_all_scenarios.csv`.
- Both summaries use the existing empirical 80th percentile, percentile bootstrap with B=10,000, bootstrap seed 20260727, and the existing CI-based classification rule.
- OLD has 4,000 snapshot-level samples per scenario; NEW has 10,000. Consequently, this is a campaign-to-campaign comparison and does not isolate beam radius from the increased Monte Carlo sample count.

## Classification totals

| Classification | OLD | NEW | Delta |
|---|---|---|---|
| compliant | 68 | 84 | 16 |
| borderline | 6 | 3 | -3 |
| non-compliant | 102 | 89 | -13 |

Changed classifications: **19 of 176 points**.

## Classification transitions

| OLD | NEW | Points |
|---|---|---|
| borderline | compliant | 6 |
| non-compliant | borderline | 3 |
| non-compliant | compliant | 10 |

## First CI-supported compliant distance

| Technique | Altitude | LF | FS height | Old supported distance | New supported distance | Changed? |
|---|---|---|---|---|---|---|
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

## Margin changes

- Mean NEW-OLD M_20: 0.781 dB.
- Median NEW-OLD M_20: 0.733 dB.
- Range of NEW-OLD M_20: 0.360 to 1.634 dB.
- Mean INR_20 CI half-width: OLD 0.157 dB; NEW 0.107 dB.

### Largest absolute M_20 differences

| Scenario | OLD M_20 | NEW M_20 | Delta |
|---|---|---|---|
| Power back-off, 525 km, LF 20%, FS 20 m, 0 km | 2.399 | 4.033 | 1.634 |
| Power back-off, 525 km, LF 20%, FS 40 m, 0 km | 2.500 | 4.133 | 1.633 |
| Power back-off, 340 km, LF 50%, FS 40 m, 0 km | -10.723 | -9.261 | 1.462 |
| Power back-off, 340 km, LF 50%, FS 20 m, 0 km | -10.813 | -9.376 | 1.437 |
| Exclusion zone, 525 km, LF 20%, FS 40 m, 40 km | -2.986 | -1.790 | 1.196 |
| Exclusion zone, 525 km, LF 20%, FS 20 m, 40 km | -3.094 | -1.908 | 1.186 |
| Exclusion zone, 340 km, LF 20%, FS 20 m, 30 km | -4.955 | -3.779 | 1.176 |
| Power back-off, 525 km, LF 20%, FS 40 m, 10 km | 3.495 | 4.666 | 1.171 |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 30 km | -4.864 | -3.709 | 1.156 |
| Power back-off, 525 km, LF 20%, FS 20 m, 10 km | 3.430 | 4.572 | 1.143 |
| Power back-off, 340 km, LF 50%, FS 20 m, 70 km | -3.476 | -2.377 | 1.099 |
| Power back-off, 340 km, LF 50%, FS 20 m, 100 km | -3.333 | -2.243 | 1.089 |
| Power back-off, 340 km, LF 50%, FS 20 m, 80 km | -3.407 | -2.320 | 1.087 |
| Power back-off, 340 km, LF 50%, FS 40 m, 80 km | -3.322 | -2.242 | 1.080 |
| Power back-off, 340 km, LF 50%, FS 40 m, 90 km | -3.278 | -2.199 | 1.079 |

### Points near zero in OLD or NEW (|M_20| <= 0.25 dB)

| Scenario | OLD M_20 | OLD class | NEW M_20 | NEW class | NEW CI |
|---|---|---|---|---|---|
| Exclusion zone, 340 km, LF 20%, FS 20 m, 60 km | -0.894 | non-compliant | -0.230 | non-compliant | [-0.256, -0.197] |
| Exclusion zone, 340 km, LF 20%, FS 20 m, 80 km | -0.088 | non-compliant | 0.578 | compliant | [0.551, 0.605] |
| Exclusion zone, 340 km, LF 20%, FS 20 m, 90 km | 0.117 | compliant | 0.811 | compliant | [0.785, 0.835] |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 60 km | -0.803 | non-compliant | -0.142 | non-compliant | [-0.171, -0.115] |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 80 km | -0.003 | borderline | 0.673 | compliant | [0.647, 0.699] |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 90 km | 0.196 | compliant | 0.891 | compliant | [0.867, 0.922] |
| Exclusion zone, 525 km, LF 50%, FS 20 m, 70 km | -0.795 | non-compliant | -0.100 | non-compliant | [-0.120, -0.077] |
| Exclusion zone, 525 km, LF 50%, FS 20 m, 80 km | -0.616 | non-compliant | 0.088 | compliant | [0.069, 0.106] |
| Exclusion zone, 525 km, LF 50%, FS 20 m, 100 km | 0.145 | compliant | 0.829 | compliant | [0.809, 0.851] |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 70 km | -0.685 | non-compliant | 0.004 | borderline | [-0.016, 0.025] |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 80 km | -0.513 | non-compliant | 0.184 | compliant | [0.166, 0.205] |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 90 km | -0.159 | non-compliant | 0.483 | compliant | [0.462, 0.501] |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 100 km | 0.238 | compliant | 0.929 | compliant | [0.910, 0.949] |
| Power back-off, 340 km, LF 20%, FS 20 m, 10 km | 0.171 | borderline | 0.936 | compliant | [0.817, 1.013] |
| Power back-off, 340 km, LF 20%, FS 40 m, 10 km | 0.247 | compliant | 1.008 | compliant | [0.890, 1.093] |
| Power back-off, 525 km, LF 50%, FS 20 m, 30 km | -0.680 | non-compliant | -0.014 | borderline | [-0.153, 0.137] |
| Power back-off, 525 km, LF 50%, FS 20 m, 40 km | -0.228 | non-compliant | 0.575 | compliant | [0.414, 0.715] |
| Power back-off, 525 km, LF 50%, FS 20 m, 50 km | -0.010 | borderline | 0.747 | compliant | [0.595, 0.893] |
| Power back-off, 525 km, LF 50%, FS 20 m, 60 km | 0.164 | borderline | 0.896 | compliant | [0.748, 1.048] |
| Power back-off, 525 km, LF 50%, FS 20 m, 70 km | 0.241 | compliant | 0.998 | compliant | [0.859, 1.149] |
| Power back-off, 525 km, LF 50%, FS 40 m, 30 km | -0.590 | non-compliant | 0.083 | borderline | [-0.051, 0.233] |
| Power back-off, 525 km, LF 50%, FS 40 m, 40 km | -0.118 | borderline | 0.655 | compliant | [0.512, 0.802] |
| Power back-off, 525 km, LF 50%, FS 40 m, 50 km | 0.063 | borderline | 0.841 | compliant | [0.693, 0.982] |

## Points whose CI started or stopped crossing zero

### Started crossing zero

- Exclusion zone, 525 km, LF 50%, FS 40 m, 70 km
- Power back-off, 525 km, LF 50%, FS 20 m, 30 km
- Power back-off, 525 km, LF 50%, FS 40 m, 30 km

### Stopped crossing zero

- Exclusion zone, 340 km, LF 20%, FS 40 m, 80 km: compliant
- Power back-off, 340 km, LF 20%, FS 20 m, 10 km: compliant
- Power back-off, 525 km, LF 50%, FS 20 m, 50 km: compliant
- Power back-off, 525 km, LF 50%, FS 20 m, 60 km: compliant
- Power back-off, 525 km, LF 50%, FS 40 m, 40 km: compliant
- Power back-off, 525 km, LF 50%, FS 40 m, 50 km: compliant

## All changed classifications

| Scenario | OLD M_20 | OLD class | NEW M_20 | NEW class |
|---|---|---|---|---|
| Exclusion zone, 340 km, LF 20%, FS 20 m, 70 km | -0.374 | non-compliant | 0.323 | compliant |
| Exclusion zone, 340 km, LF 20%, FS 20 m, 80 km | -0.088 | non-compliant | 0.578 | compliant |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 70 km | -0.283 | non-compliant | 0.403 | compliant |
| Exclusion zone, 340 km, LF 20%, FS 40 m, 80 km | -0.003 | borderline | 0.673 | compliant |
| Exclusion zone, 525 km, LF 50%, FS 20 m, 80 km | -0.616 | non-compliant | 0.088 | compliant |
| Exclusion zone, 525 km, LF 50%, FS 20 m, 90 km | -0.258 | non-compliant | 0.382 | compliant |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 70 km | -0.685 | non-compliant | 0.004 | borderline |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 80 km | -0.513 | non-compliant | 0.184 | compliant |
| Exclusion zone, 525 km, LF 50%, FS 40 m, 90 km | -0.159 | non-compliant | 0.483 | compliant |
| Power back-off, 340 km, LF 20%, FS 20 m, 0 km | -0.479 | non-compliant | 0.372 | compliant |
| Power back-off, 340 km, LF 20%, FS 20 m, 10 km | 0.171 | borderline | 0.936 | compliant |
| Power back-off, 340 km, LF 20%, FS 40 m, 0 km | -0.388 | non-compliant | 0.437 | compliant |
| Power back-off, 525 km, LF 50%, FS 20 m, 30 km | -0.680 | non-compliant | -0.014 | borderline |
| Power back-off, 525 km, LF 50%, FS 20 m, 40 km | -0.228 | non-compliant | 0.575 | compliant |
| Power back-off, 525 km, LF 50%, FS 20 m, 50 km | -0.010 | borderline | 0.747 | compliant |
| Power back-off, 525 km, LF 50%, FS 20 m, 60 km | 0.164 | borderline | 0.896 | compliant |
| Power back-off, 525 km, LF 50%, FS 40 m, 30 km | -0.590 | non-compliant | 0.083 | borderline |
| Power back-off, 525 km, LF 50%, FS 40 m, 40 km | -0.118 | borderline | 0.655 | compliant |
| Power back-off, 525 km, LF 50%, FS 40 m, 50 km | 0.063 | borderline | 0.841 | compliant |

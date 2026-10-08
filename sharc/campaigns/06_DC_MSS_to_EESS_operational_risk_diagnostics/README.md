# Operational-risk diagnostics campaign

Runnable matrix:

`2 altitudes × 2 EESS systems × 2 load factors × 6 guard bands = 48 inputs`

- Altitude: 340 and 525 km
- EESS: Systems B and D
- Load factor: 0.2 and 0.5
- Guard band: 80, 75, 70, 65, 60 and 10 MHz
- DC-MSS center frequency: `2197.5 - GB` MHz
- DC-MSS bandwidth: 5 MHz
- Paraguay, South-America coverage and geographic margin 0 km
- 5000 snapshots and master seed 157
- Legacy handover OFF
- V2 `RISK_GATED_TOP_K` ON
- Operational-risk diagnostics ON, top-3, candidate details OFF

GB=5 MHz is intentionally excluded because it is in the variable region of
`SpectralMaskMSS`; this campaign studies operational geometry in the flat
spurious-emission regime.

Generate/validate inputs:

```powershell
python Scripts/generate.py --write
```

Run the prepared matrix:

```powershell
python Scripts/run_multiple_campaigns_mut_thread.py
```

The approved 200-snapshot invariance artifacts remain under `analysis/` and
are not selected by the campaign launcher.

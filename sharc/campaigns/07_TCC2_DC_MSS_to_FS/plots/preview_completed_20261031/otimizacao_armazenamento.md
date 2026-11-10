# TCC2: lossless detailed-record storage

## Scope

`detailed_record_format: DELTA` is an export-only option under
`imt.topology.mss_dc.interference_aware_handover_v2`. Legacy inputs default to
`FULL`. The campaign base now uses `DELTA`; baseline and PBO still disable
detailed links/users exports entirely.

23 not-yet-started HO inputs were changed only to add this export option.
The other 89 inputs, existing outputs and running workers were preserved.
Existing workers retain FULL; this does not free previously occupied space.

## Representation and analysis

`tcc2_links.delta.jsonl.gz` and `tcc2_users.delta.jsonl.gz` store the first
state of each snapshot, then only changed values at each accepted step.
All original CSV values and all rows at each step can be reconstructed.
No rounding, subsampling, user removal, or physics changes are performed.
This saves disk space, not necessarily RAM.

Use the streaming reader for either legacy or new outputs:

```python
from sharc.support.tcc2_detailed_records import read_detailed_rows

for row in read_detailed_rows(output_folder, "links"):
    # CSV-compatible dictionaries, with string values as in csv.DictReader.
    pass
```

INR, snapshots, steps, events and candidates keep their existing formats.
Readers that directly require detailed CSV filenames must use this helper.

## Verification

- 36 unit/regression tests passed.
- `validate_physics.py --compare-delta`: four profiles, two snapshots each,
  in both FULL and DELTA (16 isolated test snapshots).
- Exact equality of INR, decisions, RNG and reconstructed detail rows.
- The 340 km FS40 LF50 HO5 test exercised four accepted changes across two
  snapshots: 2,685,523 -> 1,081,649 bytes for links/users (59.7% reduction).
- Existing HO30 physical-test sample: links 7,684,449 -> 1,540,018 bytes;
  users 7,470,459 -> 1,322,380 bytes (81.1% combined reduction).
  Reconstruction verified by row count and SHA-256 of canonical row values.
- Cases with no accepted changes were about 4-5% larger. These small tests
  do NOT establish a campaign-wide compression ratio or guarantee disk fit.

Validation: `tmp/tcc2_delta_validation_20261031/delta_validation.json`.
Source benchmark files in `tmp/tcc2_victim_only_validation_20261026` were kept.
No production HO archive was converted, replaced, or deleted.

## Existing archives

The module CLI can convert a CLOSED CSV to a NEW delta archive, verify every
reconstructed row and preserve its source. Never convert a running output.
Conversion alone initially uses extra space. Removing an original after
verified replacement is a separate operation, not performed in this change.

## Result classification

See `ho_bootstrap_classification.json` for the completed-HO comparisons,
using the existing campaign-02 10,000-resample 95% percentile bootstrap.
No evaluated completed HO moved a borderline baseline to supported compliant.
The LF20 baselines were already supported compliant. The newly completed
340 km FS20 LF50 HO5 remains supported non-compliant.

PBO inventory at this audit: 28/80 complete; 52 remaining (5 running,
45 not started and 2 interrupted). This is a time-specific inventory.

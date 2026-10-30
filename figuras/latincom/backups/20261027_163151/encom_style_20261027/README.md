# LATINCOM: direct reuse of the Encom geometry

Run from the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe tools/generate_latincom_figures.py
```

Use `--preview` for white-background review PNGs only. `--figures cover architecture context methodology`
can select the figures to render. Final PNGs are 600 dpi; PDF and SVG keep vector
lines, footprints, maps, cells and labels. Satellites are the existing raster artwork.

## Sources and changes

The original Encom module is imported directly from
`sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/generate_hex_presentation_images.py`.
It is not modified. This replaces the earlier reduced reimplementation of its drawing functions.

- 2A: the spot-beam label is removed. The ground cell is a hexagon in perspective;
  gateway, feeder link and dedicated MSS terminal are retained. One bidirectional
  service-link arrow replaces the separate beam centerline. Both architecture
  figures retain horizontal satellites.
- 2B: a connected hexagonal ground patch is projected with the same flattening
  and shear as the reference style; beam vertices and terminals share that ground.
- Page 3: `local_coverage_geometry` supplies the same terrain, clipped cells and
  zigzag frontier used in `v3/itu_pbo_zoom_border.png`. The original `beam` function
  generates each beam from its satellite feed to a projected cell footprint.
  Both ends of the wanted FS link and multiple interfering satellites are shown.
- SHARC: the same ground geometry is reused for each snapshot. Exclusion removes
  service near the fixed receiver; back-off changes active border-cell power.
  The exclusion circle is projected onto the terrain, and cell activity changes
  between illustrative realizations.
- Cover: a metric equal-area projection and a clipped drawing grid reuse the
  mesh construction in `v3/cover_pbo_brazil.png`. The display radius is scaled
  by 2.4 for slide legibility; it is not the campaign beam radius. `fit_map`,
  `draw_grid`, `draw_geometry` and `beam` come from the original source. The
  regional panel includes Brazil, Argentina, Uruguay, Paraguay, Bolivia, Chile
  and Peru; the other serves Brazil and Argentina. Mitigation extents are
  enlarged and explicitly marked as illustrative, not simulation results.

Satellite tilt in page 3 and the SHARC snapshots is aligned with the center of
each selected beam fan. Satellite body, solar panels and antenna feed share one
rotation. In the cover, only the outer satellites are tilted toward their beam
fans. Footprints remain on the same ground geometry; the tilt is illustrative,
not an orbital attitude recovered from simulation output.

The diagrams do not imply that DC-MSS has no gateway; page 2B shows the access
segment only. All beam choices and cell activity shown are illustrative.
No campaign inputs, samples or scientific results are changed.

Latest pre-edit backup: `../backups/20261027_141255`. Earlier exported figures are also
preserved in their existing directories.

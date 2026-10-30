# LATINCOM: direct reuse of the Encom geometry

Run from the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe tools/generate_latincom_figures.py
```

Use `--preview` for white-background review PNGs only. `--figures cover architecture context methodology`
can select the figures to render. Final PNGs are 600 dpi; PDF and SVG keep vector
lines, footprints, maps, cells and labels. Satellites are the existing raster artwork;
the off-axis intensity haze in page 3 is the reference's deterministic raster field.

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
- Page 3: panel (a), without PBO, from `v3/itu_pbo_zoom_border.png` is reproduced
  with exactly the same ground projection, satellite position, five selected
  cells, beam hulls and off-axis fields. Text is in English. The receiver is
  replaced by a directional dish, and a reciprocal FS transmitter is added
  north of the victim, farther into the ground plane.
- All victim FS symbols face north, into the drawing. Their rear reflector
  shell, stiffening ribs and pole mount are visible from the south; the
  radome faces away from the viewer. The transmitter in page 3 faces south
  toward the victim, so its white front radome is visible. The wanted link
  follows the same projected north-south ground direction.
  The shared vector pictogram uses a shielded point-to-point microwave dish
  on a mounting pole, not a cellular panel tower or an open gateway dish.
  This does not change the separate satellite gateway in figure 2A.
  Form reference only (no electrical values or product identity are adopted):
  [RFS/Aviat point-to-point antenna datasheet](https://aviat-store.aviatnetworks.com/au/amfile/file/download/file/293/product/13326/).
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
  The map vertical scale is 0.80 and grid strokes are 0.58 pt. The complete
  FS pictogram is fitted within Paraguay using its map polygon. This is a
  schematic symbol placement, not a change to the receiver's simulation
  coordinates; the illustrative exclusion circle follows this symbol.
  The exclusion panel's middle satellite has two beams, with a geometry
  check ensuring neither crosses the FS pictogram.

Satellite tilt in the SHARC snapshots is aligned with the center of
each selected beam fan. Satellite body, solar panels and antenna feed share one
rotation. In the cover, only the outer satellites are tilted toward their beam
fans. Footprints remain on the same ground geometry; the tilt is illustrative,
not an orbital attitude recovered from simulation output.

The diagrams do not imply that DC-MSS has no gateway; page 2B shows the access
segment only. All beam choices and cell activity shown are illustrative.
No campaign inputs, samples or scientific results are changed.

Run `& .\.venv\Scripts\python.exe tools/test_latincom_figures.py` to verify
reference geometry, FS symbols and the architecture service-link arrow.

Latest pre-edit backup: `../backups/20261027_164316`. Earlier exported figures are also
preserved in their existing directories.

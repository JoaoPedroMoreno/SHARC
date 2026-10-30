# LATINCOM: direct reuse of the Encom geometry

Run from the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe tools/generate_latincom_figures.py
```

Use `--preview` for white-background review PNGs only. `--figures cover architecture context methodology antenna`
can select the figures to render. Final PNGs are 600 dpi; PDF and SVG keep vector
lines, footprints, maps, cells and labels. Satellites are the existing raster artwork;
FS dishes are embedded transparent Blender renders of the approved antenna model;
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
- All victim FS symbols face north, into the drawing. The shared symbol now
  uses the approved Blender model: an open circular paraboloid with a feed horn,
  three support struts, a rear mechanical mount and a vertical metallic pole. There
  is no radome, cellular panel or generic tower symbol. The transmitter in
  page 3 faces south toward the victim. The wanted link follows the same
  projected north-south direction.
  `tools/render_latincom_fs_assets.py` renders the approved model from
  `../antenna_proposal_v2/fs_antenna_proposal.blend`, without changing its shape
  or hardware. Materials, color management and soft lights are reused from
  the Encom `v3/satellite_from_paper.blend` source. This replaces the bright
  metallic finish with the same restrained grey finish as the satellite.
  Run it with Blender's `-b --python` options to rebuild sprites
  and the projected-anchor manifest in `../antenna_assets/`.
  `tools/latincom_fs_antenna.py` embeds those sprites and connects signal lines
  to the projected feed position. The north-facing views match the projected
  north of the maps and snapshot ground planes. A separate south-facing view
  supplies the wanted FS transmitter. Both symbols on page 3 use a 0.72
  drawing scale to keep the dishes and wanted link visibly separated.
  The aperture plane is vertical and the boresight has zero vertical
  component. An elevated technical illustration view reveals the feed beyond
  the rim; this pictogram camera is not the orbital simulator's camera.
  Dimensions and focal ratio are illustrative, not simulated antenna parameters.
  `latincom_fs_antenna.png` (transparent), `.pdf` and `.svg` are standalone
  versions of this same symbol. The separate gateway in 2A is unchanged.
- SHARC: the same ground geometry is reused for each snapshot. Exclusion removes
  service near the fixed receiver; back-off changes active border-cell power.
  The exclusion circle is projected onto the terrain, and cell activity changes
  between illustrative realizations.
  The presentation now uses short labels instead of explanatory paragraphs.
  Four snapshots illustrate the two methods, followed by an explicitly
  illustrative CCDF and a signed protection-margin axis. That schematic
  curve is not generated from campaign samples and is not a new result.
- Page 3 no longer includes the text "Wanted FS link". The wanted-link arrow
  and both FS antennas remain in place.
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

Latest pre-edit backup: `../backups/20261028_195905_style_and_methodology`.
Earlier exported figures are also
preserved in their existing directories.

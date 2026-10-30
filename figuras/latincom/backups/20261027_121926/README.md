# LATINCOM presentation figures

Reproduce with `python tools/generate_latincom_figures.py` from the repository.

## Deliverables

- `latincom_cover`: regional exclusion and conditional border-strip power back-off in separate panels, with dense cell grids and two satellites per scenario.
- `latincom_page_2`: comparison of conventional MSS and direct service to IMT user equipment.
- `latincom_page_2A_conventional_mss` and `latincom_page_2B_dc_mss_imt`: independent exports of the architecture panels.
- `latincom_page_3`: several satellite downlinks interfering with the receiving end of a wanted terrestrial FS link.
- `latincom_sharc_monte_carlo`: the existing three-block layout with two illustrative snapshots per mitigation method, two satellites per snapshot, varying cell activity and mitigation states.

Each figure has PNG (600 dpi), PDF and SVG exports. The first three PNGs have
transparent backgrounds; the methodology PNG has a white background. Preview
PNGs use a white background and lower resolution.

## Style provenance

The satellite artwork is reused from
`sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/v3/satellite_from_paper.png`.
The satellite placement function, receiver tower, palette and hexagon primitive
are extracted directly from `generate_hex_presentation_images.py` in the same
presentation-assets directory. Extraction avoids loading unrelated GIS libraries.
The receiver is the original schematic tower symbol, not a new antenna pattern.
Hexagons are rotated to fit a staggered-row arrangement without overlap.

PDF/SVG retain vector lines, labels, cells and tower; the satellite is an embedded
raster asset, exactly as in the reference figures. These are not fully vector files.

Inactive cells are white with dashed gray borders; excluded cells use pale gray fills and thin solid borders. The exclusion radius
uses a separate red solid circle. Interference alone uses red dashed arrows.
The original methodological figure filename in `figuras` is also updated.

## Scientific scope and outstanding verification

All positions and region outlines are conceptual, not actual border coordinates,
distances or orbital snapshots. No simulation inputs or results are changed.
The methodology uses N snapshots rather than assuming all available runs have
the same number of observations. Power back-off is 10 dB in the border strip.

The figures follow the corrected slide roles in the user's October 27 brief.
No PPTX was modified. Previous figures and source scripts were backed up in
`backups/20261027_100810` before replacement. Original simulation data and the
Encom reference files remain unchanged. The cover's two panels are separate
scenarios, not a claim that both mitigation methods were simulated jointly.
The conceptual architecture panels do not imply that conventional MSS supports
only one user; they illustrate the dedicated-terminal versus IMT-device distinction.

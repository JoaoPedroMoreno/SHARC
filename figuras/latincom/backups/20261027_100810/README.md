# LATINCOM presentation figures

Reproduce with `python tools/generate_latincom_figures.py` from the repository.

## Deliverables

- `latincom_cover`: cross-border coexistence and selective power back-off.
- `latincom_page_2`: several DC-MSS downlinks contributing interference to one FS receiver.
- `latincom_page_3`: exclusion-zone and border-strip power back-off comparison.
- `latincom_sharc_monte_carlo`: scenario setup, two mitigation branches, aggregate INR and protection-margin assessment.

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

Excluded cells use pale gray fills and thin solid borders. The exclusion radius
uses a separate red solid circle. Interference alone uses red dashed arrows.
The original methodological figure filename in `figuras` is also updated.

## Scientific scope and outstanding verification

All positions and region outlines are conceptual, not actual border coordinates,
distances or orbital snapshots. No simulation inputs or results are changed.
The methodology uses N snapshots rather than assuming all available runs have
the same number of observations. Power back-off is 10 dB in the border strip.

No LATINCOM PPTX was found in the repository. Pages 2 and 3 are proposed assets
based on the supplied brief; their exact correspondence to the current slide
content cannot be verified until the deck is available. No PPT was modified.

# LATINCOM: revised regional cover and MSS architecture

Generate with `python tools/generate_latincom_figures.py`.

- Cover: Natural Earth country boundaries from the repository, using the same reader and satellite asset as the Encom artwork. The two panels show the seven-country regional service area and Brazil/Argentina service area separately. Cells, beam selection, exclusion circle and border strip are conceptual and have no quantitative scale.
- Page 2A: terrestrial parabolic gateway, feeder link, transparent/bent-pipe satellite, service link and dedicated satellite handset with external antenna and keypad. An elliptical spot beam replaces the cellular hexagons.
- Page 2B: direct access to conventional IMT user equipment. It illustrates the access segment, not the absence of a gateway or mobile core in the complete system.
- Page 3: distinct service cells assigned to each satellite at different lateral positions and depths; red dashed interference paths converge on the receiving end of the wanted FS link.
- Page 7: each satellite is assigned a distinct nearby active cell in each illustrative snapshot; the exclusions and power-back-off rules remain unchanged.

The PNG files are exported at 600 dpi. PDF and SVG preserve vector text, cells and lines; the original satellite artwork remains an embedded raster asset. Preview PNGs have a white background. No new simulations were run and no simulation results were changed.

Earlier assets and scripts were backed up in `../backups/20261027_121926`.
This revision is exported to a separate directory, preserving the preceding versions.

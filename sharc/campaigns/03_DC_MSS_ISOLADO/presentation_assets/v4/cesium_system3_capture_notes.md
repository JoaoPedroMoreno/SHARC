# Cesium: System 3

Final image: `cesium_system3_constellation.png` (1920 x 1080).

This is a browser capture of the existing Cesium viewer with a temporary
presentation-only adapter. The capture's JPEG transport was re-encoded as PNG;
no objects, coordinates or text were added by raster editing.

Source configuration:
`sharc/campaigns/03_DC_MSS_ISOLADO/Script/base_input.yaml`.

Verified API metadata: 5280 satellites, one frame, Brazil service area,
2155 MHz, 5 MHz bandwidth, 25.803 km beam radius.
The YAML specifies 48 orbital planes, 110 satellites per plane, circular
340 km orbits and 53 degree inclination.

The capture uses t=0 from the existing OrbitModel, not a campaign Monte Carlo
snapshot. It does not calculate network performance. Orange points
represent satellites (3.5 px, restored to the previous size). Orbital-plane lines, legend,
title and parameter panel have been removed at the user's request. The globe
is centered in the image. Orange does not encode PBO in this constellation
view. Point sizes are symbols, not physical scale.
Earth occludes satellites on the far side. All 5280 are in the scene, not all
are visible from this camera.

The original viewer, model, campaign inputs and raw outputs were not modified.
Temporary presentation adapter files are under `tmp/pbo_presentation_review/`:
`serve_cesium_capture.py`, `system3_capture.js`, `system3_capture.css`.
The adapter restricts the orbit profile to one instant and removes the
campaign-02-oriented controls, visual UEs and approximate interference layers.
Cesium and imagery attribution remain visible.

Local capture view:
`http://127.0.0.1:8013/system3_capture.html?profile=presentation`.

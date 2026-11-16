"""Prepare ONE frame with the original NGSO backend for a direct screenshot."""
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT))
import yaml
from shapely.geometry import shape, mapping, MultiPolygon, LineString
from shapely.ops import split, unary_union
from sharc.satellite.ngso.backend.orbit_backend_service import OrbitSimulationBackend

out = ROOT / 'figuras/tcc_geographic_capture'
out.mkdir(exist_ok=True)
source = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml'
cfg = yaml.safe_load(source.read_text(encoding='utf-8'))
# Illustration-only copy; the campaign is never written or executed.
cfg['imt']['topology']['central_latitude'] = -25.5169
cfg['imt']['topology']['central_longitude'] = -54.6169
copy = out / 'input_visualization.yaml'
copy.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
backend = OrbitSimulationBackend(profile='presentation', param_file=copy)
backend.profile = replace(backend.profile, n_periods=0)
payload = backend.build_simulation()
# The legacy frontend reads polygon exteriors only. Split the coverage through
# Paraguay so its excluded interior stays open, without changing its boundary.
region = shape(payload['brazilGeoJson'])
parts = []
for polygon in region.geoms if region.geom_type=='MultiPolygon' else [region]:
    parts.extend(split(polygon, LineString([(-58,-90),(-58,90)])).geoms)
assert all(not part.interiors for part in parts)
assert unary_union(parts).symmetric_difference(region).area < 1e-8
payload['brazilGeoJson'] = mapping(MultiPolygon(parts))
assert 'Suriname' in payload['meta']['serviceAreaCountryNames']
assert 'Paraguay' not in payload['meta']['serviceAreaCountryNames']
assert len(payload['frames']) == 1
(out / 'original_backend_frame.json').write_text(json.dumps(payload), encoding='utf-8')
print(json.dumps(dict(frames=len(payload['frames']),satellites=len(payload['frames'][0]['satellites']),
                     countries=payload['meta']['serviceAreaCountryNames'],station=payload['station'])))

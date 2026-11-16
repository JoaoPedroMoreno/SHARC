"""Validate the exported visualization, without running a campaign."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / '.venv/Lib/site-packages'))
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep

data = json.loads((ROOT / 'figuras/tcc_geography_data.json').read_text())
assert 'Suriname' in data['service_countries']
assert 'Paraguay' not in data['service_countries']
countries = {f['properties']['name']:shape(f['geometry']) for f in data['countries']['features']}
region = prep(unary_union([countries[name] for name in data['service_countries']]))
points = [Point(*center) for center in data['cells']]
assert all(region.contains(point) for point in points)
assert not any(countries['Paraguay'].contains(point) for point in points)
suriname_cells = sum(countries['Suriname'].contains(point) for point in points)
assert suriname_cells > 0
assert sum(sat['count'] for sat in data['satellites']) == len(points)
assert all(sat['count'] > 0 for sat in data['satellites'] if sat['ring'])
assert data['geometry']['total_satellites'] == 5280
assert data['geometry']['minimum_service_angle'] == 32
assert data['station'] != data['simulated_station']
print(f'PASS: {len(points)} cells; Suriname: {suriname_cells}; Paraguay: 0; '
      f"serving satellites: {data['geometry']['serving_satellites']}")

"""Export geographic context from campaign 07, without running a simulation."""
import json
import sys
import logging
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT))
import shapefile
import yaml
import numpy as np
from shapely.geometry import shape, Point, MultiPoint
from shapely.ops import unary_union
from shapely.prepared import prep
from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.satellite.utils.sat_utils import calc_elevation

source = ROOT / 'sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts/base_input.yaml'
cfg = yaml.safe_load(source.read_text(encoding='utf-8'))
topology = cfg['imt']['topology']
names = topology['mss_dc']['beam_positioning']['service_grid']['grid_in_zone']['from_countries']['country_names']
assert 'Paraguay' not in names
features = []
reader = shapefile.Reader(str(ROOT / 'sharc/data/countries/ne_110m_admin_0_countries.shp'))
for record in reader.iterShapeRecords():
    name = record.record['ADMIN']
    features.append(dict(type='Feature', properties=dict(name=name, service=name in names),
                         geometry=record.shape.__geo_interface__))

# Reproduce the NGSO viewer's fixed grid and highest-elevation assignment.
service = prep(unary_union([shape(f['geometry']) for f in features if f['properties']['service']]))
paraguay = shape(next(f['geometry'] for f in features if f['properties']['name']=='Paraguay'))
radius = topology['mss_dc']['beam_radius']/1000
dx, dy = radius*1.5, radius*math.sqrt(3)
cells = []
for col in range(math.floor(-85*111/dx), math.ceil(-30*111/dx)+1):
    for row in range(math.floor(-60*111/dy), math.ceil(15*111/dy)+1):
        lon, lat = col*dx/111, (row+(.5 if col%2 else 0))*dy/111
        if service.contains(Point(lon,lat)):
            cells.append([lon,lat])
orbit = topology['mss_dc']['orbits'][0]
model = OrbitModel(Nsp=orbit['sats_per_plane'], Np=orbit['n_planes'],
    phasing=orbit['phasing_deg'], long_asc=orbit['long_asc_deg'],
    omega=orbit.get('omega_deg',0), delta=orbit['inclination_deg'],
    hp=orbit['perigee_alt_km'], ha=orbit['apogee_alt_km'], Mo=orbit['initial_mean_anomaly'],
    model_time_as_random_variable=False, t_min=0, t_max=None)
positions = model.get_orbit_positions_time_instant(0)
lat,lon,alt = (positions[key][:,0] for key in ['lat','lon','alt'])
assigned = {}
active_cells = []
threshold = topology['mss_dc']['beam_positioning']['service_grid']['minimum_service_angle']
for offset in range(0,len(cells),128):
    points = np.array(cells[offset:offset+128])
    elev = calc_elevation(points[:,1,None],lat[None,:],points[:,0,None],lon[None,:],
                          sat_height=alt[None,:]*1000,es_height=0)
    best = elev.argmax(axis=1)
    for i, sat in enumerate(best):
        if elev[i,sat] >= threshold:
            center = points[i].tolist()
            assigned.setdefault(int(sat),[]).append(center)
            active_cells.append(center)
assert not any(paraguay.contains(Point(*point)) for point in active_cells)
satellites=[]
for i in range(len(lat)):
    if not (-90<lon[i]<-25 and -65<lat[i]<23): continue
    footprint = MultiPoint(assigned.get(i,[])).convex_hull
    ring = list(footprint.exterior.coords) if footprint.geom_type=='Polygon' else []
    satellites.append(dict(id=i,lon=float(lon[i]),lat=float(lat[i]),altKm=float(alt[i]),
                           count=len(assigned.get(i,[])),ring=ring))
data = dict(countries=dict(type='FeatureCollection', features=features),
            station=dict(lon=-54.6169, lat=-25.5169),
            simulated_station=dict(lon=topology['central_longitude'], lat=topology['central_latitude']),
            station_reference='https://mapcarta.com/Ciudad_del_Este',
            station_role='Illustrative city reference requested by user, not simulated FS coordinates',
            service_countries=names, frequency_mhz=cfg['imt']['frequency'],
            cells=active_cells,satellites=satellites,beam_radius_km=radius,
            geometry=dict(time_seconds=0,altitude_km=orbit['perigee_alt_km'],
                          total_satellites=len(lat),candidate_cells=len(cells),
                          assigned_cells=len(active_cells),serving_satellites=len(assigned),
                          minimum_service_angle=threshold,paraguay_cells=0,
                          load_factor_applied=False,mitigation_applied=False),
            source=str(source), map_source='Natural Earth 1:110m, same local dataset as SHARC',
            caveat='Generalized borders are not suitable for resolving the country of a border receiver. '
                   'The city reference is only for this figure; campaign coordinates remain unchanged.',
            simulated=False)
(ROOT / 'figuras/tcc_geography_data.json').write_text(json.dumps(data), encoding='utf-8')
print(json.dumps({k: data[k] for k in ['station', 'service_countries', 'frequency_mhz']}))

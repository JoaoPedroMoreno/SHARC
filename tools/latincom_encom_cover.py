"""Dense metric service grid, using the original Encom map drawing functions."""
from functools import lru_cache
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Circle, RegularPolygon
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon, MultiPoint, box
from shapely.ops import transform, unary_union, polylabel
import latincom_visual_style as s
from generate_presentation_images import load_countries, country_name

REGIONAL=('Brazil','Argentina','Uruguay','Paraguay','Bolivia','Chile','Peru')
DISPLAY_CELL_SCALE=2.4
COVER_PANEL_OFFSETS=(-.2,6.6)

@lru_cache(maxsize=1)
def geography():
    records={country_name(c):unary_union([Polygon(r) for r in c.rings if len(r)>=4])
             for c in load_countries()}
    center=records['Brazil'].centroid
    crs=CRS.from_proj4(f'+proj=laea +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m')
    project=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    countries={name:transform(project.transform,records[name]) for name in REGIONAL}
    regional=unary_union(list(countries.values()))
    return countries,regional,project

def grid(country,exclusion=None,border_zone=None):
    radius=s.original.DRAWING_RADIUS_M*DISPLAY_CELL_SCALE
    xmin,ymin,xmax,ymax=country.bounds
    cells=[]
    for row,y in enumerate(np.arange(ymin-radius,ymax+2*radius,math.sqrt(3)*radius/2)):
        for x in np.arange(xmin-2*radius,xmax+3*radius,3*radius):
            x+=(row%2)*1.5*radius
            hexagon=Polygon(s.original.hex_vertices((x,y),radius))
            if not hexagon.intersects(country):
                continue
            clipped=hexagon.intersection(country)
            if clipped.area<=1:
                continue
            p=Point(x,y)
            excluded=exclusion is not None and exclusion.covers(p)
            pbo=border_zone is not None and border_zone.covers(p)
            cells.append(dict(center=(x,y),hexagon=hexagon,shape=clipped,
                              active=not excluded,pbo=bool(pbo),excluded=excluded))
    return cells

def fs_symbol_placement(country,affine):
    """Fit the entire schematic dish inside Paraguay, not at a map boundary."""
    projected=unary_union([Polygon(affine.transform(np.asarray(p.exterior.coords)))
                           for p in s.original.polygons(country)])
    interior=polylabel(max(s.original.polygons(projected),key=lambda p:p.area),
                       tolerance=.002)
    scale=.055
    xmin,ymin,xmax,ymax=s.FS_SYMBOL_BOUNDS
    center=np.array([(xmin+xmax)/2,(ymin+ymax)/2])
    while scale>.01:
        foot=np.array([interior.x,interior.y])-center*scale
        bounds=box(foot[0]+(xmin-.1)*scale,foot[1]+(ymin-.1)*scale,
                   foot[0]+(xmax+.1)*scale,foot[1]+(ymax+.1)*scale)
        if projected.covers(bounds):
            return foot,scale,bounds
        scale*=.9
    raise ValueError('Cannot fit the FS symbol within Paraguay')


def cover():
    countries,regional,project=geography()
    fig=plt.figure(figsize=(14.4,9))
    ax=fig.add_axes([0,0,1,1],xlim=(0,14.4),ylim=(0,9))
    ax.axis('off'); ax.set_aspect('equal')
    def text(x,y,value,size=16,color=s.INK,ha='left',halo=False):
        obj=ax.text(x,y,value,fontsize=size,color=color,va='center',ha=ha,zorder=35)
        if halo:
            obj.set_path_effects([pe.withStroke(linewidth=2,foreground='white')])
        return obj
    text(.45,8.62,'DC-MSS / FS coexistence',28,'#387391')
    text(13.95,8.62,'Schematic',10,'#8B9BA4',ha='right')
    counts=[]
    for panel,kind in enumerate(['ez','pbo']):
        dx=COVER_PANEL_OFFSETS[panel]
        service=regional if kind=='ez' else unary_union([countries['Brazil'],countries['Argentina']])
        affine=s.original.fit_map(regional,(dx+.35,1.50,dx+7.65,7.0),vertical_scale=.80)
        fs_screen,fs_scale,fs_bounds=fs_symbol_placement(countries['Paraguay'],affine)
        # This is a symbol placement, not a new simulated receiver coordinate.
        display_fs=Point(affine.inverted().transform(fs_screen))
        # An enlarged illustrative zone remains legible at continental scale.
        exclusion=display_fs.buffer(180000) if kind=='ez' else None
        band=service.difference(service.buffer(-65000)) if kind=='pbo' else None
        cells=grid(service,exclusion,band)
        text(dx+4,7.95,'Exclusion zone' if kind=='ez' else 'Conditional power back-off',20,
             '#387391' if kind=='ez' else s.ORANGE,ha='center')
        for name,shape in countries.items():
            if kind=='pbo' and name not in ('Brazil','Argentina'):
                s.original.draw_geometry(ax,shape,affine,'#F4F7F5','#B8C5BE',.7,1)
        s.original.draw_grid(ax,service,cells,affine,line_width=.58)
        for name,shape in countries.items():
            s.original.draw_geometry(ax,shape,affine,'none',s.original.BORDER,.95,9)
        for cell in cells:
            if cell['excluded']:
                s.original.draw_geometry(ax,cell['shape'],affine,'#DFE5E8','#A5B0B6',.35,7)
        if exclusion is not None:
            s.original.draw_geometry(ax,exclusion,affine,'none',s.RED,1.6,11)
        used=set()
        sources=[(dx+1.75,7.00,1.8),(dx+3.9,7.35,1.9),(dx+6.25,6.95,1.8)]
        targets=[ [(-69,-10),(-64,-20),(-60,-6)],
                  [(-54,-6),(-55,-28),(-66,-35)],
                  [(-43,-9),(-48,-19),(-53,-25)] ]
        for satellite_index,(position,locations) in enumerate(zip(sources,targets)):
            selected=[]
            if kind=='ez' and satellite_index==1:
                locations=[locations[0],locations[2]]
            for lon,lat in locations:
                aim=np.array(project.transform(lon,lat))
                candidates=[(i,c) for i,c in enumerate(cells) if c['active'] and i not in used
                            and c['shape'].area>.98*c['hexagon'].area]
                i,cell=min(candidates,key=lambda pair:np.linalg.norm(np.array(pair[1]['center'])-aim))
                used.add(i)
                vertices=affine.transform(np.asarray(cell['hexagon'].exterior.coords)[:-1])
                selected.append((cell,vertices))
            center=np.mean([vertices.mean(axis=0) for _,vertices in selected],axis=0)
            tilt=s.pointing_angle(position[0],position[1],center) if satellite_index!=1 else 0
            source=s.satellite(ax,*position,tilt_deg=tilt)
            for beam_index,(cell,vertices) in enumerate(selected):
                if kind=='ez' and satellite_index==1:
                    hull=MultiPoint([tuple(source),*map(tuple,vertices)]).convex_hull
                    assert not hull.intersects(fs_bounds), 'Central beam overlaps the FS symbol'
                s.original.beam(ax,source,vertices,cell['pbo'],
                    beam_id=f'cover-{kind}-{satellite_index}:{beam_index}')
                s.original.draw_geometry(ax,cell['shape'],affine,
                    s.original.ORANGE_PALE if cell['pbo'] else s.original.BLUE_SELECTED,
                    s.ORANGE if cell['pbo'] else s.BLUE,.9,8)
        s.receiver(ax,*fs_screen,fs_scale,north=s.ground_north(affine))
        for name,coord in [('Brazil',(-49,-12)),('Argentina',(-65,-37))]:
            pos=affine.transform(project.transform(*coord))
            text(*pos,name,14,ha='center',halo=True)
        text(dx+4,1.27,'Regional service area' if kind=='ez' else 'Brazil / Argentina service area',14,ha='center')
        union=unary_union([c['shape'] for c in cells])
        assert union.difference(service).area<1
        assert service.difference(union).area/service.area<1e-8
        counts.append(dict(method=kind,cells=len(cells),outside_area_m2=union.difference(service).area,
                           fs_symbol_inside_paraguay=True,fs_symbol_scale=fs_scale,
                           service_beams=len(used)))
    ax.plot([.45,13.95],[1.02,1.02],color='#DCE4E8',lw=1,gid='cover-legend-divider')
    entries=[(.6,.78,s.original.BLUE_PALE,s.original.BLUE_EDGE,'Nominal-power cell'),
             (5.0,.78,s.original.ORANGE_PALE,s.ORANGE,'10 dB back-off'),
             (9.45,.78,'#DFE5E8','#A5B0B6','Excluded cell'),
             (.6,.29,s.original.BLUE_SELECTED,s.BLUE,'Shown beam footprint')]
    for x,y,fill,edge,caption in entries:
        ax.add_patch(RegularPolygon((x,y),6,radius=.12,orientation=math.pi/6,
                     fc=fill,ec=edge,lw=1.4,zorder=35,gid='cover-legend-cell'))
        text(x+.24,y,caption,13)
    ax.add_patch(Circle((5.0,.29),.12,fill=False,ec=s.RED,lw=1.5,zorder=35))
    text(5.24,.29,'Exclusion zone',13)
    s.receiver(ax,9.45,.11,.033,north=(0,.45))
    text(9.72,.29,'Victim FS (Paraguay)',13)
    fig._latincom_validation={'cover':counts,'illustrative_grid_radius_m':s.original.DRAWING_RADIUS_M*DISPLAY_CELL_SCALE,
                             'display_cell_scale':DISPLAY_CELL_SCALE,
                             'map_vertical_scale':.80,'grid_line_width_pt':.58,
                             'panel_center_separation':6.8,'map_height':5.5,
                             'legend_explains_cells':True,'point_callout_leaders':0,
                             'encom_functions':['fit_map','draw_grid','beam','draw_geometry']}
    return fig

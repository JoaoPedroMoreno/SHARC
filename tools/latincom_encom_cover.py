"""Dense metric service grid, using the original Encom map drawing functions."""
from functools import lru_cache
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.collections import PatchCollection
from matplotlib.patches import Circle, PathPatch, RegularPolygon
from pyproj import CRS, Transformer
from shapely.affinity import translate
from shapely.geometry import Point, Polygon, MultiPoint, box
from shapely.ops import transform, unary_union, nearest_points
import latincom_visual_style as s
from generate_presentation_images import load_countries, country_name

REGIONAL=('Brazil','Argentina','Uruguay','Paraguay','Bolivia','Chile','Peru')
DISPLAY_CELL_SCALE=2.4
COVER_PANEL_OFFSETS=(-.2,6.6)
FS_DISPLAY_SCALE=.026
EXCLUDED_EDGE='#87949D'
EXCLUDED_DASH=(0,(2.5,1.6))

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


def draw_cover_grid(ax,cells,affine):
    """Draw cell states directly, with no country fill beneath excluded cells."""
    patches,faces,edges,widths,styles=[],[],[],[],[]
    for cell in cells:
        for polygon in s.original.polygons(cell['shape']):
            patches.append(PathPatch(s.original.mpl_path(polygon)))
            excluded=cell['excluded']
            faces.append('none' if excluded else
                         s.original.ORANGE_PALE if cell['pbo'] else s.original.BLUE_PALE)
            edges.append(EXCLUDED_EDGE if excluded else
                         s.ORANGE if cell['pbo'] else s.original.BLUE_EDGE)
            widths.append(.8 if excluded else .58)
            styles.append(EXCLUDED_DASH if excluded else 'solid')
    collection=PatchCollection(patches,facecolors=faces,edgecolors=edges,
                               linewidths=widths,linestyles=styles,zorder=3,
                               gid='cover-cell-grid')
    collection.set_transform(affine+ax.transData)
    ax.add_collection(collection)
    return collection


@lru_cache(maxsize=1)
def triple_border():
    """Locate the junction using the existing country boundaries."""
    countries,_,_=geography()
    br_ar=countries['Brazil'].boundary.intersection(countries['Argentina'].boundary)
    return nearest_points(countries['Paraguay'].boundary,br_ar)[0]


def fs_symbol_placement(country,affine):
    """Place the dish nearest the triple border, wholly within Paraguay."""
    projected=unary_union([Polygon(affine.transform(np.asarray(p.exterior.coords)))
                           for p in s.original.polygons(country)])
    target=Point(affine.transform(triple_border().coords[0]))
    scale=FS_DISPLAY_SCALE
    xmin,ymin,xmax,ymax=s.FS_SYMBOL_BOUNDS
    while scale>.01:
        corners=np.array([(xmin-.1,ymin-.1),(xmin-.1,ymax+.1),
                          (xmax+.1,ymin-.1),(xmax+.1,ymax+.1)])*scale
        # Every corner must stay inside; validate the entire box as well.
        feasible=projected
        for x,y in corners:
            feasible=feasible.intersection(translate(projected,xoff=-x,yoff=-y))
        # Ciudad del Este is on the Paraguayan side, north of the junction.
        feasible=feasible.intersection(box(projected.bounds[0],target.y+.01,
                                            projected.bounds[2],projected.bounds[3]))
        feasible=feasible.buffer(-1e-6)
        if not feasible.is_empty:
            candidate=nearest_points(feasible,target)[0]
            foot=np.array(candidate.coords[0])
            bounds=box(*(foot+corners[0]),*(foot+corners[3]))
            if projected.covers(bounds) and candidate.distance(target)<.25:
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
        draw_cover_grid(ax,cells,affine)
        for name,shape in countries.items():
            s.original.draw_geometry(ax,shape,affine,'none',s.original.BORDER,.95,9)
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
                footprints=s.original.draw_geometry(ax,cell['shape'],affine,
                    s.original.ORANGE_PALE if cell['pbo'] else s.original.BLUE_PALE,
                    s.ORANGE if cell['pbo'] else s.original.BLUE_EDGE,.58,8)
                for footprint in footprints:
                    footprint.set_gid('cover-service-footprint')
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
                           fs_placement='nearest BR-AR-PY junction, inside Paraguay',
                           fs_base_display=fs_screen.tolist(),
                           triple_border_display=affine.transform(triple_border().coords[0]).tolist(),
                           service_beams=len(used)))
    ax.plot([.45,13.95],[1.02,1.02],color='#DCE4E8',lw=1,gid='cover-legend-divider')
    entries=[(.6,.78,s.original.BLUE_PALE,s.original.BLUE_EDGE,'Nominal-power cell','solid'),
             (5.0,.78,s.original.ORANGE_PALE,s.ORANGE,'Power-reduced cell (10 dB)','solid'),
             (10.0,.78,'none',EXCLUDED_EDGE,'Excluded cell',EXCLUDED_DASH)]
    for x,y,fill,edge,caption,style in entries:
        ax.add_patch(RegularPolygon((x,y),6,radius=.12,orientation=math.pi/6,
                     fc=fill,ec=edge,lw=1.4,ls=style,zorder=35,gid='cover-legend-cell'))
        text(x+.24,y,caption,13)
    ax.add_patch(Circle((3.6,.29),.12,fill=False,ec=s.RED,lw=1.5,zorder=35))
    text(3.84,.29,'Exclusion zone',13)
    s.receiver(ax,7.9,.11,.033,north=(0,.45))
    text(8.17,.29,'Victim FS (Paraguay)',13)
    fig._latincom_validation={'cover':counts,'illustrative_grid_radius_m':s.original.DRAWING_RADIUS_M*DISPLAY_CELL_SCALE,
                             'display_cell_scale':DISPLAY_CELL_SCALE,
                             'map_vertical_scale':.80,'grid_line_width_pt':.58,
                             'panel_center_separation':6.8,'map_height':5.5,
                             'legend_explains_cells':True,'point_callout_leaders':0,
                             'cell_states':['nominal-power','power-reduced','excluded'],
                             'excluded_cells_transparent':True,
                             'separate_footprint_highlight':False,
                             'encom_functions':['fit_map','mpl_path','beam','draw_geometry']}
    return fig

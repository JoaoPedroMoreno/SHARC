"""Dense metric service grid, using the original Encom map drawing functions."""
from functools import lru_cache
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon
from shapely.ops import transform, unary_union
import latincom_visual_style as s
from generate_presentation_images import load_countries, country_name

REGIONAL=('Brazil','Argentina','Uruguay','Paraguay','Bolivia','Chile','Peru')

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
    radius=s.original.DRAWING_RADIUS_M
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

def cover():
    countries,regional,project=geography()
    fig=plt.figure(figsize=(16,9))
    ax=fig.add_axes([0,0,1,1],xlim=(0,16),ylim=(0,9))
    ax.axis('off'); ax.set_aspect('equal')
    def text(x,y,value,size=16,color=s.INK,ha='left',halo=False):
        obj=ax.text(x,y,value,fontsize=size,color=color,va='center',ha=ha,zorder=35)
        if halo:
            obj.set_path_effects([pe.withStroke(linewidth=2,foreground='white')])
        return obj
    text(.55,8.5,'DC-MSS / FS coexistence',28,'#387391')
    fs=Point(project.transform(-54.5746686,-25.5549751))
    counts=[]
    for panel,kind in enumerate(['ez','pbo']):
        dx=panel*8
        service=regional if kind=='ez' else unary_union([countries['Brazil'],countries['Argentina']])
        # An enlarged illustrative zone remains legible at continental scale.
        exclusion=fs.buffer(180000) if kind=='ez' else None
        band=service.difference(service.buffer(-65000)) if kind=='pbo' else None
        cells=grid(service,exclusion,band)
        affine=s.original.fit_map(regional,(dx+.35,.95,dx+7.65,5.55),vertical_scale=.50)
        text(dx+.5,7.84,'Exclusion zone' if kind=='ez' else 'Conditional power back-off',20,
             '#387391' if kind=='ez' else s.ORANGE)
        for name,shape in countries.items():
            if kind=='pbo' and name not in ('Brazil','Argentina'):
                s.original.draw_geometry(ax,shape,affine,'#F4F7F5','#B8C5BE',.7,1)
        s.original.draw_grid(ax,service,cells,affine,line_width=.30)
        for name,shape in countries.items():
            s.original.draw_geometry(ax,shape,affine,'none','#8EA6B3',.55,9)
        for cell in cells:
            if cell['excluded']:
                s.original.draw_geometry(ax,cell['shape'],affine,'#DFE5E8','#A5B0B6',.35,7)
        if exclusion is not None:
            s.original.draw_geometry(ax,exclusion,affine,'none',s.RED,1.6,11)
        used=set()
        sources=[(dx+1.75,6.68,1.8),(dx+3.9,7.1,1.9),(dx+6.25,6.42,1.8)]
        targets=[ [(-69,-10),(-64,-20),(-60,-6)],
                  [(-54,-6),(-55,-28),(-66,-35)],
                  [(-43,-9),(-48,-19),(-53,-25)] ]
        for position,locations in zip(sources,targets):
            source=s.satellite(ax,*position)
            for lon,lat in locations:
                aim=np.array(project.transform(lon,lat))
                candidates=[(i,c) for i,c in enumerate(cells) if c['active'] and i not in used
                            and c['shape'].area>.98*c['hexagon'].area]
                i,cell=min(candidates,key=lambda pair:np.linalg.norm(np.array(pair[1]['center'])-aim))
                used.add(i)
                vertices=affine.transform(np.asarray(cell['hexagon'].exterior.coords)[:-1])
                s.original.beam(ax,source,vertices,cell['pbo'])
                s.original.draw_geometry(ax,cell['shape'],affine,
                    s.original.ORANGE_PALE if cell['pbo'] else s.original.BLUE_SELECTED,
                    s.ORANGE if cell['pbo'] else s.BLUE,.9,8)
        fs_screen=affine.transform(fs.coords[0])
        s.receiver(ax,*fs_screen,.055)
        text(dx+6.4,2.3,'Victim FS',14,s.GREEN)
        ax.plot([dx+6.3,fs_screen[0]+.1],[2.3,fs_screen[1]+.12],c=s.GREEN,lw=1,zorder=22)
        if exclusion is not None:
            text(dx+5.85,1.75,r'$R_{ez}$',16,s.RED)
            ax.plot([dx+5.75,fs_screen[0]+.2],[1.8,fs_screen[1]-.05],c=s.RED,lw=.9,zorder=22)
        for name,coord in [('Brazil',(-49,-12)),('Argentina',(-65,-37))]:
            pos=affine.transform(project.transform(*coord))
            text(*pos,name,14,ha='center',halo=True)
        paraguay=affine.transform((countries['Paraguay'].centroid.x,countries['Paraguay'].centroid.y))
        text(dx+.65,2.15,'Paraguay',13)
        ax.plot([dx+1.8,paraguay[0]],[2.15,paraguay[1]],c=s.INK,lw=.8,zorder=23)
        text(dx+4,.65,'Regional service area' if kind=='ez' else 'Brazil / Argentina service area',15,ha='center')
        union=unary_union([c['shape'] for c in cells])
        assert union.difference(service).area<1
        assert service.difference(union).area/service.area<1e-8
        counts.append(dict(method=kind,cells=len(cells),outside_area_m2=union.difference(service).area))
    text(.55,.20,'Schematic: mitigation extents enlarged for visibility.',10,'#8B9BA4')
    fig._latincom_validation={'cover':counts,'grid_radius_m':s.original.DRAWING_RADIUS_M,
                             'encom_functions':['fit_map','draw_grid','beam','draw_geometry']}
    return fig

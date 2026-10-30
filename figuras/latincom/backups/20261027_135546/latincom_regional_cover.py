"""Regional schematic using the same Natural Earth source as the Encom artwork."""
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Polygon, Circle
import latincom_visual_style as s

sys.path.insert(0,str(s.REFERENCE))
from generate_presentation_images import load_countries, country_name

REGIONAL={'Brazil','Argentina','Uruguay','Paraguay','Bolivia','Chile','Peru'}

def cover():
    fig=plt.figure(figsize=(12,6.75))
    ax=fig.add_axes([0,0,1,1],xlim=(0,12),ylim=(0,6.75))
    ax.axis('off'); ax.set_aspect('equal')
    def text(x,y,value,size=14,color=s.INK,ha='left'):
        ax.text(x,y,value,fontsize=size,color=color,ha=ha,va='center',zorder=35)
    text(.45,6.32,'DC-MSS / FS coexistence',26,'#387391')
    countries=[c for c in load_countries() if country_name(c) in REGIONAL]
    for panel,kind in enumerate(['ez','pbo']):
        dx=panel*6
        served=REGIONAL if kind=='ez' else {'Brazil','Argentina'}
        text(dx+.45,5.77,'Exclusion zone' if kind=='ez' else 'Conditional power back-off',18,
             '#387391' if kind=='ez' else s.ORANGE)
        # Common schematic projection, with identical scaling in both panels.
        def project(coords):
            a=np.asarray(coords)
            return np.column_stack((dx+3+(a[:,0]+58)*.083,a[:,1]*.055+3.64))
        paths={}
        for c in countries:
            name=country_name(c)
            rings=[Path(project(r)) for r in c.rings]
            path=Path.make_compound_path(*rings)
            paths[name]=path
            ax.add_patch(PathPatch(path,fc=s.original.BLUE_PALE if name in served else '#F1F7F3',
                                   ec='#ADBEC6',lw=.8,zorder=1))
        service=Path.make_compound_path(*(paths[name] for name in served))
        clip=PathPatch(service,transform=ax.transData)
        fs=project([(-54.5746686,-25.5549751)])[0]
        cells=[]
        for row,y in enumerate(np.arange(.62,3.98,.168)):
            for x in np.arange(dx+1.15,dx+5.4,.194):
                center=np.array([x+(row%2)*.097,y])
                if not service.contains_point(center):
                    continue
                excluded=kind=='ez' and np.linalg.norm(center-fs)<.32
                boundary=any(not service.contains_point(center+v) for v in
                             [(0,.16),(0,-.16),(.16,0),(-.16,0)])
                affected=kind=='pbo' and boundary
                fill='#E3E8EB' if excluded else s.original.ORANGE_PALE if affected else '#DEEDF4'
                color='#AAB8C0' if excluded else s.ORANGE if affected else s.BLUE
                patch=Polygon(s.hexagon(*center,.112),fc=fill,ec=color,lw=.38,zorder=3)
                patch.set_clip_path(clip); ax.add_patch(patch)
                if not excluded:
                    cells.append((center,affected))
        # Explicit targets spread across the service region, rather than sorted grid indices.
        desired=[(-65,-13),(-49,-10),(-60,-36)] if kind=='ez' else [(-59,-8),(-42,-17),(-63,-35)]
        sats=[(dx+1.18,4.83),(dx+4.65,4.99),(dx+3.02,4.38)]
        used=set()
        for (sx,sy),lonlat in zip(sats,desired):
            source=s.satellite(ax,sx,sy,1.48)
            target=project([lonlat])[0]
            order=sorted(range(len(cells)),key=lambda i:np.linalg.norm(cells[i][0]-target))
            selected=[]
            for i in order:
                if i not in used and all(np.linalg.norm(cells[i][0]-cells[j][0])>.29 for j in selected):
                    selected.append(i); used.add(i)
                if len(selected)==2:
                    break
            for i in selected:
                center,pbo=cells[i]
                footprint=s.hexagon(*center,.112)
                s.original.beam(ax,source,footprint,pbo=pbo,broad=True)
                patch=Polygon(footprint,fc=s.original.ORANGE_PALE if pbo else s.original.BLUE_SELECTED,
                              ec=s.ORANGE if pbo else s.BLUE,lw=1,zorder=8)
                patch.set_clip_path(clip); ax.add_patch(patch)
        if kind=='ez':
            ax.add_patch(Circle(fs,.32,fill=False,ec=s.RED,lw=1.5,zorder=21))
            text(dx+4.55,1.38,r'$R_{ez}$',16,s.RED)
            ax.plot([dx+4.48,fs[0]+.28],[1.4,fs[1]-.1],c=s.RED,lw=1,zorder=22)
        target=s.receiver(ax,fs[0],fs[1]-.07,.046)
        text(dx+4.55,1.95,'Victim FS',12,s.GREEN)
        ax.plot([dx+4.5,target[0]+.13],[1.95,target[1]-.12],c=s.GREEN,lw=1,zorder=22)
        # Geographic labels avoid competing with the narrow Paraguay outline.
        text(dx+4.13,2.95,'Brazil',15,'#387391',ha='center')
        text(dx+2.47,.99,'Argentina',12,ha='center')
        text(dx+.58,1.65,'Paraguay',12)
        ax.plot([dx+1.65,fs[0]-.10],[1.65,fs[1]],c=s.INK,lw=.75,zorder=22)
        text(dx+3,.40,'Regional service area' if kind=='ez' else 'Brazil / Argentina service area',13,ha='center')
    text(.45,.11,'Natural Earth boundaries; cells and mitigation extent are illustrative.',9,'#8B9BA4')
    return fig

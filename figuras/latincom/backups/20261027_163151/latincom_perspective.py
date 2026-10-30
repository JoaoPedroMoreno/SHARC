"""Perspective ground, footprints and beam fans from the Encom reference."""
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch
from matplotlib.transforms import Affine2D
from shapely.geometry import Polygon, Point
import latincom_visual_style as s

EXCLUDED = '#E2E7EA'
GRAY = '#AAB8C0'

def label(ax,x,y,value,size=15,color=s.INK,ha='left'):
    return ax.text(x,y,value,fontsize=size,color=color,va='center',ha=ha,zorder=35)

def interference(ax,source,target,lw=1.5):
    ax.annotate('',xy=target,xytext=source,zorder=17,
                arrowprops=dict(arrowstyle='-|>',color=s.RED,lw=lw,
                                linestyle=(0,(5,3)),shrinkA=2,shrinkB=3))

def tower_on_ground(ax,local,position,scale):
    x,y=position
    foundation=local.transform([(x-2.8,y-2.2),(x+2.8,y-2.2),
                                (x+2.8,y+2.2),(x-2.8,y+2.2)])
    ax.add_patch(Patch(foundation,fc='#D7E8DE',ec=s.GREEN,lw=1,zorder=12))
    foot=local.transform(position)
    return s.receiver(ax,*foot,scale)

def plane(ax,local,method='none',phase=None):
    ground,base_grid,_,_,border=s.original.local_coverage_geometry()
    terrain=local.transform(np.asarray(ground.exterior.coords))
    ax.add_patch(Patch(terrain,fc='#F1F7F2',ec='#A4B9AD',lw=1.2,zorder=1))
    victim=(-11.5,0)
    exclusion=Point(victim).buffer(15.0,resolution=64)
    if method=='ez':
        # Extend the reference grid into the territory containing the FS.
        base_grid=[]
        for col in range(-5,7):
            for row in range(-3,7):
                center=(1.5*5.6*col,math.sqrt(3)*5.6*(row+.5*(col%2)))
                shape=Polygon(s.original.hex_vertices(center,5.6)).intersection(ground)
                if shape.area>1e-8:
                    base_grid.append((col,row,shape))
    cells=[]
    for col,row,shape in base_grid:
        center=shape.representative_point()
        excluded=method=='ez' and exclusion.covers(center)
        active=True if phase is None else ((col*7+row*3+phase*4)%9 not in (0,1,5))
        pbo=method=='pbo' and col==0 and active
        color=GRAY if excluded or not active else s.ORANGE if pbo else s.BLUE
        nominal_fill=s.original.BLUE_SELECTED if phase is not None else s.original.BLUE_PALE
        fill=EXCLUDED if excluded else 'white' if not active else s.original.ORANGE_PALE if pbo else nominal_fill
        vertices=local.transform(np.asarray(shape.exterior.coords)[:-1])
        ax.add_patch(Patch(vertices,fc=fill,ec=color,lw=.65 if phase is not None else 1.1,
                           ls=(0,(2,2)) if not active and not excluded else '-',zorder=3))
        cells.append(dict(key=(col,row),vertices=vertices,active=active and not excluded,
                          pbo=pbo,shape=shape))
    if method=='ez':
        boundary=local.transform(np.asarray(exclusion.exterior.coords))
        ax.plot(boundary[:,0],boundary[:,1],color=s.RED,lw=1.3,zorder=10)
        a,b=local.transform([victim,(victim[0]+15,victim[1])])
        ax.plot([a[0],b[0]],[a[1],b[1]],color=s.RED,lw=.9,zorder=10)
    else:
        frontier=local.transform(np.asarray(border.coords))
        ax.plot(frontier[:,0],frontier[:,1],color=s.INK,lw=1.4 if phase is None else .85,
                ls=(0,(5,3)),zorder=10)
    return cells, victim

def select_cells(cells,keys,used=None):
    used=set() if used is None else used
    selected=[]
    for key in keys:
        choices=[c for c in cells if c['active'] and c['key'] not in used]
        if not choices:
            break
        cell=min(choices,key=lambda c:(c['key'][0]-key[0])**2+(c['key'][1]-key[1])**2)
        used.add(cell['key'])
        selected.append(cell)
    return selected

def illuminate(ax,source,selected):
    for cell in selected:
        s.original.beam(ax,source,cell['vertices'],pbo=cell['pbo'],broad=True,
                        visual_scale=s.original.mechanism_visual_scale(cell['pbo']))
        ax.add_patch(Patch(cell['vertices'],fc='none',ec=s.ORANGE if cell['pbo'] else s.BLUE,
                           lw=1.1,zorder=8))

def context():
    fig=plt.figure(figsize=(16,9))
    ax=fig.add_axes([0,0,1,1],xlim=(0,16),ylim=(0,9))
    ax.axis('off'); ax.set_aspect('equal')
    label(ax,.65,8.45,'Cross-border aggregate interference',28,'#387391')
    local=Affine2D().scale(.145,.053).skew_deg(8,0).translate(8.1,2.2)
    cells,victim=plane(ax,local)
    rx=tower_on_ground(ax,local,victim,.13)
    tx=tower_on_ground(ax,local,(-34,0),.13)
    ax.annotate('',xy=rx,xytext=tx,zorder=18,
                arrowprops=dict(arrowstyle='-|>',color=s.GREEN,lw=2))
    label(ax,3.12,1.67,'FS transmitter',15,s.GREEN,ha='center')
    label(ax,6.05,1.67,'Victim FS receiver',15,s.GREEN,ha='center')
    label(ax,4.78,3.53,'Wanted FS link',15,s.GREEN,ha='center')
    label(ax,4.2,4.78,'Paraguay',20,ha='center')
    label(ax,12.45,4.78,'Brazil',20,ha='center')
    label(ax,.7,6.95,'Multiple downlink contributions',17)
    label(ax,1.4,6.12,r'$I_{agg}=\sum_i I_i$',25,s.RED)
    used=set()
    groups=[((8.15,6.65,2.4),[(0,0),(0,2)]),
            ((10.65,7.50,2.5),[(2,3),(2,0)]),
            ((13.45,6.83,2.4),[(4,0),(4,2),(5,3)])]
    for (position,keys),tilt in zip(groups,[16,7,-16]):
        selected=select_cells(cells,keys,used)
        aim=np.mean([c['vertices'].mean(axis=0) for c in selected],axis=0)
        _,y,width=position
        x=aim[0]-(y-aim[1])*math.tan(math.radians(tilt))
        source=s.satellite(ax,x,y,width,tilt_deg=tilt)
        illuminate(ax,source,selected)
        interference(ax,source,rx)
    tip=local.transform((-2.8,-20))
    ax.annotate('Border',xy=tip,xytext=(8.2,.76),ha='center',fontsize=15,color=s.INK,
                arrowprops=dict(arrowstyle='-|>',color=s.INK,lw=1),zorder=25)
    label(ax,15.3,.38,'Schematic',10,GRAY,ha='right')
    return fig

def snapshot(ax,cx,cy,method,phase):
    label(ax,cx,cy+1.16,f'Snapshot {phase+1}',12,ha='center')
    local=Affine2D().scale(.029,.013).skew_deg(8,0).translate(cx,cy-.25)
    cells,victim=plane(ax,local,method,phase)
    target=tower_on_ground(ax,local,victim,.041)
    used=set()
    groups=[((cx-.12+phase*.18,cy+.71,.78),[(0,0),(0,2)]),
            ((cx+.95-phase*.12,cy+.86,.82),[(3,3),(4,0)])]
    if method=='ez':
        groups[0]=(groups[0][0],[(-3,2),(0,3)])
    for j,(position,keys) in enumerate(groups):
        selected=select_cells(cells,keys,used)
        aim=np.mean([c['vertices'].mean(axis=0) for c in selected],axis=0)
        tilt=(14 if j==0 else -14)+(phase*3)
        _,y,width=position
        x=aim[0]-(y-aim[1])*math.tan(math.radians(tilt))
        source=s.satellite(ax,x,y,width,tilt_deg=tilt)
        illuminate(ax,source,selected)
        interference(ax,source,target,.85)
    label(ax,target[0]-.22,target[1]-.35,'FS',9,s.GREEN,ha='right')
    if method=='ez':
        label(ax,cx-.43,cy-.63,r'$R_{ez}$',10,s.RED)
    else:
        a,b=local.transform([(0,-24),(8.4,-24)])
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='<->',color=s.ORANGE,lw=1))
        label(ax,cx+.23,cy-.68,r'$D_{border}$',10,s.ORANGE)

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

def tower_on_ground(ax,local,position,scale,facing='north'):
    x,y=position
    foundation=local.transform([(x-2.8,y-2.2),(x+2.8,y-2.2),
                                (x+2.8,y+2.2),(x-2.8,y+2.2)])
    ax.add_patch(Patch(foundation,fc='#E2E7EA',ec='#83949D',lw=1,zorder=12))
    foot=local.transform(position)
    return s.receiver(ax,*foot,scale,facing=facing,north=s.ground_north(local))

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
    """Encom panel (a), with the same ground, satellite and five beams."""
    fig=plt.figure(figsize=(16,8.4))
    ax=fig.add_axes([0,0,1,1],xlim=(0,120),ylim=(-3,60))
    ax.axis('off'); ax.set_aspect('equal')
    label(ax,6,53,'(a) No power back-off',27)
    local=Affine2D().scale(.92,.40).skew_deg(8,0).translate(59,11)
    ground,grid,_,_,border=s.original.local_coverage_geometry()
    terrain=local.transform(np.asarray(ground.exterior.coords))
    ax.add_patch(Patch(terrain,fc='#F1F7F2',ec='#A4B9AD',lw=1.3,
                       zorder=1,gid='shared-ground'))
    frontier=np.asarray(border.coords)
    if frontier[0,1]>frontier[-1,1]:
        frontier=frontier[::-1]
    frontier=local.transform(frontier)
    ax.plot(frontier[:,0],frontier[:,1],color=s.INK,lw=2,
            ls=(0,(5,3)),zorder=10,gid='ground-frontier')
    label(ax,32,30,'Paraguay',18,ha='center')
    label(ax,99,30,'Brazil',19,ha='center')
    label(ax,51,0,'Border',18,ha='center')
    s.original.leader(ax,(51,1.5),frontier[0],s.INK,1.3)
    cells=[]
    for column,row,shape in grid:
        vertices=local.transform(np.asarray(shape.exterior.coords)[:-1])
        ax.add_patch(Patch(vertices,fc=s.original.BLUE_PALE,ec=s.BLUE,
                           lw=1.25,zorder=3,gid='ground-cell'))
        cells.append((column,row,vertices))
    source=s.satellite(ax,77,45,27)
    targets={(0,0),(0,2),(2,3),(4,0),(4,2)}
    for column,row,vertices in cells:
        if (column,row) not in targets:
            continue
        beam_id=f'{column}:{row}'
        if column==0:
            target=s.original.off_axis_radiation(ax,source,vertices,1.0,beam_id)
            if row==2:
                off_axis_target=target
        s.original.beam(ax,source,vertices,broad=True,visual_scale=1.0,
                        beam_id='service-beam:'+beam_id)
        ax.add_patch(Patch(vertices,fc='none',ec=s.BLUE,lw=1.6,zorder=8))
    rx=tower_on_ground(ax,local,(-11.5,0),1.0,facing='north')
    tx=tower_on_ground(ax,local,(-11.5,27),1.0,facing='south')
    ax.annotate('',xy=rx,xytext=tx,zorder=25,
                arrowprops=dict(arrowstyle='-|>',color=s.GREEN,lw=1.8,
                                shrinkA=3,shrinkB=3))
    label(ax,31,26,'FS transmitter',17,s.GREEN,ha='center')
    label(ax,48.4,6.5,'Victim FS receiver',17,s.GREEN,ha='center')
    label(ax,31,20.5,'Wanted FS link',16,s.GREEN,ha='center')
    s.original.lobe_callout(ax,'Off-axis radiation',(6,39),off_axis_target,s.RED)
    s.original.lobe_callout(ax,'Main lobes',(94,38),(84,30.5),s.BLUE,side='left')
    fig._latincom_validation={'reference':'itu_pbo_zoom_border.png / panel (a)',
        'ground_cells':len(cells),'service_beams':len(targets),'satellites':1,
        'fs_directional_dishes':2,'victim_boresight':'north / into the ground plane',
        'transmitter_position':'north of receiver, facing south',
        'original_ground_and_beam_geometry_preserved':True}
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

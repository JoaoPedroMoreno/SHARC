"""Deterministic vector rendering of an open terrestrial microwave dish.

The circular aperture is vertical. Its axis is horizontal along local north;
only the illustration camera is elevated to reveal the feed beyond the rim.
Dimensions are pictogram units, not campaign antenna specifications.
"""
from functools import lru_cache
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.patches import Polygon
from matplotlib.colors import to_rgb

RADIUS=2.4
FOCAL_LENGTH=2.4
AXIS_HEIGHT=11.5
VERTEX_NORTH=.8
CAMERA_ELEVATION=np.deg2rad(55)
SYMBOL_BOUNDS=(-3.2,0.,3.2,11.2)


@lru_cache(maxsize=1)
def dish_mesh():
    faces=[]

    def face(points,color,name):
        faces.append((np.asarray(points,dtype=float),np.asarray(to_rgb(color)),name))

    def tube(a,b,radius,color,name,tip_radius=None,sides=12):
        a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        axis=(b-a)/np.linalg.norm(b-a)
        helper=np.array([0.,0.,1.]) if abs(axis[2])<.9 else np.array([1.,0.,0.])
        u=np.cross(axis,helper); u/=np.linalg.norm(u)
        v=np.cross(axis,u)
        angles=np.arange(sides)*2*np.pi/sides
        ring=np.cos(angles)[:,None]*u+np.sin(angles)[:,None]*v
        first=a+radius*ring
        last=b+(radius if tip_radius is None else tip_radius)*ring
        for i in range(sides):
            j=(i+1)%sides
            face([first[i],first[j],last[j],last[i]],color,name)
        face(first[::-1],color,name)
        face(last,color,name)

    # Vertical pole and a short rear mounting bracket, without cellular panels.
    tube((.55,0,.65),(.55,0,11.4),.22,'#BBC7D0','mast',sides=16)
    for z in (10.25,11.05):
        tube((.55,-.02,z),(.55,.50,z),.13,'#8094A1','mount')
    tube((.55,.5,10.25),(0,.58,11.5),.13,'#8094A1','mount')
    tube((.55,.5,11.05),(0,.65,11.5),.13,'#8094A1','mount')

    angles=np.linspace(0,2*np.pi,73)
    radii=np.linspace(0,RADIUS,17)

    def bowl(r,theta):
        return (r*np.cos(theta),VERTEX_NORTH+r*r/(4*FOCAL_LENGTH),
                AXIS_HEIGHT+r*np.sin(theta))

    for lower,upper in zip(radii[:-1],radii[1:]):
        for a,b in zip(angles[:-1],angles[1:]):
            points=[bowl(lower,a),bowl(upper,a),bowl(upper,b)]
            if lower>0:
                points.append(bowl(lower,b))
            face(points,'#D9E1E7','reflector')

    rim_depth=VERTEX_NORTH+RADIUS**2/(4*FOCAL_LENGTH)
    for a,b in zip(angles[:-1],angles[1:]):
        tube(bowl(RADIUS,a),bowl(RADIUS,b),.035,'#718593','rim',sides=6)

    # A side-mounted cantilever clears the rim; the horn mouth faces the dish.
    attachment=np.array(bowl(RADIUS,0))
    elbow=np.array([0,VERTEX_NORTH+FOCAL_LENGTH+.22,AXIS_HEIGHT-.25])
    arm=[attachment,np.array([RADIUS+.18,VERTEX_NORTH+FOCAL_LENGTH*.58,AXIS_HEIGHT+.2]),
         np.array([.12,VERTEX_NORTH+FOCAL_LENGTH+.35,AXIS_HEIGHT+.1]),elbow]
    for start,end in zip(arm[:-1],arm[1:]):
        for t0,t1 in zip(np.linspace(0,1,9)[:-1],np.linspace(0,1,9)[1:]):
            tube(start+t0*(end-start),start+t1*(end-start),.065,'#7F929F','feed-arm',sides=8)
    tube(elbow,(0,elbow[1],AXIS_HEIGHT),.075,'#7F929F','feed-arm',sides=8)
    focus=VERTEX_NORTH+FOCAL_LENGTH
    tube((0,focus+.42,AXIS_HEIGHT),(0,focus-.12,AXIS_HEIGHT),
         .11,'#8FA1AD','feed-horn',tip_radius=.25,sides=16)
    opening=[(.20*np.cos(t),focus-.125,AXIS_HEIGHT+.20*np.sin(t))
             for t in np.linspace(0,2*np.pi,32,endpoint=False)]
    face(opening,'#354B5A','horn-mouth')
    return faces


def draw(ax,x,y,scale,facing,north):
    if facing not in ('north','south'):
        raise ValueError('FS boresight must follow the horizontal north-south axis')
    sign=1 if facing=='north' else -1
    north=np.asarray(north,dtype=float)
    north_unit=north/np.linalg.norm(north)
    sine,cosine=np.sin(CAMERA_ELEVATION),np.cos(CAMERA_ELEVATION)

    def project(points):
        p=np.asarray(points,dtype=float)
        depth=p[...,1]*sign*sine
        return np.stack((p[...,0]+north_unit[0]*depth,
                         p[...,2]*cosine+north_unit[1]*depth),axis=-1)

    def screen(points):
        return np.array([x,y])+scale*project(points)

    base=np.array([[-1.35,.06],[1.65,.06],[1.95,.50],[-1.05,.50]])
    ax.add_patch(Polygon(base*scale+[x,y],fc='#E1E7EB',ec='#687D8A',lw=.8,
                         zorder=20,gid='fs-dish:base'))
    camera=np.array([0,-cosine,sine])
    light=np.array([-.45,-.65,.9]); light/=np.linalg.norm(light)
    polygons=[]
    for vertices,color,name in dish_mesh():
        world=vertices.copy(); world[:,1]*=sign
        normal=np.cross(world[1]-world[0],world[2]-world[0])
        length=np.linalg.norm(normal)
        if length<1e-10:
            continue
        normal/=length
        if np.dot(normal,camera)<0:
            normal=-normal
        shade=.78+.26*np.dot(normal,light)
        polygons.append((float(world.mean(axis=0)@camera),screen(vertices),
                         np.clip(color*shade,0,1),name))
    polygons.sort(key=lambda item:item[0])
    mesh=PolyCollection([item[1] for item in polygons],
                        facecolors=[item[2] for item in polygons],
                        edgecolors='face',linewidths=.2,antialiaseds=False,zorder=23)
    mesh.set_gid('fs-dish:open-parabolic-mesh')
    ax.add_collection(mesh)

    theta=np.linspace(0,2*np.pi,96)
    rim=np.column_stack((RADIUS*np.cos(theta),
                         np.full(theta.shape,VERTEX_NORTH+RADIUS**2/(4*FOCAL_LENGTH)),
                         AXIS_HEIGHT+RADIUS*np.sin(theta)))
    # The transparent semantic outline also records the circular aperture.
    ax.add_patch(Polygon(screen(rim),fc='none',ec='none',zorder=22,gid='fs-dish:reflector'))
    vertex=np.array([0,VERTEX_NORTH,AXIS_HEIGHT])
    focus=np.array([0,VERTEX_NORTH+FOCAL_LENGTH,AXIS_HEIGHT])
    axis_tip=np.array([0,VERTEX_NORTH+FOCAL_LENGTH+1.9,AXIS_HEIGHT])
    axis_start,axis_end=screen([vertex,axis_tip])
    ax.annotate('',xy=axis_end,xytext=axis_start,zorder=19,
                arrowprops=dict(arrowstyle='-|>',color='#627785',lw=.8,
                                linestyle=(0,(3,2)),mutation_scale=7,shrinkA=0,shrinkB=0))
    metadata=getattr(ax,'_fs_antenna_geometry',[])
    metadata.append(dict(facing=facing,base=np.array([x,y]),phase_center=screen(focus),
                         boresight=north*sign,boresight_3d=np.array([0,sign,0]),
                         scale=scale,feed_focus=focus.copy(),vertex=vertex.copy(),
                         reflector_radius=RADIUS,focal_length=FOCAL_LENGTH,
                         feed_horn_visible=True,radome=False))
    ax._fs_antenna_geometry=metadata
    return screen(focus)


def figure():
    """Standalone transparent-ready asset for inspecting the shared symbol."""
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(4,5))
    ax=fig.add_axes([0,0,1,1],xlim=(-3.8,4),ylim=(-.35,11.8))
    ax.set_aspect('equal'); ax.axis('off')
    draw(ax,0,0,1,'north',(.063,.45))
    ax.text(.70,11.15,'N',fontsize=12,color='#526775',ha='center',va='center')
    return fig

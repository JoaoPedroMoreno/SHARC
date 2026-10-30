"""Encom drawing primitives. Run with the repository's .venv Python."""
from pathlib import Path
import sys
import numpy as np
import matplotlib.image as mpimg
from matplotlib.patches import Polygon
from matplotlib.transforms import Affine2D

REFERENCE = Path(__file__).resolve().parents[1] / 'sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets'
sys.path.insert(0, str(REFERENCE))
import generate_hex_presentation_images as original

BLUE = original.BLUE
ORANGE = original.ORANGE
RED = original.RED
INK = original.INK
GREEN = original.GREEN
FS_SYMBOL_BOUNDS = (-2.7, 0.0, 2.7, 10.4)

def satellite(ax, x, y, width=1.2, tilt_deg=0):
    feed=original.satellite(ax, x, y, width)
    ax.images[-1].set_interpolation('bilinear')
    rotation=Affine2D().rotate_deg_around(x,y,tilt_deg)
    ax.images[-1].set_transform(rotation+ax.transData)
    return rotation.transform(feed)

def pointing_angle(x,y,target):
    """The unrotated satellite antenna axis points down in the drawing."""
    return float(np.degrees(np.arctan2(target[0]-x,y-target[1])))

def ground_north(ground_transform):
    """Screen projection of geographic north, with a fixed pictogram depth."""
    direction=ground_transform.transform((0,1))-ground_transform.transform((0,0))
    return direction * (.45 / direction[1])


def receiver(ax, x, y, scale=.065, facing='north', north=(0,.45)):
    """Shielded FS dish on a pole, viewed from the south of the ground plane.

    The victim faces north, so its rear shell and mounting hardware are visible.
    A reciprocal transmitter can face south, exposing its white radome instead.
    """
    if facing not in ('north','south'):
        raise ValueError('FS antennas must face along the north-south ground axis')
    direction=np.asarray(north,dtype=float)*(1 if facing=='north' else -1)
    transform = Affine2D().scale(scale).translate(x, y)
    edge = '#52616A'

    def patch(artist, name):
        artist.set_transform(transform + ax.transData)
        artist.set_gid('fs-dish:' + name)
        ax.add_patch(artist)

    def line(points, width=1.2, color=edge, name='support'):
        vertices = transform.transform(points)
        ax.plot(vertices[:, 0], vertices[:, 1], color=color, lw=width,
                zorder=25, gid='fs-dish:'+name)

    def project(east,depth,height):
        return np.column_stack((np.asarray(east)+direction[0]*depth,
                                np.asarray(height)+direction[1]*depth))

    patch(Polygon([(-1.5,0),(2.1,0),(2.4,.55),(-1.2,.55)],
                  fc='#DCE3E7',ec=edge,lw=.85,zorder=20),'base')
    patch(Polygon([(.55,.55),(1.25,.55),(1.25,7.3),(.55,7.3)],
                  fc='#AAB9C3',ec=edge,lw=.9,zorder=21),'mast')
    line([(.7,.8),(.7,5.1)],.6,'#E9EFF2')
    theta=np.linspace(0,2*np.pi,96)
    east=2.5*np.cos(theta)
    height=7.3+2.25*np.sin(theta)
    rear=project(east,0,height)
    front=project(east,1.5,height)
    hull=np.asarray(original.MultiPoint(np.vstack((rear,front))).convex_hull.exterior.coords)
    patch(Polygon(hull,fc='#ACBAC4',ec=edge,lw=1.1,zorder=22),'shroud')
    if facing=='north':
        patch(Polygon(front,fc='#F9FBFC',ec=edge,lw=1.05,zorder=23),'aperture')
        patch(Polygon(rear,fc='#CFD9E0',ec=edge,lw=1.1,zorder=24),'reflector')
        # Rear stiffening ribs follow the bowl depth; no exposed front-feed arms.
        for angle in np.linspace(0,2*np.pi,8,endpoint=False):
            t=np.linspace(.15,.93,24)
            rib=project(2.5*t*np.cos(angle),-1.1*(1-t*t),7.3+2.25*t*np.sin(angle))
            line(rib,.75,'#8B9DA9','rear-rib')
        hub=project(0,-1.1,7.3)[0]
        patch(Polygon([(hub[0]-.55,hub[1]-.65),(hub[0]+.55,hub[1]-.65),
                       (hub[0]+.55,hub[1]+.65),(hub[0]-.55,hub[1]+.65)],
                      fc='#879BAA',ec=edge,lw=.8,zorder=26),'rear-mount')
        line([(hub[0]+.5,hub[1]),(1.1,hub[1]),(1.1,5.1)],1.15)
        line([(.45,5.1),(1.5,5.1)],1.5)
    else:
        patch(Polygon(rear,fc='#CFD9E0',ec=edge,lw=1.1,zorder=23),'reflector')
        patch(Polygon(front,fc='#F9FBFC',ec=edge,lw=1.1,zorder=24),'aperture')
        inner=project(.94*east,1.5,7.3+.94*(height-7.3))
        line(inner,.65,'#B5C3CC','radome-rim')
    phase_center=transform.transform(project(0,1.5,7.3)[0])
    metadata=getattr(ax,'_fs_antenna_geometry',[])
    metadata.append(dict(facing=facing,base=np.array([x,y]),phase_center=phase_center,
                         boresight=direction.copy(),scale=scale))
    ax._fs_antenna_geometry=metadata
    return phase_center

def hexagon(x, y, radius):
    return original.hex_vertices((x, y), radius)

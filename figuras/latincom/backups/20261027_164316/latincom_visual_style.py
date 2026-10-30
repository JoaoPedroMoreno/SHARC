"""Encom drawing primitives. Run with the repository's .venv Python."""
from pathlib import Path
import sys
import numpy as np
import matplotlib.image as mpimg
from matplotlib.patches import Ellipse, Polygon
from matplotlib.transforms import Affine2D

REFERENCE = Path(__file__).resolve().parents[1] / 'sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets'
sys.path.insert(0, str(REFERENCE))
import generate_hex_presentation_images as original

BLUE = original.BLUE
ORANGE = original.ORANGE
RED = original.RED
INK = original.INK
GREEN = original.GREEN

def satellite(ax, x, y, width=1.2, tilt_deg=0):
    feed=original.satellite(ax, x, y, width)
    ax.images[-1].set_interpolation('bilinear')
    rotation=Affine2D().rotate_deg_around(x,y,tilt_deg)
    ax.images[-1].set_transform(rotation+ax.transData)
    return rotation.transform(feed)

def pointing_angle(x,y,target):
    """The unrotated satellite antenna axis points down in the drawing."""
    return float(np.degrees(np.arctan2(target[0]-x,y-target[1])))

def receiver(ax, x, y, scale=.065, facing='left'):
    """Directional microwave dish; return the feed for link endpoints."""
    direction = -1 if facing == 'left' else 1
    transform = Affine2D().scale(direction*scale, scale).translate(x, y)
    edge = '#52616A'

    def patch(artist, name):
        artist.set_transform(transform + ax.transData)
        artist.set_gid('fs-dish:' + name)
        ax.add_patch(artist)

    def line(points, width=1.2):
        vertices = transform.transform(points)
        ax.plot(vertices[:, 0], vertices[:, 1], color=edge, lw=width,
                zorder=23, gid='fs-dish:support')

    patch(Polygon([(-2.5, 0), (2.5, 0), (2.1, .55), (-2.1, .55)],
                  fc='#D8E0E4', ec=edge, lw=.85, zorder=20), 'base')
    patch(Polygon([(-.45, .55), (.25, .55), (.25, 6.1), (-.45, 6.1)],
                  fc='#B6C1C7', ec=edge, lw=.9, zorder=21), 'mast')
    line([(-1.8, .55), (-.15, 4.4), (1.45, .55)], .9)
    t = np.linspace(-2.8, 2.8, 64)
    bowl = np.column_stack((.16*t*t-1.7, 7.1+t))
    patch(Polygon(bowl, fc='#BFCAD0', ec=edge, lw=1.1, zorder=22), 'reflector')
    rim_x = .16*2.8**2-1.7
    patch(Ellipse((rim_x, 7.1), 1.05, 5.6, fc='#F5F7F8', ec=edge,
                  lw=1.1, zorder=23), 'aperture')
    feed = (1.65, 7.1)
    line([(rim_x, 4.3), feed, (rim_x, 9.9)], .9)
    patch(Ellipse(feed, .65, .65, fc=edge, ec='white', lw=.45, zorder=24), 'feed')
    return transform.transform(feed)

def hexagon(x, y, radius):
    return original.hex_vertices((x, y), radius)

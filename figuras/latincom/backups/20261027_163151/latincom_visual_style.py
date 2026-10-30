"""Encom drawing primitives. Run with the repository's .venv Python."""
from pathlib import Path
import sys
import numpy as np
import matplotlib.image as mpimg
from matplotlib.patches import FancyBboxPatch, Polygon
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

def receiver(ax, x, y, scale=.065):
    previous = set(ax.get_children())
    original.tower(ax, 0, 0)
    transform = Affine2D().scale(scale).translate(x, y) + ax.transData
    for artist in set(ax.get_children()) - previous:
        artist.set_transform(transform)
    return np.array([x, y + 8.8*scale])

def hexagon(x, y, radius):
    return original.hex_vertices((x, y), radius)

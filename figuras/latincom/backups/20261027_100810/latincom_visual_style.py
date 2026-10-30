"""Reuse the existing presentation artwork, without modifying its source."""
from pathlib import Path
import sys
import ast
import math
from types import SimpleNamespace
import numpy as np
import matplotlib.image as mpimg
from matplotlib.patches import FancyBboxPatch, Polygon
from matplotlib.transforms import Affine2D

REFERENCE = Path(__file__).resolve().parents[1] / 'sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets'
# Extract the unchanged drawing primitives without importing GIS dependencies.
tree = ast.parse((REFERENCE / 'generate_hex_presentation_images.py').read_text(encoding='utf-8'))
names = {'satellite', 'tower', 'hex_vertices'}
colors = {'BLUE','BLUE_EDGE','BLUE_PALE','BLUE_SELECTED','ORANGE','ORANGE_PALE',
          'RED','GREEN','INK','BORDER','WHITE'}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names
         or isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id in colors for t in n.targets)]
namespace = dict(np=np, math=math, mpimg=mpimg, FancyBboxPatch=FancyBboxPatch,
                 SATELLITE=REFERENCE / 'v3/satellite_from_paper.png')
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(REFERENCE / 'generate_hex_presentation_images.py'),'exec'),namespace)
original = SimpleNamespace(**namespace)

def beam(ax, source, footprint, pbo=False, broad=False):
    points = sorted(set(map(tuple, np.vstack([source,footprint]))))
    def cross(o,a,b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    sides=[]
    for sequence in (points,points[::-1]):
        side=[]
        for point in sequence:
            while len(side)>=2 and cross(side[-2],side[-1],point)<=0:
                side.pop()
            side.append(point)
        sides.extend(side[:-1])
    color=original.ORANGE if pbo else original.BLUE
    ax.add_patch(Polygon(sides,fc=color,alpha=.13 if pbo else .18,ec='none',zorder=5))
    center=footprint.mean(axis=0)
    ax.plot([source[0],center[0]],[source[1],center[1]],c=color,lw=1.25,alpha=.75,zorder=7)

original.beam=beam

BLUE = original.BLUE
ORANGE = original.ORANGE
RED = original.RED
INK = original.INK
GREEN = original.GREEN

def satellite(ax, x, y, width=1.2):
    feed=original.satellite(ax, x, y, width)
    ax.images[-1].set_interpolation('bilinear')
    return feed

def receiver(ax, x, y, scale=.065):
    previous = set(ax.get_children())
    original.tower(ax, 0, 0)
    transform = Affine2D().scale(scale).translate(x, y) + ax.transData
    for artist in set(ax.get_children()) - previous:
        artist.set_transform(transform)
    return np.array([x, y + 8.8*scale])

def hexagon(x, y, radius):
    vertices=original.hex_vertices((0, 0), radius)
    angle=math.pi/6
    rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    return vertices @ rotation.T + np.array([x,y])

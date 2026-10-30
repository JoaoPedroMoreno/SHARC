"""Place the approved Blender microwave dish in the LATINCOM diagrams.

Geometry and hardware come from the approved .blend model. Surface materials
and lighting come from the Encom satellite. Camera azimuth and antenna heading
change between the cached render views.
The rest of each figure remains vector artwork; dish sprites are embedded.
"""

from functools import lru_cache
from pathlib import Path
import json

import numpy as np
from PIL import Image
from matplotlib.patches import Polygon
from matplotlib.transforms import Affine2D


ASSETS = Path(__file__).resolve().parents[1] / "figuras/latincom/antenna_assets"
DRAWING_UNITS_PER_METRE = 7.5


@lru_cache(maxsize=1)
def manifest():
    return json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=3)
def asset(name):
    model = manifest()["views"][name]
    with Image.open(ASSETS / model["image"]) as source:
        source = source.convert("RGBA")
        bounds = source.getchannel("A").getbbox()
        image = np.asarray(source.crop(bounds))
    base = np.asarray(model["anchors_px"]["base"])
    factor = DRAWING_UNITS_PER_METRE / model["pixels_per_world_unit"]

    def local(pixels):
        return (np.asarray(pixels) - base) * [factor, -factor]

    left, top, right, bottom = bounds
    lower = local([left, bottom])
    upper = local([right, top])
    extent = np.array([lower[0], upper[0], lower[1], upper[1]])
    anchors = {key: local(value) for key, value in model["anchors_px"].items()}
    return image, extent, anchors, model


def symbol_bounds():
    """Conservative bounds include the small projected north-axis indicator."""
    rectangles = []
    for name in ("map_north", "perspective_north"):
        _, extent, anchors, _ = asset(name)
        axis = anchors["axis_end"] - anchors["focus"]
        tip = anchors["focus"] + 1.3 * axis / np.linalg.norm(axis)
        rectangles.extend([[extent[0], extent[2]], [extent[1], extent[3]], tip])
    points = np.asarray(rectangles)
    lo, hi = points.min(axis=0) - .12, points.max(axis=0) + .12
    return (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))


SYMBOL_BOUNDS = symbol_bounds()


def draw(ax, x, y, scale, facing, north):
    if facing not in ("north", "south"):
        raise ValueError("FS boresight must follow the horizontal north-south axis")
    north = np.asarray(north, dtype=float)
    if north[1] <= 0:
        raise ValueError("North must point into the illustrated ground plane")
    sign = 1 if facing == "north" else -1
    ratio = north[0] / north[1]
    choices = [(abs(value["north_ratio"] - ratio), name)
               for name, value in manifest()["views"].items() if value["sign"] == sign]
    error, name = min(choices)
    if error > .002:
        raise ValueError("Render a matching dish viewpoint for this ground orientation")
    image, extent, anchors, model = asset(name)
    origin = np.array([x, y])
    # Correct rounding of the supplied north vector without tilting the mast.
    delta = ratio - model["north_ratio"]
    transform = Affine2D.from_values(scale, 0, scale * delta, scale, x, y)
    artist = ax.imshow(image, extent=extent, origin="upper", interpolation="lanczos",
                       transform=transform + ax.transData, zorder=23)
    artist.set_gid("fs-dish:approved-blender-model")
    screen = transform.transform
    focus = screen(anchors["focus"])
    vertex = screen(anchors["vertex"])
    axis = north / np.linalg.norm(north) * sign
    axis_tip = focus + scale * 1.3 * axis
    ax.annotate("", xy=axis_tip, xytext=focus, zorder=24,
                arrowprops=dict(arrowstyle="-|>", color="#627785", lw=.8,
                                linestyle=(0, (3, 2)), mutation_scale=7,
                                shrinkA=0, shrinkB=0))
    rim = (np.asarray(model["rim_px"]) - model["anchors_px"]["base"])
    rim *= [DRAWING_UNITS_PER_METRE / model["pixels_per_world_unit"],
            -DRAWING_UNITS_PER_METRE / model["pixels_per_world_unit"]]
    ax.add_patch(Polygon(screen(rim), fc="none", ec="none", zorder=22,
                         gid="fs-dish:reflector"))
    records = getattr(ax, "_fs_antenna_geometry", [])
    records.append(dict(facing=facing, base=origin, phase_center=focus,
                        boresight=north * sign, boresight_3d=np.array(model["boresight_3d"]),
                        scale=scale, feed_focus=np.array(model["focus_3d"]),
                        vertex=np.array(model["vertex_3d"]), screen_vertex=vertex,
                        reflector_radius=model["radius"], focal_length=model["focal_length"],
                        radome=False, asset=name, approved_blender_model=True,
                        render_extent=screen([[extent[0], extent[2]], [extent[1], extent[3]]])))
    ax._fs_antenna_geometry = records
    return focus


def figure():
    """Standalone north-facing view used by the diagram export command."""
    import matplotlib.pyplot as plt
    xmin, ymin, xmax, ymax = SYMBOL_BOUNDS
    fig = plt.figure(figsize=(4, 5))
    ax = fig.add_axes([0, 0, 1, 1], xlim=(xmin - .5, xmax + .5),
                      ylim=(ymin - .5, ymax + .5))
    ax.set_aspect("equal")
    ax.axis("off")
    draw(ax, 0, 0, 1, "north", (np.tan(np.deg2rad(8)) * .45, .45))
    return fig

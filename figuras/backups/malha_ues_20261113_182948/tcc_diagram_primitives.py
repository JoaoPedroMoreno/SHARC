"""Shared ground-anchored hardware for TCC diagrams, not simulation geometry."""
from functools import lru_cache
from pathlib import Path
import json

import numpy as np
from PIL import Image
from matplotlib.patches import Polygon
from matplotlib.transforms import Affine2D
from matplotlib.path import Path as MplPath

from generate_latincom_figures import terminal

ROOT = Path(__file__).resolve().parents[1]
SATELLITE_TILT = -5


def ground_plane(ax, transform, bounds, zorder=1):
    xmin, ymin, xmax, ymax = bounds
    corners = transform.transform([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)])
    ax.add_patch(Polygon(corners, facecolor="#f2f6f5", edgecolor="#b3c2be",
                         lw=1, zorder=zorder, gid="shared-ground-plane"))
    records = getattr(ax, "_tcc_ground_planes", [])
    records.append(corners)
    ax._tcc_ground_planes = records
    return corners


def handset(ax, foot, height=.4):
    """Reuse Encom's terminal, anchored by its bottom edge on the ground."""
    old_patches, old_lines = len(ax.patches), len(ax.lines)
    terminal(ax, 0, .31)
    affine = Affine2D().scale(height/.64).translate(*foot)
    for artist in list(ax.patches)[old_patches:]+list(ax.lines)[old_lines:]:
        artist.set_transform(affine+ax.transData)
        artist.set_zorder(28)
        artist.set_linewidth(.65)
        artist.set_gid("encom-ue-handset")


@lru_cache(maxsize=1)
def fs_asset():
    folder = ROOT / "figuras/tcc_assets/fs_horizontal_north"
    model = json.loads((folder / "manifest.json").read_text())["views"]["angular"]
    with Image.open(folder / model["image"]) as source:
        bounds = source.getchannel("A").getbbox()
        pixels = np.asarray(source.crop(bounds))
    assert model["boresight_3d"] == [0, 1, 0]
    return model, pixels, bounds


def fs_on_ground(ax, base, height=2.4):
    assert any(MplPath(plane).contains_point(base) for plane in ax._tcc_ground_planes), \
        "FS foundation must lie on the same ground plane as the service cells"
    model, pixels, (left, top, right, bottom) = fs_asset()
    factor = height/(bottom-top)
    source_base = np.array(model["anchors_px"]["base"])

    def project(point):
        return np.asarray(base)+(np.asarray(point)-source_base)*[factor, -factor]

    low, high = project([left, bottom]), project([right, top])
    ax.imshow(pixels, extent=(low[0], high[0], low[1], high[1]),
              zorder=25, interpolation="lanczos", gid="ground-anchored-FS")
    focus = project(model["anchors_px"]["focus"])
    axis = project(model["anchors_px"]["axis_end"])-focus
    axis /= np.linalg.norm(axis)
    assert abs(axis[1]) < .001, "North must be screen-horizontal in this viewpoint"
    return focus, axis

"""Render the unchanged paper satellite as a reusable transparent scene asset."""

from pathlib import Path
import sys

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "illustration"))
import generate_pbo_illustration as paper


def main():
    output = HERE / "v3"
    output.mkdir(parents=True, exist_ok=True)
    scene, camera, materials = paper.configure_scene()
    paper.create_satellite(0.0, materials)
    camera.location = (0.0, -29.5, 18.35)
    paper.look_at(camera, Vector((0.0, 0.0, 7.0)))
    camera.data.ortho_scale = 4.8
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 600
    scene.render.film_transparent = True
    scene.render.filepath = str(output / "satellite_from_paper.png")
    scene["source_model"] = "illustration/generate_pbo_illustration.py:create_satellite"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "satellite_from_paper.blend"))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()

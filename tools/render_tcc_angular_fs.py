"""New viewpoint of the approved FS model; existing renders remain unchanged."""
from pathlib import Path
import sys
import json
import math

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_latincom_fs_assets as renderer

OUT = renderer.ROOT / "figuras/tcc_assets/fs_horizontal_north"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(renderer.SOURCE))
    scene = bpy.context.scene
    visual_style = renderer.apply_encom_materials(scene)
    for obj in scene.objects:
        if obj.name.startswith(("Boresight dash", "North arrowhead", "North label")):
            obj.hide_render = True
    camera = scene.camera
    target = Vector((0, 0, .95))
    # Look from the west. North is exactly left, while the mast stays vertical.
    camera.location = target+Vector((-3, 0, 3*math.sqrt(3)))
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.4
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1600
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.filepath = str(OUT / "angular.png")
    bpy.context.view_layer.update()

    def project(point):
        p = world_to_camera_view(scene, camera, point)
        return [p.x*1400, (1-p.y)*1600]

    vertex = Vector((0, renderer.VERTEX, renderer.AXIS_HEIGHT))
    focus = vertex+Vector((0, renderer.FOCAL_LENGTH, 0))
    anchors = {"base": project(renderer.BASE), "vertex": project(vertex),
               "focus": project(focus), "axis_end": project(focus+Vector((0, 1, 0)))}
    assert abs(anchors["axis_end"][1]-anchors["focus"][1]) < .01
    manifest = {"source_model": str(renderer.SOURCE), "visual_style": visual_style,
                "views": {"angular": {"image": "angular.png", "anchors_px": anchors,
                                      "boresight_3d": [0, 1, 0], "elevation_deg": 0}}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    main()

r"""Render the approved Blender dish at the LATINCOM ground-plane viewpoints.

Run: G:\Blender\blender.exe -b --python tools/render_latincom_fs_assets.py
The source model is unchanged. These transparent sprites carry projected
anchors so links end at the feed and the mast stays vertical when placed.
"""

from pathlib import Path
import json
import math
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "figuras/latincom/antenna_proposal_v2/fs_antenna_proposal.blend"
OUT = ROOT / "figuras/latincom/antenna_assets"
ELEVATION = math.radians(60)
RADIUS, FOCAL_LENGTH, AXIS_HEIGHT, VERTEX = .55, .48, 1.46, .05
BASE = Vector((0, -.22, 0))
VIEWS = (
    ("map_north", 0., 1),
    ("perspective_north", math.tan(math.radians(8)), 1),
    ("perspective_south", math.tan(math.radians(8)), -1),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"source_model": str(SOURCE.relative_to(ROOT)),
                "camera_elevation_deg": math.degrees(ELEVATION),
                "illustrative_dimensions": True, "views": {}}
    for name, north_ratio, sign in VIEWS:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        scene = bpy.context.scene
        camera = scene.camera
        for obj in scene.objects:
            if obj.name.startswith(("Boresight dash", "North arrowhead", "North label")):
                obj.hide_render = True
        rotation = (Matrix.Translation(BASE) @ Matrix.Rotation(0 if sign == 1 else math.pi, 4, "Z")
                    @ Matrix.Translation(-BASE))
        for obj in scene.objects:
            if obj.type == "MESH":
                obj.matrix_world = rotation @ obj.matrix_world
        yaw = math.atan(north_ratio * math.sin(ELEVATION))
        target = Vector((0, 0, .95))
        camera.location = target + 6 * Vector((math.sin(yaw) * math.cos(ELEVATION),
                                               -math.cos(yaw) * math.cos(ELEVATION),
                                               math.sin(ELEVATION)))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 2.4
        scene.render.resolution_x = 2000
        scene.render.resolution_y = 2200
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True
        scene.render.filepath = str(OUT / f"{name}.png")
        bpy.context.view_layer.update()

        def project(point):
            projected = world_to_camera_view(scene, camera, Vector(point))
            return [projected.x * scene.render.resolution_x,
                    (1 - projected.y) * scene.render.resolution_y]

        vertex = rotation @ Vector((0, VERTEX, AXIS_HEIGHT))
        focus = rotation @ Vector((0, VERTEX + FOCAL_LENGTH, AXIS_HEIGHT))
        end = focus + Vector((0, sign, 0))
        anchors = {"base": project(BASE), "vertex": project(vertex),
                   "focus": project(focus), "axis_end": project(end)}
        camera_right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
        right_px = project(BASE + camera_right)
        pixels_per_unit = abs(right_px[0] - anchors["base"][0])
        dx = anchors["axis_end"][0] - anchors["focus"][0]
        dy = anchors["focus"][1] - anchors["axis_end"][1]
        assert abs(dx / dy - north_ratio) < 1e-5
        assert abs(focus.z - vertex.z) < 1e-8
        manifest["views"][name] = {
            "image": f"{name}.png", "north_ratio": north_ratio, "sign": sign,
            "pixels_per_world_unit": pixels_per_unit,
            "anchors_px": anchors, "vertex_3d": list(vertex), "focus_3d": list(focus),
            "radius": RADIUS, "focal_length": FOCAL_LENGTH,
            "boresight_3d": [0, sign, 0], "radome": False,
            "rim_px": [project(rotation @ Vector((RADIUS * math.cos(t),
                        VERTEX + RADIUS ** 2 / (4 * FOCAL_LENGTH),
                        AXIS_HEIGHT + RADIUS * math.sin(t))))
                       for t in [i * math.tau / 96 for i in range(96)]],
        }
        if "--metadata-only" not in sys.argv:
            bpy.ops.render.render(write_still=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"LATINCOM_ANTENNA_ASSETS={OUT}", flush=True)


if __name__ == "__main__":
    main()

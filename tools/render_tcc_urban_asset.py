"""Render an urban obstruction with the original Latincom Blender materials."""
from pathlib import Path
import json
import math

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sharc/campaigns/03_DC_MSS_ISOLADO/presentation_assets/v3/satellite_from_paper.blend"
OUT = ROOT / "figuras/tcc_assets"


def cube(name, location, dimensions, material, bevel=.045):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        modifier = obj.modifiers.new("Soft manufactured edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def main():
    OUT.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    wall = scene.objects["Satellite body"].data.materials[0]
    roof = scene.objects["Satellite lower bus"].data.materials[0]
    for obj in list(scene.objects):
        if obj.type not in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    glass = bpy.data.materials.new("Muted Latincom blue glazing")
    glass.diffuse_color = (.22, .40, .51, 1)
    glass.use_nodes = True
    shader = glass.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (.22, .40, .51, 1)
    shader.inputs["Roughness"].default_value = .4
    for number, (x, y, w, d, h) in enumerate(((-3.0, 0, 1.7, 1.6, 2.8),
                                            (-.4, 0, 2.0, 1.7, 4.4),
                                            (2.2, 0, 2.1, 1.7, 6.0))):
        cube(f"Building {number}", (x, y, h/2), (w, d, h), wall)
        cube(f"Roof {number}", (x, y, h+.06), (w+.06, d+.06, .12), roof, .02)
        floors = int(h/.7)
        for floor in range(floors):
            z = .5+floor*.66
            for col in range(3):
                xx = x + (col-1)*w*.28
                cube("Front window", (xx, y-d/2-.012, z), (w*.18, .025, .32), glass, .012)
            for col in range(2):
                yy = y+(col-.5)*d*.43
                cube("Side window", (x+w/2+.012, yy, z), (.025, d*.25, .32), glass, .012)
    camera = scene.camera
    target = Vector((0, 0, 2.9))
    camera.location = target + Vector((2, -20, 4))
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 9.5
    for obj in scene.objects:
        if obj.type == "LIGHT":
            obj.location.z += 2
    scene.render.resolution_x = 1500
    scene.render.resolution_y = 1500
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 24
        scene.cycles.use_denoising = True
        scene.cycles.device = "CPU"
    scene.render.filepath = str(OUT / "urban_obstruction.png")
    bpy.context.view_layer.update()
    base = world_to_camera_view(scene, camera, Vector((2.2, -.85, 0)))
    top = world_to_camera_view(scene, camera, Vector((2.2, -.85, 6)))
    (OUT / "urban_obstruction.json").write_text(json.dumps(dict(
        source_style=str(SOURCE), base_uv=[base.x, base.y], top_uv=[top.x, top.y],
        illustrative=True, dimensions_not_to_scale=True,
        materials=[wall.name, roof.name, glass.name]), indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "urban_obstruction.blend"))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()

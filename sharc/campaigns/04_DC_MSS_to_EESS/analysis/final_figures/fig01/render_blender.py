"""Blender base render for the two-panel didactic geometry figure."""
from __future__ import annotations

import math
import json
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


HERE = Path(__file__).resolve().parent
OUT = HERE / "figure1_blender_base.png"
BLEND = HERE / "fig01_geometry.blend"
ANCHORS = HERE / "fig01_anchors.json"

BLUE = (0.000, 0.447, 0.698, 1)
ORANGE = (0.902, 0.624, 0.000, 1)
GREEN = (0.000, 0.620, 0.451, 1)
CYAN = (0.337, 0.706, 0.914, 1)
RED = (0.835, 0.200, 0.120, 1)
GRAY = (0.42, 0.46, 0.49, 1)
GROUND = (0.78, 0.80, 0.76, 1)
DARK = (0.10, 0.13, 0.16, 1)


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def mat(name, color, metallic=0.0, roughness=0.55, emission=False):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = color
        bsdf.inputs["Emission Strength"].default_value = 0.35
    return material


def transparent_mat(name, color, alpha=0.16, emission=False):
    material = mat(name, (*color[:3], alpha), emission=emission)
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Alpha"].default_value = alpha
    material.diffuse_color = (*color[:3], alpha)
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    return material


def cylinder(start, end, radius, material, name="link"):
    start, end = Vector(start), Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20, radius=radius, depth=direction.length,
        location=(start + end) / 2,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    return obj


def dashed(start, end, radius, material, name, count=16):
    start, end = Vector(start), Vector(end)
    for index in range(count):
        a = index / count
        b = min(a + 0.58 / count, 1.0)
        cylinder(start.lerp(end, a), start.lerp(end, b), radius,
                 material, f"{name}_{index:02d}")


def arrow(start, end, radius, material, name="arrow"):
    start, end = Vector(start), Vector(end)
    direction = (end - start).normalized()
    cylinder(start, end - direction * radius * 5, radius, material, name)
    bpy.ops.mesh.primitive_cone_add(
        vertices=24, radius1=radius * 3.2, radius2=0,
        depth=radius * 7, location=end - direction * radius * 1.7,
    )
    head = bpy.context.object
    head.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    head.data.materials.append(material)


def curve(points, radius, material, name):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 3
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, value in zip(spline.points, points):
        point.co = (*value, 1)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)


def curved_arrow(start, control, end, radius, material, name):
    start, control, end = Vector(start), Vector(control), Vector(end)
    points = []
    for index in range(41):
        t = index / 40
        points.append((1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end)
    curve(points, radius, material, name)
    arrow(points[-3], points[-1], radius, material, f"{name}_head")
    return points


def beam_cone(origin, direction, length, radius, material, name):
    origin, direction = Vector(origin), Vector(direction).normalized()
    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=radius, radius2=0.015, depth=length,
        location=origin + direction * length / 2,
    )
    obj = bpy.context.object
    obj.name = name
    # Cone apex (local +Z) at the antenna and broad base along the pointing direction.
    obj.rotation_euler = (-direction).to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    return obj


def arc(origin, vector_a, vector_b, radius, material, name):
    origin = Vector(origin)
    a, b = Vector(vector_a).normalized(), Vector(vector_b).normalized()
    angle = math.acos(max(-1, min(1, a.dot(b))))
    axis = a.cross(b).normalized()
    points = []
    for index in range(33):
        direction = a.copy()
        direction.rotate(__import__("mathutils").Matrix.Rotation(
            angle * index / 32, 4, axis
        ))
        points.append(origin + radius * direction)
    curve(points, 0.018, material, name)


def satellite(location, accent, materials, name):
    location = Vector(location)
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    bus = bpy.context.object
    bus.name = name
    bus.scale = (0.22, 0.18, 0.16)
    bus.data.materials.append(materials["dish"])
    for side in (-1, 1):
        panel_location = location + Vector((side * 0.39, 0, 0))
        bpy.ops.mesh.primitive_cube_add(size=1, location=panel_location)
        panel = bpy.context.object
        panel.scale = (0.50, 0.04, 0.24)
        panel.data.materials.append(materials["panel"])
        # Solar-cell grid remains strictly inside the blue panel boundaries.
        for offset in (-0.060, 0.060):
            cylinder(panel_location + Vector((-0.215, -0.026, offset)),
                     panel_location + Vector((0.215, -0.026, offset)),
                     0.0045, materials["panel_grid"], "solar_grid_h")
        for offset in (-0.135, 0.0, 0.135):
            cylinder(panel_location + Vector((offset, -0.026, -0.095)),
                     panel_location + Vector((offset, -0.026, 0.095)),
                     0.0045, materials["panel_grid"], "solar_grid_v")


def ground_patch(center, active_location, materials, width=5.2):
    # The cellular tessellation itself is the ground plane; no rectangular
    # slab is placed underneath it.
    size = 0.30
    active_location = Vector(active_location)
    for row in range(-6, 7):
        for column in range(-9, 10):
            x = active_location.x + math.sqrt(3) * size * (column + row / 2)
            y = active_location.y + 1.5 * size * row
            if not (center - width / 2 + .28 <= x <= center + width / 2 - .28):
                continue
            if not (-1.10 <= y <= 1.55):
                continue
            active = row == 0 and column == 0
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=6, radius=size * .94, depth=.020,
                location=(x, y, .015), rotation=(0, 0, math.pi / 6),
            )
            tile = bpy.context.object
            tile.name = "active_service_cell" if active else "service_grid_cell"
            tile.data.materials.append(materials["blue"] if active else materials["grid_cell"])


def dish(location, direction, materials):
    location, direction = Vector(location), Vector(direction).normalized()
    mast_top = location + Vector((0, 0, 0.42))
    cylinder(location, mast_top, 0.045, materials["metal"], "dish_mast")
    # Shallow parabolic reflector with axis along local +Z, then oriented.
    rings, segments = 9, 48
    verts = [(0, 0, -0.08)]
    for ring in range(1, rings + 1):
        radius = 0.30 * ring / rings
        z = -0.08 * (1 - (ring / rings) ** 2)
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            verts.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces = []
    for index in range(segments):
        faces.append((0, 1 + index, 1 + (index + 1) % segments))
    for ring in range(1, rings):
        a, b = 1 + (ring - 1) * segments, 1 + ring * segments
        for index in range(segments):
            faces.append((a + index, a + (index + 1) % segments,
                          b + (index + 1) % segments, b + index))
    mesh = bpy.data.meshes.new("dish_mesh")
    mesh.from_pydata(verts, [], faces)
    reflector = bpy.data.objects.new("EESS_reflector", mesh)
    bpy.context.collection.objects.link(reflector)
    reflector.location = mast_top
    reflector.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    reflector.data.materials.append(materials["dish"])
    feed = mast_top + direction * 0.34
    cylinder(mast_top - direction * 0.06, feed, 0.018,
             materials["metal"], "feed_arm")
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10,
                                        radius=0.045, location=feed)
    bpy.context.object.data.materials.append(materials["dark"])


def setup_scene():
    clear()
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 3600
    scene.render.resolution_y = 1900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(OUT)
    scene.world.color = (1, 1, 1)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 0.85
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.ops.object.light_add(type="AREA", location=(-4, -5, 9))
    bpy.context.object.data.energy = 1050
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 7
    bpy.ops.object.light_add(type="AREA", location=(5, 1, 7))
    bpy.context.object.data.energy = 700
    bpy.context.object.data.size = 6
    bpy.ops.object.camera_add(location=(0, -15.5, 8.3))
    camera = bpy.context.object
    camera.data.type = "PERSP"
    camera.data.lens = 61
    camera.rotation_euler = (Vector((0, 0, 2.0)) - camera.location).to_track_quat(
        "-Z", "Y"
    ).to_euler()
    scene.camera = camera
    return scene


def main():
    scene = setup_scene()
    materials = {
        "blue": mat("service blue", BLUE, emission=True),
        "orange": mat("serving orange", ORANGE, emission=True),
        "green": mat("EESS green", GREEN, emission=True),
        "cyan": mat("target cyan", CYAN, emission=True),
        "red": mat("critical red", RED, emission=True),
        "gray": mat("aux gray", GRAY),
        "ground": mat("neutral ground", (0.57, 0.59, 0.60, 1), roughness=0.9),
        "grid_cell": transparent_mat("inactive grid cell", (0.66, 0.70, 0.73, 1), alpha=0.52),
        "dark": mat("dark", DARK, metallic=0.45),
        "black": mat("handover black", (0.005, 0.005, 0.005, 1), roughness=0.95),
        "metal": mat("satellite metal", (0.23, 0.26, 0.29, 1), metallic=0.8),
        "panel": mat("solar panel", (0.02, 0.15, 0.32, 1), metallic=0.4),
        "panel_grid": mat("panel grid", (0.50, 0.80, 0.95, 1), emission=True),
        "dish": mat("dish", (0.27, 0.31, 0.34, 1), metallic=0.78),
        "eess_beam": transparent_mat("EESS beam", GREEN, alpha=0.13, emission=True),
    }

    # Panel (a): same service cell, changed serving satellite.
    cell = Vector((-4.1, 0.0, 0.08))
    eess = Vector((-1.8, 0.05, 0.02))
    serving = Vector((-4.2, 0.25, 4.2))
    # Negative Y places the non-interfering target visibly closer to the camera.
    target = Vector((-2.2, -1.25, 3.65))
    ground_patch(-3.4, cell, materials)
    eess_pointing = Vector((-0.35, 0, 0.94))
    dish(eess, eess_pointing, materials)
    beam_cone(eess + Vector((0, 0, 0.34)), eess_pointing, 2.15, 0.34,
              materials["eess_beam"], "left_eess_beam")
    satellite(serving, materials["orange"], materials, "serving_satellite")
    satellite(target, materials["cyan"], materials, "target_satellite")
    cylinder(serving, cell, 0.025, materials["green"], "serving_to_cell")
    dashed(target, cell, 0.022, materials["orange"], "target_to_cell")
    dashed(serving, eess + Vector((0, 0, 0.35)), 0.032,
           materials["red"], "interference_path", count=22)
    path = curved_arrow(
        serving + Vector((0.25, -0.05, 0.25)),
        Vector((-3.15, -1.35, 4.72)),
        target + Vector((-0.18, 0, 0.25)),
        0.026, materials["black"], "handover_curve",
    )

    # Panel (b): angular definitions in one clean geometric plane.
    rx = Vector((4.95, 0.05, 0.02))
    tx = Vector((2.75, 0.15, 4.05))
    cell_b = Vector((1.75, 0.0, 0.08))
    ground_patch(3.35, cell_b, materials)
    rx_boresight = Vector((-0.15, 0.0, 0.99))
    dish(rx, rx_boresight, materials)
    beam_cone(rx + Vector((0, 0, 0.30)), rx_boresight, 2.55, 0.38,
              materials["eess_beam"], "right_eess_beam")
    satellite(tx, materials["orange"], materials, "angular_satellite")
    arrow(tx, cell_b, 0.020, materials["green"], "tx_boresight")
    arrow(tx, rx + Vector((0, 0, 0.30)), 0.018, materials["red"], "tx_to_eess")
    arrow(rx + Vector((0, 0, 0.30)),
          rx + Vector((0, 0, 0.30)) + rx_boresight * 2.6,
          0.020, materials["green"], "rx_boresight")
    arrow(rx + Vector((0, 0, 0.30)), tx, 0.014,
          materials["red"], "rx_to_satellite")
    arc(tx, cell_b - tx, rx - tx, 0.78, materials["orange"], "psi_tx_arc")
    arc(rx + Vector((0, 0, 0.30)), rx_boresight, tx - rx,
        0.68, materials["green"], "psi_rx_arc")

    def arc_mid(origin, vector_a, vector_b, radius):
        a, b = Vector(vector_a).normalized(), Vector(vector_b).normalized()
        return Vector(origin) + radius * (a + b).normalized()

    anchor_world = {
        "left_serving": serving,
        "left_target": target,
        "left_cell": cell + Vector((0, 0, .08)),
        "left_eess": eess + Vector((0, 0, .45)),
        "left_interference": serving.lerp(eess + Vector((0, 0, .35)), .55),
        "left_handover": path[len(path) // 2],
        "left_eess_beam": eess + Vector((0, 0, .34)) + eess_pointing.normalized() * 1.35,
        "right_satellite": tx,
        "right_cell": cell_b,
        "right_eess": rx + Vector((0, 0, .35)),
        "right_tx_boresight": tx.lerp(cell_b, .55),
        "right_tx_to_eess": tx.lerp(rx + Vector((0, 0, .30)), .50),
        "right_rx_boresight": rx + Vector((0, 0, .30)) + rx_boresight.normalized() * 1.55,
        "right_psi_tx": arc_mid(tx, cell_b - tx, rx - tx, .78),
        "right_psi_rx": arc_mid(rx + Vector((0, 0, .30)), rx_boresight, tx - rx, .68),
    }
    anchors = {}
    for key, point in anchor_world.items():
        ndc = world_to_camera_view(scene, scene.camera, point)
        anchors[key] = {"x": float(ndc.x), "y": float(ndc.y)}
    ANCHORS.write_text(json.dumps(anchors, indent=2), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.render.render(write_still=True)
    print(OUT)


if __name__ == "__main__":
    main()

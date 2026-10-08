"""Render Fig. 1 as a data-driven Blender scene for the DC-MSS/EESS paper.

The geometry is read from the representative operational event selected by
``scripts/01_scenario_reassociation.py``. Satellite ranges are enlarged by a
common factor for legibility, while the realized ENU directions and off-axis
angles are preserved.

Run with:
    G:\\Blender\\blender.exe -b --python render_fig01_article.py
"""
from __future__ import annotations

import csv
import math
import site
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SCRIPT = Path(__file__).resolve()
FIGURES = SCRIPT.parents[2]
REPO = SCRIPT.parents[6]
EVENT_CSV = FIGURES / "data" / "fig01_representative_event.csv"
OUT = SCRIPT.with_name("fig01_scenario_reassociation_blender_base.png")
BLEND = SCRIPT.with_name("fig01_scenario_reassociation.blend")
COUNTRIES = REPO / "sharc" / "data" / "countries" / "ne_110m_admin_0_countries.shp"
site.addsitedir(str(REPO / ".venv" / "Lib" / "site-packages"))
import shapefile  # noqa: E402


EARTH_RADIUS = 4.0
EARTH_RADIUS_M = 6_371_000.0
ENU_SCALE = EARTH_RADIUS / EARTH_RADIUS_M
SATELLITE_RANGE_EXAGGERATION = 2.25
INK = (0.035, 0.055, 0.075, 1.0)
BLUE = (0.00, 0.32, 0.65, 1.0)
CYAN = (0.00, 0.66, 0.72, 1.0)
RED = (0.84, 0.15, 0.08, 1.0)
GREEN = (0.00, 0.55, 0.35, 1.0)
ORANGE = (0.95, 0.55, 0.00, 1.0)
LIGHT_GRAY = (0.78, 0.82, 0.84, 1.0)


def read_event() -> dict[str, str]:
    with EVENT_CSV.open(newline="", encoding="utf-8") as stream:
        return next(csv.DictReader(stream))


def f(event: dict[str, str], key: str) -> float:
    return float(event[key])


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.curves, bpy.data.meshes, bpy.data.materials,
                       bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name: str, rgba, *, metallic=0.0, roughness=0.55,
             emission=None, emission_strength=0.0, alpha=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = emission
            bsdf.inputs["Emission Strength"].default_value = emission_strength
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = emission
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha is not None:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.diffuse_color = (*rgba[:3], alpha)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
    return mat


def make_materials():
    return {
        "earth": material("Earth ocean", (0.055, 0.19, 0.28, 1), metallic=0.05, roughness=0.38),
        "land": material("South America", (0.68, 0.75, 0.66, 1), roughness=0.78),
        "border": material("Country boundaries", (0.16, 0.21, 0.20, 1), roughness=0.65),
        "paraguay": material("Paraguay highlight", (0.98, 0.66, 0.16, 1), roughness=0.52),
        "blue": material("Service link", BLUE, emission=BLUE, emission_strength=0.22),
        "cyan": material("Target service link", CYAN, emission=CYAN, emission_strength=0.22),
        "red": material("Interference link", RED, emission=RED, emission_strength=0.28),
        "green": material("EESS desired direction", GREEN, emission=GREEN, emission_strength=0.22),
        "orange": material("Reassociation", ORANGE, emission=ORANGE, emission_strength=0.15),
        "ink": material("Ink", INK, roughness=0.48),
        "metal": material("Satellite body", (0.22, 0.25, 0.28, 1), metallic=0.82, roughness=0.24),
        "panel": material("Solar cells", (0.015, 0.15, 0.36, 1), metallic=0.36, roughness=0.22),
        "panel_grid": material("Solar cell grid", (0.50, 0.78, 0.98, 1), metallic=0.20, roughness=0.30),
        "dish": material("EESS dish", (0.77, 0.80, 0.82, 1), metallic=0.72, roughness=0.28),
        "beam_blue": material("Serving beam", (*BLUE[:3], 1), alpha=0.12, roughness=0.65),
        "beam_cyan": material("Candidate beam", (*CYAN[:3], 1), alpha=0.10, roughness=0.65),
        "white": material("Label white", (0.98, 0.985, 0.99, 1), roughness=0.85),
    }


def normalize(v: Vector) -> Vector:
    return v.normalized() if v.length else Vector((0, 0, 1))


def cylinder_between(name, start, end, radius, mat, vertices=20):
    start, end = Vector(start), Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=direction.length,
                                        location=(start + end) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return obj


def dashed_line(name, start, end, radius, mat, count=18, duty=0.58):
    start, end = Vector(start), Vector(end)
    for idx in range(count):
        a = idx / count
        b = min((idx + duty) / count, 1.0)
        cylinder_between(f"{name}_{idx:02d}", start.lerp(end, a),
                         start.lerp(end, b), radius, mat, vertices=12)


def cone_arrow(name, start, end, radius, mat):
    cylinder_between(name + "_shaft", start, end, radius, mat)
    direction = normalize(Vector(end) - Vector(start))
    tip_center = Vector(end) + direction * radius * 2.1
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=radius * 3.3,
                                    radius2=0, depth=radius * 6.2,
                                    location=tip_center)
    arrow = bpy.context.object
    arrow.name = name + "_head"
    arrow.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    arrow.data.materials.append(mat)


def curve_tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = radius
    curve.bevel_resolution = 4
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, point in zip(spline.bezier_points, points):
        bp.co = point
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def local_sphere_point(lat_deg, lon_deg, radius, eess_lat, eess_lon):
    lat, lon = map(math.radians, (lat_deg, lon_deg))
    lat0, lon0 = map(math.radians, (eess_lat, eess_lon))
    p = Vector((math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon), math.sin(lat)))
    east = Vector((-math.sin(lon0), math.cos(lon0), 0))
    north = Vector((-math.sin(lat0) * math.cos(lon0),
                    -math.sin(lat0) * math.sin(lon0), math.cos(lat0)))
    up = Vector((math.cos(lat0) * math.cos(lon0),
                 math.cos(lat0) * math.sin(lon0), math.sin(lat0)))
    return Vector((p.dot(east), p.dot(north), p.dot(up))) * radius


def add_earth_and_countries(event, mats):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128,
                                        radius=EARTH_RADIUS, location=(0, 0, 0))
    earth = bpy.context.object
    earth.name = "Earth"
    earth.data.materials.append(mats["earth"])
    bpy.ops.object.shade_smooth()

    reader = shapefile.Reader(str(COUNTRIES))
    fields = [field[0] for field in reader.fields[1:]]
    continent_idx = fields.index("CONTINENT")
    name_idx = fields.index("NAME") if "NAME" in fields else None
    lat0, lon0 = f(event, "eess_latitude_deg"), f(event, "eess_longitude_deg")
    for record in reader.iterShapeRecords():
        if record.record[continent_idx] != "South America":
            continue
        country = record.record[name_idx] if name_idx is not None else ""
        points = record.shape.points
        parts = list(record.shape.parts) + [len(points)]
        fill_mat = mats["paraguay"] if country == "Paraguay" else mats["land"]
        for part_index, (start, end) in enumerate(zip(parts[:-1], parts[1:])):
            segment = points[start:end]
            if len(segment) < 3:
                continue
            verts = [local_sphere_point(lat, lon, EARTH_RADIUS + 0.012, lat0, lon0)
                     for lon, lat in segment]
            mesh = bpy.data.meshes.new(f"{country}_{part_index}_mesh")
            mesh.from_pydata(verts, [], [list(range(len(verts)))])
            mesh.update()
            obj = bpy.data.objects.new(f"{country}_{part_index}", mesh)
            bpy.context.collection.objects.link(obj)
            obj.data.materials.append(fill_mat)
            for idx in range(len(verts) - 1):
                cylinder_between(f"border_{country}_{part_index}_{idx}",
                                 verts[idx] * 1.0025, verts[idx + 1] * 1.0025,
                                 0.007, mats["border"], vertices=8)


def cube_oriented(name, location, dimensions, basis, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    obj.rotation_euler = basis.to_euler()
    obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def satellite_basis(location):
    z_axis = -normalize(location)
    x_axis = normalize(Vector((0, 0, 1)).cross(z_axis))
    if x_axis.length < 0.1:
        x_axis = Vector((1, 0, 0))
    y_axis = normalize(z_axis.cross(x_axis))
    return Matrix((x_axis, y_axis, z_axis)).transposed()


def add_satellite(name, location, mats, accent):
    location = Vector(location)
    basis = satellite_basis(location)
    x_axis = basis.col[0].xyz
    bus = cube_oriented(name + "_bus", location, (0.22, 0.20, 0.18), basis, mats["metal"])
    for side in (-1, 1):
        panel_center = location + x_axis * side * 0.37
        panel = cube_oriented(name + f"_panel_{side}", panel_center,
                              (0.48, 0.025, 0.20), basis, mats["panel"])
        for offset in (-0.07, 0, 0.07):
            p0 = panel_center - x_axis * 0.22 + basis.col[2].xyz * offset
            p1 = panel_center + x_axis * 0.22 + basis.col[2].xyz * offset
            cylinder_between(name + f"_grid_{side}_{offset}", p0, p1,
                             0.003, mats["panel_grid"], vertices=6)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.065,
                                        location=location - normalize(location) * 0.13)
    bpy.context.object.data.materials.append(accent)
    return bus


def tangent_circle(name, center, normal, radius, mat, width=0.012):
    normal = normalize(Vector(normal))
    u = normalize(normal.cross(Vector((0, 1, 0))))
    if u.length < 0.1:
        u = Vector((1, 0, 0))
    v = normalize(normal.cross(u))
    points = [Vector(center) + radius * (math.cos(t) * u + math.sin(t) * v)
              for t in [2 * math.pi * i / 64 for i in range(65)]]
    curve_tube(name, points, width, mat)


def add_dish(location, boresight, mats):
    location = Vector(location)
    normal = normalize(location)
    boresight = normalize(Vector(boresight))
    mast_top = location + normal * 0.20
    cylinder_between("EESS_mast", location, mast_top, 0.030, mats["metal"])
    u = normalize(boresight.cross(Vector((0, 0, 1))))
    if u.length < 0.1:
        u = Vector((1, 0, 0))
    v = normalize(boresight.cross(u))
    center = mast_top + boresight * 0.035
    rings, segments, radius, depth = 9, 64, 0.15, 0.055
    verts = [center - boresight * depth]
    for ring in range(1, rings + 1):
        rr = radius * ring / rings
        axial = -depth * (1 - (ring / rings) ** 2)
        for idx in range(segments):
            angle = 2 * math.pi * idx / segments
            verts.append(center + boresight * axial + rr * (math.cos(angle) * u + math.sin(angle) * v))
    faces = []
    for idx in range(segments):
        faces.append((0, 1 + idx, 1 + (idx + 1) % segments))
    for ring in range(1, rings):
        row, nxt = 1 + (ring - 1) * segments, 1 + ring * segments
        for idx in range(segments):
            faces.append((row + idx, row + (idx + 1) % segments,
                          nxt + (idx + 1) % segments, nxt + idx))
    mesh = bpy.data.meshes.new("EESS_dish_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    dish = bpy.data.objects.new("EESS_dish", mesh)
    bpy.context.collection.objects.link(dish)
    dish.data.materials.append(mats["dish"])
    feed = center + boresight * 0.15
    cylinder_between("EESS_feed_arm", center - boresight * depth, feed,
                     0.009, mats["metal"], vertices=12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10,
                                        radius=0.028, location=feed)
    bpy.context.object.data.materials.append(mats["ink"])


def beam_cone(name, satellite, cell, radius, mat):
    satellite, cell = Vector(satellite), Vector(cell)
    direction = normalize(satellite - cell)
    u = normalize(direction.cross(Vector((0, 0, 1))))
    if u.length < 0.1:
        u = Vector((1, 0, 0))
    v = normalize(direction.cross(u))
    ring = [cell + radius * (math.cos(2 * math.pi * i / 72) * u
                             + math.sin(2 * math.pi * i / 72) * v)
            for i in range(72)]
    verts = [satellite] + ring
    faces = [(0, 1 + i, 1 + ((i + 1) % 72)) for i in range(72)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)


def add_text(name, body, location, size, mat, camera, align="CENTER"):
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.002
    obj.data.bevel_depth = 0.0007
    obj.data.materials.append(mat)
    direction = camera.location - obj.location
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    return obj


def add_angle_arc(name, origin, a, b, radius, mat):
    origin = Vector(origin)
    a, b = normalize(Vector(a)), normalize(Vector(b))
    angle = math.acos(max(-1.0, min(1.0, a.dot(b))))
    axis = normalize(a.cross(b))
    points = []
    for idx in range(41):
        t = idx / 40
        direction = a.copy()
        direction.rotate(Matrix.Rotation(angle * t, 4, axis))
        points.append(origin + direction * radius)
    curve_tube(name, points, 0.009, mat)


def setup_scene():
    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 3600
    scene.render.resolution_y = 2100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(OUT)
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Paper white")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
    bg.inputs["Strength"].default_value = 0.80
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"

    bpy.ops.object.light_add(type="AREA", location=(5.5, -5.0, 11.0))
    key = bpy.context.object
    key.data.energy = 1050
    key.data.shape = "DISK"
    key.data.size = 7.0
    bpy.ops.object.light_add(type="AREA", location=(-5.0, 3.0, 7.5))
    fill = bpy.context.object
    fill.data.energy = 650
    fill.data.size = 8.0
    bpy.ops.object.light_add(type="AREA", location=(0.0, 5.0, 2.0))
    rim = bpy.context.object
    rim.data.energy = 500
    rim.data.size = 5.0

    bpy.ops.object.camera_add(location=(7.7, -10.5, 8.7))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 8.8
    camera.data.lens = 58
    target = Vector((-0.45, 0.15, 4.15))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    return scene, camera


def main():
    event = read_event()
    scene, camera = setup_scene()
    mats = make_materials()
    add_earth_and_countries(event, mats)

    eess = Vector((0, 0, EARTH_RADIUS + 0.035))
    service = eess + Vector((f(event, "service_cell_enu_x_m"),
                             f(event, "service_cell_enu_y_m"),
                             f(event, "service_cell_enu_z_m"))) * ENU_SCALE
    current_vec = Vector((f(event, "current_satellite_enu_x_m"),
                          f(event, "current_satellite_enu_y_m"),
                          f(event, "current_satellite_enu_z_m"))) * ENU_SCALE
    target_vec = Vector((f(event, "target_satellite_enu_x_m"),
                         f(event, "target_satellite_enu_y_m"),
                         f(event, "target_satellite_enu_z_m"))) * ENU_SCALE
    current = eess + current_vec * SATELLITE_RANGE_EXAGGERATION
    target = eess + target_vec * SATELLITE_RANGE_EXAGGERATION
    boresight = Vector((f(event, "eess_boresight_x"),
                        f(event, "eess_boresight_y"),
                        f(event, "eess_boresight_z")))

    add_satellite("Serving_satellite", current, mats, mats["red"])
    add_satellite("Target_satellite", target, mats, mats["cyan"])
    add_dish(eess, boresight, mats)
    tangent_circle("Service_cell_ring", service + normalize(service) * 0.015,
                   service, 0.115, mats["blue"], width=0.014)
    tangent_circle("EESS_station_ring", eess + normalize(eess) * 0.012,
                   eess, 0.09, mats["green"], width=0.010)

    cylinder_between("Serving_service_link", current, service, 0.018, mats["blue"])
    dashed_line("Target_service_link", target, service, 0.016, mats["cyan"], count=22)
    cylinder_between("Interference_path", current, eess, 0.022, mats["red"])
    dashed_line("Candidate_residual_path", target, eess, 0.010, mats["orange"], count=18)
    cone_arrow("EESS_boresight", eess + boresight * 0.08,
               eess + boresight * 1.45, 0.018, mats["green"])
    beam_cone("Serving_beam", current, service, 0.15, mats["beam_blue"])
    beam_cone("Target_beam", target, service, 0.15, mats["beam_cyan"])

    control = (current + target) * 0.5 + normalize(current + target) * 0.75 + Vector((0, 0, 0.35))
    reassociation_points = [current * 0.97 + control * 0.03, control, target * 0.97 + control * 0.03]
    curve_tube("Reassociation_arc", reassociation_points, 0.022, mats["orange"])
    cone_arrow("Reassociation_arrow", reassociation_points[-1] - normalize(target - control) * 0.16,
               reassociation_points[-1], 0.018, mats["orange"])

    add_angle_arc("psi_rx", eess, boresight, current - eess, 0.40, mats["green"])
    add_angle_arc("psi_tx", current, service - current, eess - current, 0.25, mats["red"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.render.render(write_still=True)
    print(f"[ok] {OUT}")
    print(f"[ok] {BLEND}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

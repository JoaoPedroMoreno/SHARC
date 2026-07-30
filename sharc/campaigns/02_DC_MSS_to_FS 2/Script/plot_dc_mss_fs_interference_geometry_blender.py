"""Render a clean 3D conceptual diagram for DC-MSS interference into FS.

The figure is a schematic, not a geodetic map. It is designed for a paper and
shows the two simulated interference mechanisms around a triple border:

  (A) Regional coverage: DC-MSS beams illuminate Brazil, Argentina and Paraguay.
      The FS receiver in Paraguay can be hit by a main lobe.
  (B) Cross-border spillover: DC-MSS beams are restricted to Brazil/Argentina.
      The FS receiver in Paraguay is reached only by side-lobe leakage.

Run:
    G:\\Blender\\blender.exe -b --python plot_dc_mss_fs_interference_geometry_blender.py
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import bpy
from mathutils import Euler, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR.parent / "plots" / "conceptual_geometry_blender"
PNG_PATH = OUT_DIR / "dc_mss_fs_interference_geometry_blender.png"
ARTICLE_PNG_PATH = SCRIPT_DIR.parents[3] / "figuras" / "geometria_interferencia.png"
BLEND_PATH = OUT_DIR / "dc_mss_fs_interference_geometry_blender.blend"

PANEL_A_X = -3.25
PANEL_B_X = 3.25
GROUND_Z = 0.0
SAT_Z = 2.85
FOOTPRINT_Z = 0.018
COMMON_BEAM_OFFSET_X = 0.26
COMMON_BEAM_OFFSET_Y = 0.26
COMMON_SAT_ROLL_DEG = -8.0


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(
    name: str,
    color: tuple[float, float, float, float],
    alpha: float | None = None,
    roughness: float = 0.55,
    metallic: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha is not None:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
            mat.show_transparent_back = True
    return mat


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "brazil": material("Brazil green", (0.45, 0.78, 0.52, 0.92), alpha=0.92),
        "argentina": material("Argentina blue", (0.46, 0.68, 0.94, 0.92), alpha=0.92),
        "paraguay": material("Paraguay amber", (0.98, 0.72, 0.34, 0.92), alpha=0.92),
        "brazil_legend": material("Brazil legend", (0.20, 0.70, 0.36, 1.0)),
        "argentina_legend": material("Argentina legend", (0.22, 0.54, 0.90, 1.0)),
        "paraguay_legend": material("Paraguay legend", (0.93, 0.63, 0.10, 1.0)),
        "region_edge": material("Region edge", (0.22, 0.22, 0.22, 1.0)),
        "main_beam": material("Main beam translucent", (0.02, 0.28, 0.68, 0.20), alpha=0.20),
        "main_line": material("Main beam line", (0.00, 0.20, 0.55, 1.0)),
        "side_line": material("Side lobe leakage", (0.90, 0.08, 0.07, 1.0)),
        "sat_body": material("Satellite dark body", (0.20, 0.22, 0.24, 1.0), roughness=0.36),
        "sat_panel": material("Satellite blue solar panel", (0.08, 0.24, 0.52, 1.0), roughness=0.32),
        "sat_panel_cell": material("Solar panel cell lines", (0.75, 0.86, 0.98, 1.0)),
        "orbit_outline": material("Orbit arrow outline", (0.10, 0.12, 0.16, 1.0)),
        "orbit_core": material("Orbit arrow core", (0.42, 0.72, 1.00, 1.0)),
        "fs": material("FS antenna mast", (0.45, 0.48, 0.50, 1.0), roughness=0.34, metallic=0.20),
        "fs_reflector": material("FS reflector back", (0.64, 0.66, 0.66, 1.0), roughness=0.36, metallic=0.18),
        "fs_dark": material("FS antenna dark", (0.18, 0.20, 0.21, 1.0), roughness=0.40, metallic=0.12),
        "fs_boresight": material("FS azimuth arrow", (0.92, 0.04, 0.04, 1.0), roughness=0.32),
        "text": material("Text charcoal", (0.05, 0.05, 0.05, 1.0)),
        "blue_text": material("Text blue", (0.00, 0.18, 0.46, 1.0)),
        "red_text": material("Text red", (0.78, 0.03, 0.04, 1.0)),
        "north": material("North arrow", (0.08, 0.08, 0.08, 1.0)),
    }


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_poly(name: str, pts: list[tuple[float, float]], mat: bpy.types.Material, z: float = GROUND_Z) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata([(x, y, z) for x, y in pts], [], [list(range(len(pts)))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_cylinder_between(
    name: str,
    start: tuple[float, float, float] | Vector,
    end: tuple[float, float, float] | Vector,
    radius: float,
    mat: bpy.types.Material,
    vertices: int = 24,
) -> bpy.types.Object:
    start_v = Vector(start)
    end_v = Vector(end)
    mid = (start_v + end_v) * 0.5
    diff = end_v - start_v
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=diff.length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = diff.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return obj


def add_dashed_line(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    mat: bpy.types.Material,
    radius: float = 0.014,
    dashes: int = 12,
    dash_fraction: float = 0.055,
) -> None:
    s = Vector(start)
    e = Vector(end)
    for idx in range(dashes):
        a = idx / dashes
        b = min(a + dash_fraction, 1.0)
        add_cylinder_between(f"{name}_{idx:02d}", s.lerp(e, a), s.lerp(e, b), radius, mat, vertices=16)


def add_text(
    name: str,
    body: str,
    loc: tuple[float, float, float],
    size: float,
    mat: bpy.types.Material,
    align: str = "CENTER",
    ground: bool = False,
) -> bpy.types.Object:
    if ground:
        rot = (math.radians(64), 0, 0)
    else:
        rot = (math.radians(62), 0, 0)
    bpy.ops.object.text_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.0015
    obj.data.materials.append(mat)
    return obj


def region_polygons(cx: float) -> dict[str, list[tuple[float, float]]]:
    # Required schematic order after flipping the north axis toward the viewer:
    # Brazil spans the left side, Argentina is upper-right, Paraguay is
    # lower-right, with the FS close to the Brazil/Paraguay boundary.
    return {
        "Brazil": [
            (cx - 2.72, 1.12),
            (cx - 0.28, 1.02),
            (cx + 0.22, 0.16),
            (cx + 0.10, -0.18),
            (cx - 0.28, -0.92),
            (cx - 2.70, -1.08),
        ],
        "Argentina": [
            (cx - 0.28, 1.02),
            (cx + 2.58, 1.06),
            (cx + 2.52, 0.04),
            (cx + 0.22, 0.16),
        ],
        "Paraguay": [
            (cx + 0.10, -0.18),
            (cx + 0.22, 0.16),
            (cx + 2.52, 0.04),
            (cx + 2.64, -0.98),
            (cx - 0.28, -0.92),
        ],
    }


def add_country_regions(cx: float, mats: dict[str, bpy.types.Material], regional: bool) -> dict[str, tuple[float, float, float]]:
    polys = region_polygons(cx)
    mats_by_country = {
        "Brazil": mats["brazil"],
        "Argentina": mats["argentina"],
        "Paraguay": mats["brazil"] if regional else mats["paraguay"],
    }
    for country, pts in polys.items():
        add_poly(f"{country}_{cx}", pts, mats_by_country[country])
        for idx in range(len(pts)):
            a = pts[idx]
            b = pts[(idx + 1) % len(pts)]
            add_cylinder_between(f"{country}_edge_{cx}_{idx}", (a[0], a[1], 0.025), (b[0], b[1], 0.025), 0.006, mats["region_edge"], vertices=8)

    if regional:
        add_poly(f"Paraguay_victim_overlay_{cx}", polys["Paraguay"], mats["paraguay"], z=0.018)

    # Interior labels, slightly lifted to stay visible above the country surfaces.
    add_text(f"brazil_label_{cx}", "Brazil", (cx - 1.42, -0.02, 0.18), 0.32, mats["text"], ground=True)
    add_text(f"arg_label_{cx}", "Argentina", (cx + 1.32, 0.58, 0.18), 0.32, mats["text"], ground=True)
    add_text(f"par_label_{cx}", "Paraguay", (cx + 1.72, -0.70, 0.18), 0.32, mats["text"], ground=True)

    return {
        "Brazil": (cx - 1.45, -0.02, FOOTPRINT_Z),
        "Argentina": (cx + 1.30, 0.58, FOOTPRINT_Z),
        "Paraguay": (cx + 1.26, -0.56, FOOTPRINT_Z),
        "FS": (cx + 0.42, -0.34, FOOTPRINT_Z),
        "Triple": (cx + 0.16, 0.02, FOOTPRINT_Z),
    }


def rotate_offset(offset: tuple[float, float, float], rot: tuple[float, float, float]) -> Vector:
    vec = Vector(offset)
    euler = Euler(rot)
    vec.rotate(euler)
    return vec


def common_service_footprint(sat: tuple[float, float, float]) -> tuple[float, float]:
    return (sat[0] + COMMON_BEAM_OFFSET_X, sat[1] + COMMON_BEAM_OFFSET_Y)


def add_satellite(
    name: str,
    loc: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
    roll_deg: float = 0.0,
    target: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    x, y, z = loc
    if target is None:
        rot = Euler((math.radians(pitch_deg), math.radians(roll_deg), math.radians(yaw_deg)))
    else:
        direction = Vector(target) - Vector(loc)
        rot = direction.to_track_quat("-Z", "Y").to_euler()
        rot.rotate_axis("Z", math.radians(roll_deg))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, z))
    body = bpy.context.object
    body.name = f"{name}_body"
    body.dimensions = (0.28, 0.22, 0.20)
    body.rotation_euler = rot
    body.data.materials.append(mats["sat_body"])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    for side in (-1, 1):
        panel_center = Vector((x, y, z)) + rotate_offset((side * 0.43, 0.0, 0.01), rot)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=panel_center)
        panel = bpy.context.object
        panel.name = f"{name}_solar_panel_{side}"
        panel.dimensions = (0.48, 0.035, 0.24)
        panel.rotation_euler = rot
        panel.data.materials.append(mats["sat_panel"])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for k in (-0.09, 0.0, 0.09):
            start = Vector((x, y, z)) + rotate_offset((side * 0.20, -0.024, k), rot)
            end = Vector((x, y, z)) + rotate_offset((side * 0.66, -0.024, k), rot)
            add_cylinder_between(
                f"{name}_panel_cell_{side}_{k}",
                start,
                end,
                0.0045,
                mats["sat_panel_cell"],
                vertices=6,
            )
        for k in (0.32, 0.48, 0.61):
            start = Vector((x, y, z)) + rotate_offset((side * k, -0.025, -0.105), rot)
            end = Vector((x, y, z)) + rotate_offset((side * k, -0.025, 0.105), rot)
            add_cylinder_between(
                f"{name}_panel_cross_cell_{side}_{k}",
                start,
                end,
                0.004,
                mats["sat_panel_cell"],
                vertices=6,
            )

    feed_loc = Vector((x, y, z)) + rotate_offset((0.0, 0.0, -0.18), rot)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.08, location=feed_loc)
    feed = bpy.context.object
    feed.name = f"{name}_feed"
    feed.scale.z = 0.45
    feed.rotation_euler = rot
    feed.data.materials.append(mats["sat_body"])
    return tuple(feed_loc)


def add_footprint_cone(
    name: str,
    aperture: tuple[float, float, float],
    center_xy: tuple[float, float],
    radius: float,
    mats: dict[str, bpy.types.Material],
) -> None:
    center = (center_xy[0], center_xy[1], FOOTPRINT_Z)
    n = 96
    verts = [aperture]
    for i in range(n):
        th = 2 * math.pi * i / n
        verts.append((center[0] + radius * math.cos(th), center[1] + 0.72 * radius * math.sin(th), center[2]))
    faces = [(0, i, 1 if i == n else i + 1) for i in range(1, n + 1)]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats["main_beam"])

    add_cylinder_between(f"{name}_center", aperture, center, 0.015, mats["main_line"], vertices=18)
    # Smooth footprint rim.
    prev = verts[-1]
    for i in range(1, n + 1):
        cur = verts[i]
        if i % 3 == 0:
            add_cylinder_between(f"{name}_rim_{i}", prev, cur, 0.0045, mats["main_line"], vertices=6)
        prev = cur


def add_orbit_arc(
    name: str,
    center: tuple[float, float, float],
    width: float,
    mats: dict[str, bpy.types.Material],
    start_deg: float = 202,
    end_deg: float = 338,
) -> None:
    pts = []
    for idx in range(28):
        t = math.radians(start_deg + (end_deg - start_deg) * idx / 27)
        pts.append((center[0] + width * math.cos(t), center[1] + 0.28 * math.sin(t), center[2] + 0.07 * math.sin(t)))
    for idx in range(len(pts) - 1):
        add_cylinder_between(f"{name}_arc_outline_{idx}", pts[idx], pts[idx + 1], 0.012, mats["orbit_outline"], vertices=10)
        add_cylinder_between(f"{name}_arc_core_{idx}", pts[idx], pts[idx + 1], 0.0055, mats["orbit_core"], vertices=8)
    # Small arrow head following the arc.
    end = pts[-1]
    prev = pts[-2]
    direction = Vector(end) - Vector(prev)
    bpy.ops.mesh.primitive_cone_add(vertices=18, radius1=0.065, depth=0.13, location=end)
    arrow = bpy.context.object
    arrow.name = f"{name}_arrow_outline"
    arrow.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    arrow.data.materials.append(mats["orbit_outline"])
    bpy.ops.mesh.primitive_cone_add(
        vertices=18,
        radius1=0.037,
        depth=0.145,
        location=Vector(end) + direction.normalized() * 0.003,
    )
    arrow_core = bpy.context.object
    arrow_core.name = f"{name}_arrow_core"
    arrow_core.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    arrow_core.data.materials.append(mats["orbit_core"])


def add_fs_antenna(name: str, loc: tuple[float, float, float], mats: dict[str, bpy.types.Material]) -> tuple[float, float, float]:
    x, y, z = loc
    top = (x, y, z + 0.66)
    add_cylinder_between(f"{name}_mast", (x, y, z), top, 0.028, mats["fs"], vertices=24)
    # The FS antenna azimuth points north. Here north is toward the camera
    # (-Y), i.e. coming out of the screen. The red dashed satellite-to-FS link
    # therefore reaches the front/feed side of the dish.
    rim_y = y - 0.28
    back_y = y - 0.04
    radius = 0.205
    rings = 12
    segments = 72
    verts = [(x, back_y, z + 0.68)]
    for r_idx in range(1, rings + 1):
        rr = radius * r_idx / rings
        yy = back_y + (rim_y - back_y) * (r_idx / rings) ** 1.75
        for seg in range(segments):
            th = 2 * math.pi * seg / segments
            verts.append((x + rr * math.cos(th), yy, z + 0.68 + rr * math.sin(th)))
    faces = []
    for seg in range(segments):
        faces.append((0, 1 + seg, 1 + ((seg + 1) % segments)))
    for r_idx in range(1, rings):
        row = 1 + (r_idx - 1) * segments
        nxt = 1 + r_idx * segments
        for seg in range(segments):
            faces.append((row + seg, row + ((seg + 1) % segments), nxt + ((seg + 1) % segments), nxt + seg))
    mesh = bpy.data.meshes.new(f"{name}_dish_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    dish = bpy.data.objects.new(f"{name}_north_facing_dish", mesh)
    bpy.context.collection.objects.link(dish)
    dish.data.materials.append(mats["fs_reflector"])
    prev = (x + radius, rim_y, z + 0.68)
    for seg in range(1, segments + 1):
        th = 2 * math.pi * seg / segments
        cur = (x + radius * math.cos(th), rim_y, z + 0.68 + radius * math.sin(th))
        add_cylinder_between(f"{name}_dish_rim_{seg}", prev, cur, 0.0065, mats["fs_dark"], vertices=8)
        prev = cur
    add_cylinder_between(f"{name}_back_strut", top, (x, back_y + 0.10, z + 0.68), 0.014, mats["fs_dark"], vertices=12)
    receive_point = (x, y - 0.50, z + 0.68)
    add_cylinder_between(f"{name}_feed_arm", top, receive_point, 0.010, mats["fs_dark"], vertices=12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.038, location=receive_point)
    feed = bpy.context.object
    feed.name = f"{name}_feed"
    feed.data.materials.append(mats["fs_dark"])
    return receive_point


def add_direction_indicator(mats: dict[str, bpy.types.Material]) -> None:
    x, y, z = 4.95, -1.86, 0.12
    # North is out of the screen/toward the viewer (-Y). Use the standard
    # vector symbol: circle with a central dot.
    radius = 0.16
    prev = (x + radius, y, z)
    for seg in range(1, 49):
        th = 2 * math.pi * seg / 48
        cur = (x + radius * math.cos(th), y, z + radius * math.sin(th))
        add_cylinder_between(f"compass_out_circle_{seg}", prev, cur, 0.005, mats["north"], vertices=8)
        prev = cur
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.035, location=(x, y, z))
    dot = bpy.context.object
    dot.name = "compass_out_dot"
    dot.data.materials.append(mats["north"])
    add_cylinder_between("compass_east_west", (x - 0.26, y, z), (x + 0.26, y, z), 0.0045, mats["north"], vertices=8)
    add_text("compass_north_label", "N out of screen", (x - 1.06, y + 0.04, z + 0.02), 0.082, mats["north"], align="LEFT", ground=True)


def draw_panel_a(mats: dict[str, bpy.types.Material]) -> None:
    anchors = add_country_regions(PANEL_A_X, mats, regional=True)
    fs_top = add_fs_antenna("fs_a", anchors["FS"], mats)

    sats = []
    attitude_index = 0
    sat_layout_a = {
        "par": [
            ((-1.00, 0.06, 0.42), (-0.84, 0.22), -30, 7, -10),
            ((0.38, -0.36, 0.08), (0.58, -0.18), 18, -9, 6),
        ],
        "arg": [
            ((-0.44, 0.20, 0.24), (-0.18, 0.34), -8, 10, -8),
            ((0.42, -0.12, 0.50), (0.70, 0.08), 32, -7, 10),
        ],
        "bra": [
            ((-0.28, -0.54, 0.30), (-0.06, -0.34), -24, 9, 7),
            ((1.04, -0.40, 0.12), (0.34, 0.02), 26, -8, -9),
        ],
    }
    main_lobe_fs_aperture = None
    side_lobe_fs_aperture = None
    for country, base in (
        ("par", anchors["Paraguay"]),
        ("arg", anchors["Argentina"]),
        ("bra", anchors["Brazil"]),
    ):
        for idx, (sat_offset, footprint_offset, yaw, pitch, roll) in enumerate(sat_layout_a[country]):
            dx, dy, dz = sat_offset
            sat = (base[0] + dx, base[1] + dy, SAT_Z + dz)
            # Off-axis beam steering: footprint is near the satellite nadir, but
            # shifted toward the served territory/cell.
            is_main_lobe_fs = country == "par" and idx == 0
            is_side_lobe_fs = country == "bra" and idx == 1
            if is_main_lobe_fs:
                footprint = (base[0] + footprint_offset[0], base[1] + footprint_offset[1])
            else:
                footprint = common_service_footprint(sat)
            target = (footprint[0], footprint[1], FOOTPRINT_Z)
            aperture = add_satellite(
                f"sat_a_{country}_{idx}",
                sat,
                mats,
                yaw_deg=yaw,
                pitch_deg=pitch,
                roll_deg=COMMON_SAT_ROLL_DEG,
                target=target,
            )
            add_footprint_cone(f"beam_a_{country}_{idx}", aperture, footprint, 0.22 if is_main_lobe_fs else 0.31, mats)
            sats.append((country, sat, aperture))
            if is_main_lobe_fs:
                main_lobe_fs_aperture = aperture
            if is_side_lobe_fs:
                side_lobe_fs_aperture = aperture
            attitude_index += 1

    # Panel A separates the mechanisms: one blue main lobe directly covers the
    # FS, while a different satellite contributes only side-lobe leakage.
    if side_lobe_fs_aperture:
        add_dashed_line(
            "side_lobe_a",
            side_lobe_fs_aperture,
            fs_top,
            mats["side_line"],
            radius=0.014,
            dashes=9,
            dash_fraction=0.075,
        )


def draw_panel_b(mats: dict[str, bpy.types.Material]) -> None:
    anchors = add_country_regions(PANEL_B_X, mats, regional=False)
    fs_top = add_fs_antenna("fs_b", anchors["FS"], mats)

    sats = []
    attitude_index = 0
    sat_layout_b = {
        "arg": [
            ((-0.84, 0.22, 0.18), (-0.60, 0.38), -14, 9, -8),
            ((0.52, -0.10, 0.46), (0.74, 0.10), 24, -9, 9),
        ],
        "bra": [
            ((-1.04, -0.52, 0.34), (-0.82, -0.32), -28, 11, 8),
            ((1.08, -0.34, 0.10), (1.36, -0.14), 36, -7, -10),
        ],
    }
    for country, base in (("arg", anchors["Argentina"]), ("bra", anchors["Brazil"])):
        for idx, (sat_offset, footprint_offset, yaw, pitch, roll) in enumerate(sat_layout_b[country]):
            dx, dy, dz = sat_offset
            sat = (base[0] + dx, base[1] + dy, SAT_Z + dz)
            footprint = (base[0] + footprint_offset[0], base[1] + footprint_offset[1])
            target = (footprint[0], footprint[1], FOOTPRINT_Z)
            is_interferer = country == "bra" and idx == 1
            aperture = add_satellite(
                f"sat_b_{country}_{idx}",
                sat,
                mats,
                yaw_deg=yaw,
                pitch_deg=pitch,
                roll_deg=COMMON_SAT_ROLL_DEG,
                target=target,
            )
            add_footprint_cone(f"beam_b_{country}_{idx}", aperture, footprint, 0.24 if is_interferer else 0.31, mats)
            sats.append((sat, aperture))
            attitude_index += 1

    # Side-lobe leakage only from the closest Brazil-serving satellite.
    add_dashed_line(
        "side_lobe_b",
        sats[3][1],
        fs_top,
        mats["side_line"],
        radius=0.014,
        dashes=9,
        dash_fraction=0.075,
    )


def add_legend(mats: dict[str, bpy.types.Material]) -> None:
    add_text("panel_a_caption", "(A) Regional coverage", (PANEL_A_X, -1.74, 0.11), 0.32, mats["text"], ground=True)
    add_text("panel_b_caption", "(B) Cross-border spillover", (PANEL_B_X, -1.74, 0.11), 0.32, mats["text"], ground=True)
    z = 0.09
    entries = [
        ("Brazil service", mats["brazil_legend"], -5.85, -2.62),
        ("Argentina service", mats["argentina_legend"], -1.80, -2.62),
        ("Paraguay / FS victim", mats["paraguay_legend"], 2.55, -2.62),
        ("Main-lobe downlink", mats["main_line"], -3.95, -3.22),
        ("Side-lobe interference", mats["side_line"], 0.95, -3.22),
    ]
    for label, mat, x, y in entries:
        if "service" in label or "victim" in label:
            add_poly(f"legend_{label}", [(x, y), (x + 0.42, y), (x + 0.42, y + 0.23), (x, y + 0.23)], mat, z)
            add_cylinder_between(f"legend_edge_{label}_0", (x, y, z + 0.006), (x + 0.42, y, z + 0.006), 0.006, mats["region_edge"], vertices=6)
            add_cylinder_between(f"legend_edge_{label}_1", (x + 0.42, y, z + 0.006), (x + 0.42, y + 0.23, z + 0.006), 0.006, mats["region_edge"], vertices=6)
            add_cylinder_between(f"legend_edge_{label}_2", (x + 0.42, y + 0.23, z + 0.006), (x, y + 0.23, z + 0.006), 0.006, mats["region_edge"], vertices=6)
            add_cylinder_between(f"legend_edge_{label}_3", (x, y + 0.23, z + 0.006), (x, y, z + 0.006), 0.006, mats["region_edge"], vertices=6)
        elif "Side" in label:
            add_dashed_line(
                f"legend_{label}",
                (x, y + 0.085, z),
                (x + 0.72, y + 0.085, z),
                mat,
                radius=0.014,
                dashes=3,
                dash_fraction=0.18,
            )
        else:
            add_cylinder_between(f"legend_{label}", (x, y + 0.085, z), (x + 0.72, y + 0.085, z), 0.016, mat, vertices=12)
        add_text(f"legend_text_{label}", label, (x + 0.84, y + 0.085, z + 0.005), 0.32, mats["text"], align="LEFT", ground=True)


def setup_scene() -> dict[str, bpy.types.Material]:
    clear_scene()
    mats = make_materials()

    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 80
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.scene.view_settings.look = "None"
    bpy.context.scene.world = bpy.data.worlds.new("white_world")
    bpy.context.scene.world.color = (1.0, 1.0, 1.0)
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (1, 1, 1, 1)
        bg.inputs["Strength"].default_value = 0.95

    bpy.ops.object.light_add(type="AREA", location=(0, -5.8, 7.5))
    key = bpy.context.object
    key.name = "large_key_light"
    key.data.energy = 650
    key.data.size = 6.5
    bpy.ops.object.light_add(type="AREA", location=(0, 4.0, 5.5))
    fill = bpy.context.object
    fill.name = "soft_fill_light"
    fill.data.energy = 160
    fill.data.size = 8.0

    bpy.ops.object.camera_add(location=(0, -8.6, 6.1))
    cam = bpy.context.object
    cam.name = "Camera"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 12.8
    look_at(cam, (0, -0.04, 0.95))
    bpy.context.scene.camera = cam

    bpy.context.scene.render.resolution_x = 4200
    bpy.context.scene.render.resolution_y = 2200
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.color_mode = "RGBA"
    return mats


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mats = setup_scene()
    draw_panel_a(mats)
    draw_panel_b(mats)
    add_legend(mats)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.context.scene.render.filepath = str(PNG_PATH)
    bpy.ops.render.render(write_still=True)
    ARTICLE_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PNG_PATH, ARTICLE_PNG_PATH)
    print(f"[ok] {PNG_PATH}")
    print(f"[ok] {ARTICLE_PNG_PATH}")
    print(f"[ok] {BLEND_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

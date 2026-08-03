#!/usr/bin/env python3
"""Generate an academic 3D illustration of selective DC-MSS power back-off.

Run with:
    blender --background --python generate_pbo_illustration.py

Only native Blender APIs and the bundled Bfont typeface are used. The scene is
laid out for a two-column IEEE figure and rendered at 2800 x 1575 pixels.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# User-adjustable parameters
# ---------------------------------------------------------------------------

RENDER_WIDTH = 2800
RENDER_HEIGHT = 1575
RENDER_SAMPLES = 64
PBO_LABEL_DB = 10
BEAM_COUNT = 5
PBO_BEAM_INDICES = {1, 3}
IEEE_DOUBLE_COLUMN_WIDTH_IN = 7.16
PUBLICATION_DPI = 300

# Text sizes are deliberately conservative. At 2800 px, the smallest text is
# about 48-52 px tall and remains approximately 9 pt after reduction to a
# 7.16-inch, 300-dpi two-column IEEE figure.
TEXT_SIZE = {
    "panel_title": 0.62,
    "annotation": 0.46,
    "legend": 0.56,
    "secondary": 0.39,
}

MIN_TEXT_POINTS = {
    "panel_title": 12.0,
    "annotation": 10.0,
    "legend": 9.0,
    "secondary": 8.0,
}

COLORS = {
    "background": (0.965, 0.972, 0.978, 1.0),
    "earth": (0.61, 0.73, 0.76, 1.0),
    "satellite": (0.62, 0.65, 0.68, 1.0),
    "satellite_dark": (0.22, 0.26, 0.30, 1.0),
    "solar": (0.055, 0.20, 0.36, 1.0),
    "solar_grid": (0.48, 0.68, 0.78, 1.0),
    "nominal": (0.02, 0.31, 0.68, 1.0),
    "pbo": (0.86, 0.27, 0.045, 1.0),
    "user_affected": (0.66, 0.12, 0.035, 1.0),
    "user_unaffected": (0.02, 0.31, 0.23, 1.0),
    "interference": (0.65, 0.17, 0.13, 1.0),
    "text": (0.035, 0.045, 0.055, 1.0),
    "line": (0.055, 0.065, 0.075, 1.0),
    "divider": (0.70, 0.73, 0.76, 1.0),
}

OUTPUT_DIR = Path(__file__).resolve().parent
PNG_PATH = OUTPUT_DIR / "fig_pbo_ilustracao.png"
BLEND_PATH = OUTPUT_DIR / "fig_pbo_ilustracao.blend"


# ---------------------------------------------------------------------------
# Scene and material helpers
# ---------------------------------------------------------------------------

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def validate_publication_text_sizes(camera: bpy.types.Object) -> dict[str, float]:
    """Estimate printed point sizes at IEEE two-column width and enforce minima."""
    vertical_field = camera.data.ortho_scale * RENDER_HEIGHT / RENDER_WIDTH
    publication_scale = (
        IEEE_DOUBLE_COLUMN_WIDTH_IN * PUBLICATION_DPI / RENDER_WIDTH
    )
    estimates = {}
    for role, world_size in TEXT_SIZE.items():
        rendered_pixels = world_size / vertical_field * RENDER_HEIGHT
        printed_points = (
            rendered_pixels * publication_scale / PUBLICATION_DPI * 72.0
        )
        estimates[role] = printed_points
        if printed_points < MIN_TEXT_POINTS[role]:
            raise RuntimeError(
                f"{role} is estimated at {printed_points:.1f} pt; "
                f"minimum is {MIN_TEXT_POINTS[role]:.1f} pt"
            )
    return estimates


def set_input(node, names: tuple[str, ...], value) -> None:
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def make_material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    roughness: float = 0.55,
    metallic: float = 0.0,
    alpha: float | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    rgba = (*color[:3], color[3] if alpha is None else alpha)
    material.diffuse_color = rgba
    principled = material.node_tree.nodes.get("Principled BSDF")
    set_input(principled, ("Base Color",), rgba)
    set_input(principled, ("Roughness",), roughness)
    set_input(principled, ("Metallic",), metallic)
    set_input(principled, ("Alpha",), rgba[3])
    if emission_strength > 0:
        set_input(principled, ("Emission Color", "Emission"), rgba)
        set_input(principled, ("Emission Strength",), emission_strength)
    if rgba[3] < 1.0:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        material.use_transparency_overlap = False
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.append(material)


def smooth_object(obj: bpy.types.Object) -> None:
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def add_bevel(obj: bpy.types.Object, width: float, segments: int = 3) -> None:
    modifier = obj.modifiers.new(name="Edge softening", type="BEVEL")
    modifier.width = width
    modifier.segments = segments


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def face_camera(obj: bpy.types.Object, camera: bpy.types.Object) -> None:
    # The publication camera is orthographic, so all labels should share its
    # exact orientation. Pointing every label toward the camera position would
    # introduce needless perspective-like slant near the panel edges.
    obj.rotation_euler = camera.rotation_euler.copy()


def cube(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material: bpy.types.Material,
    *,
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        add_bevel(obj, bevel)
    assign_material(obj, material)
    return obj


def cylinder_between(
    name: str,
    start: Vector,
    end: Vector,
    radius: float,
    material: bpy.types.Material,
    vertices: int = 16,
) -> bpy.types.Object:
    delta = end - start
    length = delta.length
    if length <= 1e-7:
        raise ValueError(f"Cannot create zero-length cylinder: {name}")
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=length,
        location=midpoint,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    assign_material(obj, material)
    return obj


def cone_between(
    name: str,
    start: Vector,
    end: Vector,
    base_radius: float,
    top_radius: float,
    material: bpy.types.Material,
    vertices: int = 64,
) -> bpy.types.Object:
    delta = start - end
    length = delta.length
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=base_radius,
        radius2=top_radius,
        depth=length,
        end_fill_type="NGON",
        location=midpoint,
    )
    obj = bpy.context.object
    obj.name = name
    # Local +Z points from the footprint to the satellite.
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    assign_material(obj, material)
    return obj


def arrow_head(
    name: str,
    base: Vector,
    tip: Vector,
    radius: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    delta = tip - base
    bpy.ops.mesh.primitive_cone_add(
        vertices=24,
        radius1=radius,
        radius2=0.0,
        depth=delta.length,
        location=(base + tip) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    assign_material(obj, material)
    return obj


def add_text(
    name: str,
    body: str,
    location: tuple[float, float, float],
    size: float,
    material: bpy.types.Material,
    camera: bpy.types.Object,
    *,
    align: str = "CENTER",
    extrude: float = 0.004,
) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = extrude
    obj.data.bevel_depth = 0.0015
    obj.data.bevel_resolution = 2
    obj.data.space_line = 0.92
    assign_material(obj, material)
    face_camera(obj, camera)
    if hasattr(obj, "visible_shadow"):
        obj.visible_shadow = False
    return obj


# ---------------------------------------------------------------------------
# Technical scene elements
# ---------------------------------------------------------------------------

def ground_height(panel_x: float, x: float, y: float) -> float:
    sx, sy, sz, zc = 4.65, 2.9, 1.18, -1.12
    dx = (x - panel_x) / sx
    dy = y / sy
    inside = max(0.0, 1.0 - dx * dx - dy * dy)
    return zc + sz * math.sqrt(inside)


def create_earth_cap(
    panel_x: float,
    earth_material: bpy.types.Material,
) -> None:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=96,
        ring_count=48,
        location=(panel_x, 0.15, -1.12),
    )
    earth = bpy.context.object
    earth.name = f"Earth cap {panel_x:+.1f}"
    earth.scale = (4.65, 2.9, 1.18)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(earth, earth_material)
    smooth_object(earth)


def create_satellite(
    panel_x: float,
    materials: dict[str, bpy.types.Material],
) -> Vector:
    z = 7.20
    body = cube(
        "Satellite body",
        (panel_x, 0.0, z),
        (1.05, 0.78, 0.72),
        materials["satellite"],
        bevel=0.10,
    )
    body.rotation_euler[2] = math.radians(2.5)
    cube(
        "Satellite lower bus",
        (panel_x, -0.06, z - 0.43),
        (0.62, 0.48, 0.18),
        materials["satellite_dark"],
        bevel=0.05,
    )
    for side in (-1, 1):
        x = panel_x + side * 1.34
        cylinder_between(
            "Solar boom",
            Vector((panel_x + side * 0.48, 0.0, z)),
            Vector((x - side * 0.66, 0.0, z)),
            0.045,
            materials["satellite_dark"],
        )
        panel = cube(
            "Solar panel",
            (x, 0.0, z),
            (1.35, 0.10, 0.66),
            materials["solar"],
            bevel=0.035,
        )
        panel.rotation_euler[0] = math.radians(4)
        for grid_x in (-0.40, 0.0, 0.40):
            cube(
                "Solar grid vertical",
                (x + grid_x, -0.061, z),
                (0.025, 0.018, 0.61),
                materials["solar_grid"],
            )
        cube(
            "Solar grid horizontal",
            (x, -0.061, z),
            (1.30, 0.018, 0.025),
            materials["solar_grid"],
        )
    # Downlink antenna/feed.
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        radius=0.16,
        location=(panel_x, -0.08, z - 0.55),
    )
    feed = bpy.context.object
    feed.name = "Downlink feed"
    assign_material(feed, materials["satellite_dark"])
    smooth_object(feed)
    return Vector((panel_x, -0.03, z - 0.55))


def create_cell(
    name: str,
    target: Vector,
    ring_material: bpy.types.Material,
) -> None:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.63,
        minor_radius=0.045,
        major_segments=64,
        minor_segments=12,
        location=target + Vector((0.0, 0.0, 0.035)),
    )
    ring = bpy.context.object
    ring.name = name
    assign_material(ring, ring_material)


def create_user(
    name: str,
    location: Vector,
    material: bpy.types.Material,
) -> None:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=0.085,
        depth=0.26,
        location=location + Vector((0.0, 0.0, 0.15)),
    )
    mast = bpy.context.object
    mast.name = f"{name} mast"
    assign_material(mast, material)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        radius=0.16,
        location=location + Vector((0.0, 0.0, 0.34)),
    )
    head = bpy.context.object
    head.name = name
    assign_material(head, material)
    smooth_object(head)


def dashed_interference_arrow(
    name: str,
    source: Vector,
    target: Vector,
    material: bpy.types.Material,
    radius: float,
) -> None:
    count = 34
    points = []
    for index in range(count + 1):
        t = index / count
        point = source.lerp(target, t)
        point.z += 0.46 + 0.70 * 4.0 * t * (1.0 - t)
        points.append(point)
    for index in range(count - 2):
        if index % 3 != 2:
            cylinder_between(
                f"{name} dash {index}",
                points[index],
                points[index + 1],
                radius,
                material,
                vertices=10,
            )
    arrow_head(
        f"{name} head",
        points[-3],
        points[-1],
        radius * 3.4,
        material,
    )


def create_panel(
    panel_x: float,
    selective_pbo: bool,
    materials: dict[str, bpy.types.Material],
) -> dict[str, Vector]:
    create_earth_cap(panel_x, materials["earth"])
    satellite = create_satellite(panel_x, materials)
    x_offsets = (-2.72, -1.36, 0.0, 1.36, 2.72)
    y_offsets = (0.28, -0.20, 0.14, -0.25, 0.30)
    targets = []
    for index, (x_offset, y_offset) in enumerate(zip(x_offsets, y_offsets)):
        x = panel_x + x_offset
        z = ground_height(panel_x, x, y_offset)
        target = Vector((x, y_offset, z + 0.05))
        targets.append(target)
        is_pbo = selective_pbo and index in PBO_BEAM_INDICES
        beam_material = materials["beam_pbo"] if is_pbo else materials["beam_nominal"]
        line_material = materials["pbo"] if is_pbo else materials["nominal"]
        cone_between(
            f"{'PBO' if is_pbo else 'Nominal'} beam {index}",
            satellite,
            target,
            0.52 if is_pbo else 0.72,
            0.07 if is_pbo else 0.11,
            beam_material,
        )
        cylinder_between(
            f"Beam centerline {index}",
            satellite,
            target,
            0.037 if is_pbo else 0.055,
            line_material,
            vertices=14,
        )
        create_cell(
            f"Cell {index}",
            target,
            materials["pbo"] if is_pbo else materials["nominal"],
        )
        if selective_pbo:
            user_material = (
                materials["user_affected"]
                if is_pbo else materials["user_unaffected"]
            )
        else:
            user_material = materials["user_unaffected"]
        create_user(f"User {index}", target, user_material)

    interference_material = materials["interference"]
    radius = 0.028 if selective_pbo else 0.046
    for source_index in sorted(PBO_BEAM_INDICES):
        dashed_interference_arrow(
            f"Interference {source_index} to 2",
            targets[source_index],
            targets[2],
            interference_material,
            radius,
        )
    return {
        "satellite": satellite,
        "affected_user": targets[1] + Vector((0.0, 0.0, 0.34)),
        "unaffected_user": targets[2] + Vector((0.0, 0.0, 0.34)),
        "pbo_beam_mid": satellite.lerp(targets[1], 0.48),
    }


def create_callout(
    name: str,
    text: str,
    location: tuple[float, float, float],
    target: Vector,
    camera: bpy.types.Object,
    materials: dict[str, bpy.types.Material],
    *,
    leader_bias: float = 0.0,
) -> None:
    # Orthographic labels share a single foreground direction: camera local
    # +Z. Using the vector to the camera position would skew depth offsets at
    # the panel edges and misalign the annotation leaders.
    foreground = (camera.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    text_position = Vector(location) + foreground * 0.035
    text_object = add_text(
        name,
        text,
        tuple(text_position),
        TEXT_SIZE["annotation"],
        materials["text"],
        camera,
    )
    bpy.context.view_layer.update()

    # Keep the leaders outside the real text bounds. The former white backing
    # plates are intentionally omitted so the scene remains visible behind all
    # annotations.
    bounds = [Vector(corner) for corner in text_object.bound_box]
    min_x = min(point.x for point in bounds)
    max_x = max(point.x for point in bounds)
    min_y = min(point.y for point in bounds)
    max_y = max(point.y for point in bounds)
    world_units_per_pixel = camera.data.ortho_scale / RENDER_WIDTH
    padding_x = 14.0 * world_units_per_pixel
    padding_y = 10.0 * world_units_per_pixel
    clearance_width = max_x - min_x + 2.0 * padding_x
    clearance_height = max_y - min_y + 2.0 * padding_y
    local_center = Vector(((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, 0.0))
    text_center = text_object.matrix_world @ local_center
    # Pull leaders slightly toward the camera so translucent beam volumes do
    # not wash out the dark publication strokes.
    horizontal = (camera.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    vertical = (camera.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    if leader_bias:
        start = text_center
        start += horizontal * math.copysign(clearance_width * 0.52, leader_bias)
        start -= vertical * clearance_height * 0.12
    else:
        start = text_center - vertical * clearance_height * 0.52
    start += foreground * 0.080
    line_end = target + foreground * 0.160
    cylinder_between(
        f"{name} leader",
        start,
        line_end,
        0.038,
        materials["line"],
        vertices=12,
    )
    delta = (line_end - start).normalized()
    arrow_head(
        f"{name} arrow",
        line_end - delta * 0.34,
        line_end,
        0.130,
        materials["line"],
    )


def create_legend(
    camera: bpy.types.Object,
    materials: dict[str, bpy.types.Material],
) -> None:
    # Pack the enlarged single-column legend into one transparent row below
    # both Earth caps. Explicit marker/text anchors avoid collisions.
    entries = [
        (-10.65, -10.35, "Feixe nominal", "nominal_line"),
        (-6.90, -6.60, "Feixe com PBO", "pbo_line"),
        (-2.75, -2.45, "Usuário afetado", "affected"),
        (1.50, 1.80, "Usuário não afetado", "unaffected"),
        (6.75, 7.19, "Interferência", "interference"),
    ]
    z = -1.50
    y = -4.72
    for marker_x, text_x, label, symbol in entries:
        if symbol in {"nominal_line", "pbo_line"}:
            material = materials[
                "nominal" if symbol == "nominal_line" else "pbo"]
            cylinder_between(
                f"Legend {symbol}",
                Vector((marker_x - 0.28, y, z)),
                Vector((marker_x + 0.28, y, z)),
                0.055,
                material,
                vertices=14,
            )
        elif symbol == "interference":
            material = materials["interference"]
            for offset in (-0.30, 0.02):
                cylinder_between(
                    "Legend interference dash",
                    Vector((marker_x + offset, y, z)),
                    Vector((marker_x + offset + 0.19, y, z)),
                    0.035,
                    material,
                    vertices=12,
                )
            arrow_head(
                "Legend interference arrow",
                Vector((marker_x + 0.17, y, z)),
                Vector((marker_x + 0.34, y, z)),
                0.090,
                material,
            )
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=32,
                ring_count=16,
                radius=0.14,
                location=(marker_x, y, z),
            )
            marker = bpy.context.object
            marker.name = f"Legend {symbol}"
            assign_material(
                marker,
                materials[
                    "user_affected" if symbol == "affected"
                    else "user_unaffected"
                ],
            )
            smooth_object(marker)
        add_text(
            f"Legend text {label}",
            label,
            (text_x, y, z),
            TEXT_SIZE["legend"],
            materials["text"],
            camera,
            align="LEFT",
        )


def configure_scene() -> tuple[bpy.types.Scene, bpy.types.Object, dict]:
    clear_scene()
    scene = bpy.context.scene
    # Blender 5.x exposes Eevee as BLENDER_EEVEE; Blender 4.x used the
    # BLENDER_EEVEE_NEXT identifier. Select the available identifier so the
    # publication script stays reproducible across both releases.
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = RENDER_WIDTH
    scene.render.resolution_y = RENDER_HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 12
    scene.render.film_transparent = True
    scene.render.filepath = str(PNG_PATH)
    scene.render.use_file_extension = True
    if hasattr(scene, "eevee"):
        scene.eevee.taa_samples = RENDER_SAMPLES

    scene.world.color = COLORS["background"][:3]
    world_nodes = scene.world.node_tree
    scene.world.use_nodes = True
    background = world_nodes.nodes.get("Background")
    background.inputs["Color"].default_value = COLORS["background"]
    background.inputs["Strength"].default_value = 0.82

    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0

    materials = {
        "earth": make_material("Earth", COLORS["earth"], roughness=0.82),
        "satellite": make_material("Satellite body", COLORS["satellite"], metallic=0.35),
        "satellite_dark": make_material("Satellite dark", COLORS["satellite_dark"], metallic=0.45),
        "solar": make_material("Solar panel", COLORS["solar"], metallic=0.3, roughness=0.38),
        "solar_grid": make_material("Solar grid", COLORS["solar_grid"], metallic=0.2),
        "nominal": make_material("Nominal line", COLORS["nominal"], emission_strength=0.28),
        "pbo": make_material("PBO line", COLORS["pbo"], emission_strength=0.16),
        "beam_nominal": make_material(
            "Nominal beam volume", COLORS["nominal"], alpha=0.19,
            roughness=0.42, emission_strength=0.18,
        ),
        "beam_pbo": make_material(
            "PBO beam volume", COLORS["pbo"], alpha=0.105,
            roughness=0.48, emission_strength=0.07,
        ),
        "user_affected": make_material("Affected user", COLORS["user_affected"], roughness=0.5),
        "user_unaffected": make_material("Unaffected user", COLORS["user_unaffected"], roughness=0.5),
        "interference": make_material("Interference", COLORS["interference"], emission_strength=0.14),
        "text": make_material("Text", COLORS["text"], roughness=0.5),
        "line": make_material(
            "Callout line", COLORS["line"], roughness=0.48,
            emission_strength=0.10,
        ),
        "divider": make_material("Divider", COLORS["divider"], roughness=0.8),
    }

    bpy.ops.object.camera_add(location=(0.0, -29.5, 14.2))
    camera = bpy.context.object
    camera.name = "Orthographic publication camera"
    camera.data.type = "ORTHO"
    # Blender's orthographic scale describes the horizontal field for this
    # 16:9 render. A 22.8-unit field keeps titles, callouts, and the full legend
    # inside the frame while preserving publication-scale text.
    camera.data.ortho_scale = 22.80
    camera.data.lens = 65
    look_at(camera, Vector((0.0, 0.0, 3.05)))
    scene.camera = camera

    # Broad, soft illumination avoids cinematic shadows and preserves labels.
    bpy.ops.object.light_add(type="AREA", location=(0.0, -8.0, 16.5))
    key = bpy.context.object
    key.name = "Soft key light"
    key.data.energy = 1200
    key.data.shape = "DISK"
    key.data.size = 10.0
    look_at(key, Vector((0.0, 0.0, 2.5)))
    for x in (-10.0, 10.0):
        bpy.ops.object.light_add(type="AREA", location=(x, -3.0, 8.0))
        fill = bpy.context.object
        fill.name = "Panel fill light"
        fill.data.energy = 520
        fill.data.size = 7.0
        look_at(fill, Vector((x * 0.55, 0.0, 2.0)))
    return scene, camera, materials


def build_scene() -> None:
    scene, camera, materials = configure_scene()
    estimated_text_points = validate_publication_text_sizes(camera)
    left = create_panel(-5.72, False, materials)
    right = create_panel(5.72, True, materials)

    add_text(
        "Panel title a",
        "(a) Sem PBO",
        (-5.72, 0.55, 8.90),
        TEXT_SIZE["panel_title"],
        materials["text"],
        camera,
    )
    add_text(
        "Panel title b",
        "(b) PBO seletivo",
        (5.72, 0.55, 8.90),
        TEXT_SIZE["panel_title"],
        materials["text"],
        camera,
    )

    cylinder_between(
        "Panel divider",
        Vector((0.0, 2.20, -0.92)),
        Vector((0.0, 2.20, 8.82)),
        0.024,
        materials["divider"],
        vertices=12,
    )

    create_callout(
        "Reduced desired signal",
        "Menor sinal\ndesejado",
        (2.60, -1.85, 1.30),
        right["affected_user"],
        camera,
        materials,
        leader_bias=1.0,
    )
    create_callout(
        "Reduced interference",
        "Menor interferência\nrecebida",
        (8.35, -1.70, 2.05),
        right["unaffected_user"],
        camera,
        materials,
        leader_bias=-1.0,
    )
    create_callout(
        "PBO label",
        f"PBO = {PBO_LABEL_DB} dB",
        (3.02, -0.95, 4.72),
        right["pbo_beam_mid"],
        camera,
        materials,
        leader_bias=1.0,
    )
    create_legend(camera, materials)

    # Publication metadata travels with the .blend file.
    scene["figure_purpose"] = "Selective DC-MSS-IMT power back-off mechanism"
    scene["target_layout"] = "IEEE single-column; legend enlarged"
    scene["render_resolution"] = f"{RENDER_WIDTH}x{RENDER_HEIGHT}"
    scene["minimum_text_policy"] = "No text below 8 pt at two-column width"
    scene["estimated_text_points"] = ", ".join(
        f"{role}={points:.1f} pt"
        for role, points in estimated_text_points.items()
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"Estimated text sizes at {IEEE_DOUBLE_COLUMN_WIDTH_IN:.2f} in: "
          f"{scene['estimated_text_points']}")
    print(f"Rendered: {PNG_PATH}")
    print(f"Saved:    {BLEND_PATH}")


if __name__ == "__main__":
    build_scene()

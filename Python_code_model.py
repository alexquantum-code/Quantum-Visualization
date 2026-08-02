import bpy
import math
from mathutils import Vector


# -------------------------
# Reset scene
# -------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene

# Render engine selection
engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
if "BLENDER_EEVEE_NEXT" in engines:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
elif "BLENDER_EEVEE" in engines:
    scene.render.engine = "BLENDER_EEVEE"
else:
    scene.render.engine = "BLENDER_WORKBENCH"

scene.render.resolution_x = 1260
scene.render.resolution_y = 630
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.filepath = "//paper_optomechanical_3d_corrected.png"
scene.world.color = (0.96, 0.96, 0.96)

# Safe color-management choices
try:
    scene.view_settings.view_transform = "Standard"
except Exception:
    pass
try:
    scene.view_settings.look = "None"
except Exception:
    pass
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# -------------------------
# Materials
# -------------------------
def make_mat(
    name,
    color,
    metallic=0.0,
    roughness=0.40,
    emission_strength=0.0
):
    m = bpy.data.materials.new(name)
    m.use_nodes = True

    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    # Blender 5.x emission inputs, with fallback for older versions.
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    elif "Emission" in bsdf.inputs:
        bsdf.inputs["Emission"].default_value = (*color, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength

    return m

# Slightly luminous cavity materials
RED = make_mat(
    "LSP red",
    (1.0, 0.02, 0.01),
    metallic=0.0,
    roughness=0.30,
    emission_strength=0.35
)

ORANGE = make_mat(
    "Cavity orange",
    (0.95, 0.50, 0.15),
    metallic=0.0,
    roughness=0.35,
    emission_strength=0.20
)

BLUE = make_mat("Mirror blue", (0.72, 0.80, 0.92), 0.0, 0.38)
BLUE_EDGE = make_mat("Mirror edge", (0.48, 0.60, 0.78), 0.0, 0.33)
GREY = make_mat("Spring grey", (0.55, 0.55, 0.55), 0.50, 0.25)
DARK = make_mat("Dark", (0.06, 0.06, 0.06), 0.0, 0.45)
WHITE = make_mat("White", (1.0, 1.0, 1.0), 0.0, 1.0)

# -------------------------
# Helpers
# -------------------------
def smooth(obj):
    if hasattr(obj.data, "polygons"):
        for p in obj.data.polygons:
            p.use_smooth = True

def add_bevel(obj, width=0.02, segments=2):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments

def add_sphere(name, loc, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=40, ring_count=20, radius=radius, location=loc
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    smooth(obj)
    return obj

def add_cylinder_between(name, p0, p1, radius, material, vertices=48):
    p0 = Vector(p0)
    p1 = Vector(p1)
    d = p1 - p0
    mid = (p0 + p1) * 0.5
    length = d.length

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=length, location=mid
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    smooth(obj)
    return obj

def add_arrow(name, x0, x1, z, waves=3.0, amplitude=0.18):
    # Sinusoidal input shaft. The envelope tapers the wave to zero at both
    # ends, giving a clean connection to the arrowhead and a smooth start.
    shaft_end = x1 - 0.48
    samples = 180
    points = []

    for i in range(samples):
        t = i / (samples - 1)
        x = x0 + (shaft_end - x0) * t
        envelope = math.sin(math.pi * t) ** 0.65
        z_wave = z + amplitude * envelope * math.sin(2.0 * math.pi * waves * t)
        points.append((x, 0, z_wave))

    add_curve(name + "_sinusoidal_shaft", points, 0.075, RED)

    # Arrowhead remains centered and points toward the left mirror.
    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=0.25, radius2=0.0, depth=0.48,
        location=(x1 - 0.24, 0, z),
        rotation=(0, math.radians(90), 0)
    )
    cone = bpy.context.object
    cone.name = name + "_head"
    cone.data.materials.append(RED)
    smooth(cone)

def add_text(name, body, loc, size=0.40, align="CENTER"):
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(90), 0, 0))
    txt = bpy.context.object
    txt.name = name
    txt.data.body = body
    txt.data.align_x = align
    txt.data.align_y = "CENTER"
    txt.data.size = size
    txt.data.extrude = 0.007
    txt.data.bevel_depth = 0.003
    txt.data.materials.append(DARK)
    return txt

def add_curve(name, points, bevel_depth, material):
    curve = bpy.data.curves.new(name + "_curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 6
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 4

    spl = curve.splines.new("POLY")
    spl.points.add(len(points) - 1)
    for p, co in zip(spl.points, points):
        p.co = (*co, 1.0)

    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj

def create_hourglass(name, x0, x1, zc, r_end, r_mid, depth_scale, material,
                     segments_x=70, segments_ring=64):
    verts = []
    faces = []

    for i in range(segments_x + 1):
        t = i / segments_x
        x = x0 + (x1 - x0) * t
        edge_factor = abs(2.0 * t - 1.0) ** 1.7
        rz = r_mid + (r_end - r_mid) * edge_factor
        ry = rz * depth_scale

        for j in range(segments_ring):
            a = 2.0 * math.pi * j / segments_ring
            y = ry * math.cos(a)
            z = zc + rz * math.sin(a)
            verts.append((x, y, z))

    for i in range(segments_x):
        row = i * segments_ring
        nxt = (i + 1) * segments_ring
        for j in range(segments_ring):
            j2 = (j + 1) % segments_ring
            faces.append((row + j, row + j2, nxt + j2, nxt + j))

    left_center = len(verts)
    verts.append((x0, 0, zc))
    right_center = len(verts)
    verts.append((x1, 0, zc))

    for j in range(segments_ring):
        j2 = (j + 1) % segments_ring
        faces.append((left_center, j2, j))
        r0 = segments_x * segments_ring
        faces.append((right_center, r0 + j, r0 + j2))

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    smooth(obj)
    return obj

def add_small_mirror(name, x, z, radius_z=0.90, radius_y=0.30, thickness_x=0.16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, location=(x, 0, z))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (thickness_x, radius_y, radius_z)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(BLUE)
    smooth(obj)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.50,
        minor_radius=0.024,
        major_segments=64,
        minor_segments=12,
        location=(x - thickness_x * 0.85, 0, z),
        rotation=(0, math.radians(90), 0)
    )
    rim = bpy.context.object
    rim.name = name + "_rim"
    rim.scale = (1.0, radius_y / 0.50, radius_z / 0.50)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rim.data.materials.append(BLUE_EDGE)
    smooth(rim)
    return obj

def add_long_shared_mirror(name, x, z_center, radius_z=3.58, radius_y=0.5, thickness_x=0.22):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, location=(x, 0, z_center))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (thickness_x, radius_y, radius_z)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(BLUE)
    smooth(obj)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.70,
        minor_radius=0.026,
        major_segments=72,
        minor_segments=14,
        location=(x - thickness_x * 0.82, 0, z_center),
        rotation=(0, math.radians(90), 0)
    )
    rim = bpy.context.object
    rim.name = name + "_rim"
    rim.scale = (1.0, radius_y / 0.50, radius_z / 0.50)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rim.data.materials.append(BLUE_EDGE)
    smooth(rim)
    return obj

# -------------------------
# Main layout
# -------------------------
x_left = -4.45
x_shared = 2.05
z_top = 1.78
z_bottom = -1.38
z_mid = (z_top + z_bottom) / 2.0

# Cavities extend from the two small left mirrors to the one shared movable mirror
create_hourglass(
    "Strong cavity with LSP",
    x_left, x_shared, z_top,
    r_end=0.82, r_mid=0.30,
    depth_scale=0.48, material=RED
)
create_hourglass(
    "Weak cavity",
    x_left, x_shared, z_bottom,
    r_end=0.78, r_mid=0.28,
    depth_scale=0.46, material=ORANGE
)

# Two small left mirrors only
add_small_mirror("upper left small mirror", x_left - 0.10, z_top,
                 radius_z=0.88, radius_y=0.30, thickness_x=0.16)
add_small_mirror("lower left small mirror", x_left - 0.10, z_bottom,
                 radius_z=0.86, radius_y=0.30, thickness_x=0.16)

# One shared long movable mirror on the right
shared_mirror_x = x_shared + 0.12
add_long_shared_mirror("shared movable mirror", shared_mirror_x, z_mid,
                       radius_z=2.25, radius_y=0.34, thickness_x=0.22)

# Input arrows
add_arrow("upper input", -6.65, -4.80, z_top)
add_arrow("lower input", -6.65, -4.80, z_bottom)

# LSP nanoparticle cluster in upper cavity
cluster_center_x = -1.55
cluster = [
    (-0.37, -0.05,  0.42),
    ( 0.00,  0.02,  0.53),
    ( 0.38, -0.04,  0.41),
    (-0.49,  0.00,  0.08),
    (-0.10, -0.10,  0.11),
    ( 0.34,  0.03,  0.06),
    (-0.38, -0.02, -0.33),
    ( 0.03,  0.05, -0.42),
    ( 0.42, -0.04, -0.28),
]
for i, (dx, dy, dz) in enumerate(cluster):
    add_sphere(
        f"Ag nanoparticle {i}",
        (cluster_center_x + dx, -0.31 + dy, z_top + dz),
        0.125, RED
    )

# -------------------------
# Spring and fixed mirror
# -------------------------
spring_z = z_mid
pad_x = shared_mirror_x + 0.35
spring_x0 = pad_x + 0.22
spring_x1 = 4.65
fixed_mirror_x = 5.70

# Pad that links spring to the shared movable mirror
bpy.ops.mesh.primitive_cylinder_add(
    vertices=64, radius=0.34, depth=0.22,
    location=(pad_x, 0, spring_z),
    rotation=(0, math.radians(90), 0)
)
pad = bpy.context.object
pad.name = "spring coupling pad"
pad.data.materials.append(GREY)
smooth(pad)

# Straight left connector: shared mirror pad -> spring centerline
pad_right_face = pad_x + 0.11
add_cylinder_between(
    "spring left connector",
    (pad_right_face, 0, spring_z),
    (spring_x0, 0, spring_z),
    0.075, GREY
)

# Helical spring with tapered ends.
# The taper forces both endpoints onto the centerline, so the spring is
# physically continuous with the left and right connectors.
turns = 6.0
samples = 440
spring_points = []
for i in range(samples):
    t = i / (samples - 1)
    x = spring_x0 + (spring_x1 - spring_x0) * t
    ang = 2 * math.pi * turns * t

    # Smooth envelope: zero radius at both ends, full radius in the middle.
    envelope = math.sin(math.pi * t) ** 0.65
    y = (0.16 * envelope) * math.cos(ang)
    z = spring_z + (0.36 * envelope) * math.sin(ang)
    spring_points.append((x, y, z))

add_curve("mechanical spring", spring_points, 0.075, GREY)

# Straight right connector: spring centerline -> front face of fixed support
fixed_left_face = fixed_mirror_x - 0.60
add_cylinder_between(
    "spring right connector",
    (spring_x1, 0, spring_z),
    (fixed_left_face, 0, spring_z),
    0.075, GREY
)

# Far-right fixed long mirror / support
bpy.ops.mesh.primitive_cube_add(location=(fixed_mirror_x, 0, 0.28))
wall = bpy.context.object
wall.name = "fixed long mirror"
wall.scale = (0.60, 0.42, 2.72)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
wall.data.materials.append(BLUE)
add_bevel(wall, 0.02, 2)

# -------------------------
# Dotted L guide and slash
# -------------------------
for i in range(15):
    add_sphere(f"L dot {i}", (2.80 + 0.12 * i, -0.36, 2.67), 0.022, DARK)

add_curve("L vertical", [(4.08, -0.36, 2.66), (4.08, -0.36, 2.98)], 0.018, DARK)
add_curve("L cap", [(4.08, -0.36, 2.66), (4.26, -0.36, 2.66)], 0.018, DARK)

add_curve("small slash", [(-4.78, -0.36, 0.73), (-4.61, -0.36, 0.92)], 0.025, DARK)

# -------------------------
# Labels
# -------------------------
label_y = -0.48
add_text("omega LSP", "ωₗₛₚ", (-3.45, label_y, 1.83), 0.39)
add_text("omega zero", "ω₀", (-3.70, label_y, -1.30), 0.45)
add_text("a_s", "âₛ", (1.10, label_y, 2.03), 0.42)
add_text("a_w", "â𝓌", (1.12, label_y, -1.18), 0.42)
add_text("b", "b̂", (2.88, label_y, 1.24), 0.38)
add_text("omega m", "ωₘ", (4.05, label_y, 1.18), 0.38)
add_text("L label", "L", (3.95, label_y, 2.86), 0.34)
# -------------------------
# Camera
# -------------------------
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam

cam.location = (0.0, -15.5, 0.55)
target = Vector((0.20, 0.0, 0.25))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
cam.data.type = "ORTHO"
cam.data.ortho_scale = 14 # slightly wider to fit the corrected layout

# -------------------------
# Lighting
# -------------------------
key_data = bpy.data.lights.new("Key light", "AREA")
key_data.energy = 900
key_data.shape = "RECTANGLE"
key_data.size = 8.0
key = bpy.data.objects.new("Key light", key_data)
bpy.context.collection.objects.link(key)
key.location = (-3.5, -6.0, 7.0)
key.rotation_euler = (math.radians(28), 0, math.radians(-18))

fill_data = bpy.data.lights.new("Fill light", "AREA")
fill_data.energy = 420
fill_data.size = 7.0
fill = bpy.data.objects.new("Fill light", fill_data)
bpy.context.collection.objects.link(fill)
fill.location = (5.0, -4.0, 3.5)
fill.rotation_euler = (math.radians(55), 0, math.radians(155))

front_data = bpy.data.lights.new("Front light", "AREA")
front_data.energy = 240
front_data.size = 10.0
front = bpy.data.objects.new("Front light", front_data)
bpy.context.collection.objects.link(front)
front.location = (0.0, -8.0, 0.0)
front.rotation_euler = (math.radians(90), 0, 0)

# White background plane behind the model
bpy.ops.mesh.primitive_plane_add(
    size=30,
    location=(0, 1.7, 0.2),
    rotation=(math.radians(90), 0, 0)
)
back = bpy.context.object
back.name = "white background"
back.data.materials.append(WHITE)

# -------------------------
# Subtle compositor glow
# -------------------------
scene.use_nodes = True
nodes = scene.node_tree.nodes
links = scene.node_tree.links

nodes.clear()

render_layers = nodes.new("CompositorNodeRLayers")
glare = nodes.new("CompositorNodeGlare")
composite = nodes.new("CompositorNodeComposite")

glare.glare_type = "FOG_GLOW"
glare.quality = "HIGH"
glare.threshold = 0.8
glare.size = 6

# -1.0 means almost no glow; values closer to 0 make it stronger.
glare.mix = -0.95

links.new(render_layers.outputs["Image"], glare.inputs["Image"])
links.new(glare.outputs["Image"], composite.inputs["Image"])

# -------------------------
# Render
# -------------------------
bpy.ops.render.render(write_still=True)


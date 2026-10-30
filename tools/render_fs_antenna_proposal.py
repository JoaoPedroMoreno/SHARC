r"""Blender-only FS antenna proposal; does not modify the LATINCOM figures.

Run: G:\Blender\blender.exe -b --python tools/render_fs_antenna_proposal.py
Coordinates: X east, Y north, Z up. The reflector axis is horizontal north.
All dimensions are illustrative, not campaign antenna dimensions.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector

OUT=Path(__file__).resolve().parents[1]/'figuras/latincom/antenna_proposal_v2'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def material(name,color,metallic=0,roughness=.5):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Metallic'].default_value=metallic
    shader.inputs['Roughness'].default_value=roughness
    return mat


porcelain=material('Reflector light grey',(.66,.72,.77),.15,.48)
back=material('Rear shell',(.40,.49,.56),.35,.44)
steel=material('Galvanized mounting hardware',(.30,.39,.46),.6,.37)
rim_material=material('Rolled rim',(.40,.49,.57),.55,.34)
horn_material=material('Feed horn',(.29,.36,.41),.55,.34)
dark=material('Horn aperture',(.035,.052,.066),0,.8)
axis_material=material('Horizontal north axis',(.18,.27,.33),0,.6)


def finish(obj,name,mat,smooth=True,bevel=0):
    obj.name=name
    obj.data.materials.append(mat)
    if smooth and hasattr(obj.data,'polygons'):
        for polygon in obj.data.polygons:
            polygon.use_smooth=True
    if bevel:
        mod=obj.modifiers.new('Small manufactured edge bevel','BEVEL')
        mod.width=bevel
        mod.segments=3
    return obj


def cylinder(name,a,b,radius,mat,vertices=32):
    a,b=Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,
                                       depth=(b-a).length,location=(a+b)/2)
    obj=bpy.context.object
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return finish(obj,name,mat,bevel=.0015)


def cube(name,location,size,mat,bevel=.004):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object
    obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(obj,name,mat,smooth=False,bevel=bevel)


R=.55
F=.48
H=1.46
VERTEX=.05
DEPTH=R*R/(4*F)

# A thickened circular paraboloid, not a flat disc with a shaded outline.
segments=128
rings=40
vertices=[(0,VERTEX,H)]
for j in range(1,rings+1):
    r=R*j/rings
    for i in range(segments):
        theta=2*math.pi*i/segments
        vertices.append((r*math.cos(theta),VERTEX+r*r/(4*F),H+r*math.sin(theta)))
faces=[]
for i in range(segments):
    faces.append((0,1+(i+1)%segments,1+i))
for j in range(rings-1):
    first=1+j*segments
    second=first+segments
    for i in range(segments):
        k=(i+1)%segments
        faces.append((first+i,first+k,second+k,second+i))
mesh=bpy.data.meshes.new('True circular paraboloid')
mesh.from_pydata(vertices,[],faces); mesh.update()
reflector=bpy.data.objects.new('Open parabolic reflector',mesh)
bpy.context.collection.objects.link(reflector)
finish(reflector,'Open parabolic reflector',porcelain)
reflector.data.materials.append(back)
solid=reflector.modifiers.new('Reflector sheet thickness','SOLIDIFY')
solid.thickness=.014
solid.material_offset=1
solid.material_offset_rim=1
bevel=reflector.modifiers.new('Rim edge finish','BEVEL')
bevel.width=.003; bevel.segments=3

bpy.ops.mesh.primitive_torus_add(major_radius=R,minor_radius=.011,
    major_segments=128,minor_segments=16,location=(0,VERTEX+DEPTH,H),
    rotation=(math.pi/2,0,0))
finish(bpy.context.object,'Rolled circular rim',rim_material)

# Pole, clamps, pivot and short rear bracket are separately readable parts.
cube('Base plate',(0,-.22,.02),(.32,.28,.04),steel)
cylinder('Vertical mounting mast',(0,-.22,.04),(0,-.22,1.64),.043,steel,48)
for x in (-.115,.115):
    for y in (-.31,-.13):
        cylinder('Base bolt',(x,y,.038),(x,y,.054),.012,rim_material,6)
for z in (H-.16,H+.05):
    cylinder('Mast clamp',(0,-.22,z-.023),(0,-.22,z+.023),.055,rim_material,48)
    cube('Rear mounting bracket',(0,-.10,z),(.12,.20,.045),steel)
    for x in (-.075,.075):
        cylinder('Clamp bolt',(x,-.25,z),(x,-.18,z),.012,rim_material,6)
cylinder('Elevation pivot',(-.10,-.025,H),(.10,-.025,H),.045,steel,48)
cylinder('Reflector rear hub',(0,-.02,H),(0,VERTEX-.01,H),.10,back,64)

# Compact prime-focus feed horn with its open mouth aimed toward the reflector.
focus=VERTEX+F
horn_back=focus+.08
horn_front=focus-.04
count=48
horn_vertices=[]
for y,radius in ((horn_back,.025),(horn_front,.057)):
    horn_vertices.extend([(radius*math.cos(2*math.pi*i/count),y,
                           H+radius*math.sin(2*math.pi*i/count)) for i in range(count)])
horn_faces=[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
horn_mesh=bpy.data.meshes.new('Hollow tapered horn')
horn_mesh.from_pydata(horn_vertices,[],horn_faces); horn_mesh.update()
horn=bpy.data.objects.new('Visible feed horn',horn_mesh)
bpy.context.collection.objects.link(horn)
finish(horn,'Visible feed horn',horn_material)
thickness=horn.modifiers.new('Horn wall','SOLIDIFY'); thickness.thickness=.004
cylinder('Dark feed aperture',(0,horn_front+.014,H),(0,horn_front+.017,H),.048,dark,48)
for angle in (30,150,270):
    theta=math.radians(angle)
    anchor=(R*.94*math.cos(theta),VERTEX+DEPTH-.01,H+R*.94*math.sin(theta))
    cylinder('Feed support strut',anchor,(0,horn_back,H),.008,steel,16)
cylinder('Feed mounting collar',(0,horn_back-.014,H),(0,horn_back+.014,H),.032,steel)

# The boresight is an exact horizontal vector: no elevation tilt is applied.
for i in range(5):
    a=horn_back+.06+i*.055
    cylinder('Boresight dash',(0,a,H),(0,a+.028,H),.0035,axis_material,12)
tip=horn_back+.36
bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.016,radius2=0,depth=.065,
    location=(0,tip,H),rotation=(-math.pi/2,0,0))
finish(bpy.context.object,'North arrowhead',axis_material)


def area(name,location,power,size):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power; data.shape='DISK'; data.size=size
    obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj)
    obj.location=location
    obj.rotation_euler=(Vector((0,.1,1.2))-obj.location).to_track_quat('-Z','Y').to_euler()


area('Large soft key',(-3,4,6),450,4)
area('Soft fill',(4,-2,4),300,3)
area('Rear edge',(-2,-3,4),350,3)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.resolution_x=1400
scene.render.resolution_y=1700
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=True
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
scene.view_settings.view_transform='Standard'
scene.view_settings.look='None'
scene.view_settings.exposure=0

bpy.ops.object.camera_add()
camera=bpy.context.object
camera.data.type='ORTHO'; camera.data.ortho_scale=2.50
camera.data.lens=50
scene.camera=camera
target=Vector((0,.15,1.03))
label_data=bpy.data.curves.new('North label','FONT')
label_data.body='N'; label_data.size=.065
label_data.align_x='CENTER'; label_data.align_y='CENTER'
label=bpy.data.objects.new('North label',label_data)
bpy.context.collection.objects.link(label)
label.data.materials.append(axis_material)
label.location=(0,tip+.10,H+.045)

assert abs(horn_front-focus)<.1
assert Vector(reflector.rotation_euler).length<1e-10
for name,position in [('north_rear_three_quarter',(6,-2.8,3.7)),
                      ('front_inspection',(4.8,6,3.5))]:
    camera.location=position
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    label.rotation_euler=camera.rotation_euler
    scene.render.filepath=str(OUT/f'fs_antenna_{name}.png')
    bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'fs_antenna_proposal.blend'))
print(f'ANTENNA_PROPOSAL_OUTPUT={OUT}',flush=True)

import bpy, os, sys, math
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
GEN = os.path.join(ROOT, 'generated')
EXPORT = os.path.join(ROOT, 'export')
BLEND_DIR = os.path.join(ROOT, 'blender')
# Landmarks de la cara calibrados a mano (versionados; render_face_grid.py solo escribe
# una version automatica si el archivo no existe).
LANDMARKS = os.path.join(BLEND_DIR, 'landmarks.json')
RENDERS = os.path.join(GEN, 'renders')
FPS = 24

def ensure_dirs():
    for d in (GEN, EXPORT, RENDERS):
        os.makedirs(d, exist_ok=True)

def args():
    """Argumentos después de '--'."""
    if '--' in sys.argv:
        return sys.argv[sys.argv.index('--') + 1:]
    return []

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.unit_settings.system = 'METRIC'

def set_engine():
    items = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    for cand in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'):
        if cand in items:
            bpy.context.scene.render.engine = cand
            return cand
    raise RuntimeError('sin motor de render')

def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def add_camera(location, target, lens=35, name='Camera'):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    look_at(ob, target)
    bpy.context.scene.camera = ob
    return ob

def add_light(name, type='POINT', location=(0, 0, 2), energy=100, color=(1, 1, 1), size=0.5):
    li = bpy.data.lights.new(name, type)
    li.energy = energy
    li.color = color
    if type == 'AREA': li.size = size
    if type == 'POINT': li.shadow_soft_size = size
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = location
    return ob

def mat(name, color=(0.8, 0.8, 0.8, 1), roughness=0.6, metallic=0.0,
        emission=None, emission_strength=0.0, image_path=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if image_path:
        img = bpy.data.images.load(image_path, check_existing=True)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if emission is not None:
            nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])
    elif emission is not None:
        bsdf.inputs['Emission Color'].default_value = emission
    if emission is not None or image_path:
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    return m

def box(name, size, location, material=None, collection=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if material: ob.data.materials.append(material)
    if collection:
        for c in ob.users_collection: c.objects.unlink(ob)
        collection.objects.link(ob)
    return ob

def cylinder(name, radius, depth, location, rotation=(0, 0, 0), material=None, verts=24, collection=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=location, rotation=rotation)
    ob = bpy.context.active_object
    ob.name = name
    if material: ob.data.materials.append(material)
    if collection:
        for c in ob.users_collection: c.objects.unlink(ob)
        collection.objects.link(ob)
    return ob

def plane(name, size_xy, location, rotation=(0, 0, 0), material=None, collection=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=location, rotation=rotation)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size_xy[0], size_xy[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    if material: ob.data.materials.append(material)
    if collection:
        for c in ob.users_collection: c.objects.unlink(ob)
        collection.objects.link(ob)
    return ob

def tri_count(obj):
    if obj.type != 'MESH': return 0
    return sum(max(len(p.vertices) - 2, 0) for p in obj.data.polygons)

def scene_tri_count():
    return sum(tri_count(o) for o in bpy.context.scene.objects)

def render(path, res=(1280, 720), samples=32):
    sc = bpy.context.scene
    set_engine()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    if hasattr(sc, 'eevee'):
        sc.eevee.taa_render_samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('RENDER', path)

def export_glb(path, draco=True, animations=True, **extra):
    """Exporta la escena a GLB. `extra` son opciones adicionales de bpy.ops.export_scene.gltf
    (pisan las de abajo). Las opciones que no existan en el RNA de este Blender se descartan
    y se imprimen (EXPORT_DROPPED) para que nunca pasen desapercibidas."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kwargs = dict(
        filepath=path, export_format='GLB', export_yup=True, export_apply=True,
        export_animations=animations, export_animation_mode='NLA_TRACKS',
        export_nla_strips=True, export_def_bones=True, export_skins=True,
        export_morph=False, export_image_format='AUTO', export_image_quality=85,
        export_optimize_animation_size=True,
        export_draco_mesh_compression_enable=draco, export_draco_mesh_compression_level=6,
    )
    kwargs.update(extra)
    valid = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    dropped = sorted(k for k in kwargs if k not in valid)
    if dropped:
        print('EXPORT_DROPPED kwargs sin soporte en este Blender:', dropped)
    kwargs = {k: v for k, v in kwargs.items() if k in valid}
    bpy.ops.export_scene.gltf(**kwargs)
    print('EXPORT', path, os.path.getsize(path))

def save(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print('SAVED', path)

def setup_viewport(shading='MATERIAL'):
    """Deja todos los visores 3D del archivo mirando por la camara de la escena y en Material Preview,
    para que el .blend abra listo en la interfaz (los scripts corren sin ventana y la vista guardada
    quedaba en cualquier sitio, a menudo dentro del escritorio)."""
    n = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                space.shading.type = shading
                space.clip_end = 100.0
                if space.region_3d is not None:
                    space.region_3d.view_perspective = 'CAMERA'
                n += 1
    print('VIEWPORT', n, 'visores 3D en camara /', shading)
    return n


def fail(msg):
    print('CHECK FAILED:', msg)
    sys.exit(1)

def fcurves_of(act):
    """F-curves de una accion, con o sin 'slots' (Blender >= 4.4)."""
    fcs = list(getattr(act, 'fcurves', []) or [])
    if fcs:
        return fcs
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                fcs += list(cb.fcurves)
    return fcs


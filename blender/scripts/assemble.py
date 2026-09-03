# blender/scripts/assemble.py
# Ensamblaje final: abre scene.blend, appendea el personaje animado (character_anim.blend,
# Armature + Body + partes de la cara emparentadas a huesos), lo sienta sobre 'seat_anchor',
# importa la mini moto (generated/moto/dr150.glb) escalada a MOTO_LENGTH de largo sobre
# 'moto_anchor', pone el HDR nocturno como mundo, y renderiza el render de aprobacion
# generated/renders/assembled_v1.png con la camara de aprobacion de scene.blend.
# Guarda SOLO blender/avatar.blend (nunca scene.blend / character*.blend).
# Uso: tools/run_blender.sh - blender/scripts/assemble.py [-- <nombre_render>]
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common, poses
from mathutils import Vector

MOTO_LENGTH = 0.25          # largo de la moto de juguete (m)
MOTO_YAW_DEG = -30.0        # giro en Z para que se lea desde la camara de aprobacion
MOTO_TEX = 1024             # texturas 1k para todo menos el personaje
common.ensure_dirs()

bpy.ops.wm.open_mainfile(filepath=os.path.join(common.BLEND_DIR, 'scene.blend'))
sc = bpy.context.scene

# ------------------------------------------------------------------ personaje animado
# Se traen TODOS los objetos (Armature, Body y las 8 partes de la cara emparentadas a huesos);
# el emparentamiento se conserva porque se cargan juntos.
with bpy.data.libraries.load(os.path.join(common.BLEND_DIR, 'character_anim.blend')) as (src, dst):
    dst.objects = [n for n in src.objects]
char_col = bpy.data.collections.new('Character'); sc.collection.children.link(char_col)
char_objs = [o for o in dst.objects if o is not None and o.type in ('ARMATURE', 'MESH')]
for o in char_objs:
    char_col.objects.link(o)
arm = bpy.data.objects['Armature']
bodies = [o for o in char_objs if o.type == 'MESH']
print('CHAR objetos', sorted(o.name for o in char_objs))
poses.apply(arm, poses.SIT)          # sin frame: no crea keyframes
bpy.context.view_layer.update()


def seat_on_anchor(arm, anchor_name='seat_anchor'):
    """Copiado de sit_test.py (Task 7, verificado): el punto medio de las cabezas de
    thighL/thighR (la cadera) va a seat_anchor + SEAT_LIFT. Mover 'spine' al anchor
    (como decia el brief) deja el cuerpo demasiado bajo, metido en el asiento."""
    anchor = bpy.data.objects[anchor_name]
    bpy.context.view_layer.update()
    hips = (arm.matrix_world @ arm.pose.bones['thighL'].head +
            arm.matrix_world @ arm.pose.bones['thighR'].head) / 2
    target = Vector((anchor.location.x, anchor.location.y, anchor.location.z + poses.SEAT_LIFT))
    arm.location += target - hips
    bpy.context.view_layer.update()
    return arm.location.copy()


def world_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for b in objs:
        ev = b.evaluated_get(dg); me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    return pts


def inside(pts, xr, yr, zr):
    return sum(1 for p in pts if xr[0] <= p.x <= xr[1] and yr[0] <= p.y <= yr[1] and zr[0] <= p.z <= zr[1])


def character_checks(tag):
    """Mismos chequeos numericos de sit_test.py: 0 vertices del personaje dentro del
    escritorio, base/tapa del laptop y respaldo. Dentro del asiento solo cae tela
    (ruedo del hoodie / pantalon), no el cuerpo."""
    pts = world_verts(bodies)
    P = lambda n: [round(v, 3) for v in (arm.matrix_world @ arm.pose.bones[n].head)]
    print(f'POSE[{tag}] hip', P('thighL'), P('thighR'), 'knee', P('shinL'), 'ankle', P('footL'),
          'wrist', P('handL'), P('handR'), 'head', P('spine006'))
    desk = inside(pts, (-1.0, 1.0), (0.75, 1.55), (0.7225, 0.7575))      # tablero del escritorio
    lap = inside(pts, (-0.16, 0.16), (0.87, 1.09), (0.758, 0.770))       # base del laptop
    lid = inside(pts, (-0.16, 0.16), (1.05, 1.11), (0.77, 0.99))         # tapa/pantalla del laptop
    back = inside(pts, (-0.25, 0.25), (0.28, 0.36), (0.48, 1.08))        # respaldo de la silla
    seat_box = inside(pts, (-0.25, 0.25), (0.30, 0.80), (0.39, 0.47))    # volumen del asiento
    minz = min(p.z for p in pts)
    hip_z = (arm.matrix_world @ arm.pose.bones['thighL'].head).z
    print(f'CHECK[{tag}] verts_en_escritorio', desk, 'en_base_laptop', lap, 'en_tapa_laptop', lid,
          'en_respaldo', back, '(objetivo 0)')
    print(f'CHECK[{tag}] pies_min_z', round(minz, 4), 'cadera_sobre_asiento', round(hip_z - 0.470, 4),
          'verts_dentro_del_asiento', seat_box, '(tela: ruedo del hoodie / pantalon)')
    return desk + lap + lid + back


print('SEAT armature.location', [round(v, 4) for v in seat_on_anchor(arm)])
character_checks('SIT')

# ------------------------------------------------------------------ moto mini
moto_path = os.path.join(common.GEN, 'moto', 'dr150.glb')
if os.path.exists(moto_path):
    before = set(bpy.data.objects); before_img = set(bpy.data.images)
    bpy.ops.import_scene.gltf(filepath=moto_path)
    new = [o for o in bpy.data.objects if o not in before]
    moto_col = bpy.data.collections.new('Moto'); sc.collection.children.link(moto_col)
    root = bpy.data.objects.new('moto_mini', None); moto_col.objects.link(root)
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        moto_col.objects.link(o)
        if o.parent is None: o.parent = root
    bpy.context.view_layer.update()
    meshes = [o for o in new if o.type == 'MESH']
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    dims = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
    axis = max(range(3), key=lambda i: dims[i])
    print('MOTO import objetos', [o.name for o in new], 'tris', sum(common.tri_count(o) for o in meshes),
          'bbox_xyz', [round(d, 3) for d in dims], 'eje_largo', 'XYZ'[axis])
    s = MOTO_LENGTH / dims[axis]
    root.scale = (s, s, s)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    anchor = bpy.data.objects['moto_anchor'].location
    # centrar la huella XY de la moto sobre el anchor y apoyar la base en el tope de la repisa
    cx = (max(p.x for p in pts) + min(p.x for p in pts)) / 2
    cy = (max(p.y for p in pts) + min(p.y for p in pts)) / 2
    minz = min(p.z for p in pts)
    root.rotation_euler = (0, 0, math.radians(MOTO_YAW_DEG))
    # el giro es alrededor del origen del root, asi que se rota el offset XY tambien
    off = Vector((-cx, -cy, 0)); off.rotate(root.rotation_euler)
    root.location = (anchor.x + off.x, anchor.y + off.y, anchor.z - minz)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    print('MOTO escala', round(s, 5), 'yaw', MOTO_YAW_DEG, 'root.location', [round(v, 4) for v in root.location],
          'bbox_final x', round(min(p.x for p in pts), 3), round(max(p.x for p in pts), 3),
          'y', round(min(p.y for p in pts), 3), round(max(p.y for p in pts), 3),
          'z', round(min(p.z for p in pts), 4), round(max(p.z for p in pts), 4),
          'repisa_top', round(anchor.z, 4))
    # texturas de la moto a 1k (regla global: 1k para todo menos el personaje)
    for img in bpy.data.images:
        if img in before_img: continue
        w, h = img.size
        if max(w, h) > MOTO_TEX:
            img.scale(MOTO_TEX, MOTO_TEX)
            img.pack()
        print('MOTO textura', img.name, 'de', (w, h), 'a', tuple(img.size),
              'packed', img.packed_file.size if img.packed_file else None)
else:
    print('MOTO no encontrada:', moto_path)

# ------------------------------------------------------------------ HDR como mundo
hdr = os.path.join(common.EXPORT, 'night.hdr')
if os.path.exists(hdr):
    nt = sc.world.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(hdr)
    nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color'])
    nt.nodes['Background'].inputs['Strength'].default_value = 0.6
    print('HDR mundo', hdr)

# ------------------------------------------------------------------ render de aprobacion
for m in ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop'):
    bpy.data.materials[m].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.5
arm.animation_data.action = None
for t in arm.animation_data.nla_tracks:
    t.mute = (t.name != 'typing')
sc.frame_set(12)
bpy.context.view_layer.update()
bad = character_checks('typing@12')
name = (common.args() or ['assembled_v1'])[0]
common.render(os.path.join(common.RENDERS, f'{name}.png'), res=(1600, 900), samples=48)
print('TOTAL_TRIS', common.scene_tri_count())
print('INTERSECCIONES', bad, '(objetivo 0)')
# rutas relativas (HDR, texturas) para que avatar.blend funcione si se mueve el repo
bpy.ops.file.make_paths_relative()
common.save(os.path.join(common.BLEND_DIR, 'avatar.blend'))

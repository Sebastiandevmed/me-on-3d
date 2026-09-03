# blender/scripts/add_face_parts.py
# Task 8: añade a blender/character.blend párpados, cejas y candongas movidos por huesos.
#
# Convención que Task 9 debe poder dar por cierta:
#   * hueso 'eyelidL' / 'eyelidR'  : rotación +70° en su X LOCAL = ojo cerrado; 0 = abierto.
#   * hueso 'eyebrow_L' / 'eyebrow_R': traslación +0.012 en su Z LOCAL = ceja levantada.
# Para que "X local" y "Z local" coincidan con los ejes de mundo, los cuatro huesos se
# crean apuntando a +Y (head -> tail = (0, +0.015, 0)) con roll 0: en Blender un hueso
# con dirección +Y y roll 0 tiene matriz local identidad, así que X local = +X mundo y
# Z local = +Z mundo. (El personaje mira a +Y y su lado izquierdo está en -X.)
#
# Geometría:
#   * Párpado: disco radial cuyos vértices se colocan por RAYCAST sobre la cara y se
#     desplazan 1.5 mm a lo largo de la normal, así que en la pose CERRADA calca la piel.
#     Luego la malla se gira -70° alrededor del eje X que pasa por el pivote (borde
#     superior del ojo, 6 mm hacia dentro): esa es la pose de reposo (ojo ABIERTO), en la
#     que el párpado queda escondido dentro del cráneo. Aplicar +70° lo devuelve a cerrado.
#   * Ceja: cordón curvo de sección elíptica, también apoyado por raycast sobre la frente,
#     un poco más grande que la ceja pintada para taparla; al subir 12 mm se nota.
#   * Candongas: dos aros de plata anidados por oreja, colgando del lóbulo, en el plano YZ.
#
# El script MODIFICA character.blend EN SITIO y lo guarda. Es idempotente: al empezar
# borra los objetos/huesos que hubiera creado una ejecución anterior, así se puede repetir
# para calibrar sin volver a importar el personaje (import_character.py rehace el .blend y
# se llevaría por delante el logo del pecho).
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/add_face_parts.py
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector, Matrix

HEAD_BONE = 'spine006'
LID_ANGLE = 70.0        # grados (convención Task 9)
BROW_RAISE = 0.012      # m (convención Task 9)
LID_OFFSET = 0.0015     # m que el párpado sobresale de la piel al estar cerrado
LID_THICK = 0.0015      # m de grosor del párpado (solidify)
LID_PIVOT_BACK = 0.006  # m hacia dentro de la cara donde queda el pivote
LID_PIVOT_UP = 0.016    # m por encima del centro del ojo donde queda el pivote
BROW_OFFSET = 0.0003    # m que la ceja sobresale de la piel (apenas apoyada)
BROW_THICK = 0.0030     # m de bulto de la ceja (perfil eliptico, se afila en las puntas)
BROW_ARCH = 0.0015      # m de arco de la ceja
BROW_SEGS = 11          # secciones a lo largo de la ceja
BROW_PROF = 8           # vertices del perfil eliptico
BONE_LEN = 0.015
HOOP_MINOR = 0.0016
HOOP_R1, HOOP_R2 = 0.0095, 0.0130
HOOP_X_IN = 0.0000      # m: el plano del aro va justo en la superficie del lóbulo

OBJ_NAMES = ('eyelid_L', 'eyelid_R', 'eyebrow_L_mesh', 'eyebrow_R_mesh',
             'earring_L1', 'earring_L2', 'earring_R1', 'earring_R2')
BONE_NAMES = ('eyelidL', 'eyelidR', 'eyebrow_L', 'eyebrow_R')


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# --------------------------------------------------------------------------- utilidades

def obj_mode():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def cleanup(arm):
    """Borra lo que hubiera creado una ejecución anterior (idempotencia)."""
    obj_mode()
    gone = []
    for o in list(bpy.data.objects):
        if o.name in OBJ_NAMES or o.name.startswith('FP_'):
            name = o.name
            bpy.data.objects.remove(o, do_unlink=True)
            gone.append(name)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for n in BONE_NAMES:
        eb = arm.data.edit_bones.get(n)
        if eb:
            arm.data.edit_bones.remove(eb)
            gone.append(n)
    bpy.ops.object.mode_set(mode='OBJECT')
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    print('CLEANUP', gone)


class Face:
    """Raycast contra la malla de la cabeza para apoyar la geometría en la piel."""

    def __init__(self, body):
        self.body = body
        self.mw = body.matrix_world
        self.mwi = self.mw.inverted()
        self.nmat = self.mw.to_3x3().inverted().transposed()

    def front(self, x, z, y0=0.17):
        """Punto y normal de la superficie frontal en (x, z), mirando hacia -Y."""
        o = self.mwi @ Vector((x, y0, z))
        d = (self.mwi.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
        hit, loc, nor, _ = self.body.ray_cast(o, d)
        if not hit:
            return None, None
        return self.mw @ loc, (self.nmat @ nor).normalized()


def push_world():
    """Fondo gris temporal: en EEVEE un material metalico sin entorno sale negro y las
    candongas no se verian plateadas en los renders de aprobacion."""
    sc = bpy.context.scene
    created = sc.world is None
    if created:
        sc.world = bpy.data.worlds.new('FP_World')
    w = sc.world
    prev_nodes = w.use_nodes
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    prev = (tuple(bg.inputs[0].default_value), bg.inputs[1].default_value)
    bg.inputs[0].default_value = (0.42, 0.44, 0.50, 1.0)
    bg.inputs[1].default_value = 0.55
    return (created, w, prev_nodes, prev)


def pop_world(state):
    created, w, prev_nodes, prev = state
    if created:
        bpy.context.scene.world = None
        bpy.data.worlds.remove(w)
        return
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = prev[0]
    bg.inputs[1].default_value = prev[1]
    w.use_nodes = prev_nodes


def new_mesh_object(name, verts, faces, material):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def recalc_and_solidify(ob, thickness):
    obj_mode()
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    if thickness:
        md = ob.modifiers.new('solidify', 'SOLIDIFY')
        md.thickness = thickness
        md.offset = 1.0
        bpy.ops.object.modifier_apply(modifier=md.name)


def shade_smooth(ob):
    obj_mode()
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth()


def add_bones(arm, specs):
    """specs: [(nombre, head_world)] -> huesos hijos de HEAD_BONE apuntando a +Y, roll 0."""
    obj_mode()
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    ai = arm.matrix_world.inverted()
    for name, head_w in specs:
        eb = arm.data.edit_bones.new(name)
        eb.head = ai @ Vector(head_w)
        eb.tail = ai @ (Vector(head_w) + Vector((0.0, BONE_LEN, 0.0)))
        eb.roll = 0.0
        eb.parent = arm.data.edit_bones[HEAD_BONE]
        eb.use_connect = False
        eb.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')


def parent_to_bone(arm, ob, bone):
    """Parenta ob al hueso conservando su transformación de mundo actual.
    (El parentado a hueso de Blender usa la COLA del hueso como origen; en vez de
    reproducir esa matriz a mano se mide y se invierte.)"""
    world = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    ob.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    parent_mat = ob.matrix_world @ ob.matrix_basis.inverted()
    ob.matrix_parent_inverse = parent_mat.inverted()
    ob.matrix_world = world
    bpy.context.view_layer.update()


# --------------------------------------------------------------------------- piezas

def make_lid(face, name, centre, a, b, material, ey_hint):
    """Disco radial pegado a la piel (pose CERRADA)."""
    ex, ez = centre
    rings, seg = 3, 16

    def surf(dx, dz):
        p, n = face.front(ex + dx, ez + dz)
        if p is None:
            return Vector((ex + dx, ey_hint + LID_OFFSET, ez + dz))
        return p + n * LID_OFFSET

    verts = [surf(0.0, 0.0)]
    for r in range(1, rings + 1):
        rho = r / rings
        for s in range(seg):
            ang = 2 * math.pi * s / seg
            verts.append(surf(a * rho * math.cos(ang), b * rho * math.sin(ang)))
    faces = []
    for s in range(seg):
        faces.append((0, 1 + (s + 1) % seg, 1 + s))
    for r in range(rings - 1):
        b0, b1 = 1 + r * seg, 1 + (r + 1) * seg
        for s in range(seg):
            s2 = (s + 1) % seg
            faces.append((b0 + s2, b1 + s2, b1 + s, b0 + s))
    return new_mesh_object(name, verts, faces, material)


def make_brow(face, name, x_in, x_out, z_c, h, material):
    """Cordon curvo de seccion eliptica apoyado en la frente, afilado en las puntas,
    algo mas grande que la ceja pintada para taparla."""
    up = Vector((0.0, 0.0, 1.0))
    n, prof = BROW_SEGS, BROW_PROF
    verts, faces = [], []
    for i in range(n):
        t = i / (n - 1)
        taper = math.sin(math.pi * t) ** 0.5
        x = x_in + t * (x_out - x_in)
        z = z_c + BROW_ARCH * math.sin(math.pi * t)
        hh = (h / 2.0) * (0.30 + 0.70 * taper)
        tt = BROW_THICK * (0.35 + 0.65 * taper)
        p, nor = face.front(x, z)
        if p is None:
            p, nor = Vector((x, 0.10, z)), Vector((0.0, 1.0, 0.0))
        base = p + nor * (BROW_OFFSET + tt / 2.0)
        for k in range(prof):
            ang = 2 * math.pi * k / prof
            verts.append(base + nor * ((tt / 2.0) * math.cos(ang)) + up * (hh * math.sin(ang)))
    for i in range(n - 1):
        for k in range(prof):
            k2 = (k + 1) % prof
            faces.append((i * prof + k, i * prof + k2, (i + 1) * prof + k2, (i + 1) * prof + k))
    faces.append(tuple(range(prof - 1, -1, -1)))
    faces.append(tuple(range((n - 1) * prof, n * prof)))
    return new_mesh_object(name, verts, faces, material)


def make_hoop(name, centre, major, material):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=HOOP_MINOR,
                                     major_segments=16, minor_segments=6,
                                     location=centre, rotation=(0.0, math.radians(90.0), 0.0))
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(material)
    return ob


# --------------------------------------------------------------------------- main

def main():
    common.ensure_dirs()
    lm = json.load(open(os.path.join(common.GEN, 'landmarks.json')))
    arm = bpy.data.objects['Armature']
    body = bpy.data.objects['Body']
    cleanup(arm)
    face = Face(body)

    skin = [srgb_to_linear(c) for c in lm.get('skin_srgb', [0.93, 0.63, 0.54])]
    print('SKIN_LINEAR', [round(c, 4) for c in skin])
    m_skin = common.mat('Eyelid', tuple(skin) + (1.0,), roughness=0.72)
    brow_col = [srgb_to_linear(c) for c in lm.get('brow_srgb', [0.114, 0.067, 0.082])]
    print('BROW_LINEAR', [round(c, 5) for c in brow_col])
    m_brow = common.mat('Brow', tuple(brow_col) + (1.0,), roughness=0.85)
    m_silver = common.mat('Silver', (0.90, 0.90, 0.92, 1.0), roughness=0.20, metallic=1.0)

    a = lm['eye_radius']
    b = lm['eye_half_h']
    bone_specs, pending = [], []

    for side in ('L', 'R'):
        eye = Vector(lm[f'eye_{side}'])
        p, _ = face.front(eye.x, eye.z)
        ey = p.y if p else eye.y
        print(f'EYE_{side}', [round(v, 4) for v in (eye.x, ey, eye.z)])

        lid = make_lid(face, f'eyelid_{side}', (eye.x, eye.z), a, b, m_skin, ey)
        recalc_and_solidify(lid, LID_THICK)
        shade_smooth(lid)
        pivot = Vector((eye.x, ey - LID_PIVOT_BACK, eye.z + LID_PIVOT_UP))
        # la malla se construye CERRADA; girándola -70° queda en reposo = ABIERTA,
        # y el +70° de la convención la devuelve exactamente a cerrada.
        rot = (Matrix.Translation(pivot)
               @ Matrix.Rotation(math.radians(-LID_ANGLE), 4, 'X')
               @ Matrix.Translation(-pivot))
        lid.data.transform(rot)
        bone_specs.append((f'eyelid{side}', pivot))
        pending.append((lid, f'eyelid{side}'))

        brow = Vector(lm[f'brow_{side}'])
        half = lm['brow_len'] / 2.0
        x_in, x_out = (brow.x + half, brow.x - half) if side == 'L' else (brow.x - half, brow.x + half)
        bm = make_brow(face, f'eyebrow_{side}_mesh', x_in, x_out, brow.z, lm['brow_h'], m_brow)
        recalc_and_solidify(bm, 0.0)
        shade_smooth(bm)
        bp, _ = face.front(brow.x, brow.z)
        bone_specs.append((f'eyebrow_{side}', bp if bp else brow))
        pending.append((bm, f'eyebrow_{side}'))

    for side in ('L', 'R'):
        ear = Vector(lm[f'ear_{side}'])
        sgn = -1.0 if side == 'L' else 1.0
        hx = ear.x - sgn * HOOP_X_IN
        for i, r in enumerate((HOOP_R1, HOOP_R2)):
            ring = make_hoop(f'earring_{side}{i + 1}', (hx, ear.y, ear.z - r), r, m_silver)
            shade_smooth(ring)
            parent_to_bone(arm, ring, HEAD_BONE)
        print(f'EAR_{side}', [round(v, 4) for v in (hx, ear.y, ear.z)])

    add_bones(arm, bone_specs)
    for ob, bone in pending:
        parent_to_bone(arm, ob, bone)

    for name, _ in bone_specs:
        pb = arm.pose.bones[name]
        pb.rotation_mode = 'XYZ'          # el glTF deja QUATERNION y rotation_euler se ignoraría
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)

    extra = sum(common.tri_count(bpy.data.objects[n]) for n in OBJ_NAMES)
    total = sum(common.tri_count(o) for o in bpy.data.objects if o.type == 'MESH')
    print('FACE_PARTS_TRIS', extra, 'TOTAL_TRIS', total)

    # ---------------------------------------------------------------- renders de control
    hz = (arm.matrix_world @ arm.pose.bones[HEAD_BONE].head).z
    prev_cam = bpy.context.scene.camera
    world_state = push_world()
    cam = common.add_camera((0.0, 0.85, hz + 0.10), (0.0, 0.0, hz + 0.09), lens=85, name='FP_Cam')
    common.add_light('FP_key', 'AREA', (-0.6, 0.9, hz + 0.5), 160, size=0.9)
    common.add_light('FP_fill', 'AREA', (0.7, 0.8, hz + 0.1), 90, size=0.9)
    common.render(os.path.join(common.RENDERS, 'face_parts_open.png'), res=(900, 900), samples=48)

    for s in 'LR':
        pb = arm.pose.bones[f'eyelid{s}']
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (math.radians(LID_ANGLE), 0.0, 0.0)
        arm.pose.bones[f'eyebrow_{s}'].location = (0.0, 0.0, BROW_RAISE)
    bpy.context.view_layer.update()
    common.render(os.path.join(common.RENDERS, 'face_parts_closed_browup.png'), res=(900, 900), samples=48)

    for s in 'LR':
        arm.pose.bones[f'eyelid{s}'].rotation_euler = (0.0, 0.0, 0.0)
        arm.pose.bones[f'eyebrow_{s}'].location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    for s, sgn in (('L', -1.0), ('R', 1.0)):
        cam.location = (sgn * 0.5, -0.02, hz + 0.025)
        common.look_at(cam, (0.0, -0.03, hz + 0.02))
        common.render(os.path.join(common.RENDERS, f'face_parts_ear_{s}.png'), res=(800, 800), samples=48)

    for o in list(bpy.data.objects):
        if o.name.startswith('FP_'):
            bpy.data.objects.remove(o, do_unlink=True)
    if prev_cam and prev_cam.name in bpy.data.objects:
        bpy.context.scene.camera = prev_cam
    pop_world(world_state)

    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('FACE_PARTS OK')


if __name__ == '__main__':
    main()

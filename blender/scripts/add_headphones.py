# blender/scripts/add_headphones.py
# Task 4: pieza de audifonos (arco eliptico + dos copas) movida por el hueso 'headphones'.
#
# Convencion que animate.py, el visor y Task 5 dan por cierta:
#   * hueso 'headphones' hijo de spine006, con head = head de spine006 (asi el nodo glTF sale
#     con traslacion 0 respecto a la cabeza), tail = head + (0, 0, 0.05) y roll 0
#     ->  X local = +X mundo, Y local = +Z mundo, Z local = -Y mundo
#     (una traslacion de mundo (dx, dy, dz) es (dx, dz, -dy) en local). Se VERIFICA al final.
#   * reposo (rotacion 0, traslacion 0) = audifonos COLGANDO DEL CUELLO: copas a los lados,
#     delante-abajo del menton, y el arco hacia atras metido en la capucha.
#   * "puestos" = rotation_euler ON_ROT + location ON_LOC (espacio local del hueso), que se
#     escriben en blender/headphones.json junto con los centros de las copas en los dos estados
#     (en el espacio local de REPOSO del hueso) para que animate.py lleve las manos a ellos.
#
# COMO SE CONSTRUYE: la pieza se modela en su posicion PUESTA (sobre la cabeza, arco por encima
# de la gorra, copas centradas en las orejas de landmarks.json). Se calcula la transformacion
# rigida de mundo T_NECK que la baja al cuello (giro NECK_ROT_DEG alrededor del eje X de mundo
# que pasa por la cabeza del hueso, mas la traslacion que lleva el centro del arco a
# NECK_CENTER), se aplica a las mallas y se parentan al hueso: eso deja el REPOSO en el cuello.
# El estado ON es entonces el que deshace T_NECK, expresado en el espacio local del hueso:
#     mundo_delta(P) = A @ P @ A^-1   con A = arm.matrix_world @ bone.matrix_local
#     queremos mundo_delta(ON) = T_NECK^-1   ->   ON = A^-1 @ T_NECK^-1 @ A
# (no se puede usar el atajo "ON = -NECK": la inversa de (R, t) no es (-R, -t) cuando hay giro).
#
# Idempotente: al empezar borra sus objetos y su hueso. MODIFICA character.blend EN SITIO.
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/add_headphones.py
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector, Matrix
from add_face_parts import obj_mode, parent_to_bone, shade_smooth, recalc_and_solidify, load_landmarks

BONE, PARENT = 'headphones', 'spine006'
OBJS = ('headphones_band', 'headphones_cup_L', 'headphones_cup_R')
BONE_LEN = 0.05                    # m: largo del hueso (apunta a +Z de mundo)

# --- geometria en la posicion PUESTA (mundo, personaje de pie) -------------------------------
CENTRE_OFF = (0.0, 0.005, 0.008)   # m: centro del arco = punto medio de las orejas + esto
BAND_A = 0.132                     # m: semieje X del arco (cabeza: |x| max = 0.112 a la altura
                                   #    de las orejas; deja 4 mm de aire con la cara interna)
BAND_B = 0.236                     # m: semieje Z (corona de la gorra en z = 1.750; el centro
                                   #    del arco esta en z = 1.530 -> 0.220 + tubo + 5 mm de aire)
BAND_R = 0.009                     # m: radio del tubo del arco
BAND_SEGS, BAND_STEPS = 8, 24      # secciones del tubo y tramos del arco
CUP_R, CUP_D = 0.045, 0.032        # m: radio y grosor de la copa
CUP_VERTS = 20

# --- estado de REPOSO (colgando del cuello) --------------------------------------------------
NECK_ROT_DEG = 70.0                # grados alrededor del eje X de MUNDO que pasa por la cabeza
                                   # del hueso; positivo tumba el arco hacia atras (-Y)
NECK_CENTER = (0.0, 0.040, 1.390)  # m: donde queda el centro del arco (= centro de las copas)

OUT_JSON = os.path.join(common.BLEND_DIR, 'headphones.json')
ON_TOL = 0.005                     # m: error maximo admitido al reproducir la posicion puesta


def cleanup(arm):
    """Borra lo que hubiera creado una ejecucion anterior (idempotencia)."""
    obj_mode()
    gone = []
    for o in list(bpy.data.objects):
        if o.name in OBJS:
            gone.append(o.name)
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones.get(BONE)
    if eb:
        arm.data.edit_bones.remove(eb)
        gone.append(BONE)
    bpy.ops.object.mode_set(mode='OBJECT')
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    print('HP CLEANUP', gone)


def add_bone(arm):
    """Hueso 'headphones': hijo de spine006, misma cabeza, apuntando a +Z de mundo, roll 0."""
    obj_mode()
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    par = arm.data.edit_bones[PARENT]
    eb = arm.data.edit_bones.new(BONE)
    eb.head = par.head.copy()
    eb.tail = par.head + Vector((0.0, 0.0, BONE_LEN))
    eb.roll = 0.0
    eb.parent = par
    eb.use_connect = False
    eb.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')


def tube(name, path, radius, material, segs=BAND_SEGS):
    """Tubo abierto a lo largo de una polilinea (lista de Vector en mundo)."""
    verts, faces = [], []
    up = Vector((0.0, 1.0, 0.0))
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        n = (t.cross(up) if abs(t.dot(up)) < 0.9 else t.cross(Vector((1.0, 0.0, 0.0)))).normalized()
        b = t.cross(n)
        for k in range(segs):
            a = 2 * math.pi * k / segs
            verts.append(p + (n * math.cos(a) + b * math.sin(a)) * radius)
    for i in range(len(path) - 1):
        for k in range(segs):
            v0, v1 = i * segs + k, i * segs + (k + 1) % segs
            faces.append((v0, v1, v1 + segs, v0 + segs))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def cup(name, centre, m_black, m_grey):
    """Copa: cilindro con el eje en X, biselado; la tapa EXTERIOR va en gris (el detalle)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=CUP_VERTS, radius=CUP_R, depth=CUP_D,
                                        location=centre, rotation=(0.0, math.radians(90.0), 0.0))
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(m_black)
    ob.data.materials.append(m_grey)
    bev = ob.modifiers.new('bevel', 'BEVEL')
    bev.width = 0.006
    bev.segments = 2
    bpy.ops.object.modifier_apply(modifier=bev.name)
    # el cilindro se crea con su eje en el Z LOCAL (la rotacion de 90 grados en Y lo lleva a
    # +X de mundo), asi que la tapa exterior es la de z local con el signo del lado.
    sgn = 1.0 if centre[0] > 0 else -1.0
    for poly in ob.data.polygons:
        if len(poly.vertices) > 4 and poly.center.z * sgn > CUP_D * 0.3:
            poly.material_index = 1          # tapa exterior = gris
    return ob


def main():
    common.ensure_dirs()
    lm = load_landmarks()
    arm = bpy.data.objects.get('Armature')
    if not arm or arm.type != 'ARMATURE':
        common.fail('no hay Armature en el .blend')
    if PARENT not in arm.data.bones:
        common.fail(f'no existe el hueso {PARENT}')
    cleanup(arm)
    add_bone(arm)
    bpy.context.view_layer.update()

    m_black = common.mat('Headphones', (0.012, 0.012, 0.014, 1.0), roughness=0.62)
    m_grey = common.mat('Headphones_detail', (0.16, 0.16, 0.18, 1.0), roughness=0.45)

    # ---------------------------------------------------------- geometria en la posicion PUESTA
    centre = (Vector(lm['ear_L']) + Vector(lm['ear_R'])) / 2.0 + Vector(CENTRE_OFF)
    print('HP centro del arco (puesto)', [round(v, 4) for v in centre])
    path = [centre + Vector((BAND_A * math.cos(a), 0.0, BAND_B * math.sin(a)))
            for a in [math.pi * i / BAND_STEPS for i in range(BAND_STEPS + 1)]]
    band = tube('headphones_band', path, BAND_R, m_black)
    recalc_and_solidify(band, 0.0)
    on_cup = {'L': centre + Vector((-BAND_A, 0.0, 0.0)), 'R': centre + Vector((BAND_A, 0.0, 0.0))}
    cups = {s: cup(f'headphones_cup_{s}', on_cup[s], m_black, m_grey) for s in 'LR'}
    objs = [band] + [cups[s] for s in 'LR']
    for o in objs:
        shade_smooth(o)

    # ---------------------------------------------------------- T_NECK: de la cabeza al cuello
    bone = arm.data.bones[BONE]
    head_w = arm.matrix_world @ bone.head_local
    A = arm.matrix_world @ bone.matrix_local          # espacio local del hueso -> mundo (reposo)
    rot = Matrix.Rotation(math.radians(NECK_ROT_DEG), 4, 'X')
    t_rot = Matrix.Translation(head_w) @ rot @ Matrix.Translation(-head_w)
    t_neck = Matrix.Translation(Vector(NECK_CENTER) - (t_rot @ centre)) @ t_rot
    for o in objs:
        o.matrix_world = t_neck @ o.matrix_world
    bpy.context.view_layer.update()
    for o in objs:
        parent_to_bone(arm, o, BONE)
    bpy.context.view_layer.update()

    # ---------------------------------------------------------- estado ON = deshacer T_NECK
    p_on = A.inverted() @ t_neck.inverted() @ A
    on_rot = tuple(p_on.to_euler('XYZ'))
    on_loc = tuple(p_on.to_translation())
    pb = arm.pose.bones[BONE]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = on_rot
    pb.location = on_loc
    bpy.context.view_layer.update()
    err = max((cups[s].matrix_world.translation - on_cup[s]).length for s in 'LR')
    print('HP on_head rotation_deg', [round(math.degrees(v), 3) for v in on_rot],
          'location', [round(v, 5) for v in on_loc])
    print('HP on_head reproduce la posicion puesta, error', round(err, 5), 'm')
    if err > ON_TOL:
        common.fail(f'la transformacion ON no devuelve la pieza a la cabeza (error {err:.4f} m)')
    cup_head = {s: tuple(A.inverted() @ cups[s].matrix_world.translation) for s in 'LR'}

    pb.rotation_euler = (0.0, 0.0, 0.0)
    pb.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    cup_rest = {s: tuple(A.inverted() @ cups[s].matrix_world.translation) for s in 'LR'}
    for s in 'LR':
        print(f'HP copa {s} reposo(mundo)', [round(v, 4) for v in cups[s].matrix_world.translation])

    # ---------------------------------------------------------- convencion de ejes del hueso
    m3 = A.to_3x3()
    axes = {'X': (m3 @ Vector((1, 0, 0))).normalized(), 'Y': (m3 @ Vector((0, 1, 0))).normalized(),
            'Z': (m3 @ Vector((0, 0, 1))).normalized()}
    want = {'X': Vector((1, 0, 0)), 'Y': Vector((0, 0, 1)), 'Z': Vector((0, -1, 0))}
    for k in 'XYZ':
        print(f'HP eje {k} local ->', [round(v, 4) for v in axes[k]])
        if axes[k].dot(want[k]) < 0.999:
            common.fail(f'el hueso {BONE} no cumple la convencion: {k} local deberia ser '
                        f'{tuple(want[k])} y es {tuple(round(v, 4) for v in axes[k])}')

    with open(OUT_JSON, 'w') as f:
        json.dump({'_note': 'generado por blender/scripts/add_headphones.py; rotacion y '
                            'traslacion en el ESPACIO LOCAL del hueso headphones (reposo = '
                            'colgando del cuello). cup_offset_* son los centros de las copas '
                            'en el espacio local de REPOSO del hueso, en cada estado.',
                   'on_head': {'rotation_deg': [round(math.degrees(v), 3) for v in on_rot],
                               'location': [round(v, 5) for v in on_loc]},
                   'cup_offset_rest': {s: [round(v, 5) for v in cup_rest[s]] for s in 'LR'},
                   'cup_offset_head': {s: [round(v, 5) for v in cup_head[s]] for s in 'LR'},
                   'cup_radius': CUP_R}, f, indent=1)
        f.write('\n')
    print('HP json', OUT_JSON)

    extra = sum(common.tri_count(bpy.data.objects[n]) for n in OBJS)
    total = sum(common.tri_count(o) for o in bpy.data.objects if o.type == 'MESH')
    print('HP TRIS', extra, 'TOTAL_TRIS', total)

    # ---------------------------------------------------------------- renders de control
    # (todas las camaras se purgan aqui y al final; no se restaura ninguna previa)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(o)
    common.add_light('HP_key', 'AREA', (-0.8, 1.2, 1.9), 300, (0.9, 0.9, 1.0), size=1.0)
    common.add_light('HP_fill', 'AREA', (1.0, 0.8, 1.4), 150, (1.0, 0.95, 0.9), size=1.0)
    common.add_light('HP_back', 'AREA', (0.0, -1.2, 1.9), 220, (1.0, 1.0, 1.0), size=1.0)
    cam = common.add_camera((0.45, 1.15, 1.62), (0.0, 0.0, 1.50), lens=55, name='HP_Cam')

    def shot(tag):
        common.render(os.path.join(common.RENDERS, f'headphones_{tag}.png'), res=(900, 900), samples=48)
        loc, rot3 = cam.location.copy(), cam.rotation_euler.copy()
        cam.location = (1.30, -0.35, 1.55)
        common.look_at(cam, (0.0, -0.02, 1.50))
        common.render(os.path.join(common.RENDERS, f'headphones_{tag}_side.png'), res=(900, 900), samples=48)
        cam.location, cam.rotation_euler = loc, rot3

    shot('rest')
    pb.rotation_euler = on_rot
    pb.location = on_loc
    bpy.context.view_layer.update()
    shot('on')
    pb.rotation_euler = (0.0, 0.0, 0.0)
    pb.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(o)
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('HP OK')


if __name__ == '__main__':
    main()

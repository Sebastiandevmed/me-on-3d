# blender/scripts/fix_head_weights.py
# El rig automatico de Meshy reparte el peso de la cabeza entre el hueso del cuello (spine005) y el
# de la cabeza (spine006) con una rampa MUY larga: medido en character.blend, a la altura de la
# barbilla el cuello todavia pesa un 30-40 % y a la altura de los ojos un 10 %. Mientras los dos
# huesos giran juntos no se nota, pero el visor (y lookAround) giran SOLO spine006 para seguir el
# cursor: la barba y la mandibula se quedan a medio camino entre la cabeza y el cuello, la barba se
# estira hacia el pecho y aparece una "papada".
#
# Arreglo: por encima de la mandibula el cuello no pinta nada. Todo el peso que spine005 tenga en
# un vertice con z >= Z_FULL pasa a spine006; entre Z_KEEP y Z_FULL se hace una rampa suave para
# que la garganta siga siendo cuello. Es lo que la gente llama "bloquear" la cabeza: gira rigida.
#
# Alturas en coordenadas de mundo de character.blend (de pie, mira a +Y), relativas a la base del
# hueso spine006 (HZ ~ 1.502 m), que Meshy coloca justo en la barbilla:
#   * Z_FULL = HZ + 0.005: desde la punta de la barbilla hacia arriba la cabeza es 100 % spine006.
#   * Z_KEEP = HZ - 0.045: de ahi para abajo (garganta y collar) los pesos no se tocan.
#
# --probe renderiza la cabeza girada (yaw 40 grados y pitch -15) SIN cambiar los pesos, para ver el
# defecto; la ejecucion normal cambia los pesos, renderiza la misma pose y guarda character.blend.
# --dry-run hace todo menos guardar. Idempotente: Body['head_weights_fixed'] evita aplicarlo dos
# veces (aplicarlo dos veces seria inocuo, pero asi el log lo dice).
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/fix_head_weights.py [-- --probe|--dry-run]
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector, Matrix

NECK_BONE, HEAD_BONE = 'spine005', 'spine006'
Z_FULL_OFF = +0.005            # m sobre la base de spine006: de aqui arriba todo es cabeza
Z_KEEP_OFF = -0.045            # m sobre la base de spine006: de aqui abajo no se toca nada
PROBE_YAW, PROBE_PITCH = 40.0, -15.0   # grados de la pose de control (mira a su izquierda y abajo)
CAM_Z = 1.60                   # m: centro de los renders de control
ORTHO_SCALE = 0.55             # m de ancho de los renders ortograficos
RES = (900, 900)

args = common.args()
PROBE, DRY = '--probe' in args, '--dry-run' in args
arm = bpy.data.objects.get('Armature')
if not arm or NECK_BONE not in arm.data.bones or HEAD_BONE not in arm.data.bones:
    common.fail(f'no hay Armature con los huesos {NECK_BONE} y {HEAD_BONE}')
body = bpy.data.objects.get('Body')
if not body:
    common.fail('no hay malla Body en el .blend')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm
          and NECK_BONE in {g.name for g in o.vertex_groups}]
if not meshes:
    common.fail(f'ninguna malla del armature tiene pesos en {NECK_BONE}')

HZ = (arm.matrix_world @ arm.data.bones[HEAD_BONE].head_local).z
Z_FULL, Z_KEEP = HZ + Z_FULL_OFF, HZ + Z_KEEP_OFF
print(f'HEADW base de {HEAD_BONE} z={HZ:.4f}; rampa {Z_KEEP:.4f} .. {Z_FULL:.4f}')


def ramp(z):
    """0 = pesos intactos (garganta), 1 = todo el peso del cuello pasa a la cabeza."""
    t = (z - Z_KEEP) / (Z_FULL - Z_KEEP)
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def neck_share(ob, z_lo, z_hi):
    """Fraccion del peso total que tiene el cuello en los vertices de la franja [z_lo, z_hi)."""
    names = {g.index: g.name for g in ob.vertex_groups}
    neck = tot = 0.0
    for v in ob.data.vertices:
        z = (ob.matrix_world @ v.co).z
        if z_lo <= z < z_hi:
            for g in v.groups:
                tot += g.weight
                if names[g.group] == NECK_BONE:
                    neck += g.weight
    return neck / tot if tot else 0.0


def report(tag):
    for ob in meshes:
        print(f'HEADW {tag} {ob.name}: cuello en barbilla..+6cm = {neck_share(ob, Z_FULL, Z_FULL + 0.06):.3f}, '
              f'en +6..+20cm = {neck_share(ob, Z_FULL + 0.06, Z_FULL + 0.20):.3f}, '
              f'garganta (rampa) = {neck_share(ob, Z_KEEP, Z_FULL):.3f}')


report('antes')
if body.get('head_weights_fixed') and not PROBE:
    print('HEADW ya aplicado; nada que hacer')
    sys.exit(0)

if not PROBE:
    moved_total = 0
    for ob in meshes:
        vg_neck = ob.vertex_groups[NECK_BONE]
        vg_head = ob.vertex_groups.get(HEAD_BONE) or ob.vertex_groups.new(name=HEAD_BONE)
        moved = 0
        for v in ob.data.vertices:
            t = ramp((ob.matrix_world @ v.co).z)
            if t <= 0.0:
                continue
            w_neck = next((g.weight for g in v.groups if g.group == vg_neck.index), 0.0)
            if w_neck <= 0.0:
                continue
            w_head = next((g.weight for g in v.groups if g.group == vg_head.index), 0.0)
            vg_head.add([v.index], w_head + w_neck * t, 'REPLACE')
            if t >= 1.0:
                vg_neck.remove([v.index])
            else:
                vg_neck.add([v.index], w_neck * (1 - t), 'REPLACE')
            moved += 1
        ob.data.update()
        print(f'HEADW {ob.name}: {moved} vertices repesados')
        moved_total += moved
    if not moved_total:
        common.fail('ningun vertice tenia peso de cuello por encima de Z_KEEP: recalibrar')
    body['head_weights_fixed'] = True
    report('despues')

# ------------------------------------------------------------------ render de control con la cabeza girada
# Solo gira spine006 (como hace el visor). La rotacion se pide en mundo (yaw sobre Z, pitch sobre X)
# y se convierte al espacio local del hueso: local = B^-1 * R * B, con B = orientacion del hueso en reposo.
pb = arm.pose.bones[HEAD_BONE]
B = (arm.matrix_world @ arm.data.bones[HEAD_BONE].matrix_local).to_3x3()
R = Matrix.Rotation(math.radians(PROBE_YAW), 3, 'Z') @ Matrix.Rotation(math.radians(PROBE_PITCH), 3, 'X')
pb.rotation_mode = 'QUATERNION'
pb.rotation_quaternion = (B.inverted() @ R @ B).to_quaternion()
bpy.context.view_layer.update()

common.ensure_dirs()
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
common.add_light('HW_key', 'AREA', (-0.8, 1.2, 2.0), 300, (0.9, 0.9, 1.0), size=1.0)
common.add_light('HW_fill', 'AREA', (1.0, 0.8, 1.6), 150, (1.0, 0.95, 0.9), size=1.0)
common.add_light('HW_back', 'AREA', (0.0, -1.2, 2.0), 200, (1.0, 1.0, 1.0), size=1.0)
tag = 'before' if PROBE else 'after'
cam = common.add_camera((0.0, 1.5, CAM_Z), (0.0, 0.0, CAM_Z), name='HW_Cam')
cam.data.type = 'ORTHO'
cam.data.ortho_scale = ORTHO_SCALE
common.render(os.path.join(common.RENDERS, f'head_weights_{tag}_front.png'), res=RES, samples=48)
cam.location = (1.5, 0.0, CAM_Z)
common.look_at(cam, (0.0, 0.0, CAM_Z))
common.render(os.path.join(common.RENDERS, f'head_weights_{tag}_side.png'), res=RES, samples=48)

pb.rotation_quaternion = (1, 0, 0, 0)
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
if PROBE:
    print('HEADW probe renderizado; no se guarda')
elif DRY:
    print('HEADW dry-run; no se guarda')
else:
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('HEADW OK')

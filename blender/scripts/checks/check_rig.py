# blender/scripts/checks/check_rig.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
from mathutils import Vector
arm = bpy.data.objects.get('Armature')
if not arm or arm.type != 'ARMATURE': common.fail('no hay Armature')
names = {b.name for b in arm.data.bones}
need = ['spine', 'spine001', 'spine002', 'spine003', 'spine005', 'spine006',
        'upper_armL', 'forearmL', 'handL', 'upper_armR', 'forearmR', 'handR',
        'thighL', 'shinL', 'footL', 'thighR', 'shinR', 'footR',
        'shoulderL', 'shoulderR', 'toeL', 'toeR', 'headfront']
need += ['eyelidL', 'eyelidR', 'eyebrow_L', 'eyebrow_R']
need += ['headphones']            # Task 4: hueso de la pieza de audifonos
missing = [n for n in need if n not in names]
if missing: common.fail(f'faltan huesos {missing}')
for o in ('earring_L1', 'earring_L2', 'earring_R1', 'earring_R2',
          'eyelid_L', 'eyelid_R', 'eyebrow_L_mesh', 'eyebrow_R_mesh',
          'headphones_band', 'headphones_cup_L', 'headphones_cup_R'):
    ob = bpy.data.objects.get(o)
    if not ob: common.fail(f'falta objeto {o}')
    if ob.parent_type != 'BONE': common.fail(f'{o} no esta parentado a hueso')
# convencion Task 8/9: +70 grados en X local del parpado = ojo cerrado, y +0.012 en Z
# local de la ceja = ceja levantada. Solo se cumple si los ejes locales de esos huesos
# coinciden con los del mundo, asi que se verifica aqui.
for bn in ('eyelidL', 'eyelidR', 'eyebrow_L', 'eyebrow_R'):
    m = (arm.matrix_world @ arm.data.bones[bn].matrix_local).to_3x3()
    lx = (m @ Vector((1, 0, 0))).normalized()
    lz = (m @ Vector((0, 0, 1))).normalized()
    if lx.dot(Vector((1, 0, 0))) < 0.999: common.fail(f'{bn}: X local no es +X de mundo ({lx[:]})')
    if lz.dot(Vector((0, 0, 1))) < 0.999: common.fail(f'{bn}: Z local no es +Z de mundo ({lz[:]})')

# convencion Task 4: el hueso 'headphones' apunta a +Z de mundo con roll 0, asi que
# X local = +X mundo, Y local = +Z mundo y Z local = -Y mundo. La rotacion y la traslacion
# de blender/headphones.json solo significan lo que dicen si esto se cumple.
hp = (arm.matrix_world @ arm.data.bones['headphones'].matrix_local).to_3x3()
for ax, want in ((Vector((1, 0, 0)), Vector((1, 0, 0))), (Vector((0, 1, 0)), Vector((0, 0, 1))),
                 (Vector((0, 0, 1)), Vector((0, -1, 0)))):
    got = (hp @ ax).normalized()
    if got.dot(want) < 0.999: common.fail(f'headphones: eje local {ax[:]} deberia ir a {want[:]} y va a {got[:]}')
if arm.data.bones['headphones'].parent.name != 'spine006':
    common.fail('headphones no cuelga de spine006')
d = (arm.data.bones['headphones'].head_local - arm.data.bones['spine006'].head_local).length
if d > 1e-5: common.fail(f'la cabeza de headphones no coincide con la de spine006 ({d:.5f} m)')

meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Body')]
if not meshes: common.fail('no hay malla Body')
# presupuesto de triangulos: TODAS las mallas del .blend son el personaje (cuerpo +
# parpados + cejas + candongas + audifonos), asi que se suman todas, no solo Body*.
# El tope subio de 40000 a 42000 en Task 4 para dar sitio a la pieza de audifonos (~860 tris).
all_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
tris = sum(common.tri_count(m) for m in all_meshes)
body_tris = sum(common.tri_count(m) for m in meshes)
if tris > 42000: common.fail(f'personaje demasiado pesado: {tris}')
zs = [(m.matrix_world @ Vector(v.co)).z for m in meshes for v in m.data.vertices]
h = max(zs) - min(zs)
if not (1.6 < h < 1.9): common.fail(f'altura fuera de rango: {h}')
if min(zs) < -0.02 or min(zs) > 0.02: common.fail(f'los pies no están en z=0: {min(zs)}')
# orientación: la cara (headfront) debe quedar en +Y respecto a la cabeza (spine006)
hf = arm.matrix_world @ arm.data.bones['headfront'].head_local
s6 = arm.matrix_world @ arm.data.bones['spine006'].head_local
if hf.y <= s6.y: common.fail(f'el personaje no mira a +Y: headfront.y={hf.y:.3f} spine006.y={s6.y:.3f}')
for m in meshes:
    vg = {g.name for g in m.vertex_groups}
    if 'spine006' not in vg: common.fail(f'{m.name} sin pesos en spine006')
print('CHECK_RIG OK tris=', tris, '(Body', body_tris, '+ partes faciales',
      tris - body_tris, ') mallas=', len(all_meshes), 'h=', round(h, 3))

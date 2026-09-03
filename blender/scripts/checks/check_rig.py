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
missing = [n for n in need if n not in names]
if missing: common.fail(f'faltan huesos {missing}')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Body')]
if not meshes: common.fail('no hay malla Body')
tris = sum(common.tri_count(m) for m in meshes)
if tris > 40000: common.fail(f'personaje demasiado pesado: {tris}')
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
print('CHECK_RIG OK tris=', tris, 'h=', round(h, 3))

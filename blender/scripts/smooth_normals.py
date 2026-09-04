# blender/scripts/smooth_normals.py
# La malla de Meshy viene abollada (ondulaciones de "escaneo" en gorra, hoodie y cara) y en el visor,
# con luz suave y sombras, se lee como plastilina. Alisar POSICIONES no sirve: la malla son ~4500
# islas con bordes que no coinciden (ni soldando a 0.1 mm), y cualquier suavizado abre huecos.
#
# Lo que si funciona es alisar solo el SOMBREADO: se hace una copia de Body, se remalla por voxels
# (una sola cascara limpia) y se suaviza fuerte; luego se transfieren sus normales como normales
# personalizadas de Body (Data Transfer, CUSTOM_NORMAL, interpolacion de la cara mas cercana). Ningun
# vertice se mueve, las UV y los pesos quedan intactos, y el exportador glTF escribe las normales
# personalizadas tal cual (Draco las conserva). Probado con voxel 6 mm/5 it y 10 mm/10 it en
# generated/renders/normals_*.png; se usa un punto intermedio.
#
# Va despues de fix_head_weights.py (o de cualquier script que mueva vertices de Body, como
# hide_neck_headphones.py) y antes de check_rig.py. Idempotente: Body['normals_smoothed'].
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/smooth_normals.py [--dry-run]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common

VOXEL = 0.008        # m: tamano de voxel del remallado de la copia (mas chico = conserva mas detalle)
ITERS = 8            # iteraciones del Smooth (factor 1.0) sobre la copia

args = common.args()
DRY = '--dry-run' in args
body = bpy.data.objects.get('Body')
if not body:
    common.fail('no hay malla Body en el .blend')
if body.get('normals_smoothed'):
    print('NORMALS ya aplicado; nada que hacer')
    sys.exit(0)
if bpy.data.objects.get('BodyProxy'):
    bpy.data.objects.remove(bpy.data.objects['BodyProxy'])

common.obj_mode() if hasattr(common, 'obj_mode') else None
for o in bpy.data.objects:
    o.select_set(False)
proxy = body.copy(); proxy.data = body.data.copy(); proxy.name = 'BodyProxy'
bpy.context.scene.collection.objects.link(proxy)
proxy.modifiers.clear()
proxy.vertex_groups.clear()
r = proxy.modifiers.new('R', 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = VOXEL; r.use_smooth_shade = True
s = proxy.modifiers.new('S', 'SMOOTH'); s.factor = 1.0; s.iterations = ITERS
bpy.context.view_layer.objects.active = proxy; proxy.select_set(True)
bpy.ops.object.modifier_apply(modifier='R')
bpy.ops.object.modifier_apply(modifier='S')
proxy.select_set(False)
print('NORMALS copia remallada:', len(proxy.data.polygons), 'caras (voxel', VOXEL, 'm, smooth', ITERS, 'it)')
if len(proxy.data.polygons) < 5000:
    common.fail('el remallado salio demasiado pobre; revisar VOXEL')

dt = body.modifiers.new('NT', 'DATA_TRANSFER'); dt.object = proxy
dt.use_loop_data = True; dt.data_types_loops = {'CUSTOM_NORMAL'}; dt.loop_mapping = 'POLYINTERP_NEAREST'
while body.modifiers.find('NT') > 0:          # antes del Armature: las normales se transfieren en reposo
    bpy.context.view_layer.objects.active = body; bpy.ops.object.modifier_move_up(modifier='NT')
bpy.context.view_layer.objects.active = body; body.select_set(True)
bpy.ops.object.modifier_apply(modifier='NT')
body.select_set(False)
if not body.data.has_custom_normals:
    common.fail('Body no quedo con normales personalizadas')
mesh_proxy = proxy.data
bpy.data.objects.remove(proxy); bpy.data.meshes.remove(mesh_proxy)
body['normals_smoothed'] = True
print('NORMALS transferidas a Body (normales personalizadas)')

# render de control (mismo encuadre que fix_head_weights)
common.ensure_dirs()
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
common.add_light('NS_key', 'AREA', (-0.8, 1.2, 2.0), 300, (0.9, 0.9, 1.0), size=1.0)
common.add_light('NS_fill', 'AREA', (1.0, 0.8, 1.6), 150, (1.0, 0.95, 0.9), size=1.0)
cam = common.add_camera((0.0, 1.5, 1.45), (0.0, 0.0, 1.45), name='NS_Cam')
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.9
common.render(os.path.join(common.RENDERS, 'normals_smoothed.png'), res=(900, 900), samples=48)
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
if DRY:
    print('NORMALS dry-run; no se guarda')
else:
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('NORMALS OK')

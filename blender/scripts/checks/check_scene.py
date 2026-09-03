# blender/scripts/checks/check_scene.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
need = ['desk', 'chair_seat', 'laptop_base', 'screen_laptop', 'monitor_L', 'monitor_C', 'monitor_R',
        'screen_left', 'screen_center', 'screen_right', 'rgb_bar_L', 'rgb_bar_R', 'shelf',
        'shelf_bracket_0', 'shelf_bracket_1', 'shelf_arm_0', 'shelf_arm_1', 'mug',
        'controller', 'window_far', 'window_near', 'window_head', 'window_post_L', 'window_post_R',
        'wall_back_L', 'wall_back_R', 'wall_back_top', 'wall_back_bottom', 'wall_left', 'wall_right',
        'ceiling', 'floor', 'seat_anchor', 'moto_anchor']
missing = [n for n in need if n not in bpy.data.objects]
if missing: common.fail(f'faltan objetos {missing}')
t = common.scene_tri_count()
if t > 15000: common.fail(f'escena demasiado pesada: {t} tris')
for m in ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop', 'RGB_Bar'):
    if m not in bpy.data.materials: common.fail(f'falta material {m}')
if 'Wall' not in bpy.data.materials: common.fail('falta material Wall')
# box() aplica location/rotation/scale al crear (bpy.ops.object.transform_apply por defecto
# aplica los 3, aunque solo se pida scale=True), asi que .location queda en (0,0,0) para
# todo objeto hecho con box(); hay que leer el centro real en world-space via bound_box.
from mathutils import Vector
def world_center(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector(((min(c.x for c in cs) + max(c.x for c in cs)) / 2,
                    (min(c.y for c in cs) + max(c.y for c in cs)) / 2,
                    (min(c.z for c in cs) + max(c.z for c in cs)) / 2))
sh = bpy.data.objects['shelf']; an = bpy.data.objects['moto_anchor']
sh_c = world_center(sh)
if abs(an.location.z - (sh_c.z + 0.015)) > 1e-3: common.fail('moto_anchor no apoya sobre la repisa')
wl = bpy.data.objects['wall_back_R']
wl_c = world_center(wl)
if not (wl_c.y < sh_c.y < wl_c.y + 0.3): common.fail('la repisa no esta contra la pared trasera')
# Las pantallas y la ventana deben llevar textura real (build_scene.py pone un placeholder
# y avisa con WARNING PLACEHOLDER si falta el PNG; aqui eso es un fallo).
for m in ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop', 'Window_Far'):
    mt = bpy.data.materials.get(m)
    if not mt: common.fail(f'falta material {m}')
    texs = [n for n in mt.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None]
    if not texs: common.fail(f'material {m} sin nodo TEX_IMAGE con imagen (placeholder de build_scene.py)')
    print('TEX', m, texs[0].image.name, tuple(texs[0].image.size))
print('CHECK_SCENE OK tris=', t)

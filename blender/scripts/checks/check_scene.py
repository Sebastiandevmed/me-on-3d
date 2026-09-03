# blender/scripts/checks/check_scene.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
need = ['desk', 'chair_seat', 'laptop_base', 'screen_laptop', 'monitor_L', 'monitor_C', 'monitor_R',
        'screen_left', 'screen_center', 'screen_right', 'rgb_bar_L', 'rgb_bar_R', 'shelf', 'mug',
        'controller', 'window_far', 'window_near', 'floor', 'seat_anchor', 'moto_anchor']
missing = [n for n in need if n not in bpy.data.objects]
if missing: common.fail(f'faltan objetos {missing}')
t = common.scene_tri_count()
if t > 15000: common.fail(f'escena demasiado pesada: {t} tris')
for m in ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop', 'RGB_Bar'):
    if m not in bpy.data.materials: common.fail(f'falta material {m}')
# Las pantallas y la ventana deben llevar textura real (build_scene.py pone un placeholder
# y avisa con WARNING PLACEHOLDER si falta el PNG; aqui eso es un fallo).
for m in ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop', 'Window_Far'):
    mt = bpy.data.materials.get(m)
    if not mt: common.fail(f'falta material {m}')
    texs = [n for n in mt.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None]
    if not texs: common.fail(f'material {m} sin nodo TEX_IMAGE con imagen (placeholder de build_scene.py)')
    print('TEX', m, texs[0].image.name, tuple(texs[0].image.size))
print('CHECK_SCENE OK tris=', t)

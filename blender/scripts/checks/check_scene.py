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
print('CHECK_SCENE OK tris=', t)

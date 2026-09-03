# blender/scripts/sit_test.py
# Prueba de la pose sentada: abre scene.blend, appendea Armature+Body desde character.blend,
# aplica poses.SIT, sienta al personaje sobre 'seat_anchor' y renderiza.
# NUNCA guarda: ni scene.blend ni character.blend deben quedar con la pose aplicada.
# La logica de append + colocacion se reutiliza en la Task 11 (ensamblaje).
# Uso: tools/run_blender.sh - blender/scripts/sit_test.py [-- <nombre_render>]
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import bpy, common, poses
from mathutils import Vector


def append_character(scene_path=None):
    """Abre la escena y trae Armature + mallas Body desde character.blend."""
    bpy.ops.wm.open_mainfile(filepath=scene_path or os.path.join(common.BLEND_DIR, 'scene.blend'))
    with bpy.data.libraries.load(os.path.join(common.BLEND_DIR, 'character.blend')) as (src, dst):
        dst.objects = [n for n in src.objects if n == 'Armature' or n.startswith('Body')]
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
    arm = bpy.data.objects['Armature']
    bodies = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('Body')]
    return arm, bodies


def seat_on_anchor(arm, anchor_name='seat_anchor'):
    """Mueve el armature ya posado para que la cadera caiga sobre el anchor del asiento."""
    anchor = bpy.data.objects[anchor_name]
    bpy.context.view_layer.update()
    hips = (arm.matrix_world @ arm.pose.bones['thighL'].head +
            arm.matrix_world @ arm.pose.bones['thighR'].head) / 2
    target = Vector((anchor.location.x, anchor.location.y, anchor.location.z + poses.SEAT_LIFT))
    arm.location += target - hips
    bpy.context.view_layer.update()
    return arm.location.copy()


def world_verts(bodies):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for b in bodies:
        ev = b.evaluated_get(dg); me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    return pts


def inside(pts, xr, yr, zr):
    return sum(1 for p in pts if xr[0] <= p.x <= xr[1] and yr[0] <= p.y <= yr[1] and zr[0] <= p.z <= zr[1])


def main():
    arm, bodies = append_character()
    poses.apply(arm, poses.SIT)
    seat_on_anchor(arm)

    pts = world_verts(bodies)
    P = lambda n: [round(v, 3) for v in (arm.matrix_world @ arm.pose.bones[n].head)]
    print('POSE hip', P('thighL'), P('thighR'), 'knee', P('shinL'), 'ankle', P('footL'), 'toe', P('toeL'))
    print('POSE wrist', P('handL'), P('handR'), 'elbow', P('forearmL'), 'head', P('spine006'))

    minz = min(p.z for p in pts)
    # nalgas/muslos sobre la huella del asiento: el volumen del asiento es z=0.390..0.470.
    # Lo que cae dentro es el ruedo del hoodie y el pantalon ancho colgando (tela), no el cuerpo.
    seat_box = inside(pts, (-0.25, 0.25), (0.30, 0.80), (0.39, 0.47))
    desk = inside(pts, (-1.0, 1.0), (0.75, 1.55), (0.7225, 0.7575))      # tablero del escritorio
    lap = inside(pts, (-0.16, 0.16), (0.87, 1.09), (0.758, 0.770))       # base del laptop
    lid = inside(pts, (-0.16, 0.16), (1.05, 1.11), (0.77, 0.99))         # tapa/pantalla del laptop
    back = inside(pts, (-0.25, 0.25), (0.28, 0.36), (0.48, 1.08))        # respaldo de la silla
    print('CHECK pies_min_z', round(minz, 4), '(objetivo ~0)')
    hip_z = (arm.matrix_world @ arm.pose.bones['thighL'].head).z
    print('CHECK cadera_sobre_asiento', round(hip_z - 0.470, 4), 'm  verts_dentro_del_asiento', seat_box,
          '(ruedo del hoodie / pantalon, no el cuerpo)')
    print('CHECK verts_en_escritorio', desk, 'en_base_laptop', lap, 'en_tapa_laptop', lid, 'en_respaldo', back)
    print('CHECK bbox_y', round(min(p.y for p in pts), 3), round(max(p.y for p in pts), 3),
          'bbox_z', round(minz, 3), round(max(p.z for p in pts), 3))

    name = (common.args() or ['sit_v_final'])[0]
    common.render(os.path.join(common.RENDERS, f'{name}.png'))

    # vista lateral sin escritorio/monitores para revisar muslos, rodillas y pies
    HIDE = ('desk', 'desk_leg_0', 'desk_leg_1', 'laptop_lid', 'laptop_base', 'screen_laptop',
            'chair_back', 'mug', 'controller',
            'monitor_L', 'monitor_C', 'monitor_R', 'screen_left', 'screen_center', 'screen_right',
            'monitor_base_L', 'monitor_base_C', 'monitor_base_R',
            'monitor_stand_L', 'monitor_stand_C', 'monitor_stand_R')
    cam = bpy.context.scene.camera
    for n in HIDE:
        o = bpy.data.objects.get(n)
        if o: o.hide_render = True
    for l in bpy.data.objects:
        if l.type == 'LIGHT': l.data.energy *= 6
    cam.location = (2.6, 0.75, 1.05); common.look_at(cam, (0, 0.75, 0.75)); cam.data.lens = 45
    common.render(os.path.join(common.RENDERS, f'{name}_legs.png'), res=(900, 640))
    for n in HIDE:
        o = bpy.data.objects.get(n)
        if o: o.hide_render = False
    # primer plano de las manos sobre el teclado
    cam.location = (0.95, 1.75, 1.30); common.look_at(cam, (0, 0.95, 0.80)); cam.data.lens = 55
    common.render(os.path.join(common.RENDERS, f'{name}_hands.png'), res=(900, 640))
    print('NO_SAVE ok (ni scene.blend ni character.blend se modifican)')


if __name__ == '__main__':
    main()

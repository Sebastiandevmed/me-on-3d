# blender/scripts/checks/check_scene_placement.py
# Vigila la clase de fallo que en la sesion 7 mando monitor_L/R a 87 cm de su base, el control
# a 35 cm y la tapa del laptop a 29 cm, y que se veia en el visor como "las pantallas se bugean
# y aparecen lejos del escritorio o no aparecen".
#
# CAUSA: los objetos de la escena se construyen con la geometria ya en coordenadas de MUNDO
# (common.box/plane/cylinder crean la primitiva en su sitio y hornean la transformada). Si
# ademas queda una rotacion VIVA en el objeto, esa rotacion se aplica alrededor del ORIGEN DEL
# MUNDO, no del centro de la pieza, y la manda a volar tan lejos como este del origen. En
# Blender el efecto ya existe; al exportar a glTF viaja igual, porque la rotacion se escribe en
# el nodo mientras los vertices siguen en coordenadas de mundo.
#
# Dos aserciones, las dos baratas:
#   1. Ningun objeto de la escena conserva rotacion viva (todo horneado).
#   2. Cada monitor esta encima de su base y cada pantalla encima de su monitor.
#
# Uso: tools/run_blender.sh blender/scene.blend blender/scripts/checks/check_scene_placement.py
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
from mathutils import Vector

MAX_ROT = math.radians(0.01)   # rad: tolerancia de "rotacion horneada"
MAX_XY = 0.05                  # m de separacion horizontal permitida entre pieza y soporte


def world_center(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector(((min(c.x for c in cs) + max(c.x for c in cs)) / 2,
                   (min(c.y for c in cs) + max(c.y for c in cs)) / 2,
                   (min(c.z for c in cs) + max(c.z for c in cs)) / 2))


# --- 1. nada con rotacion viva
vivos = []
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    # Las piezas EMPARENTADAS (candongas y audifonos cuelgan de un hueso) llevan rotacion viva a
    # proposito: su transformacion es relativa al padre y el exportador la escribe tal cual en el
    # nodo. El bug que motivo este check era otro: common.box() horneaba la localizacion pero no
    # la rotacion, y esa rotacion suelta se aplicaba alrededor del ORIGEN DEL MUNDO sobre
    # geometria que ya estaba a 0.6-1.5 m de el. Eso solo le pasa a objetos sin padre.
    if ob.parent is not None:
        continue
    if any(abs(a) > MAX_ROT for a in ob.rotation_euler):
        vivos.append('%s (%s grados)' % (ob.name, [round(math.degrees(a), 2) for a in ob.rotation_euler]))
if vivos:
    common.fail('objetos con rotacion SIN hornear (se desplazaran al exportar): %s' % vivos)
print('PLACEMENT rotacion horneada en las %d mallas de la escena' % sum(1 for o in bpy.data.objects if o.type == 'MESH'))

# --- 2. cada monitor sobre su base, cada pantalla sobre su monitor
peor = 0.0
for tag, sname in (('L', 'screen_left'), ('C', 'screen_center'), ('R', 'screen_right')):
    mon, base, scr = (bpy.data.objects.get(n) for n in (f'monitor_{tag}', f'monitor_base_{tag}', sname))
    if mon is None or base is None or scr is None:
        common.fail(f'falta monitor_{tag} / monitor_base_{tag} / {sname}')
    cm, cb, cs = world_center(mon), world_center(base), world_center(scr)
    d_base = math.hypot(cm.x - cb.x, cm.y - cb.y)
    d_scr = math.hypot(cs.x - cm.x, cs.y - cm.y)
    peor = max(peor, d_base, d_scr)
    print('PLACEMENT monitor_%s centro %s | base %s (dxy %.3f) | pantalla dxy %.3f'
          % (tag, [round(v, 3) for v in cm], [round(v, 3) for v in cb], d_base, d_scr))
    if d_base > MAX_XY:
        common.fail(f'monitor_{tag} esta a {d_base:.3f} m de su base (tope {MAX_XY}): '
                    'rotacion sin hornear, ver common.box()')
    if d_scr > MAX_XY:
        common.fail(f'{sname} esta a {d_scr:.3f} m de monitor_{tag} (tope {MAX_XY})')

# --- 3. el tope del teclado no se movio: las manos estan calibradas contra esa altura
keys = bpy.data.objects.get('laptop_keys')
if keys is None:
    common.fail('falta laptop_keys')
top = max((keys.matrix_world @ Vector(c)).z for c in keys.bound_box)
esperado = 0.74 + 0.030
if abs(top - esperado) > 0.0005:
    common.fail(f'el tope del teclado esta en z={top:.4f} y deberia estar en {esperado:.4f}: '
                'mover esa altura obliga a recalibrar la pose de las manos (poses.py)')
print('PLACEMENT tope del teclado z=%.4f (esperado %.4f)' % (top, esperado))

print('CHECK_SCENE_PLACEMENT OK (peor separacion %.4f m)' % peor)

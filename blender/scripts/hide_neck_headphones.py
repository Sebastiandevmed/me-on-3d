# blender/scripts/hide_neck_headphones.py
# Task 4: los audifonos que Meshy modelo alrededor del cuello estan FUNDIDOS en la malla Body.
# Para que la pieza nueva (add_headphones.py) pueda subir a la cabeza sin dejar un duplicado
# pegado al cuello, este script encoge hacia el eje del cuello los vertices de las copas
# fundidas: quedan escondidos dentro de la piel del cuello / del collar del hoodie.
#
# COMO SE ELIGEN LOS VERTICES (adaptado del borrador del brief): la malla de Meshy no esta
# soldada, son ~4500 islas sueltas de <=233 vertices cada una. Aprovechando eso, la seleccion
# es POR ISLA (componente conexa): se marca una isla entera si al menos ISLAND_FRAC de sus
# vertices caen en la region de las copas. Asi se mueven copas COMPLETAS y nunca media cara de
# un poligono, que es lo que dejaba abolladuras en el hoodie y en la barba con una mascara
# suavizada por vertice (por eso este script no necesita `feather`).
#
# Region en coordenadas de mundo de character.blend (de pie, mira a +Y, su izquierda en -X),
# medida con cortes horizontales de la malla y renders ortograficos del cuello:
#   * las dos copas son discos en el plano YZ, centro (|x| ~ 0.08, y ~ +0.088, z ~ 1.385),
#     radio ~0.043; sus paredes van de |x| = 0.055 (cara interna, pegada al cuello) a
#     |x| = 0.11 (cara externa).
#   * el cuello y la barbilla viven en |x| < 0.045; el collar y la capucha del hoodie estan
#     DETRAS (y < +0.02) y no se pueden tocar: de ahi el limite inferior de Y_RANGE.
#
# El encogido es radial hacia el eje del cuello, que se lee del hueso NECK_BONE (no es una
# constante magica: el eje anatomico esta en y ~ -0.009, DETRAS del centro geometrico que se
# ve de frente). Cada vertice se lleva a radio <= TARGET_R, bien dentro de la piel.
#
# Se calibra con `--probe` (pinta la seleccion sobre la malla y renderiza; no guarda) y se
# aplica sin argumentos (guarda character.blend en sitio). `--dry-run` hace todo menos guardar.
# Idempotente: si Body['neck_headphones_hidden'] ya esta puesto, no hace nada.
#
# Los renders son ORTOGRAFICOS y centrados en (0, 0, CAM_Z) con ORTHO_SCALE m de ancho, asi que
# el mapeo pixel -> mundo es exacto y las constantes se pueden releer de la imagen:
#   frontal (camara en +Y):  x = -(px - W/2) * ORTHO_SCALE/W    z = CAM_Z - (py - H/2) * ORTHO_SCALE/H
#   lateral (camara en +X):  y = +(px - W/2) * ORTHO_SCALE/W    z = idem
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/hide_neck_headphones.py [-- --probe|--dry-run]
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector

X_RANGE = (0.047, 0.140)       # m: |x| de la region (cara interna .. externa de las copas)
Y_RANGE = (0.030, 0.155)       # m: y de la region (delante del cuello; el collar queda en y<0.02)
Z_RANGE = (1.325, 1.450)       # m: z de la region (alto de los discos de las copas)
R_MIN = 0.047                  # m: radio XY minimo al eje del cuello (protege cuello y barbilla)
ISLAND_FRAC = 0.5              # fraccion de vertices dentro de la region para marcar la isla
NECK_BONE = 'spine005'         # el eje del cuello se lee de la cabeza de este hueso
TARGET_R = 0.022               # m: radio maximo al que se encogen (dentro de la piel del cuello)
CAM_Z = 1.39                   # m: centro de los renders de control
ORTHO_SCALE = 0.40             # m de ancho de los renders ortograficos
RES = (900, 900)

args = common.args()
PROBE, DRY = '--probe' in args, '--dry-run' in args
body = bpy.data.objects.get('Body')
if not body:
    common.fail('no hay malla Body en el .blend')
arm = bpy.data.objects.get('Armature')
if not arm or NECK_BONE not in arm.data.bones:
    common.fail(f'no hay Armature con el hueso {NECK_BONE}')
if body.get('neck_headphones_hidden') and not PROBE:
    print('HP_HIDE ya aplicado; nada que hacer')
    sys.exit(0)

neck = arm.matrix_world @ arm.data.bones[NECK_BONE].head_local
AXIS = (neck.x, neck.y)
print('HP_HIDE eje del cuello (de', NECK_BONE + ')', [round(v, 4) for v in AXIS])
mw = body.matrix_world
mwi = mw.inverted()


def inside(p):
    """True si el vertice p (mundo) cae en la region de las copas fundidas."""
    return (X_RANGE[0] <= abs(p.x) <= X_RANGE[1] and Y_RANGE[0] <= p.y <= Y_RANGE[1]
            and Z_RANGE[0] <= p.z <= Z_RANGE[1]
            and math.hypot(p.x - AXIS[0], p.y - AXIS[1]) >= R_MIN)


def islands(mesh):
    """Componentes conexas de la malla -> {raiz: [indices de vertice]} (union-find)."""
    par = list(range(len(mesh.vertices)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for e in mesh.edges:
        ra, rb = find(e.vertices[0]), find(e.vertices[1])
        if ra != rb:
            par[ra] = rb
    out = {}
    for i in range(len(mesh.vertices)):
        out.setdefault(find(i), []).append(i)
    return out


pts = [mw @ v.co for v in body.data.vertices]
isl = islands(body.data)
sel, rejected, n_isl = set(), set(), 0
for idxs in isl.values():
    n_in = sum(1 for i in idxs if inside(pts[i]))
    if not n_in:
        continue
    if n_in / len(idxs) >= ISLAND_FRAC:
        sel.update(idxs)
        n_isl += 1
    else:
        rejected.update(idxs)
print('HP_HIDE islas', len(isl), '-> copas', n_isl, 'islas /', len(sel), 'vertices',
      '(descartadas por mayoria:', len(rejected), 'vertices)')
if not sel:
    common.fail('la region no selecciona ninguna isla: recalibrar X/Y/Z_RANGE')
bb = [round(f, 4) for f in (min(pts[i].x for i in sel), max(pts[i].x for i in sel),
                            min(pts[i].y for i in sel), max(pts[i].y for i in sel),
                            min(pts[i].z for i in sel), max(pts[i].z for i in sel))]
print('HP_HIDE bbox de la seleccion x', bb[0:2], 'y', bb[2:4], 'z', bb[4:6])

if PROBE:
    # rojo = isla marcada (se encoge entera); naranja = isla que toca la region pero se descarta
    slots = len(body.data.materials)
    body.data.materials.append(common.mat('HP_probe', (1.0, 0.02, 0.02, 1), roughness=0.9))
    body.data.materials.append(common.mat('HP_probe_soft', (1.0, 0.45, 0.0, 1), roughness=0.9))
    for poly in body.data.polygons:
        if any(vi in sel for vi in poly.vertices):
            poly.material_index = slots
        elif any(vi in rejected for vi in poly.vertices):
            poly.material_index = slots + 1
else:
    moved = 0
    for vi in sel:
        p = pts[vi]
        r = math.hypot(p.x - AXIS[0], p.y - AXIS[1])
        if r <= TARGET_R:
            continue
        k = TARGET_R / r
        q = Vector((AXIS[0] + (p.x - AXIS[0]) * k, AXIS[1] + (p.y - AXIS[1]) * k, p.z))
        body.data.vertices[vi].co = mwi @ q
        moved += 1
    body.data.update()
    body['neck_headphones_hidden'] = True
    print('HP_HIDE vertices encogidos', moved, 'a radio <=', TARGET_R)

# ------------------------------------------------------------------ renders de control
common.ensure_dirs()
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
common.add_light('HP_key', 'AREA', (-0.8, 1.2, 1.9), 300, (0.9, 0.9, 1.0), size=1.0)
common.add_light('HP_fill', 'AREA', (1.0, 0.8, 1.4), 150, (1.0, 0.95, 0.9), size=1.0)
common.add_light('HP_back', 'AREA', (0.0, -1.2, 1.8), 200, (1.0, 1.0, 1.0), size=1.0)
tag = 'probe' if PROBE else 'hidden'
cam = common.add_camera((0.0, 1.5, CAM_Z), (0.0, 0.0, CAM_Z), name='HP_Cam')
cam.data.type = 'ORTHO'
cam.data.ortho_scale = ORTHO_SCALE
common.render(os.path.join(common.RENDERS, f'headphones_{tag}_front.png'), res=RES, samples=48)
cam.location = (1.5, 0.0, CAM_Z)
common.look_at(cam, (0.0, 0.0, CAM_Z))
common.render(os.path.join(common.RENDERS, f'headphones_{tag}_side.png'), res=RES, samples=48)

for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        bpy.data.objects.remove(o)
if PROBE:
    print('HP_HIDE probe renderizado; no se guarda')
elif DRY:
    print('HP_HIDE dry-run; no se guarda')
else:
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('HP_HIDE OK')

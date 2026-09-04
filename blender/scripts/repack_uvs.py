# blender/scripts/repack_uvs.py
# Las "vetas claras" del hoodie en el visor NO son geometria ni sombras ni Draco (se probaron una a
# una con la sonda): son sangrado de mipmaps. Meshy empaqueta ~4500 islas UV minusculas casi
# pegadas (el 57 % del gutter esta a menos de 2 px de alguna isla, el 86 % a menos de 8 px), asi
# que en cuanto three.js reduce la textura con la distancia, la piel clara de una isla se mezcla
# con el negro del hoodie de la vecina. Sin mipmaps desaparece (probado), pero sin mipmaps la
# textura chisporrotea.
#
# Arreglo de fondo: reempaquetar con margen de verdad. Empaquetar las 4500 islas de Meshy con margen
# no sirve (probado: 12 px de margen dejan la cobertura en 5.8 %, escala 0.30), porque el problema es
# el NUMERO de islas, no el margen. Asi que primero se suelda la malla (Meshy la entrega sin soldar,
# 44030 vertices -> ~21000 a 0.5 mm) y se re-desenvuelve con Smart UV Project por angulo, que da
# pocas islas grandes; luego se hornea la textura vieja al mapa nuevo. Se hace en numpy (sin Cycles): para cada triangulo se rasteriza su version en el UV
# nuevo, se pasa por baricentricas al UV viejo y se muestrea bilineal la textura vieja. Despues,
# fix_character_material.py rasteriza la mascara y rellena los canales sobre el layout nuevo (con
# PAD mas ancho) y hace su limpieza normal; check_character_material.py sigue midiendo la fuga.
#
# Entrada: generated/character_texture_logo.png (salida de apply_chest_logo.py, que trabaja en el
# UV ORIGINAL por componentes de texel: por eso este script va DESPUES de el).
# Salida: generated/character_texture_repacked.png (SIZE x SIZE) y Body con un solo mapa UV
# ('UVRepack', el original se borra para no exportar dos TEXCOORD). Idempotente: Body['uv_repacked'].
# Borra Body['normals_smoothed'] para que smooth_normals.py se repita sobre la malla soldada.
# --probe: empaqueta y mide (cobertura, histograma de gutter) sin hornear ni guardar.
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/repack_uvs.py [--probe|--dry-run]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np

SRC = os.path.join(common.GEN, 'character_texture_logo.png')
OUT = os.path.join(common.GEN, 'character_texture_repacked.png')
SIZE = 4096            # el layout nuevo cubre ~40 % (Smart UV deja margen); a 4096 la densidad de texel queda en 1.57x la de Meshy
MARGIN_PX = 8           # margen entre islas en px de SIZE (8/4096 = la misma fraccion que el 4/2048 del barrido: 89/8px@2048 -> escala 0.65, 89/4px@2048 -> 0.79, 75/4 -> 0.75)
WELD = 0.0005           # m: distancia de soldado de vertices coincidentes
ANGLE = 66.0            # grados: limite de Smart UV Project. A 89 las dos caras de un dedo caen en la misma zona UV
                        # (10 % de los texeles de las manos solapados -> dedos negros); a 66 hay mas islas pero sin solape
OLD_ATTR = 'uv_meshy'   # el UV original de Meshy se guarda como atributo de esquina (no se exporta) para poder repetir el paso
NEW_UV = 'UVRepack'

args = common.args()
PROBE, DRY = '--probe' in args, '--dry-run' in args
body = bpy.data.objects.get('Body')
if not body:
    common.fail('no hay malla Body en el .blend')
if body.get('uv_repacked') and not PROBE:
    print('REPACK ya aplicado; nada que hacer')
    sys.exit(0)
if not os.path.exists(SRC):
    common.fail(f'falta {SRC} (ejecutar apply_chest_logo.py antes)')
me = body.data
if me.uv_layers.active is None:
    common.fail('Body sin capa UV')
if OLD_ATTR in me.attributes:      # ya se reempaqueto antes (flag borrado a mano para repetir): restaurar el UV de Meshy
    src_attr = me.attributes[OLD_ATTR]
    vals = np.empty(len(src_attr.data) * 2, dtype=np.float32); src_attr.data.foreach_get('vector', vals)
    for l in list(me.uv_layers):
        me.uv_layers.remove(l)
    restored = me.uv_layers.new(name='UVMap'); restored.data.foreach_set('uv', vals); me.uv_layers.active = restored
    print('REPACK UV de Meshy restaurado desde el atributo', OLD_ATTR)
old_name = me.uv_layers.active.name

# --- 0. soldar (las UV por loop sobreviven; los pesos se quedan con el vertice que sobrevive)
import bmesh
bm = bmesh.new(); bm.from_mesh(me); n0 = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD)
bm.to_mesh(me); bm.free(); me.update()
print('REPACK soldado a %.1f mm: vertices %d -> %d (caras %d)' % (WELD * 1000, n0, len(me.vertices), len(me.polygons)))


def gutter_stats(mask):
    """Porcentaje del gutter que queda a mas de r px de cualquier isla (islas pegadas => cae rapido)."""
    tot = (~mask).sum()
    out = {}
    for r in (2, 4, 8, 16):
        d = mask.copy()
        for _ in range(r):
            d |= np.roll(d, 1, 0) | np.roll(d, -1, 0) | np.roll(d, 1, 1) | np.roll(d, -1, 1)
        out[r] = float((~d).sum() / tot * 100)
    return out


def tri_list(uv_layer):
    """Triangulos (fan) con sus UV: lista de (loop_indices) y arrays (n,3,2) de UV."""
    uv = uv_layer.data
    tris = []
    for poly in me.polygons:
        li = list(poly.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append((li[0], li[k], li[k + 1]))
    tris = np.array(tris, dtype=np.int64)
    coords = np.empty((len(uv), 2), dtype=np.float64)
    uv.foreach_get('uv', coords.ravel())
    return tris, coords[tris]


def raster_mask(uvs, size):
    mask = np.zeros((size, size), dtype=bool)
    for t in uvs:
        xs = t[:, 0] * size; ys = (1.0 - t[:, 1]) * size
        x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(size - 1, np.ceil(xs.max()) + 1))
        y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(size - 1, np.ceil(ys.max()) + 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(d) < 1e-9: continue
        w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
        w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
        w2 = 1.0 - w0 - w1
        mask[y0:y1 + 1, x0:x1 + 1] |= (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
    return mask


# --- 1. mascara y gutter del layout ORIGINAL (para el log de antes/despues) + copia en atributo
tris, uv_old = tri_list(me.uv_layers[old_name])
if OLD_ATTR in me.attributes:
    me.attributes.remove(me.attributes[OLD_ATTR])
stash = me.attributes.new(OLD_ATTR, 'FLOAT2', 'CORNER')
buf = np.empty((len(me.loops), 2), dtype=np.float32); me.uv_layers[old_name].data.foreach_get('uv', buf.ravel())
stash.data.foreach_set('vector', buf.ravel())
mask_old = raster_mask(uv_old, SIZE)
print('REPACK antes: cobertura %.1f %%, gutter lejos de islas' % (mask_old.mean() * 100),
      {k: round(v, 1) for k, v in gutter_stats(mask_old).items()})

# --- 2. nuevo mapa UV empaquetado con margen
if NEW_UV in me.uv_layers:
    me.uv_layers.remove(me.uv_layers[NEW_UV])
new = me.uv_layers.new(name=NEW_UV, do_init=True)   # copia del activo
me.uv_layers.active = new
for o in bpy.data.objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = body; body.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.mesh.select_all(action='SELECT')
import math
bpy.ops.uv.smart_project(angle_limit=math.radians(ANGLE), island_margin=MARGIN_PX / SIZE, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
body.select_set(False)
tris2, uv_new = tri_list(me.uv_layers[NEW_UV])
assert (tris2 == tris).all()
mask_new = raster_mask(uv_new, SIZE)
print('REPACK despues: cobertura %.1f %%, gutter lejos de islas' % (mask_new.mean() * 100),
      {k: round(v, 1) for k, v in gutter_stats(mask_new).items()})
# densidad de texel relativa: area UV nueva / vieja (misma malla) -> escala lineal
def area(uv):
    a = uv[:, 1] - uv[:, 0]; b = uv[:, 2] - uv[:, 0]
    return float(np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum() / 2)
scale = (area(uv_new) / area(uv_old)) ** 0.5
print('REPACK escala lineal de texeles nueva/vieja = %.3f' % scale)
if scale < 0.6:
    common.fail('el reempaquetado pierde demasiada resolucion (escala %.2f): bajar MARGIN_PX' % scale)
if PROBE:
    print('REPACK probe; no se hornea ni se guarda')
    sys.exit(0)

# --- 3. hornear: textura vieja (UV viejo) -> textura nueva (UV nuevo), bilineal
src = bpy.data.images.load(SRC, check_existing=True); src.reload()
w, h = src.size
px = np.empty(w * h * 4, dtype=np.float32); src.pixels.foreach_get(px)
img = px.reshape(h, w, 4)[::-1, :, :3].astype(np.float32)   # arriba primero


def sample(u, v):
    """Muestreo bilineal de img en UV (arrays), con clamp."""
    x = u * w - 0.5; y = (1.0 - v) * h - 0.5
    x0 = np.clip(np.floor(x).astype(int), 0, w - 1); y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    x1 = np.clip(x0 + 1, 0, w - 1); y1 = np.clip(y0 + 1, 0, h - 1)
    fx = np.clip(x - x0, 0, 1)[..., None]; fy = np.clip(y - y0, 0, 1)[..., None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


out = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
done = np.zeros((SIZE, SIZE), dtype=bool)
contested = 0
for tn, to in zip(uv_new, uv_old):
    xs = tn[:, 0] * SIZE; ys = (1.0 - tn[:, 1]) * SIZE
    x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(SIZE - 1, np.ceil(xs.max()) + 1))
    y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(SIZE - 1, np.ceil(ys.max()) + 1))
    if x1 < x0 or y1 < y0: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
    if abs(d) < 1e-9: continue
    w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
    w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
    w2 = 1.0 - w0 - w1
    eps = -0.002
    inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
    sub = done[y0:y1 + 1, x0:x1 + 1]
    take = inside & ~sub                      # el primer triangulo que cubre un texel manda (los bordes estirados no pisan interiores)
    contested += int((inside & sub & (w0 > 0.02) & (w1 > 0.02) & (w2 > 0.02)).sum())   # interior real ya ocupado = solape
    if not take.any(): continue
    # baricentricas recortadas al triangulo para no muestrear fuera de la isla vieja
    W = np.stack([w0, w1, w2], axis=-1); W = np.clip(W, 0, None); W /= W.sum(axis=-1, keepdims=True)
    uv_src = W @ to                            # (H, W, 2)
    col = sample(uv_src[..., 0], uv_src[..., 1])
    blk = out[y0:y1 + 1, x0:x1 + 1]
    blk[take] = col[take]
    sub |= take
print('REPACK horneado: texeles cubiertos %.1f %% (mascara %.1f %%); texeles disputados (solape entre triangulos) %.2f %%'
      % (done.mean() * 100, mask_new.mean() * 100, contested / max(1, done.sum()) * 100))
if contested / max(1, done.sum()) > 0.02:
    common.fail('demasiado solape UV en el horneado (%.1f %%): bajar ANGLE' % (contested / done.sum() * 100))
if abs(done.mean() - mask_new.mean()) > 0.02:
    common.fail('el horneado no cubre la mascara nueva; revisar rasterizado')

# --- 4. guardar la textura horneada y repuntar el material (fix_character_material.py la usara como SRC)
outimg = bpy.data.images.get('character_texture_repacked') or bpy.data.images.new('character_texture_repacked', SIZE, SIZE, alpha=False)
outimg.scale(SIZE, SIZE)
buf = np.ones((SIZE, SIZE, 4), dtype=np.float32); buf[..., :3] = np.clip(out[::-1], 0, 1)
outimg.pixels.foreach_set(buf.ravel())
outimg.filepath_raw = OUT; outimg.file_format = 'PNG'; outimg.save(); outimg.reload()
print('REPACK guardada', OUT)
mat = bpy.data.materials.get('Character')
if mat and mat.use_nodes:
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None:
            n.image = outimg
# --- 5. dejar un solo mapa UV
me.uv_layers.remove(me.uv_layers[old_name])
me.uv_layers.active = me.uv_layers[NEW_UV]
me.uv_layers[NEW_UV].active_render = True
body['uv_repacked'] = True
if 'normals_smoothed' in body:      # la soldadura cambio la topologia: smooth_normals.py debe repetirse
    del body['normals_smoothed']
if DRY:
    print('REPACK dry-run; no se guarda')
else:
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('REPACK OK')

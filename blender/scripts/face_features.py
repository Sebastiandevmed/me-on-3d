# blender/scripts/face_features.py
# Retoque de las FACCIONES sobre generated/character_texture_clean.png. Va DESPUES de
# texture_touchup.py (que a su vez va despues de la segunda pasada de fix_character_material.py,
# porque esa regenera la textura desde cero y se llevaria por delante cualquier retoque).
#
# QUE ARREGLA (medido con --flat y --probe antes de tocar nada):
#   Meshy pinto una barba que cubre mandibula y mejillas, pero dejo TODO el menton y la zona de
#   la boca como una sola mancha de piel plana de ~5.8 cm de alto, sin labios y con una muesca
#   oscura abajo. En el visor eso se lee como una placa clara en mitad de la barba (y la muesca
#   como un diente). Sebastian lleva barba completa cerrada: se cierra la barba sobre el menton
#   y se deja una banda de labios con su tono.
#
# COMO: por texel, no por UV. El atlas reempaquetado son miles de islas sueltas, asi que dos
# texeles vecinos en la textura pueden estar en partes del cuerpo sin relacion. Se rasteriza cada
# triangulo de la cara y se calcula por baricentricas la posicion de MUNDO de cada texel; todas
# las decisiones se toman con esa posicion.
#
# DOS TRAMPAS que costaron varias pasadas, y por las que existe el modo --probe:
#   1. `image.pixels` de bpy entrega la imagen de ABAJO a ARRIBA y el rasterizado usa
#      y = (1 - v) * S ("arriba primero"). Sin voltear, la mascara sale espejada en vertical y
#      se pinta sobre islas que no tienen nada que ver: la zona de la cara caia sobre el hoodie.
#      Es la misma convencion de fix_character_material.py y texture_touchup.py.
#   2. `image.pixels` devuelve LINEAR (la textura esta marcada como sRGB). La piel del personaje
#      es sRGB 0.94/0.58/0.48, que en lineal cae a 0.45 de luminancia: con umbrales pensados
#      "a ojo" la cara entera se clasificaba como barba. Aqui se clasifica en sRGB.
#
# MEDIDO (--probe): la cara separa limpiamente en dos grupos por color, sin solape.
#   piel (r-b > 0.10): luminancia sRGB p5..p95 = 0.60 .. 0.86
#   pelo (r-b <= 0.10): luminancia sRGB p5..p95 = 0.31 .. 0.43
#
# Idempotente: al rellenar con color de barba, repetirlo ya no encuentra piel en la zona.
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/face_features.py
#   -- --probe   no escribe: imprime el mapa y renderiza la mascara sobre la cara
#   -- --flat    no escribe: renderiza la textura tal cual (plana, sin luz) para verla
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np

TEX = os.path.join(common.GEN, 'character_texture_clean.png')

# --- zona: caras frontales del craneo. Baja hasta 1.425 porque el menton esta en z ~1.444.
FACE_NY = 0.15          # normal.y minima (las patillas y los lados miran de costado)
FACE_Y_MIN = 0.02       # m por delante del eje de la cabeza (descarta la nuca)
FACE_Z_MIN = 1.425
FACE_X_MAX = 0.105      # m: mas alla estan las orejas

# --- clasificacion por color, en sRGB (ver "trampa 2").
SKIN_LUM = 0.55         # piel: clara...
SKIN_RED = 0.10         # ...y rojiza (r - b)
HAIR_LUM = 0.50         # pelo/barba: oscuro y sin rojo

# --- barba del menton. Todo relativo a la altura de los ojos (landmarks eye_L/R).
# El techo va ALTO a proposito: solo se rellena piel, y el bigote es pelo, asi que el borde
# de arriba lo pone la propia frontera piel/bigote y no una linea recta. Con 0.063 el corte
# recto del techo se veia como el borde de una caja.
CHIN_TOP = 0.055        # m bajo los ojos
# 0.065 y no 0.055: el difuminado del borde se come 8 mm, y a 0.055 las esquinas de arriba
# de la mancha de piel se quedaban sin rellenar y se veian como dos recuadros claros.
# Ensanchar es inofensivo porque solo se rellena PIEL, y mas alla ya es barba.
CHIN_X = 0.065          # m de medio ancho
CHIN_SOFT = 0.008       # m de borde difuminado
GRAIN = 0.5             # cuanto grano de la piel original se conserva al teñir (0 = plano)

# --- labios: la banda que NO se rellena, entre el bigote y el menton.
LIP_Z_TOP = 0.068       # m bajo los ojos
LIP_Z_BOT = 0.082       # m bajo los ojos
LIP_X = 0.018           # m de medio ancho
# Factor sobre la piel local. Con 0.62/0.40/0.38 la boca salia salmon y a tamaño real se
# leia como un caramelo pegado en mitad de la barba: en cel, con bandas y contorno, un tono
# claro en medio de una masa oscura canta mucho mas que en PBR.
LIP_TINT = (0.42, 0.26, 0.25)
# Radio (en m) alrededor del menton del que se saca el color de la barba. Sacarlo de TODO
# el pelo de la cabeza mete la gorra en la mediana y el relleno sale mas claro que la
# barba de al lado: se veia un recuadro gris en mitad de la barba.
BEARD_NEAR = 0.020
# Percentil y no mediana: la barba vecina incluye sus propias luces, y con la mediana el
# relleno salia un punto mas claro que la barba de alrededor y se leia el recuadro.
BEARD_PCT = 30


def face_texels(me, mw, S):
    """Rasteriza las caras frontales del craneo sobre el atlas.

    Devuelve (zone, wx, wy, wz, ntri): mascara SxS y la posicion de mundo de cada texel, por
    baricentricas del triangulo que lo cubre. Indices "arriba primero".
    """
    m3 = mw.to_3x3()
    uv = np.array([l.uv[:] for l in me.uv_layers.active.data], dtype=np.float64)
    zone = np.zeros((S, S), dtype=bool)
    wx = np.zeros((S, S), np.float32); wy = np.zeros((S, S), np.float32); wz = np.zeros((S, S), np.float32)
    ntri = 0
    for p in me.polygons:
        c = mw @ p.center
        if c.z < FACE_Z_MIN or c.y < FACE_Y_MIN or abs(c.x) > FACE_X_MAX:
            continue
        if (m3 @ p.normal).normalized().y < FACE_NY:
            continue
        ntri += 1
        li = list(p.loop_indices)
        for k in range(1, len(li) - 1):
            idx = [li[0], li[k], li[k + 1]]
            t = uv[idx]
            xs = t[:, 0] * S; ys = (1.0 - t[:, 1]) * S
            x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(S - 1, np.ceil(xs.max()) + 1))
            y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(S - 1, np.ceil(ys.max()) + 1))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
            if abs(d) < 1e-9:
                continue
            w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
            w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
            if not inside.any():
                continue
            P = [mw @ me.vertices[me.loops[i].vertex_index].co for i in idx]
            sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
            for arr, comp in ((wx, 0), (wy, 1), (wz, 2)):
                v = w0 * P[0][comp] + w1 * P[1][comp] + w2 * P[2][comp]
                sub = arr[sl]; sub[inside] = v[inside]
            zone[sl] |= inside
    return zone, wx, wy, wz, ntri


def to_srgb(a):
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.clip(a, 0, None), 1 / 2.4) - 0.055)


def to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def ramp(v, lo, hi):
    """0 por debajo de lo, 1 por encima de hi, con suavizado en medio."""
    t = np.clip((v - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def render_probe(img, px, dbg, lm, name):
    """Pinta `dbg` (sRGB) en el material como EMISION y renderiza la cara de frente.

    Emision y no color base porque character.blend no tiene luces: un render normal sale casi
    negro y no se distingue nada. En --probe no se guarda nada a disco.
    """
    px[..., :3] = to_linear(dbg)
    img.pixels.foreach_set(px[::-1, :, :].ravel())
    nt = bpy.data.materials['Character'].node_tree
    bsdf = nt.nodes['Principled BSDF']
    nt.links.new(bsdf.inputs['Base Color'].links[0].from_socket, bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.0
    bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
    hz = float(lm['eye_L'][2])
    cam = common.add_camera((0, 1.2, hz), (0, 0, hz), lens=85)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.34
    bpy.context.scene.camera = cam
    common.render(os.path.join(common.RENDERS, name), res=(1000, 1000))


def main():
    common.ensure_dirs()
    args = common.args()
    FLAT = '--flat' in args
    PROBE = '--probe' in args or FLAT

    body = bpy.data.objects.get('Body')
    if body is None:
        common.fail('falta Body')
    me = body.data; mw = body.matrix_world
    with open(common.LANDMARKS) as f:
        lm = json.load(f)
    eye_z = (lm['eye_L'][2] + lm['eye_R'][2]) / 2.0

    img = bpy.data.materials['Character'].node_tree.nodes['Principled BSDF'] \
        .inputs['Base Color'].links[0].from_node.image
    if img is None or not img.filepath_raw.endswith('character_texture_clean.png'):
        common.fail('el material no apunta a character_texture_clean.png (ejecutar fix_character_material.py)')
    S = img.size[0]
    buf = np.empty(S * S * 4, np.float32); img.pixels.foreach_get(buf)
    px = buf.reshape(S, S, 4)[::-1, :, :].copy()      # ver "trampa 1"
    rgb = px[..., :3].copy()
    srgb = to_srgb(rgb)                                # ver "trampa 2"
    lum = srgb.mean(2)
    red = srgb[..., 0] - srgb[..., 2]

    zone, wx, wy, wz, ntri = face_texels(me, mw, S)
    if ntri == 0 or zone.sum() < 20000:
        common.fail(f'zona de cara improbable (caras {ntri}, texeles {int(zone.sum())}): revisar FACE_*')
    is_skin = zone & (lum > SKIN_LUM) & (red > SKIN_RED)
    is_hair = zone & (lum < HAIR_LUM) & (red <= SKIN_RED)
    print('FACE %d caras, %d texeles (piel %d, pelo %d); z %.4f..%.4f, ojos z=%.4f'
          % (ntri, zone.sum(), is_skin.sum(), is_hair.sum(),
             wz[zone].min(), wz[zone].max(), eye_z))

    below = zone & (np.abs(wx) <= CHIN_X) & (wz <= eye_z - CHIN_TOP)
    # Elipse y no rectangulo: una banda recta de labios en mitad de la barba se lee como una
    # cinta pegada. La elipse se afila en las comisuras, que es como termina una boca.
    lip_zc = eye_z - (LIP_Z_TOP + LIP_Z_BOT) / 2.0
    lip_hz = (LIP_Z_BOT - LIP_Z_TOP) / 2.0
    lip_r = np.sqrt((wx / LIP_X) ** 2 + ((wz - lip_zc) / lip_hz) ** 2)
    lips = zone & (lip_r <= 1.0)
    fill = is_skin & below & ~lips

    if PROBE:
        for name, m in (('zona', zone), ('piel', is_skin), ('pelo', is_hair),
                        ('menton', below), ('labios', lips), ('relleno', fill)):
            print('  %-8s %8d texeles' % (name, int(m.sum())))
        for name, m in (('piel', is_skin), ('pelo', is_hair)):
            q = np.percentile(lum[m], [5, 50, 95]) if m.any() else [0, 0, 0]
            print('  LUM %-5s p5/p50/p95 %s' % (name, ' '.join('%.3f' % v for v in q)))
        dbg = srgb.copy()
        if not FLAT:
            dbg[zone] = dbg[zone] * 0.4 + np.array([0.0, 0.0, 0.5], np.float32)
            dbg[fill] = np.array([0.95, 0.15, 0.15], np.float32)
            dbg[lips] = np.array([0.15, 0.95, 0.25], np.float32)
        render_probe(img, px, dbg, lm, 'face_probe_%s.png' % ('flat' if FLAT else 'front'))
        return

    if not is_hair.any():
        common.fail('no se encontro barba de donde sacar el color (revisar HAIR_LUM)')
    if fill.sum() < 2000:
        common.fail('la zona de menton a rellenar tiene solo %d texeles: revisar CHIN_*' % int(fill.sum()))

    # Borde difuminado por arriba (hacia el bigote), por los lados y alrededor de los labios.
    # El difuminado de arriba va POR ENCIMA del techo, no por debajo: si no, la franja de
    # piel justo bajo el bigote se queda a medio teñir y se ve el corte. Arriba del techo solo
    # hay bigote (pelo), que no se rellena.
    w = ramp((eye_z - CHIN_TOP + CHIN_SOFT / 2) - wz, 0.0, CHIN_SOFT / 2)
    w = np.minimum(w, ramp(CHIN_X - np.abs(wx), 0.0, CHIN_SOFT))
    # Transicion CORTA alrededor de la boca (1.5 mm). Con el mismo difuminado que el resto
    # del borde, la barba solo llegaba a peso 1 en lip_r = 1.7 y quedaba un anillo de piel
    # entre el labio y la barba, que se leia como una mancha.
    w = np.minimum(w, ramp((lip_r - 1.0) * lip_hz, 0.0, 0.0015))
    w = w * fill

    near = is_hair & (np.abs(wx) <= CHIN_X + BEARD_NEAR) & (wz <= eye_z - CHIN_TOP + BEARD_NEAR)
    if near.sum() < 500:
        common.fail('no hay barba alrededor del menton de donde sacar el color (%d texeles)' % int(near.sum()))
    beard = np.percentile(rgb[near], BEARD_PCT, axis=0)
    skin_lum = float(np.median(lum[is_skin]))
    grain = 1.0 + GRAIN * (lum[..., None] / max(skin_lum, 1e-3) - 1.0)
    rgb = rgb * (1 - w[..., None]) + np.clip(beard[None, None, :] * grain, 0, 1) * w[..., None]
    print('BARBA menton: %d texeles teñidos (peso medio %.2f), color sRGB %s de %d texeles de barba vecina'
          % (int((w > 0.01).sum()), float(w[w > 0.01].mean()),
             [round(float(c), 3) for c in to_srgb(beard)], int(near.sum())))

    # --- labios: la banda queda como piel plana; se le da tono para que se lea una boca.
    lip_skin = lips & (lum > SKIN_LUM)
    if lip_skin.sum() > 200:
        base = np.median(rgb[is_skin & ~lips], axis=0)
        tint = np.clip(base * np.array(LIP_TINT, np.float32), 0, 1)
        lw = ramp(1.0 - lip_r, 0.0, 0.06) * lip_skin   # borde corto: a 0.22 la boca se veia difuminada
        rgb = rgb * (1 - lw[..., None]) + tint[None, None, :] * lw[..., None]
        print('LABIOS %d texeles, tono sRGB %s'
              % (int((lw > 0.01).sum()), [round(float(c), 3) for c in to_srgb(tint)]))
    else:
        print('LABIOS zona sin piel que teñir (%d texeles)' % int(lip_skin.sum()))

    px[..., :3] = rgb
    img.pixels.foreach_set(px[::-1, :, :].ravel())
    img.filepath_raw = TEX; img.file_format = 'PNG'; img.save()
    print('FACE_FEATURES textura guardada', TEX)
    common.save(bpy.data.filepath)


main()

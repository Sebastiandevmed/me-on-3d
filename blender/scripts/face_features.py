# blender/scripts/face_features.py
# Retoque de las FACCIONES sobre generated/character_texture_clean.png. Va DESPUES de
# texture_touchup.py (que a su vez va despues de la segunda pasada de fix_character_material.py,
# porque esa regenera la textura desde cero y se llevaria por delante cualquier retoque).
#
# QUE ARREGLA (medido con --flat y --probe antes de tocar nada):
#   Meshy pinta la barba bien —bigote, mandibula y perilla— pero deja la zona de la BOCA como
#   piel plana, sin labios. En el visor eso se lee como una placa palida en mitad de la cara.
#   Este script dibuja ahi los labios y la linea de abertura. NADA MAS: la barba de Meshy no
#   se toca (ver el bloque "LA BARBA NO SE TOCA" mas abajo, y por que rellenarla fue un error).
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
#   2. ESPACIO DE COLOR. El comentario que habia aqui decia que `image.pixels` devuelve LINEAR.
#      Es FALSO para esta imagen, y costo un bug entero: medido en la sesion 8, el PNG guarda la
#      piel de Meshy como (236, 158, 133), que es el skin_srgb del landmark, o sea que `pixels`
#      entrega sRGB. Por eso `srgb = to_srgb(rgb)` es una conversion de MAS, y por eso la
#      luminancia de la piel que imprime --probe da 0.849 y no 0.665.
#      - Los umbrales de clasificacion (SKIN_LUM, HAIR_LUM, SKIN_RED) estan calibrados contra
#        ESE espacio doblemente convertido y funcionan: no se tocan.
#      - Pero un color que se ESCRIBE va tal cual, sin to_linear(). Escribirlo convertido a
#        lineal es lo que dejaba el labio en (146, 47, 39), rojo de lapiz labial.
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

# --- LA BARBA NO SE TOCA (sesion 8) ---------------------------------------------------------
#
# Hasta la sesion 7 este script RELLENABA de color barba una zona del menton, con la premisa de
# que "Meshy dejo todo el menton y la boca como una sola mancha de piel plana". Esa premisa era
# FALSA, y es la causa del pasamontañas negro que se veia en el visor.
#
# Medido con `--probe --tex generated/character_texture_repacked.png`, o sea sobre lo que pinto
# Meshy ANTES de cualquier retoque nuestro:
#
#   ojos-58mm |............#####...######...........|   bigote, en dos mitades
#   ojos-66mm |.......########.........######.......|
#   ojos-74mm |##....##......................##...##|   piel en el centro = boca
#   ojos-86mm |#######.......................#######|   barba solo en la mandibula
#   ojos-98mm |########.....................########|
#   ojos-106mm|#########.......#####........########|   perilla
#   ojos-122mm|   ###############################   |
#
# Eso es exactamente la barba de refs/face/contact_sheet.jpg: bigote arriba, barba por la
# mandibula, boca y menton despejados, perilla debajo del labio. Lo unico que de verdad falta
# es el DIBUJO DE LOS LABIOS: Meshy deja esa zona como piel plana, y sin labios se lee como una
# placa palida en mitad de la cara.
#
# Rellenar esa zona la convertia en un bloque negro (en cel-shading todo el pelo colapsa a una
# banda plana) y la "boca" pasaba a ser la ranura que el relleno dejaba sin cubrir: de ahi los
# garabatos claros. Este script ya solo dibuja labios sobre piel.

# --- labios. Todo relativo a la altura de los ojos (landmarks eye_L/R).
# El hueco de piel que deja Meshy va de ojos-70mm a ojos-104mm en el centro; los labios ocupan
# su mitad superior y dejan menton por debajo, antes de la perilla.
MOUTH_Z = 0.081         # m bajo los ojos: la LINEA de abertura (donde se juntan los labios)
LIP_X = 0.026           # m de medio ancho (boca de 52 mm; la cara mide 105 mm de ancho)
# Asimetricos a proposito: el labio de arriba es mas fino que el de abajo. Con las dos mitades
# iguales la boca se lee como una pastilla y no como una boca.
LIP_H_UP = 0.008        # m de alto del labio superior
LIP_H_LOW = 0.011       # m de alto del labio inferior
LIP_SOFT = 0.0015       # m de borde difuminado del contorno del labio
# Tono ABSOLUTO en sRGB, no un factor sobre la piel de alrededor (con factor el resultado
# dependia de la piel vecina y se fallo por los dos lados en la sesion 6). Ahora los labios
# van sobre PIEL, no sobre barba, asi que el tono es un rosa apagado y no un marron: la piel
# del personaje es sRGB (0.94, 0.58, 0.475) y el labio tiene que quedar claramente mas oscuro
# y mas rojo, pero sin irse a marron.
# (0.74, 0.40, 0.38) salia ROJO DE LAPIZ LABIAL en el visor: el cel-shading no tiene medios
# tonos, asi que cualquier salto de saturacion respecto a la piel se lee como color puro. Lo
# que separa un labio de la piel en una ilustracion plana es el VALOR, no la saturacion: mismo
# tono que la piel (0.94, 0.58, 0.475) y un escalon mas oscuro.
LIP_SRGB = (0.78, 0.47, 0.43)
# --- linea de abertura de la boca: lo que de verdad hace legible una boca en cel-shading.
# Con el labio ya apagado, esta linea es la que carga con la legibilidad, asi que va algo mas
# gruesa que en el primer intento (0.0022).
MOUTH_W = 0.88          # fraccion de LIP_X que abarca la linea (las comisuras se afilan)
MOUTH_H = 0.0027        # m de medio alto de la linea
MOUTH_SRGB = (0.32, 0.16, 0.14)   # marron muy oscuro: la abertura entre los labios
# Guardas: la boca ronda los 2-4 mil texeles. Si se dispara es que LIP_* se comio la cara.
LIP_MIN = 800
LIP_MAX = 9000


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
    # --tex mide otra etapa de la cadena (p.ej. character_texture_repacked.png, que es lo que
    # pinto Meshy antes de cualquier retoque nuestro). Solo en modo lectura: sirve para separar
    # "esto lo pinto Meshy" de "esto lo pintamos nosotros".
    if '--tex' in args and PROBE:
        alt = args[args.index('--tex') + 1]
        if not os.path.isabs(alt): alt = os.path.join(common.ROOT, alt)
        img = bpy.data.images.load(alt, check_existing=True); img.reload()
        # El nodo del material tiene que apuntar a la MISMA imagen o el render del probe saldria
        # con la textura vieja mientras los numeros salen de la nueva. No se guarda el .blend en
        # modo probe, asi que el cambio muere con el proceso.
        bpy.data.materials['Character'].node_tree.nodes['Principled BSDF'] \
            .inputs['Base Color'].links[0].from_node.image = img
        print('FACE_FEATURES leyendo', os.path.basename(alt))
    elif img is None or not img.filepath_raw.endswith('character_texture_clean.png'):
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

    # --- forma de la boca. Dos medias elipses que comparten la linea de abertura: la de arriba
    # mas fina (LIP_H_UP) y la de abajo mas llena (LIP_H_LOW). `lip_r` vale 0 en la linea y 1 en
    # el contorno del labio, asi que sirve igual para la mascara y para el difuminado del borde.
    mouth_zc = eye_z - MOUTH_Z
    dz = wz - mouth_zc
    hz = np.where(dz >= 0, LIP_H_UP, LIP_H_LOW)          # arriba = z mayor (mas cerca de los ojos)
    lip_r = np.sqrt((wx / LIP_X) ** 2 + (dz / hz) ** 2)
    # Solo sobre PIEL: asi el bigote y la perilla que pinto Meshy se quedan como estan aunque
    # caigan dentro de la elipse. `~is_hair` y no `is_skin` porque entre HAIR_LUM (0.50) y
    # SKIN_LUM (0.55) hay una tierra de nadie donde caen los trazos con que Meshy dibujo el
    # contorno del bigote; si se excluyen quedan como garabatos claros sobre el labio.
    lips = zone & (lip_r <= 1.0) & ~is_hair

    if PROBE:
        for name, m in (('zona', zone), ('piel', is_skin), ('pelo', is_hair),
                        ('labios', lips)):
            print('  %-8s %8d texeles' % (name, int(m.sum())))
        # --- mapa de ocupacion piel/pelo en coordenadas de MUNDO (para disenar la mascara).
        # Cada celda = 4 mm. '#' = mayoria pelo, '.' = mayoria piel, ' ' = sin cara.
        CELL = 0.004
        xs, zs = wx[zone], wz[zone]
        x0, x1 = -0.075, 0.075
        z0, z1 = eye_z - 0.135, eye_z - 0.010
        nx, nz = int((x1 - x0) / CELL), int((z1 - z0) / CELL)
        print('  MAPA piel(.) / pelo(#) — columnas x de %+0.3f a %+0.3f, filas z de ojos-10mm a ojos-135mm' % (x0, x1))
        for j in range(nz):
            zlo, zhi = z1 - (j + 1) * CELL, z1 - j * CELL
            row = ''
            for i in range(nx):
                xlo, xhi = x0 + i * CELL, x0 + (i + 1) * CELL
                cel = zone & (wx >= xlo) & (wx < xhi) & (wz >= zlo) & (wz < zhi)
                ns, nh = int((cel & is_skin).sum()), int((cel & is_hair).sum())
                row += ' ' if ns + nh < 4 else ('#' if nh > ns else '.')
            print('   z=%+0.3f (ojos%+0.0fmm) |%s|' % (zhi, (zhi - eye_z) * 1000, row))
        for name, m in (('piel', is_skin), ('pelo', is_hair)):
            q = np.percentile(lum[m], [5, 50, 95]) if m.any() else [0, 0, 0]
            print('  LUM %-5s p5/p50/p95 %s' % (name, ' '.join('%.3f' % v for v in q)))
        dbg = srgb.copy()
        if not FLAT:
            dbg[zone] = dbg[zone] * 0.4 + np.array([0.0, 0.0, 0.5], np.float32)
            dbg[is_hair] = dbg[is_hair] * 0.4 + np.array([0.5, 0.25, 0.0], np.float32)   # barba de Meshy, la que NO se toca
            dbg[lips] = np.array([0.15, 0.95, 0.25], np.float32)
        render_probe(img, px, dbg, lm, 'face_probe_%s.png' % ('flat' if FLAT else 'front'))
        return

    if not is_hair.any():
        common.fail('no se encontro barba en la cara (revisar HAIR_LUM): la barba de Meshy es la referencia')
    if lips.sum() < LIP_MIN:
        common.fail('la boca tiene solo %d texeles (minimo %d): revisar MOUTH_Z / LIP_*' % (int(lips.sum()), LIP_MIN))
    if lips.sum() > LIP_MAX:
        common.fail('la boca tiene %d texeles (tope %d): la elipse se esta comiendo la cara, '
                    'revisar LIP_X / LIP_H_*' % (int(lips.sum()), LIP_MAX))

    # --- labios. Difuminado CORTO (LIP_SOFT, 1.5 mm) hacia adentro desde el contorno: mas
    # ancho y el labio se deshace en la piel; a cero se ve el escalon de texeles.
    # OJO, espacio de color (medido en la sesion 8, y NO es lo que decia el comentario viejo):
    # para ESTA imagen `img.pixels` entrega valores ya codificados en sRGB, no lineales. Se
    # comprueba en el PNG: la piel de Meshy esta guardada como (236, 158, 133), que es el
    # skin_srgb del landmark, y la mediana de luminancia que imprime --probe (0.849) solo cuadra
    # si `to_srgb(rgb)` es una conversion de MAS sobre algo que ya era sRGB.
    # Consecuencia: un color se escribe TAL CUAL, sin to_linear(). Escribirlo convertido a lineal
    # es lo que ponia el labio en (146, 47, 39) — rojo de lapiz labial — en vez de (199, 120, 110).
    # Los umbrales de clasificacion (SKIN_LUM, HAIR_LUM...) SI estan calibrados contra
    # `to_srgb(rgb)`, ese espacio doblemente convertido: no se tocan.
    tint = np.array(LIP_SRGB, np.float32)
    soft_r = LIP_SOFT / min(LIP_H_UP, LIP_H_LOW)         # LIP_SOFT en unidades de lip_r
    lw = ramp(1.0 - lip_r, 0.0, soft_r) * lips
    rgb = rgb * (1 - lw[..., None]) + tint[None, None, :] * lw[..., None]
    print('LABIOS %d texeles (peso medio %.2f), tono sRGB %s -> escrito %s'
          % (int((lw > 0.01).sum()), float(lw[lw > 0.01].mean()),
             [round(float(c), 3) for c in tint], [int(round(float(c) * 255)) for c in tint]))

    # --- linea de abertura: sin ella los dos labios son una sola mancha de tono plano, y en
    # cel-shading una mancha plana no se lee como boca.
    mouth_r = np.sqrt((wx / (LIP_X * MOUTH_W)) ** 2 + (dz / MOUTH_H) ** 2)
    mouth = zone & (mouth_r <= 1.0) & ~is_hair
    if mouth.sum() < 40:
        common.fail('la linea de la boca tiene %d texeles: revisar MOUTH_W / MOUTH_H' % int(mouth.sum()))
    mtint = np.array(MOUTH_SRGB, np.float32)      # sin to_linear: ver la nota de espacio de color arriba
    mw_ = ramp(1.0 - mouth_r, 0.0, 0.25) * mouth
    rgb = rgb * (1 - mw_[..., None]) + mtint[None, None, :] * mw_[..., None]
    print('BOCA linea %d texeles, tono sRGB %s -> escrito %s'
          % (int((mw_ > 0.01).sum()), [round(float(c), 3) for c in mtint],
             [int(round(float(c) * 255)) for c in mtint]))

    px[..., :3] = rgb
    img.pixels.foreach_set(px[::-1, :, :].ravel())
    img.filepath_raw = TEX; img.file_format = 'PNG'; img.save()
    print('FACE_FEATURES textura guardada', TEX)
    common.save(bpy.data.filepath)


main()

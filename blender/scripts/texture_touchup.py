# blender/scripts/texture_touchup.py
# Dos retoques de textura sobre el layout UV reempaquetado (van DESPUES de la segunda pasada de
# fix_character_material.py, porque esa pasada regenera character_texture_clean.png desde cero):
#
#   1. Rayas de costura ("grietas"). Meshy hornea un borde de 1 px OSCURO en las islas de piel
#      (medido: en el texel del borde el 14.6 % es oscuro contra 2-4 % en el interior) y algo CLARO
#      en las del hoodie. Con las 4500 islas originales ese borde quedaba escondido en el canal; al
#      hornear al layout nuevo (repack_uvs.py) las islas viejas se pegan unas a otras y el borde
#      aparece como rayas finas oscuras en la cara y claras en el hoodie. Se localizan las costuras
#      VIEJAS (aristas cuyo UV de Meshy no coincide entre las dos caras, o de borde) dibujadas en el
#      UV nuevo, y dentro de esa franja se reemplaza cada texel que salta de luminancia respecto al
#      promedio de su entorno fuera de la franja, SOLO si ese entorno es uniforme (asi una linea de
#      ojo o el borde barba/piel que caen sobre una costura no se tocan).
#   2. Cejas pintadas. Las cejas de malla (add_face_parts.py) tapan las pintadas en reposo, pero al
#      levantarse (browup) las pintadas quedan a la vista y se ven cuatro cejas. Se borran: en la
#      zona de la frente donde estan (landmarks brow_L/R, caras frontales) los texeles oscuros toman
#      el color de piel mas cercano.
#
# Idempotente por naturaleza (repetirlo no encuentra nada que arreglar). Requiere Body['uv_repacked']
# y el atributo 'uv_meshy' (los deja repack_uvs.py). Renders de control: generated/renders/
# touchup_face.png (reposo) y touchup_browup.png (cejas levantadas: no debe verse ninguna pintada).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/texture_touchup.py [--dry-run]
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np
from mathutils import Vector
import fix_character_material as fcm

TEX = os.path.join(common.GEN, 'character_texture_clean.png')
OLD_UV = 'uv_meshy'
BAND = 3.0          # px (a 4096) de medio ancho de la franja alrededor de cada costura vieja
REF_R = 6           # radio del promedio de referencia (texeles fuera de la franja)
REF_MIN = 12        # minimo de texeles de referencia en la ventana
REF_STD_MAX = 0.06  # entorno "uniforme": desviacion de luminancia por debajo de esto
JUMP = 0.16         # salto de luminancia texel-vs-entorno que delata una raya
BROW_DZ = 0.019     # m arriba/abajo del centro de la ceja pintada (brow_h = 0.021 -> +-0.0105, mas el arco y las puntas; el ojo llega a 1.585)
BROW_DX = 0.016     # m de margen a cada lado del largo de la ceja
BROW_NY = 0.25      # normal.y minima: solo caras frontales (la visera mira abajo, las sienes al lado)
BROW_DARK = 0.45    # luminancia por debajo de la cual un texel de la zona es ceja
BROW_SOFT = 0.62    # entre DARK y SOFT: borde antialiasado y la sombra pintada bajo la ceja, se funden con la piel
BROW_COPY_DZ = 0.026 # m: la piel de relleno se copia de la frente, esta altura por encima de cada texel (raycast); si pega en pelo/gorra, relleno dilatado
BROW_BLUR = 10      # radio del desenfoque de caja del relleno (dos pasadas)
BROW_REACH = 192    # px de dilatado para traer piel a la zona borrada (la ceja mide ~200 px de largo a 4096)


def main():
    common.ensure_dirs()
    args = common.args(); DRY = '--dry-run' in args
    body = bpy.data.objects.get('Body'); arm = bpy.data.objects.get('Armature')
    if body is None or arm is None:
        common.fail('faltan Body/Armature')
    if not body.get('uv_repacked'):
        common.fail('Body sin uv_repacked: ejecutar repack_uvs.py (y fix_character_material.py) antes')
    me = body.data
    if OLD_UV not in me.attributes:
        common.fail(f'Body sin el atributo {OLD_UV} (lo deja repack_uvs.py)')
    m = bpy.data.materials['Character']
    img = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node.image
    if img is None or not img.filepath_raw.endswith('character_texture_clean.png'):
        common.fail('el material no apunta a character_texture_clean.png (ejecutar fix_character_material.py)')
    img.reload()
    w, h = img.size
    if w != h or w < 2048:
        common.fail(f'textura {w}x{h}: se espera cuadrada >= 2048')
    S = w
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[::-1, :, :3].astype(np.float32).copy()   # arriba primero

    # ---------------------------------------------------------------- geometria
    nl = len(me.loops)
    a = me.attributes[OLD_UV]
    uv_old = np.empty(nl * 2, np.float32); a.data.foreach_get('vector', uv_old); uv_old = uv_old.reshape(-1, 2)
    uv_new = np.empty(nl * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv_new); uv_new = uv_new.reshape(-1, 2)
    lv = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', lv)
    mask = fcm.uv_mask(body, S)

    # --- 1a. costuras viejas: arista (v0,v1) cuyo UV de Meshy difiere entre sus dos caras (o de borde)
    edges = {}
    for p in me.polygons:
        li = list(p.loop_indices); n = len(li)
        for k in range(n):
            l0, l1 = li[k], li[(k + 1) % n]
            v0, v1 = int(lv[l0]), int(lv[l1])
            if v0 > v1: l0, l1, v0, v1 = l1, l0, v1, v0
            edges.setdefault((v0, v1), []).append((uv_old[l0], uv_old[l1], uv_new[l0], uv_new[l1]))
    seams = []
    for key, sides in edges.items():
        if len(sides) == 1:
            seams.append((sides[0][2], sides[0][3])); continue
        o0, o1 = sides[0][0], sides[0][1]
        if any(np.abs(s[0] - o0).max() > 1e-4 or np.abs(s[1] - o1).max() > 1e-4 for s in sides[1:]):
            for s in sides:
                seams.append((s[2], s[3]))
    print('TOUCHUP aristas', len(edges), 'costuras viejas', len(seams))

    band = np.zeros((S, S), dtype=bool)
    for p0, p1 in seams:
        x0, y0 = p0[0] * S, (1.0 - p0[1]) * S
        x1, y1 = p1[0] * S, (1.0 - p1[1]) * S
        bx0, bx1 = int(max(0, math.floor(min(x0, x1) - BAND - 1))), int(min(S - 1, math.ceil(max(x0, x1) + BAND + 1)))
        by0, by1 = int(max(0, math.floor(min(y0, y1) - BAND - 1))), int(min(S - 1, math.ceil(max(y0, y1) + BAND + 1)))
        if bx1 < bx0 or by1 < by0: continue
        gx, gy = np.meshgrid(np.arange(bx0, bx1 + 1) + 0.5, np.arange(by0, by1 + 1) + 0.5)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-12 else np.clip(((gx - x0) * dx + (gy - y0) * dy) / L2, 0.0, 1.0)
        d = np.hypot(gx - (x0 + t * dx), gy - (y0 + t * dy))
        band[by0:by1 + 1, bx0:bx1 + 1] |= d <= BAND
    band &= mask
    print('TOUCHUP franja de costuras: %.2f %% de la mascara' % (band.sum() / mask.sum() * 100))

    # --- 1b. referencia = promedio de los texeles fuera de la franja en una ventana (2R+1)^2
    def box_sum(x, r):
        c = np.cumsum(np.cumsum(np.pad(x, ((r + 1, r), (r + 1, r))), axis=0), axis=1)
        return c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]
    valid = (mask & ~band).astype(np.float32)
    cnt = box_sum(valid, REF_R)
    ref = np.stack([box_sum(rgb[..., i] * valid, REF_R) for i in range(3)], -1) / np.maximum(cnt, 1)[..., None]
    lum = rgb.mean(2)
    e1 = box_sum(lum * valid, REF_R) / np.maximum(cnt, 1)
    e2 = box_sum(lum * lum * valid, REF_R) / np.maximum(cnt, 1)
    std = np.sqrt(np.maximum(e2 - e1 * e1, 0.0))
    jump = lum - e1
    cand = band & (cnt >= REF_MIN) & (std < REF_STD_MAX)
    hard = cand & (np.abs(jump) > JUMP)
    soft = cand & ~hard & (np.abs(jump) > JUMP * 0.5)
    rgb[hard] = ref[hard]
    rgb[soft] = 0.5 * rgb[soft] + 0.5 * ref[soft]
    print('TOUCHUP rayas de costura: %d texeles reemplazados (%d oscuras sobre claro, %d claras sobre oscuro) + %d fundidos'
          % (hard.sum(), int((hard & (jump < 0)).sum()), int((hard & (jump > 0)).sum()), soft.sum()))

    # ---------------------------------------------------------------- 2. cejas pintadas
    lm = json.load(open(common.LANDMARKS))
    half = lm['brow_len'] / 2.0
    mw = body.matrix_world; m3 = mw.to_3x3()
    zone = np.zeros((S, S), dtype=bool)
    tri_of = np.full((S, S), -1, dtype=np.int64)          # indice en `tris3d` del triangulo que cubre cada texel de la zona
    bary = np.zeros((S, S, 2), dtype=np.float32)
    tris3d = []                                             # (A, B, C, n) en mundo
    ntri = 0
    for p in me.polygons:
        c = mw @ p.center; nrm = (m3 @ p.normal).normalized()
        if nrm.y < BROW_NY or c.y < 0.04: continue
        ok = False
        for side in ('L', 'R'):
            b = lm[f'brow_{side}']
            if abs(c.x - b[0]) <= half + BROW_DX and abs(c.z - b[2]) <= BROW_DZ:
                ok = True
        if not ok: continue
        ntri += 1
        li = list(p.loop_indices)
        for k in range(1, len(li) - 1):
            t = uv_new[[li[0], li[k], li[k + 1]]]
            xs = t[:, 0] * S; ys = (1.0 - t[:, 1]) * S
            x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(S - 1, np.ceil(xs.max()) + 1))
            y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(S - 1, np.ceil(ys.max()) + 1))
            if x1 < x0 or y1 < y0: continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
            if abs(d) < 1e-9: continue
            w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
            w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
            zone[y0:y1 + 1, x0:x1 + 1] |= inside
            sub = tri_of[y0:y1 + 1, x0:x1 + 1]; take = inside & (sub < 0)
            sub[take] = len(tris3d)
            bsub = bary[y0:y1 + 1, x0:x1 + 1]; bsub[take, 0] = w0[take]; bsub[take, 1] = w1[take]
            vi = [me.loops[li[0]].vertex_index, me.loops[li[k]].vertex_index, me.loops[li[k + 1]].vertex_index]
            tris3d.append(tuple(mw @ me.vertices[v].co for v in vi) + (nrm,))
    zone &= mask
    if ntri == 0 or zone.sum() < 500:
        common.fail(f'zona de cejas vacia (caras {ntri}, texeles {int(zone.sum())}): revisar landmarks/BROW_*')
    lum = rgb.mean(2)
    dark = zone & (lum < BROW_DARK)
    edge = zone & ~dark & (lum < BROW_SOFT)
    skin_src = zone & (lum >= 0.60) & (rgb[..., 0] > rgb[..., 2] + 0.15)   # piel clara y rojiza (sin el halo gris de la ceja)
    frac = dark.sum() / zone.sum()
    print('TOUCHUP zona de cejas: %d caras, %d texeles, %.1f %% oscuros (ceja pintada)' % (ntri, zone.sum(), frac * 100))
    if not (0.03 < frac < 0.8):
        common.fail('la fraccion de texeles oscuros en la zona de cejas (%.2f) no parece una ceja' % frac)
    if skin_src.sum() < 200:
        common.fail('no hay piel en la zona de cejas para rellenar')
    ref2 = fcm.dilate_colors(rgb, skin_src, BROW_REACH)
    reach = skin_src.copy()
    for _ in range(BROW_REACH):
        reach |= np.roll(reach, 1, 0) | np.roll(reach, -1, 0) | np.roll(reach, 1, 1) | np.roll(reach, -1, 1)
    skin_med = np.median(rgb[skin_src], axis=0)
    ref2[~reach] = skin_med          # parches de la zona sin piel a menos de BROW_REACH px (islas sueltas): piel media
    ok = reach.astype(np.float32)    # desenfoque SOLO sobre texeles rellenos (si no, el negro del pelo vecino lo agrisa)
    for _ in range(2):               # el dilatado arrastra el grano de la frente: se desenfoca el relleno
        c = np.maximum(box_sum(ok, BROW_BLUR), 1.0)
        ref2 = np.stack([box_sum(ref2[..., i] * ok, BROW_BLUR) for i in range(3)], -1) / c[..., None]
        ref2[~reach] = skin_med
    # relleno con piel REAL: cada texel de ceja copia la textura de la frente BROW_COPY_DZ mas arriba
    # (raycast sobre Body desde delante de la piel); asi conserva el grano de la frente y no queda un
    # parche plano. Si el rayo pega en pelo/gorra (oscuro) o no pega, queda el relleno dilatado ref2.
    src_rgb = rgb.copy()
    mwi = mw.inverted(); m3i = mwi.to_3x3()
    uv_loops = uv_new
    def uv_at(face_idx, loc):
        p = me.polygons[face_idx]; li = list(p.loop_indices)
        best = None
        for k in range(1, len(li) - 1):
            A = me.vertices[me.loops[li[0]].vertex_index].co; B = me.vertices[me.loops[li[k]].vertex_index].co; C = me.vertices[me.loops[li[k + 1]].vertex_index].co
            e0, e1, ep = B - A, C - A, loc - A
            d00, d01, d11, d20, d21 = e0.dot(e0), e0.dot(e1), e1.dot(e1), ep.dot(e0), ep.dot(e1)
            den = d00 * d11 - d01 * d01
            if abs(den) < 1e-18: continue
            v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den; u = 1 - v - w
            err = max(0, -u, -v, -w)
            if best is None or err < best[0]:
                best = (err, u * uv_loops[li[0]] + v * uv_loops[li[k]] + w * uv_loops[li[k + 1]])
        return None if best is None or best[0] > 0.02 else best[1]
    def sample(uv):
        x = uv[0] * S - 0.5; y = (1.0 - uv[1]) * S - 0.5
        x0 = int(np.clip(np.floor(x), 0, S - 1)); y0 = int(np.clip(np.floor(y), 0, S - 1)); x1 = min(x0 + 1, S - 1); y1 = min(y0 + 1, S - 1)
        fx = float(np.clip(x - x0, 0, 1)); fy = float(np.clip(y - y0, 0, 1))
        return (src_rgb[y0, x0] * (1 - fx) + src_rgb[y0, x1] * fx) * (1 - fy) + (src_rgb[y1, x0] * (1 - fx) + src_rgb[y1, x1] * fx) * fy
    fill = ref2.copy()
    ys, xs = np.where(dark | edge)
    copied = 0
    for y, x in zip(ys, xs):
        t = tri_of[y, x]
        if t < 0: continue
        A, B, C, n = tris3d[t]
        w0, w1 = float(bary[y, x, 0]), float(bary[y, x, 1]); w2 = 1.0 - w0 - w1
        P = A * w0 + B * w1 + C * w2 + Vector((0.0, 0.0, BROW_COPY_DZ))
        hit, loc, hn, fi = body.ray_cast(mwi @ (P + n * 0.015), (m3i @ (-n)).normalized(), distance=0.04)
        if not hit: continue
        uv = uv_at(fi, loc)
        if uv is None: continue
        c = sample(uv)
        if c.mean() < 0.50 or c[0] <= c[2] + 0.12: continue      # pelo, gorra o sombra: no sirve
        fill[y, x] = c; copied += 1
    rgb[dark] = fill[dark]
    wgt = np.clip((BROW_SOFT - lum[edge]) / (BROW_SOFT - BROW_DARK), 0.0, 1.0)[:, None]
    rgb[edge] = rgb[edge] * (1 - wgt) + fill[edge] * wgt
    # desenfoque leve del contorno (el borde antialiasado de la ceja quedaba como una linea clara)
    ring = dark | edge
    for _ in range(3):
        ring |= np.roll(ring, 1, 0) | np.roll(ring, -1, 0) | np.roll(ring, 1, 1) | np.roll(ring, -1, 1)
    ring &= zone
    okz = (mask & (rgb.mean(2) >= BROW_DARK)).astype(np.float32)   # el pelo/gorra vecinos no entran en el promedio (si no, el borde se vuelve a oscurecer)
    cz = np.maximum(box_sum(okz, 2), 1.0)
    blurred = np.stack([box_sum(rgb[..., i] * okz, 2) for i in range(3)], -1) / cz[..., None]
    rgb[ring] = blurred[ring]
    print('TOUCHUP cejas pintadas borradas: %d texeles + %d fundidos (%d copiados de la frente, %d con relleno dilatado); contorno difuminado %d'
          % (dark.sum(), edge.sum(), copied, len(ys) - copied, ring.sum()))
    left = (zone & (rgb.mean(2) < BROW_DARK)).sum()
    if left:
        common.fail(f'quedan {left} texeles oscuros en la zona de cejas')

    dbg = os.environ.get('TOUCHUP_DEBUG')
    if dbg:
        np.savez_compressed(os.path.join(dbg, 'touchup_debug.npz'), band=band, hard=hard, soft=soft, zone=zone, dark=dark, rgb=(np.clip(rgb, 0, 1) * 255).astype(np.uint8))
        print('TOUCHUP debug en', dbg)

    # ---------------------------------------------------------------- guardar
    buf = np.ones((S, S, 4), dtype=np.float32); buf[..., :3] = np.clip(rgb[::-1], 0, 1)
    img.pixels.foreach_set(buf.ravel())
    if DRY:
        print('TOUCHUP dry-run; no se guarda la textura')
    else:
        img.filepath_raw = TEX; img.file_format = 'PNG'; img.save(); img.reload()
        print('TOUCHUP guardada', TEX)

    # ---------------------------------------------------------------- renders de control
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    sc = bpy.context.scene
    if sc.world is None: sc.world = bpy.data.worlds.new('TU_World')
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get('Background')
    prev_bg = (tuple(bg.inputs[0].default_value), bg.inputs[1].default_value)
    bg.inputs[0].default_value = (0.42, 0.44, 0.50, 1.0); bg.inputs[1].default_value = 0.55
    hz = (arm.matrix_world @ arm.pose.bones['spine006'].head).z
    common.add_camera((0.0, 0.85, hz + 0.10), (0.0, 0.0, hz + 0.09), lens=85, name='TU_Cam')
    common.add_light('TU_key', 'AREA', (-0.6, 0.9, hz + 0.5), 160, size=0.9)
    common.add_light('TU_fill', 'AREA', (0.7, 0.8, hz + 0.1), 90, size=0.9)
    common.render(os.path.join(common.RENDERS, 'touchup_face.png'), res=(900, 900), samples=48)
    for s in 'LR':
        pb = arm.pose.bones.get(f'eyebrow_{s}')
        if pb: pb.location = (0.0, 0.0, 0.012)
    bpy.context.view_layer.update()
    common.render(os.path.join(common.RENDERS, 'touchup_browup.png'), res=(900, 900), samples=48)
    for s in 'LR':
        pb = arm.pose.bones.get(f'eyebrow_{s}')
        if pb: pb.location = (0.0, 0.0, 0.0)
    bg.inputs[0].default_value = prev_bg[0]; bg.inputs[1].default_value = prev_bg[1]
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    if not DRY:
        common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('TOUCHUP OK')


if __name__ == '__main__':
    main()

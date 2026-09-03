# blender/scripts/render_face_grid.py
# Task 8, paso 1: leer los "landmarks" de la cara (ojos, cejas, lóbulos) del
# personaje ya importado, para poder colocar párpados, cejas y candongas.
#
# Hace dos cosas complementarias:
#   1) Detección automática a partir de la TEXTURA. La cara (ojos, cejas, barba)
#      está pintada en la textura, no modelada. Se rasteriza la huella UV de cada
#      triángulo frontal de la cabeza y se retroproyecta cada téxel a coordenadas
#      de mundo por interpolación baricéntrica (misma técnica que apply_chest_logo).
#      Con eso se agrupan los téxeles oscuros en manchas (ojos y cejas) y se mide
#      el tono de piel real alrededor de los ojos.
#   2) Renders con rejilla de 1 cm (plano frontal y=+0.25 y lateral x=+0.25) para
#      verificar a ojo las coordenadas y leer la profundidad y de los ojos.
#
# El personaje mira a +Y; su lado izquierdo está en -X.
# Escribe blender/landmarks.json (que add_face_parts.py consume) SOLO si no existe: el
# archivo versionado esta calibrado a mano (lobulos, radios) y no se sobrescribe.
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/render_face_grid.py
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
import common
from mathutils import Vector

CELL = 0.002          # 2 mm: celda del grid mundo (x,z) para agrupar manchas
DARK_PERCENTILE = 12  # % de téxeles más oscuros de la cara que se consideran "tinta"


def dilate(mask, r=1):
    out = mask.copy()
    H, W = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            ys = slice(max(0, dy), H + min(0, dy)); yd = slice(max(0, -dy), H + min(0, -dy))
            xs = slice(max(0, dx), W + min(0, dx)); xd = slice(max(0, -dx), W + min(0, -dx))
            out[yd, xd] |= mask[ys, xs]
    return out


def label_components(mask):
    H, W = mask.shape
    labels = np.zeros((H, W), dtype=np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if labels[y0, x0]:
            continue
        n += 1
        stack = [(y0, x0)]
        labels[y0, x0] = n
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = n
                    stack.append((ny, nx))
    return labels, n


def face_texels(obj, arr_shape, z_lo, z_hi):
    """Rasteriza los triángulos frontales de la cabeza y devuelve
    (px, py, wx, wy, wz) por téxel, en coordenadas de mundo."""
    H, W = arr_shape[:2]
    mesh = obj.data
    mw = obj.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    uv = mesh.uv_layers.active.data
    ax = []
    for poly in mesh.polygons:
        c = mw @ poly.center
        if not (z_lo <= c.z <= z_hi) or abs(c.x) > 0.10:
            continue
        n = (nmat @ poly.normal).normalized()
        if n.y < 0.25:          # solo las caras que miran al frente (+Y)
            continue
        verts, uvs = [], []
        for li in poly.loop_indices:
            wp = mw @ mesh.vertices[mesh.loops[li].vertex_index].co
            t = uv[li].uv
            verts.append(wp); uvs.append((t.x * W, t.y * H))
        if len(verts) != 3:
            continue
        (u0, v0), (u1, v1), (u2, v2) = uvs
        x_min = max(0, int(math.floor(min(u0, u1, u2)))); x_max = min(W, int(math.ceil(max(u0, u1, u2))) + 1)
        y_min = max(0, int(math.floor(min(v0, v1, v2)))); y_max = min(H, int(math.ceil(max(v0, v1, v2))) + 1)
        if x_max <= x_min or y_max <= y_min:
            continue
        xr = np.arange(x_min, x_max); yr = np.arange(y_min, y_max)
        XX, YY = np.meshgrid(xr + 0.5, yr + 0.5)
        IIX, IIY = np.meshgrid(xr, yr)
        den = (v1 - v2) * (u0 - u2) + (u2 - u1) * (v0 - v2)
        if abs(den) < 1e-9:
            continue
        w0 = ((v1 - v2) * (XX - u2) + (u2 - u1) * (YY - v2)) / den
        w1 = ((v2 - v0) * (XX - u2) + (u0 - u2) * (YY - v2)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        ax.append((IIX[m], IIY[m],
                   (w0 * verts[0].x + w1 * verts[1].x + w2 * verts[2].x)[m],
                   (w0 * verts[0].y + w1 * verts[1].y + w2 * verts[2].y)[m],
                   (w0 * verts[0].z + w1 * verts[1].z + w2 * verts[2].z)[m]))
    if not ax:
        return None
    return tuple(np.concatenate([a[i] for a in ax]) for i in range(5))


def analyse_texture(arm, obj, hz):
    mat = obj.data.materials[0]
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    img = bsdf.inputs['Base Color'].links[0].from_node.image
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4)

    z_lo, z_hi = hz + 0.03, hz + 0.24
    t = face_texels(obj, arr.shape, z_lo, z_hi)
    if t is None:
        print('LM_FAIL no hay téxeles frontales en la cabeza')
        return None
    px, py, wx, wy, wz = t
    col = arr[py, px, :3]
    lum = col.mean(axis=1)
    thr = float(np.percentile(lum, DARK_PERCENTILE))
    dark = lum < thr
    print('FACE_TEXELS', px.size, 'oscuros', int(dark.sum()), 'umbral_lum', round(thr, 4))

    gx = np.floor((wx - wx.min()) / CELL).astype(np.int64)
    gz = np.floor((wz - wz.min()) / CELL).astype(np.int64)
    grid = np.zeros((int(gz.max()) + 3, int(gx.max()) + 3), dtype=bool)
    grid[gz[dark] + 1, gx[dark] + 1] = True
    grid = dilate(grid, 1)
    labels, n = label_components(grid)
    tl = labels[gz + 1, gx + 1]
    blobs = []
    for lbl in range(1, n + 1):
        sel = dark & (tl == lbl)
        if sel.sum() < 40:
            continue
        blobs.append(dict(n=int(sel.sum()),
                          x=float(wx[sel].mean()), y=float(wy[sel].mean()), z=float(wz[sel].mean()),
                          x0=float(wx[sel].min()), x1=float(wx[sel].max()),
                          z0=float(wz[sel].min()), z1=float(wz[sel].max())))
    blobs.sort(key=lambda b: -b['n'])
    for b in blobs:
        print('BLOB n=%5d c=(%.4f, %.4f, %.4f) x[%.4f,%.4f] z[%.4f,%.4f]'
              % (b['n'], b['x'], b['y'], b['z'], b['x0'], b['x1'], b['z0'], b['z1']))

    # tono de piel: mediana del color de la mejilla (entre el ojo y la boca, hacia
    # fuera del eje). Ojo: son valores tal cual están en la textura (sRGB), no lineales.
    ax_ = np.abs(wx)
    skin_sel = ((~dark) & (wz > hz + 0.045) & (wz < hz + 0.085) & (ax_ > 0.025) & (ax_ < 0.075))
    if skin_sel.sum() < 50:
        skin_sel = ~dark
    skin = np.median(col[skin_sel], axis=0)
    print('SKIN_RGB_sRGB', [round(float(c), 4) for c in skin], 'n=', int(skin_sel.sum()))
    for q in (25, 50, 75):
        print('  skin p%d' % q, [round(float(c), 4) for c in np.percentile(col[skin_sel], q, axis=0)])

    # tono de la ceja pintada: mediana de los texeles oscuros de la banda de las cejas
    brow_sel = (dark & (wz > hz + 0.085) & (wz < hz + 0.118) & (ax_ > 0.015) & (ax_ < 0.080))
    brow = np.median(col[brow_sel], axis=0) if brow_sel.sum() >= 50 else np.array([0.05, 0.04, 0.035])
    print('BROW_RGB_sRGB', [round(float(c), 4) for c in brow], 'n=', int(brow_sel.sum()))
    return blobs, [float(c) for c in skin], [float(c) for c in brow]


def guess_landmarks(blobs, hz):
    """Empareja manchas oscuras en pares izquierda/derecha. Los ojos son el par
    más bajo con separación clara en x; las cejas, el par justo encima."""
    pairs = []
    used = set()
    for i, a in enumerate(blobs):
        if i in used or abs(a['x']) < 0.008:
            continue
        best = None
        for j, b in enumerate(blobs):
            if j <= i or j in used:
                continue
            if a['x'] * b['x'] > 0:
                continue
            if abs(a['z'] - b['z']) > 0.012 or abs(abs(a['x']) - abs(b['x'])) > 0.012:
                continue
            if best is None or abs(a['z'] - b['z']) < abs(a['z'] - blobs[best]['z']):
                best = j
        if best is not None:
            used.add(i); used.add(best)
            L, R = (a, blobs[best]) if a['x'] < blobs[best]['x'] else (blobs[best], a)
            pairs.append((L, R))
    pairs.sort(key=lambda p: (p[0]['z'] + p[1]['z']) / 2)
    for L, R in pairs:
        print('PAIR z=%.4f  L=(%.4f,%.4f,%.4f) R=(%.4f,%.4f,%.4f)'
              % ((L['z'] + R['z']) / 2, L['x'], L['y'], L['z'], R['x'], R['y'], R['z']))
    return pairs


def build_grid(hz):
    m_g = common.mat('GridG', (0, 0, 0, 1), emission=(0, 1, 0, 1), emission_strength=5)
    m_r = common.mat('GridR', (0, 0, 0, 1), emission=(1, 0.15, 0, 1), emission_strength=6)
    m_b = common.mat('GridB', (0, 0, 0, 1), emission=(0.2, 0.5, 1, 1), emission_strength=8)
    for i in range(-15, 16):
        m = m_b if i == 0 else (m_r if i % 5 == 0 else m_g)
        t = 0.0016 if i % 5 == 0 else 0.0008
        # plano frontal: y = +0.25 (el personaje mira a +Y)
        common.box(f'gx{i}', (t, 0.0008, 0.32), (i * 0.01, 0.25, hz + 0.08), m)
        common.box(f'gz{i}', (0.32, 0.0008, t), (0, 0.25, hz + 0.08 + i * 0.01), m)
        # plano lateral: x = +0.25 (muestra su perfil DERECHO)
        common.box(f'gy{i}', (0.0008, t, 0.32), (0.25, i * 0.01, hz + 0.08), m)
        common.box(f'gyz{i}', (0.0008, 0.32, t), (0.25, 0, hz + 0.08 + i * 0.01), m)


def main():
    common.ensure_dirs()
    arm = bpy.data.objects['Armature']
    obj = bpy.data.objects['Body']
    hz = (arm.matrix_world @ arm.pose.bones['spine006'].head).z
    print('HEAD_Z', hz)

    res = analyse_texture(arm, obj, hz)
    if res:
        blobs, skin, brow = res
        pairs = guess_landmarks(blobs, hz)
        if len(pairs) >= 2:
            (eL, eR), (bL, bR) = pairs[0], pairs[1]
            lm = {
                'eye_L': [round(eL['x'], 4), round(eL['y'], 4), round(eL['z'], 4)],
                'eye_R': [round(eR['x'], 4), round(eR['y'], 4), round(eR['z'], 4)],
                'eye_radius': round(max((eL['x1'] - eL['x0']), (eR['x1'] - eR['x0'])) / 2, 4),
                'brow_L': [round(bL['x'], 4), round(bL['y'], 4), round(bL['z'], 4)],
                'brow_R': [round(bR['x'], 4), round(bR['y'], 4), round(bR['z'], 4)],
                'ear_L': [0, 0, 0], 'ear_R': [0, 0, 0],
                'skin_srgb': [round(c, 4) for c in skin],
                'brow_srgb': [round(c, 4) for c in brow],
            }
            path = common.LANDMARKS
            if not os.path.exists(path):
                json.dump(lm, open(path, 'w'), indent=2)
                print('LM_WRITTEN', path)
            else:
                print('LM_EXISTS (no se sobrescribe)', path)
            print('LM_AUTO', json.dumps(lm))

    build_grid(hz)
    cam = common.add_camera((0, 1.2, hz + 0.08), (0, 0, hz + 0.08), lens=85)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.36
    common.add_light('k', 'AREA', (-0.5, 1.0, hz + 0.6), 150, size=1.0)
    common.add_light('k2', 'AREA', (0.9, 0.8, hz + 0.3), 120, size=1.0)
    common.render(os.path.join(common.RENDERS, 'face_grid_front.png'), res=(1200, 1200))
    cam.location = (1.2, 0, hz + 0.08); common.look_at(cam, (0, 0, hz + 0.08))
    common.render(os.path.join(common.RENDERS, 'face_grid_side.png'), res=(1200, 1200))
    # perfil izquierdo (sin rejilla en ese lado, pero útil para las candongas)
    cam.location = (-1.2, 0, hz + 0.08); common.look_at(cam, (0, 0, hz + 0.08))
    common.render(os.path.join(common.RENDERS, 'face_grid_side_L.png'), res=(1200, 1200))
    print('HEAD_Z', hz)


if __name__ == '__main__':
    main()

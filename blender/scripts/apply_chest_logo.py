# blender/scripts/apply_chest_logo.py
# Task 6b: replace the white "SE" monogram on the hoodie chest with the
# company logo (refs/logo.png), by editing the base-color texture in place.
#
# The mesh's UV atlas is fragmented: triangles that sit next to each other on
# the chest are packed into unrelated, scattered locations in the 0..1 UV
# square (no single contiguous "chest island"). A plain UV-bounding-box of
# the candidate chest faces therefore covers almost the entire texture, not
# just the monogram. Instead we classify and paint per TEXEL: for every
# triangle in the chest region we rasterize its exact UV footprint, and for
# every covered pixel we back-project a world-space (x, z) position via
# barycentric interpolation of that triangle's 3 world-space vertices. This
# gives a reliable per-pixel world-position lookup regardless of how the
# atlas is packed, which is what both monogram detection and logo
# compositing are built on.
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/apply_chest_logo.py [-- --dark]
#   (--dark: logo con su tinta original oscura; por defecto se convierte en estampado claro)
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
import common

WHITE_THRESHOLD = 0.55
# 1.3 dejaba el logo del tamano del monograma SE y a esa escala no se leia nada. El pecho
# ocupa ~90 px en pantalla en el encuadre de aprobacion: el emblema tiene que ser grande.
LOGO_SCALE = 1.65
# El logo de origen es un grabado de linea fina CON GRANO (puntitos). Al bajarlo a la
# resolucion del atlas y hornearlo al UV nuevo, las lineas se rompen y el grano se convierte
# en ruido: en el visor se veia una mancha blanca irreconocible. Se binariza y se engorda el
# trazo, que conserva la FORMA y tira el grano; ademas encaja con el look cel del visor.
INK_LUM = 0.42       # luminancia por debajo de la cual un pixel del logo es tinta
INK_ALPHA = 0.40     # alfa minimo para considerar el pixel parte del dibujo
INK_GROW = 0.006     # fraccion del ancho del logo que engorda cada trazo (a 500 px: 3 px);
                     # a 0.012 las hojas del laurel se fundian en manchas y la reja del globo se cerraba
INK_PURPLE = 0.30    # densidad local minima para que una zona cuente como brillo morado (mata el grano)
INK_SOFT = 2         # radio del suavizado del borde (antialias del estarcido)
MERGE_DIST = 0.02    # m: white blobs closer than this to the main blob count as the monogram
ERASE_DILATE = 2     # grid cells (4 mm each) of world-space dilation around the monogram


def dilate(mask, r):
    """Binary dilation of a 2D bool array with a (2r+1)^2 square kernel."""
    out = mask.copy()
    H, W = mask.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            ys = slice(max(0, dy), H + min(0, dy))
            yd = slice(max(0, -dy), H + min(0, -dy))
            xs = slice(max(0, dx), W + min(0, dx))
            xd = slice(max(0, -dx), W + min(0, -dx))
            out[yd, xd] |= mask[ys, xs]
    return out


def label_components(mask):
    """4-connected component labelling of a 2D bool array (BFS, pure numpy/python).
    Returns (labels int array with 0 = background, n_labels)."""
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


def debug_white_map(wx, wz, white, path, cell=0.002):
    """Save a small PNG plotting chest texels (grey) and white texels (white) in
    world (x, z) space, so the monogram detection can be checked by eye."""
    gx = np.floor((wx - wx.min()) / cell).astype(np.int64)
    gz = np.floor((wz - wz.min()) / cell).astype(np.int64)
    W, H = int(gx.max()) + 1, int(gz.max()) + 1
    img = np.zeros((H, W, 4), dtype=np.float32)
    img[..., 3] = 1.0
    img[gz, gx, :3] = 0.3
    img[gz[white], gx[white], :3] = 1.0
    im = bpy.data.images.new('chest_white_map', W, H, alpha=True)
    im.pixels.foreach_set(img.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    print('WHITE_MAP', path, W, 'x', H)


def box_blur(a, r):
    """Media de caja de radio r sobre un array 2D float (separable, por sumas acumuladas)."""
    if r < 1:
        return a
    out = a.astype(np.float32)
    for axis in (0, 1):
        n = out.shape[axis]
        c = np.cumsum(np.concatenate([np.zeros((1,) + out.shape[1:], np.float32) if axis == 0
                                      else np.zeros((out.shape[0], 1), np.float32), out], axis=axis), axis=axis)
        lo = np.clip(np.arange(n) - r, 0, n)
        hi = np.clip(np.arange(n) + r + 1, 0, n)
        take = (lambda idx: c[idx]) if axis == 0 else (lambda idx: c[:, idx])
        out = (take(hi) - take(lo)) / (hi - lo).reshape((-1, 1) if axis == 0 else (1, -1))
    return out


def to_light_print(logo):
    """Convierte el logo en un ESTARCIDO claro sobre el hoodie casi negro.

    La version anterior invertia la luminancia pixel a pixel. Eso conserva el grano del
    grabado de origen y las lineas de un texel de ancho, que no sobreviven ni al atlas ni al
    horneado al UV nuevo ni al JPEG: en el visor el emblema salia como una mancha blanca
    rota. Aqui se binariza la tinta, se ENGORDA el trazo (INK_GROW) y se suaviza el borde,
    que es lo que hace que la forma siga leyendose a 90 px de pecho — y ademas es lo que le
    corresponde al look cel del visor.

    El brillo morado de la lanza se detecta por tono en el original y se pinta encima del
    estarcido, tambien engordado, para que no se pierda.
    """
    rgb = logo[..., :3]
    alpha = logo[..., 3]
    lum = rgb.mean(axis=2)
    r = max(1, int(round(logo.shape[1] * INK_GROW)))

    ink = dilate((alpha > INK_ALPHA) & (lum < INK_LUM), r)
    soft = np.clip(box_blur(ink.astype(np.float32), INK_SOFT), 0, 1)[..., None]

    mx = rgb.max(axis=2); mn = rgb.min(axis=2)
    # El grabado tiene grano morado disperso por todo el laurel. Sin filtrar por DENSIDAD
    # local, cada punto suelto se engorda y el emblema sale con salpicaduras lavanda.
    purple_src = (np.clip((rgb[..., 2] - rgb[..., 1]) * 3.0, 0, 1) *
                  np.clip((mx - mn) * 4.0, 0, 1) * (alpha > INK_ALPHA)) > 0.25
    purple_src = box_blur(purple_src.astype(np.float32), max(2, r)) > INK_PURPLE
    purple = np.clip(box_blur(dilate(purple_src, r).astype(np.float32), INK_SOFT), 0, 1)[..., None]

    INK_RGB = np.array([0.93, 0.93, 0.96], np.float32)    # tinta clara, apenas fria
    GLOW_RGB = np.array([0.62, 0.32, 1.00], np.float32)   # morado de la lanza
    out = np.empty_like(logo)
    out[..., :3] = INK_RGB * (1 - purple) + GLOW_RGB * purple
    out[..., 3] = np.maximum(soft[..., 0], purple[..., 0])
    return out


def world_head(arm, bone_name):
    return arm.matrix_world @ arm.pose.bones[bone_name].head


def sample_bilinear_points(img, xs, ys):
    """img: (H, W, C) float array. xs, ys: 1D float pixel-coordinate arrays.
    Returns (N, C) bilinearly sampled values, clamped at the edges."""
    H, W, C = img.shape
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = x0 + 1
    y1 = y0 + 1
    wx = (xs - x0).astype(np.float32)
    wy = (ys - y0).astype(np.float32)
    x0c = np.clip(x0, 0, W - 1)
    x1c = np.clip(x1, 0, W - 1)
    y0c = np.clip(y0, 0, H - 1)
    y1c = np.clip(y1, 0, H - 1)
    Ia = img[y0c, x0c]
    Ib = img[y0c, x1c]
    Ic = img[y1c, x0c]
    Id = img[y1c, x1c]
    wx = wx[:, None]
    wy = wy[:, None]
    top = Ia * (1 - wx) + Ib * wx
    bot = Ic * (1 - wx) + Id * wx
    return top * (1 - wy) + bot * wy


def rasterize_chest_texels(mesh, uv_data, mw, front_faces, W, H):
    """For every triangle, rasterize its UV footprint and back-project each
    covered pixel's world (x, z) via barycentric interpolation.
    Returns concatenated arrays: pixel_x, pixel_y, world_x, world_z (all 1D)."""
    all_px, all_py, all_wx, all_wz = [], [], [], []
    for poly in front_faces:
        verts, uvs = [], []
        for li in poly.loop_indices:
            vidx = mesh.loops[li].vertex_index
            wp = mw @ mesh.vertices[vidx].co
            uv = uv_data[li].uv
            verts.append(wp)
            uvs.append((uv.x * W, uv.y * H))
        (u0, v0), (u1, v1), (u2, v2) = uvs
        wx0, wz0 = verts[0].x, verts[0].z
        wx1, wz1 = verts[1].x, verts[1].z
        wx2, wz2 = verts[2].x, verts[2].z

        x_min = max(0, int(math.floor(min(u0, u1, u2))))
        x_max = min(W, int(math.ceil(max(u0, u1, u2))) + 1)
        y_min = max(0, int(math.floor(min(v0, v1, v2))))
        y_max = min(H, int(math.ceil(max(v0, v1, v2))) + 1)
        if x_max <= x_min or y_max <= y_min:
            continue

        x_range = np.arange(x_min, x_max)
        y_range = np.arange(y_min, y_max)
        XX, YY = np.meshgrid(x_range + 0.5, y_range + 0.5)
        IIX, IIY = np.meshgrid(x_range, y_range)
        denom = (v1 - v2) * (u0 - u2) + (u2 - u1) * (v0 - v2)
        if abs(denom) < 1e-9:
            continue
        w0 = ((v1 - v2) * (XX - u2) + (u2 - u1) * (YY - v2)) / denom
        w1 = ((v2 - v0) * (XX - u2) + (u0 - u2) * (YY - v2)) / denom
        w2 = 1 - w0 - w1
        mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not mask.any():
            continue

        wxs = w0 * wx0 + w1 * wx1 + w2 * wx2
        wzs = w0 * wz0 + w1 * wz1 + w2 * wz2
        all_px.append(IIX[mask])
        all_py.append(IIY[mask])
        all_wx.append(wxs[mask])
        all_wz.append(wzs[mask])

    if not all_px:
        return (np.array([], dtype=np.int64),) * 2 + (np.array([], dtype=np.float64),) * 2
    return (np.concatenate(all_px), np.concatenate(all_py),
            np.concatenate(all_wx), np.concatenate(all_wz))


def main():
    common.ensure_dirs()

    arm = bpy.data.objects.get('Armature')
    obj = bpy.data.objects.get('Body')
    if arm is None or obj is None:
        print('CHEST_LOGO_FAIL missing Armature or Body')
        sys.exit(1)

    mesh = obj.data
    mw = obj.matrix_world
    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        print('CHEST_LOGO_FAIL no active UV layer on Body')
        sys.exit(1)
    uv_data = uv_layer.data

    mat = obj.data.materials[0]
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    base_link = bsdf.inputs['Base Color'].links
    if not base_link:
        print('CHEST_LOGO_FAIL Base Color has no input link')
        sys.exit(1)
    base_node = base_link[0].from_node
    if base_node.type != 'TEX_IMAGE' or base_node.image is None:
        print('CHEST_LOGO_FAIL Base Color source is not an image texture')
        sys.exit(1)
    orig_datablock = base_node.image

    # --- orientation-agnostic front/left detection via rig bones ---
    hf = world_head(arm, 'headfront')
    s6 = world_head(arm, 'spine006')
    front_sign = 1.0 if (hf.y - s6.y) > 0 else -1.0

    hl = world_head(arm, 'handL')
    sp = world_head(arm, 'spine')
    left_sign = 1.0 if (hl.x - sp.x) > 0 else -1.0

    x_lo, x_hi = sorted([0.04 * left_sign, 0.20 * left_sign])
    z_lo, z_hi = 1.08, 1.32   # pecho; por encima queda el cuello blanco de la camiseta
    print('CHEST_BOX_PARAMS', 'front_sign=', front_sign, 'left_sign=', left_sign,
          'x=', (x_lo, x_hi), 'z=', (z_lo, z_hi))

    # --- candidate faces in the chest x/z column whose normal faces forward ---
    # (a depth-based "closest to the camera" filter fails here: the hood and the
    # drawstrings stick out further than the chest surface itself.)
    nmat = mw.to_3x3().inverted().transposed()
    front_faces, n_candidates, ys = [], 0, []
    for poly in mesh.polygons:
        c = mw @ poly.center
        if not (x_lo <= c.x <= x_hi and z_lo <= c.z <= z_hi):
            continue
        n_candidates += 1
        n = (nmat @ poly.normal).normalized()
        if n.y * front_sign > 0.2:
            front_faces.append(poly)
            ys.append(c.y)

    if not front_faces:
        print('SE_NOT_FOUND no forward-facing faces in box', 'x=', (x_lo, x_hi), 'z=', (z_lo, z_hi))
        sys.exit(1)
    torso_y_extreme = max(ys) if front_sign > 0 else min(ys)
    print('CHEST_FACES', n_candidates, 'candidates,', len(front_faces),
          'front faces, torso_y_extreme=', round(torso_y_extreme, 4))

    w, h = orig_datablock.size

    # --- idempotent original-texture bootstrap: always paint from a pristine copy ---
    orig_path = os.path.join(common.GEN, 'character_texture_original.png')
    dark_mode = '--dark' in common.args()
    suffix = '_dark' if dark_mode else ''
    logo_out_path = os.path.join(common.GEN, f'character_texture_logo{suffix}.png')

    if not os.path.exists(orig_path):
        buf = np.empty(w * h * 4, dtype=np.float32)
        orig_datablock.pixels.foreach_get(buf)
        tmp_img = bpy.data.images.new('character_texture_original_tmp', w, h, alpha=True)
        tmp_img.pixels.foreach_set(buf)
        tmp_img.filepath_raw = orig_path
        tmp_img.file_format = 'PNG'
        tmp_img.save()
        bpy.data.images.remove(tmp_img)
        print('BOOTSTRAPPED_ORIGINAL', orig_path)

    work_img = bpy.data.images.load(orig_path, check_existing=False)
    ow, oh = work_img.size
    if (ow, oh) != (w, h):
        print('CHEST_LOGO_FAIL original texture size mismatch', (ow, oh), (w, h))
        sys.exit(1)
    buf = np.empty(ow * oh * 4, dtype=np.float32)
    work_img.pixels.foreach_get(buf)
    arr = buf.reshape(oh, ow, 4).copy()
    bpy.data.images.remove(work_img)

    # --- per-texel classification via barycentric world-position back-projection ---
    px_all, py_all, wx_all, wz_all = rasterize_chest_texels(mesh, uv_data, mw, front_faces, ow, oh)
    if px_all.size == 0:
        print('SE_NOT_FOUND no rasterized texels for chest faces')
        sys.exit(1)

    colors_all = arr[py_all, px_all, :3]
    white_all = colors_all.min(axis=1) > WHITE_THRESHOLD
    print('CHEST_TEXELS', px_all.size, 'total,', int(white_all.sum()), 'white')

    debug_white_map(wx_all, wz_all, white_all, os.path.join(common.RENDERS, 'chest_white_map.png'))

    if not white_all.any():
        print('SE_NOT_FOUND no white texels in chest region',
              'chest_box=', 'x=', (x_lo, x_hi), 'z=', (z_lo, z_hi), 'white_px=0')
        sys.exit(1)

    # --- isolate the monogram: connected components of white texels on a world-space
    # (x, z) grid. The drawstring aglets are also white and sit lower/closer to the
    # centre line; they form separate, smaller blobs. Keep the largest blob plus any
    # blob whose bbox lies within MERGE_DIST of it (S and E may be separate blobs).
    cell = 0.004  # 4 mm
    gx = np.floor((wx_all - wx_all.min()) / cell).astype(np.int64)
    gz = np.floor((wz_all - wz_all.min()) / cell).astype(np.int64)
    GW, GH = gx.max() + 3, gz.max() + 3
    grid = np.zeros((GH, GW), dtype=bool)
    grid[gz[white_all] + 1, gx[white_all] + 1] = True
    grid = dilate(grid, 1)
    labels, n_labels = label_components(grid)
    if n_labels == 0:
        print('SE_NOT_FOUND no white blobs')
        sys.exit(1)
    tex_labels = labels[gz + 1, gx + 1]
    counts = np.bincount(tex_labels[white_all], minlength=n_labels + 1)
    counts[0] = 0
    main_lbl = int(counts.argmax())
    keep = {main_lbl}
    bb = {}
    for lbl in range(1, n_labels + 1):
        sel = white_all & (tex_labels == lbl)
        if not sel.any():
            continue
        bb[lbl] = (wx_all[sel].min(), wx_all[sel].max(), wz_all[sel].min(), wz_all[sel].max())
    mx0, mx1, mz0, mz1 = bb[main_lbl]
    for lbl, (bx0, bx1, bz0, bz1) in bb.items():
        gap_x = max(bx0 - mx1, mx0 - bx1, 0.0)
        gap_z = max(bz0 - mz1, mz0 - bz1, 0.0)
        if math.hypot(gap_x, gap_z) <= MERGE_DIST:
            keep.add(lbl)
    se_mask = white_all & np.isin(tex_labels, list(keep))
    print('SE_BLOBS', n_labels, 'blobs; kept', sorted(keep), 'sizes',
          {l: int(counts[l]) for l in range(1, n_labels + 1)})
    for lbl, (bx0, bx1, bz0, bz1) in bb.items():
        print('  BLOB', lbl, 'x=', (round(bx0, 4), round(bx1, 4)), 'z=', (round(bz0, 4), round(bz1, 4)))

    se_x_min, se_x_max = wx_all[se_mask].min(), wx_all[se_mask].max()
    se_z_min, se_z_max = wz_all[se_mask].min(), wz_all[se_mask].max()
    print('SE_WORLD_BOX', 'x=', (round(se_x_min, 4), round(se_x_max, 4)),
          'z=', (round(se_z_min, 4), round(se_z_max, 4)), 'white_px=', int(se_mask.sum()))

    # --- erase the monogram: every texel whose grid cell is within ERASE_DILATE cells of
    # a kept white cell (world-space dilation: never bleeds into other UV islands) gets
    # the local hoodie colour (median of non-white texels around the monogram).
    se_grid = np.zeros_like(grid)
    se_grid[gz[se_mask] + 1, gx[se_mask] + 1] = True
    se_grid = dilate(se_grid, ERASE_DILATE)
    erase = se_grid[gz + 1, gx + 1]
    margin = 0.03
    near = ((wx_all >= se_x_min - margin) & (wx_all <= se_x_max + margin) &
            (wz_all >= se_z_min - margin) & (wz_all <= se_z_max + margin) & ~erase)
    if not near.any():
        print('CHEST_LOGO_FAIL no non-white texels to sample hoodie colour from')
        sys.exit(1)
    hoodie_color = np.median(colors_all[near], axis=0)
    print('HOODIE_COLOR', [round(float(c), 4) for c in hoodie_color], 'ERASED', int(erase.sum()))
    arr[py_all[erase], px_all[erase], 0:3] = hoodie_color

    # --- logo decal box in world space: LOGO_SCALE x SE height, aspect-locked, centred ---
    se_cx = (se_x_min + se_x_max) / 2.0
    se_cz = (se_z_min + se_z_max) / 2.0
    se_h_world = se_z_max - se_z_min

    logo_path = os.path.join(common.ROOT, 'refs', 'logo.png')
    logo_img = bpy.data.images.load(logo_path, check_existing=False)
    lw, lh = logo_img.size
    lbuf = np.empty(lw * lh * 4, dtype=np.float32)
    logo_img.pixels.foreach_get(lbuf)
    logo_arr = lbuf.reshape(lh, lw, 4).copy()
    bpy.data.images.remove(logo_img)
    if not dark_mode:
        logo_arr = to_light_print(logo_arr)
    print('LOGO_MODE', 'dark' if dark_mode else 'light')

    logo_h_world = LOGO_SCALE * se_h_world
    logo_w_world = logo_h_world * (lw / lh)
    logo_x_min = se_cx - logo_w_world / 2.0
    logo_x_max = se_cx + logo_w_world / 2.0
    logo_z_min = se_cz - logo_h_world / 2.0
    logo_z_max = se_cz + logo_h_world / 2.0
    print('LOGO_WORLD_BOX', 'x=', (round(logo_x_min, 4), round(logo_x_max, 4)),
          'z=', (round(logo_z_min, 4), round(logo_z_max, 4)))

    # --- paint: alpha-composite the logo over the (erased) texture, keeping its shading ---
    in_logo = ((wx_all >= logo_x_min) & (wx_all <= logo_x_max) &
               (wz_all >= logo_z_min) & (wz_all <= logo_z_max))
    n_paint = int(in_logo.sum())
    print('PAINT_TEXELS', n_paint)
    if n_paint == 0:
        print('CHEST_LOGO_FAIL logo box selects no texels')
        sys.exit(1)

    px_p = px_all[in_logo]
    py_p = py_all[in_logo]
    wx_p = wx_all[in_logo]
    wz_p = wz_all[in_logo]

    decal_u_raw = (wx_p - logo_x_min) / logo_w_world
    decal_v = (wz_p - logo_z_min) / logo_h_world
    # keep the logo upright/non-mirrored regardless of which world-x side is
    # "his left": a viewer in front sees his left on screen-right, i.e. the
    # +left_sign*x direction, so flip u only when left_sign < 0.
    decal_u = decal_u_raw if left_sign > 0 else (1.0 - decal_u_raw)

    logo_sample = sample_bilinear_points(logo_arr, decal_u * lw - 0.5, decal_v * lh - 0.5)
    alpha = np.clip(logo_sample[:, 3:4], 0.0, 1.0)
    base_rgb = arr[py_p, px_p, 0:3]
    final_rgb = logo_sample[:, 0:3] * alpha + base_rgb * (1 - alpha)

    arr[py_p, px_p, 0:3] = final_rgb
    print('LOGO_COMPOSITED', n_paint, 'texels, alpha>0.1:', int((alpha[:, 0] > 0.1).sum()))

    # --- save the new texture and repoint every node using the original image ---
    # NOTE: bpy.data.images.new() already defaults new color images to the
    # 'sRGB' colorspace (matching the original base-color texture). Do NOT
    # reassign new_img.colorspace_settings.name after foreach_set: doing so
    # before save() silently zeroes the RGB channels on write in this
    # Blender version (verified empirically) - alpha survives, RGB does not.
    new_img = bpy.data.images.new('texture_0_logo', ow, oh, alpha=True)
    new_img.pixels.foreach_set(arr.astype(np.float32).ravel())
    new_img.filepath_raw = logo_out_path
    new_img.file_format = 'PNG'
    new_img.save()
    print('SAVED_TEXTURE', logo_out_path)

    updated = 0
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image == orig_datablock:
                n.image = new_img
                updated += 1
    print('UPDATED_NODES', updated)

    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))

    # --- verification render: chest close-up, then clean up cam/light ---
    chest_center_x = se_cx
    cam_target = (chest_center_x, torso_y_extreme, se_cz)
    cam_loc = (chest_center_x, torso_y_extreme + front_sign * 0.8, se_cz)
    light_loc = (chest_center_x - 0.3 * left_sign, torso_y_extreme + front_sign * 0.5, se_cz + 0.5)
    fill_loc = (chest_center_x + 0.4 * left_sign, torso_y_extreme + front_sign * 0.6, se_cz - 0.2)

    cam = common.add_camera(cam_loc, cam_target, lens=70, name='ChestCam')
    light = common.add_light('ChestLight', 'AREA', light_loc, energy=400, color=(1, 1, 1), size=1.2)
    fill = common.add_light('ChestFill', 'AREA', fill_loc, energy=150, color=(1, 1, 1), size=1.0)

    common.render(os.path.join(common.RENDERS, f'chest_logo{suffix}.png'), res=(900, 900), samples=64)

    cam_data, light_data, fill_data = cam.data, light.data, fill.data
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)
    bpy.data.objects.remove(fill, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    bpy.data.lights.remove(light_data)
    bpy.data.lights.remove(fill_data)

    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
    print('CHEST_LOGO OK')


if __name__ == '__main__':
    main()

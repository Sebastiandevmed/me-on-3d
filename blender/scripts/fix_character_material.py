# blender/scripts/fix_character_material.py
# Corrige el material del personaje (Meshy lo exporta como METAL rugoso autoiluminado:
# Metallic 1, Roughness 1, Emission 1 con la textura base, specular x2) y limpia la textura:
#   1. mascara de islas UV rasterizada desde los triangulos de Body (2048x2048);
#   2. dilatado del color de cada isla sobre los canales (PAD px): el relleno color piel de
#      Meshy sangra en los bordes con mipmaps/JPEG y se ve como motas cafes en el hoodie;
#   3. mediana 3x3 (dos pasadas) SOLO en pixeles oscuros (luminancia < DARK): quita el ruido
#      de la ropa negra sin tocar la cara.
# Guarda generated/character_texture_clean.png y generated/character_uv_mask.png (blanco = isla,
# negro = hueco entre islas, usada por el check para medir la fuga de piel solo en los huecos),
# apunta el material a la textura limpia y guarda character.blend.
# Idempotente: parte SIEMPRE de generated/character_texture_logo.png (salida de apply_chest_logo.py).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/fix_character_material.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np

# Si repack_uvs.py ya corrio, la textura de partida es la horneada al UV nuevo (mismo contenido que
# character_texture_logo.png pero en el layout con margen); si no, la del logo en el UV de Meshy.
_REPACKED = os.path.join(common.GEN, 'character_texture_repacked.png')
_LOGO = os.path.join(common.GEN, 'character_texture_logo.png')
SRC = _LOGO   # main() cambia a _REPACKED si Body['uv_repacked'] esta puesto (no por existencia del archivo: puede ser de una corrida vieja)
OUT = os.path.join(common.GEN, 'character_texture_clean.png')
SIZE = 2048       # tamano por defecto; main() lo ajusta al de la textura de origen (4096 tras repack_uvs.py)
PAD = 16          # px de dilatado sobre los canales con el layout de Meshy (islas a 2-4 px: mas no cabe)
PAD_REPACKED = 32 # idem tras repack_uvs.py (islas grandes con margen: 32 cubre hasta el nivel 4 de mipmap)


def pad_for(body):
    """Ancho de dilatado que corresponde al layout UV actual de Body (lo usa tambien el check)."""
    return PAD_REPACKED if body.get('uv_repacked') else PAD
DARK = 0.25       # luminancia por debajo de la cual se aplica la mediana
MEDIAN_PASSES = 2
ROUGHNESS = 0.85


def uv_mask(body, size):
    """Mascara booleana (size x size) con True en los texeles cubiertos por triangulos UV."""
    me = body.data
    if me.uv_layers.active is None:
        common.fail('Body sin capa UV activa')
    uv = me.uv_layers.active.data
    mask = np.zeros((size, size), dtype=bool)
    tris = []
    for poly in me.polygons:
        li = list(poly.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append((uv[li[0]].uv, uv[li[k]].uv, uv[li[k + 1]].uv))
    # rasterizado por baricentricas en la caja de cada triangulo (numpy, sin PIL)
    for a, b, c in tris:
        xs = np.array([a.x, b.x, c.x]) * size; ys = (1.0 - np.array([a.y, b.y, c.y])) * size
        x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(size - 1, np.ceil(xs.max()) + 1))
        y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(size - 1, np.ceil(ys.max()) + 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(d) < 1e-9: continue
        w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
        w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
        w2 = 1.0 - w0 - w1
        eps = -0.002
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside
    return mask


_ORTHO = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))


def _spread(rgb, filled, offsets):
    """Suma de los vecinos ya rellenos en `offsets` y cuantos eran."""
    acc = np.zeros_like(rgb); cnt = np.zeros(filled.shape, dtype=np.float32)
    for dy, dx in offsets:
        sh = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
        fm = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
        acc += sh * fm[..., None]; cnt += fm
    return acc, cnt


def dilate_colors(rgb, mask, steps):
    """Rellena los pixeles fuera de la mascara con el color de la isla MAS CERCANA
    (iterativo: cada paso avanza un anillo desde las islas ya rellenas).

    Dos sub-pasadas por paso, ortogonales antes que diagonales, y NO una media de los 8
    vecinos a la vez. La diferencia importa donde dos islas de color muy distinto comparten
    canaleta, que en el atlas de Meshy es casi en todas partes (islas a 2-4 px): promediando
    los 8, un texel de canaleta pegado a una isla de piel pero en diagonal a una de hoodie
    salia gris, y ese gris es lo que el filtro bilineal se lleva de vuelta al borde de la
    isla clara. Con ortogonal primero, el anillo de cada isla toma solo el color de la isla
    a la que de verdad toca."""
    rgb = rgb.copy(); filled = mask.copy()
    for _ in range(steps):
        new_rgb = rgb.copy(); new_filled = filled.copy()
        acc, cnt = _spread(rgb, filled, _ORTHO)
        take = (~filled) & (cnt > 0)
        new_rgb[take] = acc[take] / cnt[take][:, None]
        new_filled |= take
        acc, cnt = _spread(rgb, filled, _DIAG)      # solo los que no tocaban ninguna isla de lado
        take = (~new_filled) & (cnt > 0)
        new_rgb[take] = acc[take] / cnt[take][:, None]
        new_filled |= take
        rgb, filled = new_rgb, new_filled
    return rgb


def median3(rgb):
    stack = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            stack.append(np.roll(np.roll(rgb, dy, axis=0), dx, axis=1))
    return np.median(np.stack(stack, axis=0), axis=0)


def main():
    common.ensure_dirs()
    global SRC, PAD
    if bpy.data.objects['Body'].get('uv_repacked'):
        SRC = _REPACKED
    PAD = pad_for(bpy.data.objects['Body'])
    print('TEXCLEAN PAD', PAD)
    print('TEXCLEAN textura de origen', os.path.basename(SRC))
    if not os.path.exists(SRC):
        common.fail(f'falta {SRC} (ejecutar apply_chest_logo.py antes)')
    body = bpy.data.objects['Body']
    m = bpy.data.materials['Character']
    bsdf = m.node_tree.nodes['Principled BSDF']

    # --- 1. textura de origen (siempre la de apply_chest_logo.py)
    src = bpy.data.images.load(SRC, check_existing=True)
    src.reload()
    w, h = src.size
    px = np.empty(w * h * 4, dtype=np.float32); src.pixels.foreach_get(px)
    img = px.reshape(h, w, 4)[::-1, :, :3]          # bpy guarda de abajo a arriba; se voltea a "arriba primero"
    global SIZE
    if w != h or w < 2048:
        common.fail(f'textura de origen {w}x{h}: se espera cuadrada y >= 2048')
    SIZE = w

    # --- 2. mascara UV y dilatado
    mask = uv_mask(body, SIZE)
    print('TEXCLEAN mascara islas', round(float(mask.mean()), 4), 'de la textura')
    if not (0.15 < mask.mean() < 0.95):
        common.fail('la mascara UV cubre una fraccion improbable de la textura')

    # se guarda la mascara como PNG (blanco = dentro de isla, negro = hueco entre islas) para que
    # el check pueda medir el color piel SOLO en los huecos, no en toda la textura (la piel real
    # de la cara esta dentro de las islas y no debe contarse como fuga). Misma orientacion de filas
    # que la textura al guardar (bpy guarda de abajo a arriba: se voltea igual que rgb mas abajo).
    mask_path = os.path.join(common.GEN, 'character_uv_mask.png')
    mask_img = bpy.data.images.get('character_uv_mask') or bpy.data.images.new('character_uv_mask', SIZE, SIZE, alpha=False)
    mask_img.scale(SIZE, SIZE)
    mbuf = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    mbuf[..., :3] = mask[::-1, :, None].astype(np.float32)
    mask_img.pixels.foreach_set(mbuf.ravel())
    mask_img.filepath_raw = mask_path; mask_img.file_format = 'PNG'
    mask_img.save(); mask_img.reload()
    print('TEXCLEAN mascara UV guardada', mask_path)

    rgb = dilate_colors(img, mask, PAD)
    # lo que queda sin rellenar (canales anchos) toma el color medio de la ropa (oscuro) en vez de piel
    filled = mask.copy()
    for _ in range(PAD):
        filled |= np.roll(filled, 1, 0) | np.roll(filled, -1, 0) | np.roll(filled, 1, 1) | np.roll(filled, -1, 1)
    dark_sel = mask & (img.mean(axis=2) < DARK)
    if not dark_sel.any():
        common.fail('no hay pixeles oscuros dentro de la mascara UV para calcular el color de relleno lejano')
    dark_mean = np.median(img[dark_sel], axis=0)
    rgb[~filled] = dark_mean
    print('TEXCLEAN color de relleno lejano', [round(float(c), 3) for c in dark_mean])

    # --- 3. mediana en oscuros (solo dentro de islas)
    lum = rgb.mean(axis=2)
    dark = mask & (lum < DARK)
    for _ in range(MEDIAN_PASSES):
        med = median3(rgb)
        rgb[dark] = med[dark]
    print('TEXCLEAN pixeles suavizados', int(dark.sum()))

    # --- 4. guardar PNG y apuntar el material
    out = bpy.data.images.get('character_texture_clean') or bpy.data.images.new('character_texture_clean', SIZE, SIZE, alpha=False)
    out.scale(SIZE, SIZE)
    buf = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    buf[..., :3] = np.clip(rgb[::-1], 0, 1)
    out.pixels.foreach_set(buf.ravel())
    out.filepath_raw = OUT; out.file_format = 'PNG'
    out.save(); out.reload()
    print('TEXCLEAN guardada', OUT)
    # NOTA: el nombre real del datablock de imagen NO es 'character_texture_logo' (lo es
    # solo el nombre de archivo): apply_chest_logo.py lo crea como 'texture_0_logo' (Blender
    # le agrega sufijo .001 si ya existia un datablock con ese nombre). Repuntar por nombre de
    # datablock no funciona; se repunta por identidad contra 'src' (cargado arriba desde SRC,
    # que es el mismo archivo que usan los nodos, asi que check_existing=True devuelve el mismo
    # datablock).
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is src:
            n.image = out

    # --- 5. material
    for l in list(m.node_tree.links):
        if l.to_node == bsdf and l.to_socket.name == 'Emission Color':
            m.node_tree.links.remove(l)
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Roughness'].default_value = ROUGHNESS
    bsdf.inputs['Emission Strength'].default_value = 0.0
    bsdf.inputs['Emission Color'].default_value = (0, 0, 0, 1)
    bsdf.inputs['Specular IOR Level'].default_value = 0.5
    # Meshy deja 'Specular Tint' en (2,2,2): el exportador glTF lo emite como
    # KHR_materials_specular.specularColorFactor [2,2,2] y el hoodie negro brilla como plastico.
    # Blanco (1,1,1) es el valor por defecto, asi que la extension desaparece del GLB
    # (lo verifica export_glb.py: 'Character sin KHR_materials_specular').
    bsdf.inputs['Specular Tint'].default_value = (1.0, 1.0, 1.0, 1.0)
    body['texture_clean'] = True
    print('MATERIAL Character metallic 0 roughness', ROUGHNESS, 'emission 0 specular_tint 1')

    # --- 6. render de aprobacion (misma camara que apply_chest_logo: torso de frente)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.add_camera((0.0, 1.6, 1.25), (0.0, 0.0, 1.25), lens=70)
    common.add_light('k', 'AREA', (-1.0, 1.5, 2.0), 250, (0.85, 0.9, 1.0), size=1.2)
    common.add_light('f', 'AREA', (1.2, 1.2, 1.0), 80, (1.0, 0.95, 0.9), size=1.5)
    common.render(os.path.join(common.RENDERS, 'material_fix.png'), res=(900, 900), samples=48)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))


if __name__ == '__main__':
    main()

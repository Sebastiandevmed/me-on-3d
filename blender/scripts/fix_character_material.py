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

SRC = os.path.join(common.GEN, 'character_texture_logo.png')
OUT = os.path.join(common.GEN, 'character_texture_clean.png')
SIZE = 2048
PAD = 16          # px de dilatado sobre los canales
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


def dilate_colors(rgb, mask, steps):
    """Rellena los pixeles fuera de la mascara con el color del vecino de isla mas cercano
    (iterativo: cada paso copia desde los 8 vecinos ya rellenos)."""
    rgb = rgb.copy(); filled = mask.copy()
    for _ in range(steps):
        new_rgb = rgb.copy(); new_filled = filled.copy()
        acc = np.zeros_like(rgb); cnt = np.zeros(mask.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0: continue
                sh = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                fm = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
                acc += sh * fm[..., None]; cnt += fm
        take = (~filled) & (cnt > 0)
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
    if (w, h) != (SIZE, SIZE):
        common.fail(f'textura de origen {w}x{h}, esperada {SIZE}x{SIZE}')

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

# blender/scripts/redilate_texture.py
# Vuelve a dilatar el color de las islas sobre las CANALETAS de la textura, al final de la cadena.
#
# EL BUG QUE ARREGLA (sesion 8). El orden de la cadena era:
#     fix_character_material.py   -> limpia y DILATA el color de cada isla sobre las canaletas
#     texture_touchup.py          -> repinta dentro de las islas (borra las cejas pintadas)
#     face_features.py            -> repinta dentro de las islas (barba del menton, labios)
# Los dos ultimos trabajan POR TEXEL rasterizando triangulos, asi que solo tocan texeles que
# estan DENTRO de una isla. Las canaletas conservan el color que tenian ANTES del repintado:
# color piel. Es decir, cada isla que se oscurecio a barba quedo rodeada de un anillo de piel.
#
# En pantalla la cara se ve AMPLIADA (la textura da ~0.5 mm por texel y la cabeza ocupa unos
# 600 px), asi que el filtro bilineal magnifica: un anillo de 1 texel se convierte en una raya
# de 2-4 px de color piel siguiendo el borde de cada isla. Eso es lo que se veia como "lineas
# color piel" por toda la barba y como la boca "garabateada" — la banda de labios es estrecha
# y cruza varios bordes de isla, asi que el halo se la comia por los dos lados.
#
# No es un problema de mipmaps: a esa distancia el muestreo es de MAGNIFICACION y ni siquiera
# se usan. Por eso ?mat=nomip no cambiaba nada.
#
# Reusa uv_mask() y dilate_colors() de fix_character_material.py: son la version probada, y
# la mascara tiene que salir de la MISMA capa UV que usa el resto de la cadena.
#
# Idempotente: dilatar dos veces sobre la misma mascara da el mismo resultado (no toca ningun
# texel dentro de isla).
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/redilate_texture.py
#      -- --out generated/otra.png   escribe en otro archivo en vez de en sitio (para comparar)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np
import fix_character_material as fcm

TEX = os.path.join(common.GEN, 'character_texture_clean.png')


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out_path = TEX
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1]
        if not os.path.isabs(out_path):
            out_path = os.path.join(common.ROOT, out_path)

    body = bpy.data.objects['Body']
    if not body.get('uv_repacked'):
        common.fail('Body sin uv_repacked: redilate_texture.py va DESPUES de repack_uvs.py')
    if not os.path.exists(TEX):
        common.fail(f'falta {TEX} (ejecutar fix_character_material.py antes)')

    src = bpy.data.images.load(TEX, check_existing=True)
    src.reload()
    w, h = src.size
    if w != h:
        common.fail(f'textura {w}x{h}: se espera cuadrada')
    px = np.empty(w * h * 4, dtype=np.float32); src.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[::-1, :, :3].copy()   # bpy guarda de abajo a arriba

    mask = fcm.uv_mask(body, w)
    frac = float(mask.mean())
    print('REDILATE mascara islas', round(frac, 4), 'de la textura')
    if not (0.15 < frac < 0.95):
        common.fail('la mascara UV cubre una fraccion improbable de la textura')

    pad = fcm.pad_for(body)
    before = rgb.copy()
    dil = fcm.dilate_colors(rgb, mask, pad)
    rgb[~mask] = dil[~mask]                         # dentro de isla NO se toca un solo texel

    # Relleno LEJANO, exactamente como fix_character_material.py. Hace falta porque
    # dilate_colors() avanza por los 8 vecinos (diagonales incluidas) mientras que el alcance
    # `filled` se mide por los 4 ortogonales: la dilatacion llega un poco mas lejos de lo que
    # se considera "cubierto", y esos texeles de mas se rellenan con el color oscuro de la ropa.
    # Sin esto, el color piel se cuela mas alla del alcance y check_character_material.py falla
    # con skin_frac_far por encima del umbral.
    filled = mask.copy()
    for _ in range(pad):
        filled |= np.roll(filled, 1, 0) | np.roll(filled, -1, 0) | np.roll(filled, 1, 1) | np.roll(filled, -1, 1)
    dark_sel = mask & (rgb.mean(axis=2) < fcm.DARK)
    if not dark_sel.any():
        common.fail('no hay texeles oscuros dentro de la mascara para el relleno lejano')
    rgb[~filled] = np.median(rgb[dark_sel], axis=0)

    changed = int((np.abs(rgb - before).max(axis=2) > 1 / 255).sum())
    print('REDILATE PAD', pad, '| texeles de canaleta corregidos', changed)
    # Si el repintado posterior no hubiera dejado canaletas rancias, este numero seria ~0. Es la
    # medida del bug: cuantos texeles de canaleta llevaban un color que ya no existe en su isla.
    if changed == 0:
        print('REDILATE aviso: no habia nada que corregir')

    name = os.path.splitext(os.path.basename(out_path))[0]
    out = bpy.data.images.get(name) or bpy.data.images.new(name, w, w, alpha=False)
    out.scale(w, w)
    buf = np.ones((w, w, 4), dtype=np.float32)
    buf[..., :3] = np.clip(rgb[::-1], 0, 1)
    out.pixels.foreach_set(buf.ravel())
    out.filepath_raw = out_path; out.file_format = 'PNG'
    out.save(); out.reload()
    print('REDILATE guardada', out_path)


main()

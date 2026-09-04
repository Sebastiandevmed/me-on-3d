# blender/scripts/checks/check_character_material.py
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/checks/check_character_material.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
import numpy as np
import fix_character_material as fcm  # reusa PAD: el ancho de dilatado define donde termina el
                                       # "halo" de borde (legitimamente del color de la isla vecina,
                                       # tambien piel si esa isla es piel) y donde empieza el relleno
                                       # "lejano" (el que antes tenia el color piel global de Meshy).

m = bpy.data.materials.get('Character')
if m is None: common.fail('falta el material Character')
bsdf = m.node_tree.nodes.get('Principled BSDF')
if bsdf is None: common.fail('Character sin Principled BSDF')
val = lambda n: bsdf.inputs[n].default_value
if abs(val('Metallic')) > 1e-6: common.fail(f"Metallic {val('Metallic')} != 0")
if not (0.7 <= val('Roughness') <= 0.95): common.fail(f"Roughness {val('Roughness')} fuera de 0.7..0.95")
if abs(val('Emission Strength')) > 1e-6: common.fail(f"Emission Strength {val('Emission Strength')} != 0")
if bsdf.inputs['Emission Color'].is_linked: common.fail('Emission Color sigue enchufado a la textura')
if not bsdf.inputs['Base Color'].is_linked: common.fail('Base Color sin textura')
if abs(val('Specular IOR Level') - 0.5) > 1e-6: common.fail(f"Specular IOR Level {val('Specular IOR Level')} != 0.5")
img = bsdf.inputs['Base Color'].links[0].from_node.image
if img is None or not img.filepath_raw.endswith('character_texture_clean.png'):
    common.fail(f'Base Color no apunta a character_texture_clean.png: {img and img.filepath_raw}')
if img.size[0] != img.size[1] or img.size[0] < 2048: common.fail(f'textura limpia {tuple(img.size)}: se espera cuadrada y >= 2048 (4096 tras repack_uvs.py)')

# la mascara de islas UV (blanco = dentro de isla, negro = hueco) la escribe fix_character_material.py;
# se usa para medir la fuga de color piel SOLO en los huecos entre islas, no en toda la textura
# (contar la piel real de la cara, que esta dentro de las islas, conflaba la metrica global con
# la fuga real y pasaba/fallaba por muy poco margen).
mask_path = os.path.join(common.GEN, 'character_uv_mask.png')
if not os.path.exists(mask_path):
    common.fail('falta generated/character_uv_mask.png (ejecutar fix_character_material.py)')
mask_img = bpy.data.images.load(mask_path, check_existing=True)
mask_img.reload()
if tuple(mask_img.size) != tuple(img.size):
    common.fail(f'mascara UV {tuple(mask_img.size)} != textura limpia {tuple(img.size)}')
mw, mh = mask_img.size
mpx = np.empty(mw * mh * 4, dtype=np.float32)
mask_img.pixels.foreach_get(mpx)
mask_bool = mpx.reshape(mh, mw, 4)[:, :, 0] > 0.5

# pixeles "piel" (R alto, G medio, B bajo)
px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
img.pixels.foreach_get(px)
rgb2d = px.reshape(img.size[1], img.size[0], 4)[:, :, :3]
skin2d = (rgb2d[:, :, 0] > 0.75) & (rgb2d[:, :, 1] > 0.45) & (rgb2d[:, :, 1] < 0.72) & (rgb2d[:, :, 2] < 0.60)
global_frac = float(skin2d.mean())
gutter = ~mask_bool
gutter_frac = float(skin2d[gutter].mean()) if gutter.any() else 0.0
print('CHECK_MAT skin_frac_global', round(global_frac, 4))
print('CHECK_MAT skin_frac_gutter', round(gutter_frac, 4))

# el hueco entre islas se divide en dos zonas MUY distintas: el halo de PAD px alrededor de cada
# isla (fix_character_material.py lo pinta con el color de la isla vecina a proposito -- si esa
# isla es piel, el halo TAMBIEN debe ser piel, para que el mipmap/JPEG no cree una costura visible
# en el render; no es una fuga) y el relleno "lejano" mas alla de PAD (el que antes tenia el color
# piel GLOBAL de Meshy sin relacion con la isla mas cercana: ese es el bug real). Con un atlas tan
# fragmentado (muchas islas pequenas y juntas) el halo cubre la mayor parte del hueco -- medir
# "todo el hueco" mezcla otra vez piel legitima (la del halo junto a islas de piel) con la fuga
# real, igual que el metodo global que se reemplaza aqui. Se aisla el relleno lejano dilatando la
# mascara PAD veces (mismo PAD que usa fix_character_material.py) y se exige piel ~0 solo ahi.
filled = mask_bool.copy()
body = bpy.data.objects.get('Body')
if body is None: common.fail('no hay malla Body')
for _ in range(fcm.pad_for(body)):
    filled |= np.roll(filled, 1, 0) | np.roll(filled, -1, 0) | np.roll(filled, 1, 1) | np.roll(filled, -1, 1)
far = gutter & ~filled
far_frac = float(skin2d[far].mean()) if far.any() else 0.0
print('CHECK_MAT skin_frac_far (mas alla de PAD =', fcm.pad_for(body), 'px de cualquier isla)', round(far_frac, 4))
if far_frac > 0.01:
    common.fail(f'demasiado color piel en el relleno lejano ({far_frac:.4f} > 0.01): el dilatado no cubrio los canales')
body = bpy.data.objects.get('Body')
if body is None or not body.get('texture_clean'): common.fail("Body['texture_clean'] no esta puesto")
print('CHECK_CHARACTER_MATERIAL OK')

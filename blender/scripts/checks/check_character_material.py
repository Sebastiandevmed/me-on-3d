# blender/scripts/checks/check_character_material.py
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/checks/check_character_material.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common
import numpy as np

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
if tuple(img.size) != (2048, 2048): common.fail(f'textura limpia {tuple(img.size)} != 2048x2048')
# la textura limpia no debe tener relleno color piel en los canales: se mide la fraccion de
# pixeles "piel" (R alto, G medio, B bajo) fuera de la piel real (la piel real es < 12% del atlas)
px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
img.pixels.foreach_get(px)
rgb = px.reshape(-1, 4)[:, :3]
skin = (rgb[:, 0] > 0.75) & (rgb[:, 1] > 0.45) & (rgb[:, 1] < 0.72) & (rgb[:, 2] < 0.60)
frac = float(skin.mean())
print('CHECK_MAT skin_frac', round(frac, 4))
if frac > 0.12: common.fail(f'demasiado color piel en la textura limpia ({frac:.3f} > 0.12): el dilatado no cubrio los canales')
body = bpy.data.objects.get('Body')
if body is None or not body.get('texture_clean'): common.fail("Body['texture_clean'] no esta puesto")
print('CHECK_CHARACTER_MATERIAL OK')

#!/bin/zsh
# Regeneracion COMPLETA del personaje y del GLB, en el orden que exige la cadena
# (ver README, "Regenerar todo"). Se usa cuando cambia algo que vive antes del
# reempaquetado de UV — por ejemplo apply_chest_logo.py, que trabaja en el UV ORIGINAL de
# Meshy y por eso no se puede reejecutar sobre un character.blend ya reempaquetado.
#
# Uso: tools/rebuild_character.sh [2>&1 | tee /tmp/rebuild.log]
set -e
set -o pipefail
cd "$(dirname "$0")/.."
B=tools/run_blender.sh
step() { echo "\n=== $* ==="; }

step import_character;          $B - blender/scripts/import_character.py
step apply_chest_logo;          $B blender/character.blend blender/scripts/apply_chest_logo.py
step fix_character_material_1;  $B blender/character.blend blender/scripts/fix_character_material.py
step check_character_material;  $B blender/character.blend blender/scripts/checks/check_character_material.py
step add_face_parts;            $B blender/character.blend blender/scripts/add_face_parts.py
step hide_neck_headphones;      $B blender/character.blend blender/scripts/hide_neck_headphones.py
step add_headphones;            $B blender/character.blend blender/scripts/add_headphones.py
step fix_head_weights;          $B blender/character.blend blender/scripts/fix_head_weights.py
step close_gaps;                $B blender/character.blend blender/scripts/close_gaps.py
step repack_uvs;                $B blender/character.blend blender/scripts/repack_uvs.py
step fix_character_material_2;  $B blender/character.blend blender/scripts/fix_character_material.py
step check_character_material;  $B blender/character.blend blender/scripts/checks/check_character_material.py
step texture_touchup;           $B blender/character.blend blender/scripts/texture_touchup.py
step face_features;             $B blender/character.blend blender/scripts/face_features.py
# SIEMPRE el ultimo retoque de textura: vuelve a dilatar el color de las islas sobre las
# canaletas. texture_touchup y face_features solo pintan DENTRO de los triangulos, asi que sin
# esto las canaletas conservan el color de antes del repintado y salen como rayas claras.
step redilate_texture;          $B blender/character.blend blender/scripts/redilate_texture.py
step smooth_normals;            $B blender/character.blend blender/scripts/smooth_normals.py
step check_rig;                 $B blender/character.blend blender/scripts/checks/check_rig.py
step check_face_export;         $B blender/character.blend blender/scripts/checks/check_face_export.py
step animate;                   $B blender/character.blend blender/scripts/animate.py
step check_anim;                $B blender/character_anim.blend blender/scripts/checks/check_anim.py
step assemble;                  $B - blender/scripts/assemble.py
step export_glb;                $B blender/avatar.blend blender/scripts/export_glb.py
step glb_inspect;               python3 tools/glb_inspect.py export/avatar.glb
echo "\n=== REBUILD OK ==="

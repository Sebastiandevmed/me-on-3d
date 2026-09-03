# HANDOFF — Avatar 3D "Me on 3D"

Documento de traspaso para continuar en una conversación nueva con el mismo flujo de trabajo. Se actualiza en cada hito.

**Última actualización:** 2026-09-03 (sesión 3, plan de pulido: tareas 15-21 completas sobre las 14 de la sesión 2; pendiente: URL del repo del portafolio, aprobaciones visuales del usuario y decisión de archivado)

## Cómo retomar

1. Leer este archivo, la spec y los planes:
   - Spec: `docs/superpowers/specs/2026-09-03-avatar-3d-design.md`
   - Plan 1: `docs/superpowers/plans/2026-09-03-avatar-3d.md` (14 tareas, sesión 2)
   - Plan 2: `docs/superpowers/plans/2026-09-03-avatar-polish.md` (7 tareas de pulido, sesión 3 = tareas 15-21)
   - Ledgers de ejecución: `.superpowers/sdd/2026-09-03-avatar-3d/progress.md` y `.superpowers/sdd/2026-09-03-avatar-polish/progress.md` (qué tareas están completas, rulings tomados). OJO: `.superpowers/` está en .gitignore → el ledger solo existe en este Mac.
2. Flujo de trabajo acordado: skill **superpowers:subagent-driven-development** sobre el plan. Un subagente implementador por tarea + revisor por tarea. Las tareas marcadas [SESIÓN PRINCIPAL] (4, 5, 10, 14) las hace el agente principal porque usan Higgsfield y necesitan aprobación de Sebastián.
3. Rama git: `avatar-3d` (main solo tiene docs). Identidad git configurada localmente.
4. Hablar en español. Mostrar renders/láminas al usuario con SendUserFile y con `open` antes de cada punto de aprobación.

## Quién es el usuario (resumen)

Sebastián Escobar, desarrollador web de Medellín (Campo Valdés). Moda urbana, ropa ancha, gorras flexfit (visera curva, puesta normal, NUNCA al revés), barba completa, piel clara-oliva (no morena), pelo rizado con corte "7" (lados cortos, más largo y crespo atrás, tipo brócoli). Dos candongas en CADA oreja (obligatorio). Rap: gesto característico = cabecear con ojos cerrados. Gamer. Moto Suzuki DR150 blanca/azul con baúl negro. Stack: Shopify, Supabase, Cloudflare. Ropa: el usuario pidió luego un diseño MÁS COMERCIAL (sin letras góticas): monograma SE pequeño en el pecho, espalda con MEDELLÍN + montañas minimalistas.

## Decisiones aprobadas por el usuario

- Entregable A: `.blend` + GLB (Draco) + visor preview. NO se construye la web.
- Estilo cartoon tipo moncy.dev. Sentado tecleando en escritorio con Mac + 3 monitores, barras RGB, mini DR150 en repisa, ventana con Medellín de noche (Puente de la 4 Sur), control de consola, taza.
- Clips: introAnimation, typing, idle, Blink, browup, vibe (cabeceo rap), lookAround.
- Pipeline opción 1: lámina IA (Higgsfield nano_banana_pro) → Meshy multi_image_to_3d con rigging → Blender por script.
- Ejecución: subagentes (opción 1).

## Estado por tarea

| Tarea | Estado | Notas |
|---|---|---|
| 1 Infraestructura (common.py, glb_inspect, run_blender.sh) | ✅ completa (e3dfb01) | review limpia |
| 2 Texturas de pantalla (Chrome headless) | ✅ completa (49a181b) | generated/screens/*.png |
| 3 Escena del escritorio (build_scene.py) | ✅ completa (3fbe233) | cámara al frente (-1.3,3.7,1.95); ventana/RGB detrás; monitores bajos en arco; pantallas con backface culling; renders scene_v1.png y scene_v1_screens.png |
| 4 Lámina del personaje (Higgsfield) | ✅ APROBADA sheet_g (= sheet_APPROVED.png) | D + rizos de C. Vistas recortadas view_0..3.png |
| 5 Malla rigueada Meshy | ✅ v2 APROBADA (generated/meshy/character_rigged.glb, 82.9k tris → 38k en Blender) | espalda sin estampado (aceptado) |
| 6 Importar personaje (import_character.py, check_rig.py) | ✅ completa | autodetección de orientación con el hueso headfront (rota 180° si mira a -Y; el importador glTF deja el armature en QUATERNION, por eso se fuerza rotation_mode XYZ); cámara de control en +Y; check_rig valida headfront.y > spine006.y |
| 6b Logo en el pecho (apply_chest_logo.py) | ✅ completa | borra el "SE" por texel (componentes conexos en espacio mundo, excluye cordones/cuello) y compone `refs/logo.png` como estampado CLARO (luminancia invertida, brillo morado conservado) porque el hoodie es casi negro. Render: generated/renders/chest_logo.png. Variante oscura de comparación: chest_logo_dark.png (`-- --dark`). Es idempotente: parte siempre de generated/character_texture_original.png. **Rerun obligatorio tras cada import_character.py.** |
| 7 Pose sentada (pose_probe.py, poses.py, sit_test.py) | ✅ completa (5128355) | ejes calibrados (shin = (0,-1), no (0,1)); brazos con eulers horneados por `poses.aim()`; render de aprobación generated/renders/sit_v_final.png (+_legs, _hands) enviado al usuario |
| 8 Párpados, cejas, candongas (render_face_grid.py, add_face_parts.py, checks/check_face_export.py) | ✅ completa (dea3b6f) | huesos eyelidL/R (+70° X = cerrado), eyebrow_L/R (+0.012 Z = levantada) con ejes locales = mundo; 8 mallas parentadas a hueso (exportan como hijas del hueso, verificado); 39 496 tris; renders face_parts_open/closed_browup/ear_L/ear_R.png. add_face_parts.py es idempotente y modifica character.blend en sitio (NO reejecutar import_character.py sin repetir luego apply_chest_logo.py y add_face_parts.py) |
| 9 Animaciones (animate.py, checks/check_anim.py, anim_strip.py → character_anim.blend) | ✅ completa (bde74c3) | 7 acciones + 7 pistas NLA; sin dedos (typing = bob de manos/antebrazos); idle solo spine001/002/003/005; vibe **reescrito en la sesión 3** (216 f: se pone los audífonos, cabecea con ojos cerrados y se los quita — ver "Sesión 3" más abajo); tiras en generated/renders/strip_*.png. Regla de mezcla para el visor: idle base, typing superpuesto (huesos disjuntos), vibe/lookAround en exclusiva con idle fundido a 0. Exportar con SIT aplicada (los huesos sin clip toman la pose exportada) |
| 10 Moto + ventana Medellín (Higgsfield) | ✅ completa | generated/moto/dr150.glb (v2a: cortavientos Acerbis, sin baúl; 7958 tris, 4 MB, textura a reducir a 1k en ensamblaje/export), previews moto_preview_0..2.png. Ventana: recorte 16:9 de medellin_a → generated/window/medellin.png, plano corregido (90°,0,180°) en build_scene.py |
| 11 Ensamblaje + HDR (assemble.py, render_hdr.py → avatar.blend, export/night.hdr) | ✅ completa (fc797d1 + fix 0011ced) | 48 214 tris; colocación por muslos (importa sit_test.py); moto 0.25 m yaw -30° textura 1k; HDR 169 KB; avatar.blend guardado NEUTRO (frame 1, sin acción, pistas muted, emisión 0, rutas relativas). Render de aprobación generated/renders/assembled_v1.png. Typing corregido (655cf7f) para no atravesar el escritorio |
| 12 Exportación GLB (export_glb.py) | ✅ completa (22f7210) | export/avatar.glb 1.94 MB Draco, JPEG q85, 48 390 tris, 7 clips con solo sus huesos (keep_anim_armature=False), pose base = SIT (export_reset_pose_bones=False, pistas muted al exportar), pantallas con emissiveTexture; avatar_uncompressed.glb 4.3 MB; generated/avatar_inspect.json. **Cifras actualizadas en la sesión 3**: 9990 KB Draco / 49 390 tris, textura del personaje JPEG q92 a 2048 y `medellin` a 1504 sin reescalar; el material `Character` ya NO trae emisión |
| 13 Visor (export/preview.html, tools/serve_preview.sh) | ✅ completa (13b0bed, review limpia) | three.js 0.170 + Draco + night.hdr como entorno; intro → idle+typing+Blink; vibe/lookAround exclusivos; seguimiento de cursor en spine006 (restaura el cuaternión del clip cada frame); captura generated/renders/preview_shot.png. **Ampliado en la sesión 3** (tarea 20): luces y sombras de habitación, pecho acompañando a la cabeza, sonda `preview_probe.mjs`; YAVG 73.2. Prueba manual pendiente del usuario: `tools/serve_preview.sh` → http://localhost:8765/preview.html |
| 14 Cierre (README.md, créditos, memoria) | ✅ completa (159adec) | README; credits.log cerrado; memoria actualizada. Paso 1 (fotos definitivas) omitido: el usuario no las entregó |

## Sesión 3 (2026-09-03): plan de pulido

Plan: `docs/superpowers/plans/2026-09-03-avatar-polish.md` (7 tareas, numeradas aquí 15-21 para seguir a las 14 de la sesión 2).
Ledger: `.superpowers/sdd/2026-09-03-avatar-polish/progress.md` (solo local).
Origen: hallazgos visuales del usuario sobre `preview_shot.png` (motas claras en el hoodie, cuarto vacío/negro, typing mecánico, audífonos fundidos al cuello).

| Tarea | Estado | Notas y render de aprobación |
|---|---|---|
| 15 Material y textura del personaje (`fix_character_material.py`, `checks/check_character_material.py`) | ✅ completa (c003959 + fix 77403a0) | Metallic 0 / Roughness 0.85 / sin emisión / Specular Tint blanco; textura limpia por dilatado de islas (16 px) + mediana 3×3 en píxeles oscuros. El check mide la fuga de color piel MÁS ALLÁ del halo (`skin_frac_far` 8.76% → 0.0%, umbral 0.01) contra `generated/character_uv_mask.png`. Render: `generated/renders/material_fix.png` |
| 16 Habitación, repisa y ventana (`build_scene.py`, `checks/check_scene.py`) | ✅ completa (bda12cf) | paredes (`wall_back_L/R/top/bottom`, `wall_left`, `wall_right`), `ceiling`, hueco de ventana 3.2×1.8 con marco (`window_near`, `window_head`, `window_post_L/R`), repisa con soportes en x=2.0, z=1.45 y moto de 0.32 m. 904 tris de escena. Render: `generated/renders/scene_v1.png` |
| 17 Typing v2 (`animate.py`) | ✅ completa (b3cdd76) | golpes irregulares por mano, hover bajo y deriva lateral; el clip sigue tocando solo brazos y manos. Tira: `generated/renders/strip_typing.png` |
| 18 Audífonos como pieza aparte (`hide_neck_headphones.py`, `add_headphones.py`, `blender/headphones.json`) | ✅ completa (3427790) | las copas que Meshy dejó fundidas al cuello se encogen por isla hacia el eje del cuello; la pieza nueva (`headphones_band`, `headphones_cup_L/R`) cuelga del hueso `headphones`, hijo de `spine006`. Reposo = colgando del cuello. Render: `generated/renders/headphones_on.png` |
| 19 Vibe v2 de 216 frames (`animate.py`, `checks/check_anim.py`, `export_glb.py`) | ✅ completa (4b98ac0 + fix 805154b) | se pone los audífonos con IK de brazos (las manos alcanzan el centro de cada copa con 2.8 cm de holgura), cabecea con los ojos cerrados y se los quita; `key_arms_sit()` cierra el clip en la pose SIT. `export_glb.py` comprueba que solo `vibe` mueve `headphones`. Tira: `generated/renders/strip_vibe.png` |
| 20 Visor con luces, sombras y seguimiento (`export/preview.html`, `tools/preview_probe.mjs`) | ✅ completa (d12c6f6) | 9 luces + `PCFSoftShadowMap`; la cabeza (y el pecho al 30%) miran al cursor con composición en espacio de mundo y cancelación del giro en el hueso `headphones`; clic sobre el personaje = `vibe`. Sonda headless por CDP que guarda `preview_shot.png`, `preview_shot_look.png`, `preview_shot_vibe.png` |
| 21 Regeneración completa, ajuste del visor y docs (README, HANDOFF) | ✅ completa (39b82a9 + el commit `docs:` que sigue) | pipeline entero reejecutado desde `import_character.py`: todos los checks OK, `GLB OK` 9990 KB / 49 390 tris / 7 clips con `headphones` en los nodos, `PROBE errors []`, YAVG del visor 73.2 (rango objetivo 55-80, sin tocar las luces: key 40, ceil 6, win 5, exposición 1.15). Renders: `preview_shot*.png`, `assembled_v1.png` |

Lo que destapó la regeneración completa (arreglado en 39b82a9): `fix_character_material.py` no reseteaba `Specular Tint` (el GLB salía con `KHR_materials_specular`), `export_glb.py` buscaba `TEX_LIMITS` por `medellin.png` en vez de `medellin` (la ventana se reescalaba a 1024) y `tools/preview_probe.mjs` medía un GLB viejo del caché de Chrome.

Concesión conocida: `assemble.py` imprime `INTERSECCIONES 57` (no 0). Son vértices de `handL`/`handR` dentro de la caja `base_laptop` (la palma se hunde en el reposamanos del portátil, que solo tiene 12 mm de grosor). Es anterior a este plan (la pose `SIT` de `poses.py` no cambió) y corregirla obligaría a rehacer `typing` y `vibe`; no se ve en los renders. `verts_en_escritorio`, `en_tapa_laptop` y `en_respaldo` siguen en 0.

## Créditos Higgsfield

Saldo inicial 186. Balance real consultado antes de la Tarea 10: 94.8 (≈91 gastados; el log contaba 80). Tarea 10 gastó 38 (ventana x2 = 2, moto v1 = 2, moto v2 x2 = 4, malla Meshy = 30, autorizada por el usuario) → balance real 54.8 (consultado), ≈131 gastados. Log en `generated/credits.log`. El límite de 100 ya se superó con autorización; avisar antes de cualquier gasto nuevo.

## Archivos generados clave

- `refs/face/` frames del video del usuario; `refs/style/moto_gorra_puente.png`.
- `generated/sheet/sheet_a..d.png` láminas; `media_ids.json` ids subidos a Higgsfield (caducan, resubir si hace falta).
- `generated/screens/{code,logo,stack}.png` (logo = logo de la empresa del usuario).
- `refs/logo.png` logo de la empresa (RGBA transparente, laurel + globo + lanza morada). Va en el monitor derecho y reemplaza el monograma SE del hoodie (Task 6b, `blender/scripts/apply_chest_logo.py`).

## Pendiente del usuario

- **URL del repo del portafolio** para la integración del avatar (el plan de pulido dejó la integración fuera de alcance por no tenerla).
- **Aprobaciones visuales** de la sesión 3: `generated/renders/material_fix.png`, `headphones_on.png`, `strip_typing.png`, `strip_vibe.png`, `preview_shot.png`, `preview_shot_look.png`, `preview_shot_vibe.png`.
- DECIDIR archivado: los insumos irremplazables (generated/meshy/character_rigged.glb, generated/moto/dr150.glb, generated/window/medellin.png) y los .blend están fuera de git; opción: commitear export/avatar.glb (2 MB) y guardar copia de generated/ fuera del repo.
- Probar el visor en ventana real (`tools/serve_preview.sh` → http://localhost:8765/preview.html): sensación del seguimiento de cursor (cabeza + pecho), del clic = `vibe` y del `vibe` automático. La sonda headless (`node tools/preview_probe.mjs`) ya pasa sin errores, pero no reemplaza la prueba a mano.
- Revisión final de la rama: hecha (fable); ronda única de correcciones aplicada (ver ledger). Integrar avatar-3d en main cuando el usuario apruebe.

- Aprobar el logo en el pecho (generated/renders/chest_logo.png) — versión clara por defecto; si prefiere la tinta oscura original: chest_logo_dark.png.
- Aprobar la pose sentada (generated/renders/sit_v_final.png) y la cara (face_parts_open.png / face_parts_closed_browup.png).
- Vista de ventana: 'a' recortada (cambiar a 'b' si lo pide).
- Opcional: dejar `refs/code/*.ts` para la pantalla de código (si no, código de ejemplo). Logo ya entregado.
- Fotos definitivas de cara (opcional) para afinar el parecido al final (Tarea 14).

# HANDOFF — Avatar 3D "Me on 3D"

Documento de traspaso para continuar en una conversación nueva con el mismo flujo de trabajo. Se actualiza en cada hito.

**Última actualización:** 2026-09-03 (sesión 4: barba estirada al seguir el cursor + reempaquetado UV, normales alisadas y diagnóstico de las vetas, ver "Sesión 4". Sesión 3, plan de pulido: tareas 15-21 completas sobre las 14 de la sesión 2, revisión final de rama hecha y ola de correcciones aplicada. El usuario YA aprobó las capturas visuales de la sesión 3. Pendiente: URL del repo del portafolio, decisión de archivado, integrar `avatar-3d` en `main` y la prueba del visor en ventana real)

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
| 12 Exportación GLB (export_glb.py) | ✅ completa (22f7210) | export/avatar.glb 1.94 MB Draco, JPEG q85, 48 390 tris, 7 clips con solo sus huesos (keep_anim_armature=False), pose base = SIT (export_reset_pose_bones=False, pistas muted al exportar), pantallas con emissiveTexture; avatar_uncompressed.glb 4.3 MB; generated/avatar_inspect.json. **Cifras actualizadas tras la revisión final de la sesión 3**: 2.61 MiB (2.7 MB en disco) con Draco / 49 390 tris, TODAS las texturas en JPEG (personaje q92 a 2048, `medellin` a 1504 sin reescalar, resto a 1024); el material `Character` ya NO trae emisión |
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
| 20 Visor con luces, sombras y seguimiento (`export/preview.html`, `tools/preview_probe.mjs`) | ✅ completa (d12c6f6) | 9 luces + `PCFSoftShadowMap`; la cabeza (y el pecho al 30%) miran al cursor con composición en espacio de mundo y cancelación del giro en el hueso `headphones`; clic sobre el personaje = `vibe`. Sonda headless por CDP que guarda `preview_shot.png`, `preview_shot_look.png`, `preview_shot_vibe.png` y **afirma** (revisión final): `hpQ` no nulo, sombras encendidas, 9 luces y la cabeza girando con el cursor |
| 21 Regeneración completa, ajuste del visor y docs (README, HANDOFF) | ✅ completa (39b82a9 + el commit `docs:` que sigue) | pipeline entero reejecutado desde `import_character.py`: todos los checks OK, `GLB OK` (hoy 2.61 MiB / 2.7 MB en disco tras el arreglo de JPEG de la revisión final) / 49 390 tris / 7 clips con `headphones` en los nodos, `PROBE errors []`, YAVG del visor 73.2 (rango objetivo 55-80, sin tocar las luces: key 40, ceil 6, win 5, exposición 1.15). Renders: `preview_shot*.png`, `assembled_v1.png` |

Lo que destapó la regeneración completa (arreglado en 39b82a9): `fix_character_material.py` no reseteaba `Specular Tint` (el GLB salía con `KHR_materials_specular`), `export_glb.py` buscaba `TEX_LIMITS` por `medellin.png` en vez de `medellin` (la ventana se reescalaba a 1024) y `tools/preview_probe.mjs` medía un GLB viejo del caché de Chrome.

Margen del GLB: `export/avatar.glb` pesa 2 735 048 B = **2.61 MiB (2.7 MB en disco)** contra el `BUDGET = 10 MiB` de `export_glb.py`, o sea que usa el **26 % del presupuesto y sobra un 74 %** (7 750 712 B libres). `avatar_uncompressed.glb` pesa 5 215 944 B = 4.97 MiB.

La revisión final de la rama destapó por qué pesaba 9.76 MiB: el primer escalón de la `LADDER` de `export_glb.py` era `fmt='AUTO'`, y para el exportador glTF AUTO significa "PNG se queda PNG". Como el atlas del personaje (`bpy.data.images.new` + `file_format='PNG'`) y `medellin.png` son PNG, `CHAR_QUALITY = 92` era **inerte** y el GLB salía con 6 imágenes `image/png`. Con `LADDER[0] = dict(fmt='JPEG', quality=CHAR_QUALITY, char=2048)` las 6 salen en JPEG:

| imagen | antes (PNG) | ahora (JPEG q92) |
|---|---|---|
| `character_texture_clean` 2048² | 4 988 660 B | 900 873 B |
| `medellin` 1504×846 | 2 286 886 B | 393 997 B |
| `Image_0` (moto) 1024² | 1 752 869 B | 470 059 B |
| `code` 1024×576 | — | 102 831 B |
| `logo` 1024×576 | — | 34 582 B |
| `stack` 1024×576 | — | 28 901 B |
| **GLB completo** | **10 230 476 B** | **2 735 048 B** |

Es seguro porque ninguna textura alimenta `Alpha` (`export_glb.py` lo verifica y aborta si alguna lo hace) y el exportador conserva PNG solo para imágenes con canal alfa; `EXPORT_CHECK ... character_texture_clean mime=image/jpeg` deja atado el formato al código. Pérdida medida contra el PNG fuente: diferencia media 1.69/255, p99 = 13; sin bloques visibles en el hoodie negro ni halos en el logo del pecho (`preview_shot.png`).

La palanca para bajar peso siguen siendo las texturas, no la geometría: `CHAR_QUALITY` y `TEX_LIMITS` (`medellin` a 1504 px sin reescalar); el resto ya va a 1024. La escalera `LADDER` baja calidad/tamaño del personaje si no cabe (JPEG 92 → 85 → 70 → personaje a 1536), pero hoy pasa de sobra en el primer escalón.

Concesión conocida: `assemble.py` imprime `INTERSECCIONES 57` (no 0). Son vértices de `handL`/`handR` dentro de la caja `base_laptop` (la palma se hunde en el reposamanos del portátil, que solo tiene 12 mm de grosor). Es anterior a este plan (la pose `SIT` de `poses.py` no cambió) y corregirla obligaría a rehacer `typing` y `vibe`; no se ve en los renders. `verts_en_escritorio`, `en_tapa_laptop` y `en_respaldo` siguen en 0.

## Sesión 4 (2026-09-03): la barba se estiraba al seguir el cursor

Hallazgo del usuario en el visor real: al mirar al cursor la cara se deformaba, la barba se estiraba hacia el pecho y salía una "papada". Causa raíz (no era del visor): el rig automático de Meshy reparte el peso entre el cuello (`spine005`) y la cabeza (`spine006`) con una rampa larguísima: a la altura de la barbilla el cuello pesaba 30-40 % y a la de los ojos todavía 10 %. Como el visor (y `lookAround`) giran solo `spine006`, la mandíbula y la barba se quedaban a medio camino.

Arreglo: `blender/scripts/fix_head_weights.py` (va justo después de `add_headphones.py`, antes de `check_rig.py`). Por encima de la barbilla (z >= base de `spine006` + 5 mm) todo el peso del cuello pasa a la cabeza; entre 45 mm por debajo y ese punto hay una rampa suave para que la garganta siga siendo cuello. Idempotente con `Body['head_weights_fixed']`. `--probe` renderiza la cabeza girada (yaw 40°, pitch -15°) con los pesos viejos para ver el defecto (`generated/renders/head_weights_before_*.png`); la ejecución normal renderiza la misma pose ya arreglada (`head_weights_after_*.png`). Medido: cuello en barbilla..+6 cm 15.3 % → 0 %, en +6..+20 cm 5.4 % → 0 %.

Regenerado después: `animate.py`, `check_anim.py`, `assemble.py`, `export_glb.py`, `glb_inspect.py` y `preview_probe.mjs` (todo OK; GLB 2665 KB / 49 390 tris; `preview_shot_look.png` ya sin el bulto bajo la barbilla). Después, a petición del usuario, el visor reparte el giro por la columna (`SHARE` en `export/preview.html`): pecho 30 % del yaw, cuello (`spine005`) 20 % del yaw y 0 % del pitch, cabeza el resto. El cuello NO recibe pitch porque el collar y la capucha del hoodie llevan ~30 % de peso de `spine005` y al cabecear con el cuello la cabeza se hundía en el collar (se vio en `preview_shot.png` con una primera versión 25 %/30 %). `preview_probe.mjs` exige que `neckQ` cambie con el cursor (dist >= 0.03; medido 0.15).

El usuario reportó después "más deforme y toda la escena como plastilina". A/B controlado con la sonda (GLB viejo exportado de `avatar.blend1` + `preview.html` de dos commits atrás, contra el estado nuevo): la escena es idéntica píxel a píxel salvo el personaje, y el diff binario de los GLB solo cambia `JOINTS_0`/`WEIGHTS_0` de la malla del personaje (posiciones, normales, materiales, texturas y transformadas iguales). Causa probable del "más deforme": Chrome sirvió el `avatar.glb` VIEJO del caché (python `http.server` no manda `Cache-Control`) con el visor nuevo, o sea cuello girando sobre pesos viejos. Arreglo: `preview.html` carga `avatar.glb?v=Date.now()` y `night.hdr?v=...`. Lo de "plastilina" no se reprodujo; pendiente captura del usuario.

## Sesión 4 (cont.): "por qué parece plastilina" y las tres mejoras

Pregunta del usuario: por qué moncy.dev se ve HD y el suyo parece plastilina. Respuesta corta: moncy es modelado a mano con texturas planas; el nuestro es una malla de Meshy (IA) con textura horneada. Se aplicaron tres mejoras sin remodelar:

1. **Vetas claras en el hoodie** (las "motas" de la sesión 3 que nunca se fueron del todo). Diagnóstico por descarte con la sonda (`?mat=` y `?shadow=`/`?nb=` en `preview.html`, `PREVIEW_QUERY` en `preview_probe.mjs`): no eran textura mal rellenada (los bordes de islas oscuras miden igual de oscuros), ni Draco (el GLB sin comprimir las tiene), ni caras traseras (`FrontSide` las conserva), ni sombras (`shadow=off` las conserva), ni rendijas (render en Blender con fondo blanco: ninguna). Sin mipmaps (`?mat=nomip`) desaparecen: **sangrado de mipmap** entre islas UV vecinas, porque Meshy empaqueta ~4500 islas minúsculas a 2-4 px unas de otras (el 57 % del gutter está a <2 px de alguna isla). Limitar el nivel de mip (`TEXTURE_MAX_LOD`) no basta. Arreglo de fondo: `blender/scripts/repack_uvs.py` suelda la malla (0.5 mm, 44030 → 21247 vértices), re-desenvuelve con Smart UV Project (66°, margen 8 px de 4096) y hornea la textura vieja al mapa nuevo en numpy; la textura sale a **4096** (cobertura 36.6 %, escala de texel 0.75 respecto a Meshy a 2048 → 1.5× a 4096). A 89° las dos caras de cada dedo caían en la misma zona UV y los dedos salían negros; el script ahora aborta si más del 2 % de los texeles está disputado (medido 0.19 % a 66°). El UV de Meshy queda guardado en el atributo de esquina `uv_meshy` para poder repetir el paso. `fix_character_material.py` corre dos veces (antes y después del repack; elige la fuente y el PAD por `Body['uv_repacked']`: 16 px con Meshy, 32 px con el layout nuevo) y `export_glb.py` admite el atlas a 4096 (primer escalón de `LADDER`; `imagenes <= 4096`).
2. **Bultos de la malla** (gorra facetada, cara abollada). Alisar posiciones NO sirve: soldada o no, la malla son islas con bordes que no coinciden y cualquier Smooth abre huecos negros (probado 0.5/3, 1.0/6 y Corrective Smooth). `blender/scripts/smooth_normals.py` transfiere normales personalizadas desde una copia remallada por voxels (8 mm) y suavizada (8 it), sin mover vértices; el exportador las escribe y Draco las conserva. Va después de `repack_uvs.py` (que borra su marca porque la soldadura cambia la topología).
3. **Shading más plano**: se probaron `?mat=flat` (rugosidad 1, sin reflejo de entorno) y `?mat=toon` (`MeshToonMaterial` con la misma textura). Ninguno se dejó por defecto: `flat` casi no cambia y `toon` vira el hoodie a morado. Quedan como parámetros de prueba en `preview.html` para que el usuario compare en su navegador (`preview.html?mat=toon`).

Resultado: GLB **3.95 MB** (antes 2.6; la diferencia es el atlas a 4096) / 48 790 tris; todos los checks OK; `PROBE errors []`. Comparativas guardadas por la sonda en `preview_shot*.png`. Opción rápida vs. lenta: la spec solo registra la opción 1 (lámina IA → Meshy); la alternativa que da el nivel de moncy es modelar el personaje a mano (o encargarlo) con topología limpia y texturas planas, y reutilizar rig, clips, escena y visor tal cual.

## Créditos Higgsfield

Saldo inicial 186. Balance real consultado antes de la Tarea 10: 94.8 (≈91 gastados; el log contaba 80). Tarea 10 gastó 38 (ventana x2 = 2, moto v1 = 2, moto v2 x2 = 4, malla Meshy = 30, autorizada por el usuario) → balance real 54.8 (consultado), ≈131 gastados. Log en `generated/credits.log`. El límite de 100 ya se superó con autorización; avisar antes de cualquier gasto nuevo.

## Archivos generados clave

- `refs/face/` frames del video del usuario; `refs/style/moto_gorra_puente.png`.
- `generated/sheet/sheet_a..d.png` láminas; `media_ids.json` ids subidos a Higgsfield (caducan, resubir si hace falta).
- `generated/screens/{code,logo,stack}.png` (logo = logo de la empresa del usuario).
- `refs/logo.png` logo de la empresa (RGBA transparente, laurel + globo + lanza morada). Va en el monitor derecho y reemplaza el monograma SE del hoodie (Task 6b, `blender/scripts/apply_chest_logo.py`).

## Pendiente del usuario

- **URL del repo del portafolio** para la integración del avatar (el plan de pulido dejó la integración fuera de alcance por no tenerla).
- ~~**Aprobaciones visuales** de la sesión 3~~ — **hechas** (2026-09-03): el usuario aprobó las capturas del pulido (`material_fix.png`, `headphones_on.png`, `strip_typing.png`, `preview_shot*.png`) y las manos corregidas del `vibe` (`strip_vibe.png`).
- DECIDIR archivado: los insumos irremplazables (generated/meshy/character_rigged.glb, generated/moto/dr150.glb, generated/window/medellin.png) y los .blend están fuera de git; opción: commitear export/avatar.glb y guardar copia de generated/ fuera del repo. Peso actual del GLB: **2.61 MiB (2.7 MB en disco)** tras pasar las texturas a JPEG en la revisión final (antes de eso llegó a 10.2 MB). Meterlo en git es meter un binario de 2.7 MB que se reescribe entero en cada regeneración; a ese tamaño ya es defendible, pero si no se quiere el peso en el repo las alternativas son dejarlo fuera con copia en un bucket, o usar git-lfs.
- Probar el visor en ventana real (`tools/serve_preview.sh` → http://localhost:8765/preview.html): sensación del seguimiento de cursor (cabeza + pecho), del clic = `vibe` y del `vibe` automático. La sonda headless (`node tools/preview_probe.mjs`) ya pasa sin errores, pero no reemplaza la prueba a mano.
- Revisión final de la rama, **sesión 2**: hecha (fable); ronda única de correcciones aplicada (ver ledger de `2026-09-03-avatar-3d`).
- Revisión final de la rama, **sesión 3** (plan de pulido): hecha (fable) sobre toda la rama; ola única de correcciones aplicada (ver ledger de `2026-09-03-avatar-polish` y `.superpowers/sdd/2026-09-03-avatar-polish/final-fix-report.md`). Lo gordo: el GLB no llevaba ninguna textura JPEG (10.2 MB → 2.7 MB) y `preview_probe.mjs` solo comprobaba "cargó sin excepciones".
- **Integrar `avatar-3d` en `main`** cuando el usuario apruebe (sigue pendiente).

- Aprobar el logo en el pecho (generated/renders/chest_logo.png) — versión clara por defecto; si prefiere la tinta oscura original: chest_logo_dark.png.
- Aprobar la pose sentada (generated/renders/sit_v_final.png) y la cara (face_parts_open.png / face_parts_closed_browup.png).
- Vista de ventana: 'a' recortada (cambiar a 'b' si lo pide).
- Opcional: dejar `refs/code/*.ts` para la pantalla de código (si no, código de ejemplo). Logo ya entregado.
- Fotos definitivas de cara (opcional) para afinar el parecido al final (Tarea 14).

# HANDOFF — Avatar 3D "Me on 3D"

Documento de traspaso para continuar en una conversación nueva con el mismo flujo de trabajo. Se actualiza en cada hito.

**Última actualización:** 2026-09-27 (sesión 13, rama `calidad-avatar`: el grafiti pasó a ser una pieza 3:2 de 2.4 m que cubre la pared lateral de punta a punta y tiene RELIEVE real (capas apiladas de 6 cm + sombra de contacto + contorno cel recortado por la silueta, ver "Sesión 13"); el pre-pase del contorno acepta ahora `userData.outlineMaterial` / `userData.outline === false` por malla; encuadre vertical del hero rehecho para la pieza ancha. Antes — sesión 12: grafiti cuadrado + neones; sesión 11: cáscara interior contra las grietas. Pendiente del usuario: capturas de PipeBot, links de contacto, dominio)

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

## Sesión 5 (2026-09-03): cejas duplicadas, grietas y seguimiento brusco

Pedido del usuario: las cejas salen duplicadas al hacer el gesto, texturas mejor definidas y "cero agrietadas", seguimiento de cursor menos brusco para que la cara no se desfigure. Diagnóstico y arreglos (todo verificado con renders de Blender y con capturas del visor real en Chrome headless, encuadre de detalle de la cabeza vía `window.__view` en `preview.html`):

1. **Cejas duplicadas.** Causa: las cejas de malla de `add_face_parts.py` TAPAN las cejas pintadas de la textura de Meshy; al subir 12 mm en `browup` las pintadas quedan a la vista. Arreglo en `blender/scripts/texture_touchup.py` (paso nuevo, va después de la segunda pasada de `fix_character_material.py`): rasteriza en el UV nuevo las caras frontales de la franja de la frente donde están (landmarks `brow_L/R` ± 1.9 cm en z, ± largo/2 + 1.6 cm en x, normal.y > 0.25) y reemplaza los texeles oscuros (lum < 0.45; borde 0.45-0.62 fundido) por piel REAL copiada de la frente 2.6 cm más arriba (raycast sobre Body desde delante de la piel, se descarta si pega en pelo/gorra) con relleno dilatado de respaldo, y difumina el contorno. Render de control: `generated/renders/touchup_browup.png` (cejas de malla levantadas, ninguna pintada debajo).
2. **"Grietas".** NO eran textura: se ven igual con material plano sin textura, con backface culling y sin normales personalizadas (`generated/renders/headprobe/crack_trio.png`). Son rendijas geométricas de 0.5-3 mm entre las islas de Meshy (8563 vértices de borde, 9238 aristas de borde tras la soldadura a 0.5 mm; p50 1.1 mm, p90 2.6 mm). Arreglo: `blender/scripts/close_gaps.py` (paso nuevo, después de `fix_head_weights.py` y ANTES de `repack_uvs.py`, que ahora acepta `--force` para repetirse): cada vértice de borde avanza la mitad del camino hacia la arista de borde más cercana de OTRA isla (≤ 3 mm, solo si las normales coinciden: `NDOT` 0.3 evita pegar la cara de arriba y la de abajo de la visera), 6 pasadas, y soldadura final a 0.3 mm (21247 → 19492 vértices). A 4 mm cierra más rendijas pero la visera sale mellada: se dejó 3 mm. Renders con material plano: `gaps_before.png` / `gaps_after.png`. Quedan algunas rayas (rendijas > 3 mm o de superficies no emparejables); ya no dominan la cara.
   Regresión detectada por el usuario y corregida: la primera versión de la zona de cejas incluía caras del borde de la visera (sobresale por delante de la frente a la misma altura) y les puso piel; ahora la zona exige caras a ≤ 1 cm por delante del landmark (`BROW_DY`), normal.y ≥ 0.4 y 8 mm de margen lateral. Verificado en `headprobe/cap_fixed.png`.
   Además `texture_touchup.py` repara las rayas de costura del horneado: Meshy pinta un borde de 1 px oscuro en las islas de piel (14.6 % de texeles oscuros en el borde vs 2-4 % en el interior) y algo claro en las del hoodie; al hornear al UV nuevo esas rayas quedan DENTRO de las islas grandes. Se localizan las costuras viejas (aristas con `uv_meshy` distinto entre caras) dibujadas en el UV nuevo y, en una franja de ±3 px, se reemplaza el texel que salta > 0.16 de luminancia respecto al promedio de su entorno fuera de la franja, solo si ese entorno es uniforme (std < 0.06): las líneas de ojo o el borde barba/piel que caen sobre una costura no se tocan. La mediana de `fix_character_material.py` ya quitaba la mayoría; esto limpia el resto (~3700 texeles).
3. **Definición.** El visor activa filtrado anisotrópico máximo en todas las texturas (`map.anisotropy`): la cara y el hoodie se ven en escorzo desde la cámara y sin esto se emborronan. La resolución de partida sigue siendo la de Meshy (2048), horneada a 4096; no hay más detalle que sacar sin remodelar/repintar.
4. **Seguimiento de cursor** (`export/preview.html`): la cabeza ya no mira AL cursor sino HACIA el cursor: recorre `GAIN` = 60 % del ángulo geométrico, con topes 28° de yaw / 12° arriba / 9° abajo (antes 45/25/20: al mirar abajo la barba se hundía en el collar y de lado el cuello se retorcía), suavizado exponencial por tiempo (`TAU` 0.35 s, independiente del framerate; antes 8 % por frame) y zona muerta de 0.02 rad para el temblor del mouse. Reparto: pecho 25 % del yaw, cuello 20 %, cabeza el resto; el fundido de `followWeight` también va por tiempo (0.4 s). La sonda `preview_probe.mjs` sigue pasando (headQ dist 0.26 ≥ 0.1, neckQ 0.089 ≥ 0.03).

Resultado: todos los checks OK, `PROBE errors []`, `PROBE OK` (headQ dist 0.25, neckQ 0.086). GLB **3903 KB = 3.81 MiB** (3 996 856 B) / 47 663 tris (Body 36 273 tras cerrar rendijas; antes 37 400) / 7 clips. La primera regeneración de la sesión exportó SIN el retoque de cejas porque `texture_touchup.py` falló su chequeo final (el desenfoque del contorno mezclaba pelo vecino) y la cadena no cortó: ojo, un fallo de `common.fail` en un paso intermedio deja la textura anterior en disco; encadenar con `set -o pipefail` si se filtra la salida con grep. Capturas de detalle de la cabeza (cursor centro/izquierda/derecha/abajo/arriba y browup) en `generated/renders/headprobe/head_v2_*.png` (carpeta de trabajo, no versionada).

Extras de la sesión: `common.setup_viewport()` (lo llama `assemble.py` antes de guardar) deja `avatar.blend` con los visores 3D mirando por la cámara y en Material Preview, porque al abrirlo en la interfaz la vista guardada caía dentro del escritorio. Se instalaron las 16 skills de `kevinbadi/blender-skills` en `.claude/skills/` (sin versionar): son flujos de foto de producto por MCP (`blender-mcp` + Meshy), no aplican a la reparación del personaje; podrían servir las de Polyhaven para HDRI/materiales del cuarto.

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


## Sesión 6 (2026-09-03): cel-shading, contorno y landing de portafolio

Pedido del usuario: "que se vea más profesional y didáctico". Se acotó con preguntas a tres frentes: **personaje**, **escena** y **portafolio**. Decisiones tomadas:

- El personaje **NO se remodela ni se regenera en Meshy**: se **estiliza**. Los defectos de la malla IA dejan de leerse como error y pasan a leerse como estilo.
- La landing de portafolio SÍ se construye (la spec original la dejaba fuera): hero 3D a pantalla completa con el contenido debajo, en español y con proyectos reales.
- Spec: `docs/superpowers/specs/2026-09-03-avatar-pro-landing-design.md` (133bf54). Fases: 1 look cel → 2 refactor a `export/lib/` + sonda → 3 landing → 4 móvil/rendimiento/docs.

### Fase 1 — look cel (hecha, pendiente de aprobación)

Archivos nuevos: `export/lib/toon.js`, `export/lib/postfx.js`, `tools/look_sweep.mjs`. El GLB **no cambia**: todo vive en `export/`, así que cero riesgo sobre rig, pesos, clips y landmarks.

- **Por qué contorno por post-proceso y no inverted hull:** la malla tiene 8563 vértices de borde; un casco invertido saldría agujereado justo en la cara. El Sobel sobre profundidad + normales no depende de la topología, y de paso contornea escritorio, monitores y moto (eso es lo que unifica el look).
- **Por qué el `?mat=toon` viejo viraba a morado:** no era el toon. Las luces de la escena son azules (key `0xcfe0ff`, ventana `0x8fb8ff`, hemisférica `0x33405c`) y un hoodie casi negro multiplicado por luz azul sin base ambiental da morado. `toonLights()` mete base ambiental cálida y vuelve la key neutra.
- **RectAreaLight NO ilumina `MeshToonMaterial`** (solo Standard/Physical): la luz de la ventana pasa a `DirectionalLight`.
- **La trampa que costó cuatro pasadas:** las puntuales de las pantallas están a ~0.5 m de la cara con decay 2 (intensidad efectiva ~6) y quemaban la piel a blanco puro. Se atenúan aparte en el visor (`LIT.screen` = 0.30, `LIT.bar` = 0.70 en modo cel), no en `toonLights`.
- **Calibración final** (variante `u3` del barrido): ambiental 0.30, key 8, ventana 0.40, hemisférica 0.15, techo 3, `slit` 0.30, `blit` 0.70; contorno `thickness` 1.4 / `depthBias` 0.003 / `normalBias` 0.8; bloom umbral 2.5 fuerza 0.25; viñeta 1.05. `normalBias` por debajo de ~0.6 dibuja el RUIDO de la malla (pecas negras en la gorra); por encima de ~1.1 se pierden los pliegues.
- **Todo el look es ajustable por query** para poder barrerlo sin editar código: `?fx=off` (look PBR anterior exacto), `?toon=0`, `?outline=0`, `?bloom=0`, `?vignette=0`, y los números `amb key win hemi ceil slit blit rim rimp thick dbias nbias ostr bloomstr bloomt vign exp`.
- **`tools/look_sweep.mjs`**: abre el visor una vez por variante y guarda captura en `generated/renders/sweep/`. `--zoom` encuadra la cabeza. Es la herramienta que hizo posible calibrar.
- **`__inkFrac` cambió de definición**: contar píxeles casi negros no sirve (la escena nocturna ya tiene ~58 % casi negro y la medida satura). Ahora mide densidad de LÍNEAS (píxeles más oscuros que sus dos vecinos a distancia 2, a escala 1:1 porque el contorno mide 1-1.5 px y al reducir la imagen se difumina).
- **Sonda ampliada** (`tools/preview_probe.mjs`): afirma `fx.on`, 5 pases del composer, `lights >= 9` (antes exigía exactamente 9), y hace una segunda pasada con `?fx=off` para la comparativa A/B y para medir que el contorno pinta tinta (1.44 % vs 1.10 %). `PROBE OK`, `errors []`, headQ 0.256, neckQ 0.088.
- Comparativas para el usuario: `generated/renders/fase1_escena_ab.png` y `fase1_cabeza_ab.png`.

### Fase 1b — manos, cara y logo (hecha, pendiente de aprobación)

Tres pedidos del usuario tras ver la fase 1. Todo esto SÍ toca el GLB, a diferencia del look cel.

**1. Manos verticales al teclear** (`poses.py`, `animate.py`, `calibrate_hands.py`). Causa: `poses.aim()` clava la dirección del hueso pero deja el giro sobre su propio eje al azar, así que las manos de `TYPING_HOME` quedaban con la palma vertical, palma contra palma. Arreglo: `poses.aim_palm()` apunta también la PALMA y **reparte los 77° de torsión mitad en el antebrazo (pronación) y mitad en la muñeca**, porque los pesos de Meshy no aguantan esa torsión entera en una articulación. `poses.roll()` gira un hueso sobre su +Y local sin mover a dónde apunta. `calibrate_hands.py` regenera los eulers horneados de `TYPING_HOME` y verifica que la palma quede donde se pidió (tolerancia 8°: `aim_roll` ortogonaliza y ni `PALM_LOCAL` ni `DIR_PALM` son exactamente perpendiculares a `DIR_HAND`, así que hay un residuo de 4-5° inevitable). **Efecto colateral: `INTERSECCIONES` de `assemble.py` bajó de 57 a 4** — las 57 eran justo las palmas hundidas en el reposamanos del portátil, un pendiente abierto desde la sesión 3.

**2. Cara y barba** (`face_features.py` nuevo, `add_face_parts.py`).
- Medido con `--flat` y `--probe`: Meshy pintó barba en mandíbula y mejillas pero dejó **todo el mentón y la boca como una sola mancha de piel plana de ~5.8 cm**, sin labios y con una muesca oscura abajo (el "diente" que se veía en el visor). `face_features.py` cierra la barba sobre el mentón (rellena solo texeles de PIEL, con el color tomado del percentil 30 de la barba vecina — la mediana de todo el pelo incluye la gorra y el relleno salía más claro) y deja una elipse de labios con su tono.
- Las cejas de malla se hicieron en su día MÁS GRANDES que las pintadas para taparlas; desde la sesión 5 `texture_touchup.py` borra las pintadas, así que ya no hacía falta: con `brow_h` 21 mm y `brow_len` 66 mm eran dos barras negras que se leían como un antifaz. Ahora `BROW_H_SCALE` 0.52 y `BROW_LEN_SCALE` 0.84 (~11 × 55 mm) y color `BROW_SRGB` (0.26, 0.185, 0.155), un castaño emparentado con la barba: el landmark `brow_srgb` es el color medido de la ceja PINTADA (casi negro y morado) y como color de malla no sirve.
- **Dos trampas que costaron varias pasadas y por las que `face_features.py` tiene `--probe`/`--flat`:** (a) `image.pixels` de bpy entrega la imagen de ABAJO a ARRIBA y el rasterizado usa `y = (1-v)*S`; sin voltear, la máscara sale espejada y se pinta sobre islas sin relación (la zona de la cara caía sobre el hoodie). (b) `image.pixels` devuelve LINEAR: la piel (sRGB 0.94/0.58/0.48) cae a 0.45 de luminancia y con umbrales "a ojo" la cara entera se clasificaba como barba. Medido en sRGB la cara separa limpia: piel (r-b > 0.10) luminancia p5..p95 = 0.60..0.86; pelo p5..p95 = 0.31..0.43.

**3. Logo del pecho** (`apply_chest_logo.py`). El emblema es un grabado de línea fina CON GRANO; al bajarlo al atlas y hornearlo al UV nuevo las líneas se rompían y en el visor era una mancha blanca irreconocible. `to_light_print()` pasa de invertir la luminancia píxel a píxel a un **estarcido**: binariza la tinta, engorda el trazo (`INK_GROW` 0.006 = 3 px a 500) y suaviza el borde; el morado de la lanza se filtra por DENSIDAD local (`INK_PURPLE`) porque si no, cada punto de grano se engordaba y el emblema salía con salpicaduras lavanda. `LOGO_SCALE` 1.3 → 1.65.

**Herramientas nuevas:** `tools/rebuild_character.sh` (toda la cadena de `import_character.py` a `glb_inspect.py`, para al primer fallo) — hace falta siempre que cambie algo anterior al reempaquetado de UV, como `apply_chest_logo.py`, que trabaja en el UV ORIGINAL de Meshy. `tools/look_sweep.mjs` acepta `SWEEP_EXTRA_MS` para desplazar el instante de la captura (Blink dura 10 s y todas las variantes caían en la misma fase, a veces con el ojo cerrado).

**Estado tras la regeneración completa:** todos los checks OK, `CHECK_RIG OK` 39 237 tris, `CHECK_ANIM OK`, `INTERSECCIONES 4`, `GLB OK 3908 KB / 48 275 tris / 7 clips`, `PROBE OK` sin errores. Comparativas: `generated/renders/cara_ab.png`, `logo_ab.png`, `manos_ab.png`.

**Pendiente de la sesión 6:** aprobación de las fases 1 y 1b; luego fases 2-4. El usuario debe entregar los 3-4 proyectos reales (nombre, línea, link) y los links de contacto para el bloque `DATA` de la landing.

## Sesión 7 (2026-09-04) — barba, cejas y colocación de la escena

Pedidos del usuario, en orden: (1) "la barba y cejas quedaron mal diseñadas, arréglalas";
(2) las pantallas se bugean / aparecen lejos del escritorio, definir el teclado, logo al monitor
central, habitación más pequeña, reflejo de vidrio, soporte para las barras RGB; (3) empezar la
landing de portafolio con proyectos reales.

### Barba — el bug que causaba el "pasamontañas"

`face_features.py` cerraba la barba sobre una **caja** `|x| <= 0.065` y `z <= ojos-0.055`. Esa caja
mide 13 cm de ancho (la cara llega a 10.5) y su techo cae a media nariz, así que barría también
las mejillas. Como el script tiñe TODA la piel que cae dentro, el resultado fue teñir la mitad
inferior entera de la cara — en cel-shading colapsa a negro plano — y de paso **destruyó la línea
de mejilla que Meshy sí había pintado bien** (alta en la patilla, baja hacia la comisura, igual
que en `refs/face/contact_sheet.jpg`).

Correcciones:
- Zona = **elipse** (`CHIN_Z/RX/RZ`) ajustada a la mancha real de Meshy, medida con el mapa de
  ocupación piel/pelo que ahora imprime `--probe`. Relleno: 30 000+ téxeles → ~8 700.
- **Difuminado hacia AFUERA** de la elipse. Hacia adentro dejaba los últimos 8 mm a medio teñir
  justo donde acaba la mancha, y salía un halo color piel trazando el contorno de la boca.
  Peso medio del relleno: 0.74 → 0.96.
- Relleno de `is_skin` a **`~is_hair`**: entre `HAIR_LUM` (0.50) y `SKIN_LUM` (0.55) hay una
  tierra de nadie donde caen los trazos con que Meshy dibujó el contorno del bigote, la perilla
  y la muesca del mentón. No se teñían y quedaban como garabatos claros sobre la barba.
- **`FILL_MAX`**: la versión vieja tenía mínimo de téxeles pero no máximo, y por eso el bug pasó
  sin protestar. Ahora falla si el relleno se desborda.
- Labios y línea de boca en **sRGB absoluto**, no como factor sobre la piel de alrededor: ese
  factor es lo que produjo el color caramelo de la sesión 6 y la mancha pálida al corregirlo.
  Se añadió `MOUTH_SRGB`, la línea de abertura — sin ella los dos labios son una sola mancha.

### Cejas

`make_brow()` usaba `taper = sin(pi*t)**0.5`, que vale ~1 en casi todo el recorrido, con
`BROW_ARCH` de 2.2 mm sobre 55 mm: salía una barra recta de altura constante y puntas romas.
Ahora `brow_profile(t)` da arco asimétrico (pico a `BROW_PEAK` = 0.62 hacia la sien, +4.4 mm),
cola que cae 3.5 mm por debajo de la cabeza y grosor 60 % → 91 % → 0 (termina en punta).

### Colocación de la escena — `monitor_L/R` a 87 cm de su base

`common.box()` horneaba la escala pero quien quería una caja girada ponía `ob.rotation_euler`
DESPUÉS de la llamada. La localización sí se horneaba, la rotación no: quedaba viva en el objeto
y se aplicaba alrededor del ORIGEN DEL MUNDO sobre geometría que ya está a 0.6-1.5 m de él.
Medido en el GLB: `monitor_L`/`monitor_R` a **87 cm**, `controller` a **35 cm**, `laptop_lid` a
**29 cm**; las cajas sin rotación caían bien, y por eso el fallo parecía aleatorio.
`check_scene.py` incluso documentaba la creencia equivocada ("transform_apply aplica los 3").

Corregido en `common.box()` (acepta `rotation=` y lo hornea) + **`checks/check_scene_placement.py`**
nuevo: falla si alguna malla conserva rotación viva, si un monitor se separa >5 cm de su base o
si el tope del teclado se mueve de `DESK_Z + 0.030`.

### Resto de la escena

- Logo al monitor **central** (el más grande y el que queda de frente al rodear el escritorio).
- `laptop_keys`: 72 teclas + trackpad. La base baja 1.5 mm y las teclas rellenan ese 1.5 mm, así
  que el tope vuelve a caer en `DESK_Z + 0.030` y **no hay que recalibrar las manos**.
- Habitación 5.6×2.8 m → **4.1×2.5**, pared trasera -1.7 → -1.45, ventana reescalada a 16:9 y
  repisa de x=2.0 a **x=1.5**.
- Trípodes negros (poste + buje + 3 patas) bajo cada barra RGB.
- Vidrio: plano `window_glass` + `export/lib/glass.js`, destello aditivo (2 bandas diagonales +
  fresnel) en vez de reflexión real. En un look de bandas una reflexión planar cuesta una pasada
  entera y se ve sucia; en ilustración el vidrio se lee por el brillo. `?glass=0` lo apaga.

### Decisiones del usuario en esta sesión

- Barba **como en las fotos** (línea de mejilla baja, pómulo despejado, labios visibles). Esto
  ANULA el "barba completa cerrada" de la sesión 6.
- Monitores: **la cámara rodea** hasta ver las pantallas; no se giran hacia la sala.
- Orden de trabajo: **primero la cara**, luego la escena, luego la web.

### Landing de portafolio — contenido levantado del disco

Ver la memoria `portfolio-content.md`. Los 3 proyectos son Amaranthus Gold (producción),
Holistic Eco·Hotel (propuesta) y PipeBot (bot de WhatsApp + dashboard).
**BLOQUEANTE:** el repo de PipeBot no tiene NINGUNA captura; hay que levantar la app y tomarlas.
De contacto solo hay `sebastianmedev@gmail.com` y `github.com/Sebastiandevmed`.
`~/Desktop/Portfolio` está vacía: la landing se construye desde cero.

## Sesión 8 (2026-09-04) — la cara: por qué se veía como un pasamontañas

El usuario, viendo el visor: "la boca y barba siguen viéndose super raro, adicional que tiene
como líneas color piel que hace que se vea aún más desorganizado". Eran **tres bugs distintos**,
y los tres estaban en el pipeline de TEXTURA, no en el cel-shading (se comprobó con `?mat=basic`,
que dibuja la textura sin luz ni bandas: los defectos ya se veían ahí).

### 1. Rellenábamos nosotros la barba sobre una premisa falsa

`face_features.py` cerraba la barba sobre el mentón porque su docstring afirmaba que "Meshy dejó
todo el mentón y la boca como una sola mancha de piel plana". **Es falso.** Medido con el modo
nuevo `--probe --tex generated/character_texture_repacked.png`, o sea sobre lo que pintó Meshy
antes de tocar nada:

```
ojos-58mm  |............#####...######...........|   bigote
ojos-86mm  |#######.......................#######|   barba solo en la mandíbula
ojos-106mm |#########.......#####........########|   perilla
```

Eso es exactamente la barba de `refs/face/contact_sheet.jpg`. El "hueco de piel" del centro no
era un defecto: era la boca y el mentón. Al rellenarlo con color de barba, en cel-shading colapsa
a un plano negro (pasamontañas) y la "boca" pasaba a ser la ranura que el relleno dejaba sin
cubrir — de ahí los garabatos.

**Arreglo:** `face_features.py` ya NO rellena nada. Solo dibuja los labios (dos medias elipses
asimétricas, la de abajo más llena) y la línea de abertura, y solo sobre piel. Se borraron
`CHIN_*`, `BEARD_*`, `FILL_MAX` y `GRAIN`. Guardas nuevas `LIP_MIN`/`LIP_MAX`.

### 2. Bug de espacio de color: el labio salía rojo de lápiz labial

El comentario "trampa 2" del script afirmaba que `image.pixels` devuelve LINEAR. **También es
falso para esta imagen.** Medido: el PNG guarda la piel de Meshy como (236, 158, 133), que es el
`skin_srgb` del landmark → `pixels` entrega sRGB. Consecuencias:

- `srgb = to_srgb(rgb)` es una conversión de MÁS. Los umbrales de clasificación (`SKIN_LUM`,
  `HAIR_LUM`, `SKIN_RED`) están calibrados contra ese espacio doblemente convertido y funcionan:
  **no se tocan**.
- Pero al ESCRIBIR un color, `to_linear()` sobraba: el labio acababa en (146, 47, 39) en vez de
  en (199, 120, 110). Se comprobó contando téxeles en el atlas: 4487 cerca del valor erróneo
  contra 264 cerca del correcto.

### 3. Las líneas color piel: canaletas rancias

`fix_character_material.py` dilata el color de cada isla sobre las canaletas del atlas. Pero
`texture_touchup.py` y `face_features.py` corren DESPUÉS y pintan **por téxel rasterizando
triángulos**, así que solo tocan lo que está DENTRO de una isla. Las canaletas se quedaban con el
color de antes del repintado: cada isla que se oscurecía quedaba rodeada de un anillo de piel.

En pantalla la cara se ve AMPLIADA (≈0.5 mm por téxel, cabeza de ~600 px), así que el muestreo es
de MAGNIFICACIÓN — por eso `?mat=nomip` nunca cambió nada — y el filtro bilineal convierte ese
anillo de 1 téxel en una raya de 2-4 px.

Medido sobre los 335 622 bordes isla→canaleta del atlas: saltos de color >80/255 pasan de **3085
a 106** al re-dilatar.

**Arreglo:** `blender/scripts/redilate_texture.py` (nuevo), SIEMPRE el último retoque de textura;
ya está en `tools/rebuild_character.sh` detrás de `face_features`. Reusa `uv_mask()` y
`dilate_colors()` de `fix_character_material.py` y replica también su relleno lejano con
`dark_mean` — sin eso el color de isla se cuela más allá del alcance de `PAD` y
`check_character_material.py` falla con `skin_frac_far`.

### Otros cambios

- `face_features.py --tex <ruta>`: en modo lectura, mide otra etapa de la cadena. Es lo que
  permitió separar "lo pintó Meshy" de "lo pintamos nosotros". Repunta también el nodo del
  material o el render del probe saldría con la textura vieja mientras los números salen de la nueva.
- `preview.html ?mat=basic`: dibuja el atlas sin luz ni bandas. Es el único modo que separa
  "la textura está mal pintada" de "el cel-shading la está aplastando". **Empezar siempre por ahí.**
- `checks/check_scene_placement.py`: daba falso positivo con las candongas y los audífonos, que
  llevan rotación viva a propósito porque cuelgan de un hueso. Ahora salta los objetos con padre;
  el bug que motivó el check (rotación sin hornear aplicada alrededor del origen del mundo) solo
  le pasa a objetos sueltos.

### Callejón sin salida, para no repetirlo

Se intentó comparar etapas de textura con un `?tex=archivo.png` en el visor y con un
rasterizador de UV propio en Python. **Ninguno de los dos funcionó** (confeti de islas en las dos
orientaciones de `flipY`, y una cobertura de 0.645 contra el 0.365 real). Se quitaron los dos.
La textura se mide en Blender con `uv_mask()`, o en el PNG con PIL contra
`generated/character_uv_mask.png`; el LOOK se juzga con `tools/face_shot.mjs` sobre el GLB real.

### Verificación

`CHECK_RIG OK` 39 365 tris · `CHECK_ANIM OK` · `CHECK_FACE_EXPORT OK` ·
`CHECK_CHARACTER_MATERIAL OK` (skin_frac_far 0.0) · `CHECK_SCENE_PLACEMENT OK` ·
`GLB OK 3852 KB / 49 501 tris / 7 clips` · `PROBE OK errors []` · `FACE OK errores []`.
Comparativas: `generated/renders/boca_ab_sesion8.png`, `cara_cel.png`, `preview_shot.png`.

### Estado de la landing

**No empezada.** Solo existe `export/lib/camera-path.js` (estados de cámara con nombre e
interpolación suavizada, sin usar todavía). Faltan la fase 2 (sacar el motor de `preview.html` a
`lib/scene.js`) y la fase 3 (`index.html`). Contenido y ángulos de los 3 proyectos: memoria
`portfolio-content.md`. Bloqueantes del usuario: capturas de PipeBot (lista en
`refs/pipebot/CAPTURAS.md`) y links de contacto más allá de correo y GitHub.

## Sesión 9 (2026-09-04) — las rayas negras que aparecían y desaparecían al moverse

**Reporte:** "al moverse se crean pequeñas líneas y rayas negras, luego desaparecen"; y pedido de
"un acabado más definido y sin tantos rayones abstractos al resto del avatar".

### Diagnóstico (lo que descartó cada medida)

Sonda nueva `tools/ink_probe.mjs` (primer plano de la cara en 4 poses del cursor + capturas) y una
medida de parpadeo por píxel. Resultado del ablation:

| variante | qué cambia |
|---|---|
| `?shadow=off` | **nada** → no era acné de sombras, pese a ser el sospechoso obvio |
| `?bloom=0` | **nada** |
| `?mat=basic` | limpio, pero también apaga la luz: no concluye por sí solo |
| `?outline=0` | **los rayones desaparecen por completo**, con el mismo toon y la misma textura |

O sea: **los pintaba el término de NORMALES del pase de contorno**, entintando el ruido de la malla
de Meshy. Parpadeaban porque `smoothstep(b, b*2)` es casi un escalón: al animar, cada píxel dudoso
lo cruzaba en un frame y volvía en el siguiente.

### Arreglo (`export/lib/postfx.js`, `export/preview.html`)

Un umbral global no podía ganar: con `nbias` 0.8 el personaje salía rayado y con 2.0 el cuarto
perdía los pliegues. El umbral ahora se modula por dos factores:

1. **Sensibilidad a tinta por objeto.** El pre-pase ya no usa `scene.overrideMaterial` (es UN
   material para toda la escena) sino un `MeshNormalMaterial` por valor, intercambiado malla a
   malla. Su `opacity` viaja en la **alfa del buffer de normales** — three deja la mezcla apagada
   en materiales no `transparent`, así que llega intacta. `Body` y `Mesh_0` (las dos mallas de
   Meshy) van a `0.2`; el cuarto, cajas de Blender con normales limpias, se queda en 1.
2. **Corrección de escorzo** (`facing = |nc.z|`, o sea |N·V|): en escorzo la normal gira muy rápido
   de un píxel al siguiente aunque la superficie sea lisa. Se aplica a los dos términos — también
   quita las falsas siluetas del escritorio y el suelo vistos de canto.

Además: rampa del `smoothstep` de 2.0 a **2.8** (el píxel dudoso se desvanece en vez de encenderse
de golpe) y `LinearFilter` en el buffer de normales (promedia 4 téxeles: mata el ruido de un píxel
sin tocar los pliegues, que ocupan varios). La `DepthTexture` sigue en `Nearest`: `DEPTH_COMPONENT24`
no es filtrable en WebGL2.

Todo sigue siendo ajustable por query: `?isens=` (1 = comportamiento anterior), `?oramp=`, `?nbias=`.

### Lo que NO se arregló, y por qué

Quedan **motas oscuras sueltas** en la ceja, la sien y el mentón. Se ven **también con
`?outline=0`**: están horneadas en el atlas, no las dibuja el sombreado. No son fuga de canaleta
(el margen es `MARGIN_PX 8` a 4096, muy fuera del alcance del filtro bilineal): son téxeles del
bake original de Meshy o del traspaso al UV reempaquetado. Arreglarlo toca `repack_uvs.py` y
obliga a un `tools/rebuild_character.sh` completo — trabajo aparte, no empezado.

### Trampa de medición (para no repetirla)

`__inkFrac()` **no** sirve para juzgar este arreglo: mide área de trazo y está dominada por los
contornos legítimos, así que da 2.16 % con `isens=0.2` y 2.16 % con `isens=1` mientras las
capturas muestran una diferencia clara. Contar píxeles que oscilan tampoco sirve: al girar la
cabeza el detalle de la textura barre los píxeles y satura la medida. **Aquí manda la comparación
visual de `generated/renders/ink_*.png` a la misma pose.**

### Verificación

`PROBE OK errors []` a 60 fps, 5 pases del composer · `INK OK` en las 3 variantes.
Comparativas: `generated/renders/ink_base_p*.png` contra `ink_isens_1_p*.png` (antes) y
`ink_outline_0_p*.png` (lo que no pinta el contorno).

## Sesión 9 (cont.) — las motas de la textura: DOS INTENTOS FALLIDOS, no repetirlos

Tras arreglar el contorno quedaban motas oscuras en ceja, sien y mentón. **Siguen ahí.** Lo que sí
quedó establecido, y no hay que volver a comprobar:

- **Están horneadas en el atlas.** Se ven igual con `?outline=0` y con `?mat=basic`. No son
  sombreado, ni sombras, ni bloom, ni el contorno.

### Intento 1 — dilatar el atlas de origen antes del horneado del repack (FALLÓ)

Hipótesis: `repack_uvs.py` hornea desde `character_texture_logo.png`, el atlas crudo de Meshy con
las canaletas sin rellenar e islas a 2-4 px, y lo muestrea bilineal → el filtro cruza a la isla
vecina y se trae el negro del hoodie sobre la piel.

Se implementó (`dilate_colors` ahora es ortogonal-primero en vez de media de los 8 vecinos, y
`repack_uvs.py` dilata el atlas de origen antes de hornear) y se reconstruyó el personaje entero.
**La cara sale idéntica.** Los cambios se conservan porque el sangrado que evitan es real y barato,
pero no eran la causa.

**La trampa que llevó a esa hipótesis falsa:** se contaron "téxeles mucho más oscuros que su
vecindario" sobre el atlas — salieron 2670, con la mitad pegados al borde de isla, lo que parecía
prueba estadística. Al recortar y ampliar esas zonas, la mayoría eran **pestañas, el iris y el logo
del pecho**. Detalle legítimo. Ninguna medida sobre la textura vale sin mirar el recorte ampliado.

### Intento 2 — quitar manchas pequeñas sobre la piel (FALLÓ, no se llegó a integrar)

Filtro de componentes conexas: candidatos = téxeles rodeados de piel y mucho más oscuros que ella;
se quitan las componentes de área ≤ 60 y se conservan las grandes (ojos, cejas, barba). Se hizo la
vista previa en numpy y **se descartó al verla**: lo marcado bordeaba el ojo, la ceja y el labio. El
antialias del borde de cada rasgo se parte en componentes pequeñas, así que el filtro erosiona los
rasgos en vez de limpiar motas.

### Qué son en realidad, y la opción recomendada

No son manchas sueltas sobre piel lisa: son los **bordes piel↔gorra / piel↔barba / piel↔pelo**,
dentados a escala de téxel. La cabeza ocupa poca área del atlas (`REPACK escala lineal 0.753`: el
reempaquetado hasta PIERDE resolución) y en pantalla se magnifica ~8× (≈0.5 mm por téxel con la
cabeza a ~600 px), así que un borde irregular de 1-2 téxeles se lee como rayón.

**Opción recomendada, no ejecutada (pendiente de decisión):** dar más área de atlas a la cabeza.
Hoy `repack_uvs.py` empaqueta con densidad uniforme (`smart_project(..., area_weight=0.0)`). Si las
islas de la cabeza se escalan 2-3× antes de empaquetar, el defecto se reduce en la misma proporción
y además la cara gana definición de verdad. Es un cambio en la cadena de UV + reconstrucción
completa. Descartada la alternativa de repintar la cara a mano: `face_features.py` ya hace eso para
barba y labios y es donde más se ha peleado.

## Sesión 9 (cont.) — fase 2 y prototipo de la landing

**Fase 2 hecha.** El motor salió de `preview.html` a `export/lib/scene.js` —
`createAvatarScene(opts)` con escena, luces, GLB, mezcla de clips, seguimiento de cursor y bucle.
`preview.html` queda como arnés delgado (panel de estado, botones de clip y las variantes `?mat=`).
`tools/preview_probe.mjs` pasa sin tocarse: el contrato `window.__status / __view / __vibe /
__inkFrac` se conserva. Opciones nuevas para la landing: `controls:false` (la cámara la mueve quien
llama), `onFrame(cb)`, `onProgress`, `onReady`, `maxPixelRatio`, `start()` / `stop()`.

**Prototipo de la landing.** `export/index.html`, un solo archivo con las 5 secciones y contenido
real de los 3 proyectos, con `?modo=` para comparar los tres esquemas de presencia del 3D en vivo:

| `?modo=` | el 3D vive hasta | para qué |
|---|---|---|
| `fondo` (por omisión) | `contacto` | lienzo fijo detrás de todo, la cámara viaja por sección |
| `hero` | `hero` | solo la primera pantalla, el resto es web plana |
| `hibrido` | `stack` | 3D en hero/sobre mí/stack, se retira en proyectos |

Fuera del tramo con 3D no basta con `opacity`: se llama `av.stop()`, que es donde se recupera
batería de verdad.

Diseño: paleta sacada de las luces de la propia escena (`--noche` = `scene.background`, `--tinta` =
el color del contorno, `--neon` = las barras RGB, `--ambar` = la luz del techo), Bricolage Grotesque
+ Instrument Sans, columna de texto a la DERECHA porque `camera-path.js` manda al personaje al
tercio izquierdo. Los 3 proyectos no son 3 tarjetas iguales porque no son 3 cosas iguales.

**Sonda nueva `tools/landing_probe.mjs`**: recorre las 5 secciones en los 3 modos, afirma que la
cámara viaja, que el 3D se apaga donde el modo dice, que no hay desborde horizontal a 375 px y que
no hay errores de consola. `LANDING OK` en los tres, 54-60 fps. Ya cazó dos bugs reales: 356 px de
desborde por un velo con `inset` negativo en `vw`, y el estado de cámara `proyectos` de
`camera-path.js`, que estaba en `x = 2.35` — **fuera de la pared derecha del cuarto**, y dejaba la
sección en negro. Se corrigió eligiendo el encuadre con capturas.

**Decisión pendiente del usuario:** cuál de los tres modos. La comparación que importa es
`landing_fondo_proyectos.png` contra `landing_hibrido_proyectos.png`.

## Sesión 10 (2026-09-04) — híbrido elegido, y la landing terminada

**Decisión del usuario:** *"híbrido entonces, crea todo, no estaré, así que haz todo lo que más
puedas"*. Se cierra la comparación de los tres esquemas de presencia del 3D y `export/index.html`
deja de ser un prototipo comparador: **es el sitio**. `?modo=fondo` y `?modo=hero` quedan como
escape para volver a comparar sin tocar el código.

### Lo que el prototipo escondía y hubo que arreglar

Las capturas del prototipo se veían bien porque solo se miraba el tramo CON 3D. Al fijar el
híbrido salieron cuatro problemas reales, todos de la mitad que el prototipo no ejercitaba:

1. **Media pantalla de negro en los proyectos.** La columna de texto vive a la derecha porque
   `camera-path.js` manda al personaje al tercio izquierdo. Al apagarse el 3D esa columna se
   quedaba donde estaba, con la mitad izquierda vacía. La maqueta ahora es **por sección**
   (`.escena` contra `.plano`), no por el estado global del canvas: las secciones sin 3D son de
   ancho completo y traen su propio fondo, que además tapa el fundido del canvas al retirarse.
2. **El encuadre vertical era el de escritorio.** El `fov` de three es VERTICAL: a 375 × 812
   (aspecto 0.46 contra 1.6) el encuadre horizontal se derrumba y el personaje salía cortado y
   pegado al borde. Cada estado de `CAMERA_STATES` lleva ahora una variante `movil` con más
   ángulo y el punto de mira más bajo — mirar más abajo **sube** al personaje en el cuadro, que
   es donde tiene que estar porque el texto ocupa la mitad de abajo. `createCameraPath(...,
   {variant})` y `path.setVariant()` en el `resize` (girar el teléfono cambia cuál es el correcto).
   El de `stack` se eligió barriendo cuatro candidatos con capturas, no a ojo: el primero dejaba
   la cabeza gigante a la izquierda y los monitores —que son el punto de esa sección— en negro.
3. **"Hacé clic y se pone los audífonos" era mentira.** `pointerVibe` escuchaba en
   `renderer.domElement`, pero en la landing el canvas vive DEBAJO del contenido (`main` con
   `z-index:1`) y nunca recibía el clic. Nueva opción `pointerTarget`; la landing pasa `document`
   y el propio manejador ignora los clics que caen sobre `a`, `button`, `input` o `textarea`.
4. **El seguimiento de cursor no existía en móvil.** `scene.js` escuchaba `mousemove`. Ahora
   escucha `pointermove`, que un ratón dispara igual y un dedo también. Las sondas que simulaban
   el movimiento con `new MouseEvent('mousemove')` se actualizaron a `PointerEvent`.

### El plan B, y por qué NO puede vivir dentro del módulo

Lo cazó una captura: con el CDN de jsdelivr lento, la página se quedaba con la pantalla de carga
puesta **tapando el sitio entero**. El respaldo por temporizador estaba dentro del
`<script type="module">`… que en esa avería no llega a correr nunca.

`window.__planPlano` vive ahora en un script **clásico** y se arma pase lo que pase. Tres averías,
tres detecciones:

| Avería | Quién la detecta | En cuánto |
|---|---|---|
| Sin WebGL2 (three r170 no trae WebGL1) | `hasWebGL()` antes de construir el renderer | inmediato |
| CDN de three caído / sin importmap | reloj de arranque del script clásico; el módulo lo desarma con `window.__moduloVivo()` al correr | 8 s |
| El GLB no llega o llega roto | `onError` del loader, más un reloj de respaldo | inmediato / 25 s |
| JavaScript apagado | `<noscript><style>`: no corre ni el script clásico | inmediato |

En los cuatro el hero cae a `poster.jpg` y el texto manda. El caso `<noscript>` repite a propósito
las reglas de `body[data-3d="none"]`: sin JS no se puede poner ese atributo, y hacer que el estado
por omisión del `<body>` sea el plano obligaría a TODO el mundo a bajarse `poster.jpg`. La sonda
compara los dos caminos para que no se desincronicen.

**Trampa de CSS, para no repetirla.** El velo del hero en plan B se pintaba con `z-index:-1` y
**no se veía**: el contexto de apilado lo crea `<main>`, no la sección, así que un descendiente de
z negativo se pinta ANTES que el fondo de la propia sección — es decir, la imagen que venía a
oscurecer lo tapaba a él. El velo va en `z-index:0` y `.col` sube a `z-index:1`. (El velo de las
secciones CON 3D sí puede quedarse en `-1`: lo que tiene detrás es el canvas, que está fuera de
`main`.)

### Contenido: cada proyecto con la pieza que lo explica

El material visual de PipeBot sigue sin llegar, así que el caso se armó **sin depender de él**: un
diagrama SVG del sistema real (WhatsApp → Twilio → Node/Express → Supabase, con Redis al lado y la
cadena DeepSeek V4 Pro → Groq LLaMA 3.3 70B → Gemini 2.0 Flash con sus saltos de respaldo) y el par
`bot_active ⇄ human_active`, que es la decisión de diseño que de verdad costó. Amaranthus lleva las
dos barras de peso de JavaScript a escala real (460 KB contra 12 KB: la desproporción ES el
argumento) y Holistic, la paleta día/noche y las tres familias tipográficas que se entregaron.
Todos los datos se verificaron contra los repos en disco — el README de PipeBot dice "Groq →
Gemini", que está **desactualizado**; el código (`backend/services/llm.js`) tiene los tres.

Las notas internas (`.falta`) que el prototipo mostraba al visitante salieron de la página y
quedaron como comentarios HTML en el sitio donde va el material cuando llegue.

### Otros cambios

- **`?v=<ahora>` ya no se manda en la landing.** Rompía el caché de 4 MB en cada visita. Es una
  opción (`bustCache`) que solo usa `preview.html`, que es donde el GLB se regenera cada rato.
- **`preload` del GLB por script**, no como `<link>` fijo: adelanta la descarga al parseo del HTML
  en vez de esperar a que resuelvan el módulo y three desde el CDN, pero **no le gasta 4 MB a
  quien no tiene WebGL2**. Repite la comprobación de `hasWebGL()` a propósito: el módulo carga
  demasiado tarde para servir de algo ahí. La sonda afirma que `avatar.glb` se pide UNA vez.
- Cabecera de verdad: `og:image`/`twitter:card`, JSON-LD `Person`, `canonical`, `theme-color`,
  favicon SVG en línea, `lang="es"`, enlace de salto al contenido, hilo de secciones con
  `aria-current` y botón de copiar el correo.
- `tools/make_poster.mjs` (nuevo): genera `export/poster.jpg` (1920×1080, el cuarto sin texto) y
  `export/og.jpg` (1800×945, render + nombre en una capa aparte) **desde la escena en vivo**.

### Verificación

`LANDING OK` — `node tools/landing_probe.mjs` recorre las 5 secciones en escritorio Y en vertical
y afirma: viaje de cámara real, 3D encendido/apagado donde toca, hilo de secciones correcto, cero
desborde a 375 px, pantalla de carga retirada, `avatar.glb` pedido una sola vez, y los dos planes B
(sin WebGL y con jsdelivr bloqueado) con la página legible. 58-60 fps.
`PROBE OK errors []` y `INK OK` siguen pasando tras el cambio a `pointermove`.
Capturas: `generated/renders/landing_hibrido_*.png`, `landing_hibrido_movil_*.png`,
`landing_plano_*.png`, `landing_sincdn_*.png`.

### Bloqueantes que siguen siendo del usuario

- **Capturas de PipeBot** (`refs/pipebot/CAPTURAS.md`). El caso ya se sostiene sin ellas; las
  capturas van en una tira debajo del diagrama, no en su lugar.
- **LinkedIn, WhatsApp de trabajo y dominio propio.** Entran en la lista de contacto y en el
  `sameAs` del JSON-LD; hoy `<link rel="canonical">` apunta a un dominio que aún no existe.
- **Publicar.** Resuelto a medias: `tools/build_site.sh` arma `dist/` (4.4 MB) con el GLB copiado
  explícitamente y un `_headers` de cachés, listo para arrastrar a Netlify o Cloudflare Pages.
  Queda decidir el dominio y cambiar el `<link rel="canonical">`.

## Sesión 11 (2026-09-17) — quiebres negros y definición: cáscara interior + atlas de cabeza a 2×

**Reporte del usuario:** "aún sigo viendo quiebres negros y mucho menos definición en la página
que en el archivo original". Rama nueva `calidad-avatar` (sale de `ajuste-velo-camara`, que tenía
cambios SIN commitear de la sesión del 2026-09-08: velo más suave en `export/index.html`, cámaras
más cerca en `camera-path.js`, `tools/diag_velo.mjs` y `docs/PREGUNTAS_CLIENTE.*`. Siguen sin
commitear; no son de esta sesión y no se evaluaron).

### Diagnóstico (primer plano de la cara en el visor real, `tools/face_shot.mjs`, cuatro variantes)

| variante | rayas negras finas en mejilla / frente / sien |
|---|---|
| look actual | sí |
| `?outline=0` | sí |
| `?toon=0` | sí |
| `?fx=off` (PBR, sin composer) | **sí, en gris** |

O sea: geometría, no sombreado ni contorno ni textura. `close_gaps.py` cierra rendijas de hasta
3 mm; medido sobre `character.blend` DESPUÉS de ese paso, de los 479 vértices de borde de la
cara que miran al frente, el 46 % tiene su borde vecino a 3-10 mm (`SNAP` a 4 mm ya mellaba la
visera, sesión 5). Con `FrontSide` se ve a través de la cabeza hasta el fondo del cuarto.
Capturas: `generated/renders/cara_diag_{actual,outline_0,toon_0,fx_off,fx_off_shadow_off}.png`.

Sobre "definición": la textura de partida sigue siendo Meshy a 2048 (≈1 téxel/mm) y la cabeza
iba con la MISMA densidad que el hoodie (1.5 téxeles/mm a 4096) aunque en pantalla se magnifica
3-8×; en el hero a 1440 px la cabeza mide ~120 px, ahí el límite no es la textura sino el
cel-shading de 3 bandas + el contorno + el velo. No se tocó el look (decisión del usuario, sesión 6).

### Arreglo 1 — `blender/scripts/add_gap_shell.py` (nuevo; va tras `redilate_texture.py` y antes de `smooth_normals.py`)

Cáscara interior CERRADA bajo la piel de la cabeza. Lo que NO funcionó, para no repetirlo:

- **Duplicado hundido de la propia malla**: tendría las mismas rendijas; de frente se ve a través
  de las dos.
- **Remallado por voxels de la cabeza tal cual**: la malla es abierta y OpenVDB la convierte en
  bandas finas sueltas alrededor de cada isla; no une nada (5296 tris para toda la cabeza).
  Hay que darle GROSOR antes (Solidify 4 mm hacia dentro): cada isla se vuelve una losa cerrada
  y el remallado a 4 mm une las losas vecinas.
- **Filtrar por "punto más cercano de Body"**: en la frente bajo la visera el punto más cercano
  es la visera, no la piel → la cáscara salía a parches justo donde más rendijas hay (cobertura
  ~50 %). Se cambió por RAYOS: cada vértice se ajusta a exactamente `OFFSET` 2.5 mm bajo la piel
  (rayo hacia fuera por su normal; si no pega, rayo hacia dentro por si asomaba), los que no ven
  piel (están bajo una rendija) se relajan hacia sus vecinos, y una cara sobrevive si desde su
  centro o alguno de sus vértices hay piel frontal encima entre 1.2 y 9 mm (con el centro solo se
  perdían las caras bajo las rendijas, que son las que importan).

Después: decimado a 7000 tris, UV y pesos por `DATA_TRANSFER` (cara más cercana interpolada,
o sea que por la rendija se ve la misma piel/barba/gorra), y `join` a Body (mismo material y
misma sensibilidad a tinta). Unir descarta las normales personalizadas → borra
`Body['normals_smoothed']` y `smooth_normals.py` se repite; la cáscara recibe así las normales de
la piel exterior y no se nota un cambio de sombreado en la rendija. **Medida propia** (impresa en
cada corrida, falla si < 60 %): desde cada vértice de borde de la cara, rayo hacia dentro por su
normal alisada, ¿hay cáscara a < 15 mm? → 0-3 mm 82 %, 3-5 mm 92 %, 5-10 mm 96 %, 10-20 mm 94 %.
Renders de control con material plano: `gapshell_before.png`, `gapshell_shell.png` (la cáscara
sola: tiene que verse una cabeza casi entera), `gapshell_after.png`. `check_rig.py` sube el
presupuesto a 48 000 tris (personaje 46 364).

### Arreglo 2 — `depthMin` en `export/lib/postfx.js` (`?dmin=`, 8 mm por omisión)

Con la cáscara, la rendija ya no muestra negro pero sí un ESCALÓN de profundidad de 2.5-6 mm, y
el término de profundidad del contorno (relativo a la distancia) lo entintaba igual en primer
plano: `cara_shell_v2_dmin0.png` contra `cara_shell_v2.png`. Ahora un salto menor de `depthMin`
metros (máximo de los 4 vecinos × (far − near)) no cuenta como borde. Un pliegue real (nariz,
capucha, visera, monitor sobre escritorio) salta ≥ 1 cm; `preview_shot.png` sale con los mismos
contornos de cuarto y silueta que antes, `INK` 2.11 % (antes 2.16 %).

### Arreglo 3 — `HEAD_SCALE = 2.0` en `repack_uvs.py`

Tras `smart_project`, las islas UV cuya mayoría de área 3D queda sobre la base del cuello (islas
ENTERAS por conectividad UV; escalar caras sueltas rasgaría la isla) se escalan ×2 y se vuelve a
empaquetar con `pack_islands` (rotación, `CONCAVE`, mismo margen). Sorpresa útil: `pack_islands`
empaqueta mucho mejor que `smart_project` (48 % de cobertura frente a 36.6 %), así que la cabeza
pasa de 0.753 a **1.257** veces la densidad de Meshy y el cuerpo NO pierde (0.762). La escala se
imprime por separado y el tope mínimo (0.6) solo aplica al cuerpo. Barrido en `--probe`: ×1.7 →
1.13/0.80; ×2.4 → 1.39/0.71. No hay más detalle REAL que el de Meshy a 2048: lo que gana la cabeza
es que los bordes piel/gorra/barba y lo repintado por `face_features.py` salen menos dentados.
Para detalle de verdad, la opción sería un upscale IA del atlas (Higgsfield, cuesta créditos:
preguntar antes) o remodelar.

### Reconstrucción y verificación

`tools/rebuild_character.sh` completo (incluye ya `add_gap_shell`; unos 15 min, `texture_touchup`
es el paso lento) → `REBUILD OK`. GLB **4044 KB / 56 500 tris** (Body 43 884) / 7 clips / atlas
4096. `FACE OK`, `INK OK`, `PROBE OK errors []`, `LANDING OK` (60 fps). Comparar
`cara_diag_actual.png` (antes) con `cara_v3_head2x.png` (después) y `cara_v3_head2x_browup.png`.
Copia de seguridad de los .blend y GLB anteriores: solo en el scratchpad de la sesión (se borra).

### Lo que NO se hizo

- **`dist/` no se regeneró** ni se publicó: `tools/build_site.sh` copiaría el `export/index.html`
  con los cambios de velo/cámara sin commitear de la sesión anterior. Decidir primero qué hacer
  con esa rama; luego `tools/build_site.sh` + commit de `dist/` en `main` (GitHub Pages).
- Quedan motas horneadas en sien y mentón (sesión 9) y una raya gris tenue junto a la nariz;
  ninguna es negra ya.

## Sesión 12 (2026-09-27) — el nombre grafiteado en la pared, con paneles de neón

Pedido del usuario: que su nombre no se vea "plano" sino grafiteado, wildstyle a full, con
paneles de neón, "muy urbano y característico de Medellín", pintado en el espacio libre de la
pared junto a la ventana. Flujo acordado: 3 candidatos en Higgsfield → él escoge → se lleva a
la web como código.

### Imagen (Higgsfield, `generated/graffiti/`)

- Saldo real al empezar: **1000 créditos, plan Plus** (la memoria decía 24-54; ya no aplica el
  "no gastar sin preguntar" por saldo, pero sigue siendo cortesía avisar). Gasto de la sesión:
  **11 créditos** (3 candidatos + 1 edición, `gpt_image_2_5` calidad high 2k 1:1 = 2.75 c/u).
  Anotado en `generated/credits.log`.
- Candidatos: `cand1_wildstyle_gradiente` (magenta→naranja→cian, flores de silletero),
  `cand2_neon_tubos` (cromo/violeta, contorno de neón rosa, paneles cian, Metrocable, colibrí),
  `cand3_cromo_skyline` (cromo, filos tricolor, skyline). **Elegido: 2**, editado con la misma
  imagen como referencia para quitar los textos "COMUNA 13" (el colibrí y la corona se quedan):
  `cand2b_sin_comuna13.png` (2048², insumo irremplazable, fuera de git como el resto de
  `generated/`). Truco que funcionó a la primera: pedir la edición enumerando TODO lo que debe
  quedar igual y solo después lo que se quita.
- Textura web: `export/img/graffiti.webp` (1536², q86, 455 KB). Sí va en git y `build_site.sh`
  ya la copia (`img/*.webp`).

### Integración: `export/lib/graffiti.js` (nuevo), enganchado en `scene.js`

Cero cambios en Blender ni en el GLB. Todo vive en el visor:

- **Pared:** la lateral +X (glTF), la que queda a la IZQUIERDA de la cámara del hero: es el muro
  vacío grande junto a la ventana. Se probó también la franja de la pared trasera bajo la
  repisa (`?gwall=back`): sale diminuta y tapada por el personaje y la barra RGB
  (`generated/renders/sweep/g_back.png` contra `g_side2.png`). Pieza de 1.6 m centrada en
  (2.045, 1.18, 0.42); a 1.9 m y más alta se salía del encuadre por arriba (`g_side.png`).
- **Calcomanía:** plano `MeshStandardMaterial` (NO toon, a propósito: necesita emisivo propio
  > 2.5 lineal para el bloom) con tres texturas calculadas en canvas al cargar la imagen:
  `map` = la imagen; `emissiveMap` = solo píxeles saturados Y claros (los tubos rosa del
  contorno y los paneles cian pintados; el cromo y el muro salen negros) a intensidad 3.0;
  `alphaMap` = pintura opaca / muro de la imagen transparente. **Por qué el alpha:** en la
  primera captura la pieza se leía como un póster (rectángulo más oscuro que la pared, porque el
  toon de la pared nunca baja del 35 % y un Standard sí). Con el fondo transparente las letras
  quedan sobre la pared REAL con su luz. La máscara va en dos pasos porque los contornos negros
  son tan oscuros como el muro y con un umbral a secas se hacían agujeros: máscara desenfocada
  (radio 1.2 % del lado) que tapa lo que está pegado a pintura clara, más borde difuminado.
- **Neón físico:** dos tubos cian verticales flanqueando la pieza y un panel magenta encima,
  con soportes, emisivos a ~3.7-4 (respiran / parpadean levemente en `update`) y una
  `PointLight` cada uno (cian 0.6, magenta 0.8). A 1.4 el cian lavaba las letras a lila.
- Interruptores: `?graffiti=0`, `?gwall=side|back`, `?gsize= ?gglow= ?glit=`. `status.graffiti`
  dice la pared; `status.lights` suma las 3 puntuales (la sonda exige ≥ 9, sigue OK).

### Verificación

`node tools/look_sweep.mjs` (capturas `sweep/g_*.png`), `node tools/landing_probe.mjs` →
`LANDING OK` 60 fps, 5 secciones escritorio + vertical, plan B, sin errores;
`node tools/preview_probe.mjs` → `PROBE OK errors []`. `node tools/make_poster.mjs` regenerado:
`poster.jpg` y `og.jpg` ya traen el grafiti. Capturas de aprobación:
`generated/renders/landing_hibrido_hero.png` y `landing_hibrido_sobreMi.png`.

### Pendiente / decisiones abiertas

- **El `<h1>` "Sebastián Escobar" sigue en el hero**, así que el nombre sale dos veces (pared y
  texto). El pedido original era "en vez de plano"; decidir si el h1 se reduce a un subtítulo,
  se vuelve `sr-only` (accesibilidad/SEO) o se queda.
- **Encuadre vertical del hero (hecho, segundo pedido de la sesión; REHECHO en la sesión 13
  para la pieza ancha):** de frente el grafiti no
  entraba en cuadro (a 375 px el fov horizontal es de ~28°). Ahora `hero.movil` pone la cámara
  en la esquina delantera izquierda mirando en diagonal hacia +X: `pos (-1.75, 1.25, -2.95)`,
  `target (1.0, 0.30, 0.2)`, fov 58. Grafiti entero a la izquierda, personaje de perfil a la
  derecha, todo en el 40 % superior que deja libre la columna de texto. Se eligió entre 12
  variantes capturadas con un script de scratchpad (copias en `generated/renders/sweep/movil_*.png`;
  H3 es la elegida). Un intento de frente con más fov (A-F) metía medio techo y cortaba ambos.
- Publicado: commits de la sesión en `calidad-avatar` (incluidos los cambios de velo/cámara y el
  cuestionario de cliente que venían sin commitear), `main` avanzada por fast-forward y
  `dist/` regenerado con `tools/build_site.sh`; el push a `main` dispara el workflow de Pages.
- **Trampa de GitHub Pages (arreglada):** el primer push a `main` falló con "Branch main is not
  allowed to deploy to github-pages due to environment protection rules": el entorno
  `github-pages` tenía una política de ramas personalizada que solo permitía `landing-hibrido`
  (de cuando se probó Pages desde esa rama). Se añadió `main` con
  `gh api -X POST repos/Sebastiandevmed/me-on-3d/environments/github-pages/deployment-branch-policies -f name=main -f type=branch`
  y se relanzó el run. Sitio vivo: https://sebastiandevmed.github.io/me-on-3d/

## Sesión 13 (2026-09-27) — el grafiti cubre todo el muro y tiene relieve

Pedido del usuario (con captura del sitio vivo): "¿puedes estirar el graffiti hasta el final del
muro? También me gustaría que se viera más 3D, menos plano".

### Imagen ancha (Higgsfield, 5.5 créditos, saldo antes 989)

- `gpt_image_2_5` high 2k **3:2**, con `cand2b_sin_comuna13.png` como referencia y el truco de la
  sesión 12 (enumerar TODO lo que se conserva y al final lo que cambia: "las dos líneas se
  ESTIRAN hasta los bordes, más paneles cian repartidos"). Dos variantes: `generated/graffiti/
  wide_a.png` (**elegida**: letras de borde a borde, 5 paneles) y `wide_b.png` (6 paneles, más
  margen). 2048×1360 cada una. La cuadrada anterior quedó en `generated/graffiti/
  graffiti_cuadrado_v1.webp` por si hay que volver.
- Textura web: `export/img/graffiti.webp` ahora 2048×1360 q80, 533 KB (antes 1536² 455 KB).

### Colocación: de punta a punta de la pared lateral

`WALLS.side` en `graffiti.js`: `size` ahora es la ALTURA (1.6 m) y el ancho sale del aspecto de
la imagen (3:2 → 2.4 m). Centro `(2.045, 1.18, 0.12)` → la pieza va de z = -1.08 a 1.32. La
pared +X va de z = -4 (detrás de la cámara) a 1.445 (esquina con la ventana); desde la cámara del
hero de escritorio (fov horizontal ≈ 62°) el borde izquierdo del cuadro corta la pared en
z ≈ -1.1, así que la pieza arranca justo donde termina lo visible y muere a 12 cm de la esquina.
Los tubos cian van en los extremos (`gap` 0.08 → z = -1.28 y 1.40; el de la esquina cabe por
2 cm) y el panel magenta mide el 80 % del ancho, con tres soportes.

### Relieve: "sprite stacking" + sombra + contorno cel recortado

- **Pila de 15 planos** (`graffiti_layer_0..13` + `graffiti_decal`) con la misma silueta, de la
  pared (6 mm) hacia el cuarto hasta **6 cm** (`?gdepth=`, 0 = calcomanía plana de antes). Las
  capas de abajo llevan la imagen con tinte oscuro (`0x2a2530`) y `alphaTest 0.5` (recorte sin
  mezcla → se ordenan solas por profundidad); la de arriba es la de siempre (mapa + emisivo +
  alpha difuminado, `alphaTest 0.1`). En escorzo asoman los lados oscuros y las letras se leen
  como bloques que salen del muro. 14 capas y no 8 porque con menos el colibrí y los paneles
  mostraban "escalera" en primer plano (`generated/renders/graffiti_relieve_escorzo.png`).
- **Sombra de contacto** (`graffiti_shadow`): silueta desenfocada (1.4 % del lado) y corrida
  2 % hacia abajo, negra al 75 %, pegada al muro (3 mm) bajo la pila.
- **Contorno cel:** primero salió dibujado el RECTÁNGULO del plano. Causa: el pre-pase de
  `OutlinePass` (postfx.js) cambia TODOS los materiales por un `MeshNormalMaterial` sin máscara,
  así que el plano entero escribía profundidad a 6 cm (> `depthMin` 8 mm). Arreglo en dos
  partes: `_swapMaterials` respeta ahora `mesh.userData.outlineMaterial` (material propio para el
  pre-pase) y `mesh.userData.outline === false` (la malla se esconde en el pre-pase; lo usa la
  sombra); y `graffiti.js` da a la pila un `ShaderMaterial` equivalente al de normales pero
  recortado por la misma máscara (`normalCutout`; `MeshNormalMaterial` no admite `alphaMap`,
  avisó con un warning). Resultado: la tinta sigue el borde de las letras en relieve
  (`?gink=`, 0.6 por omisión).
- Suelo de ruido en la máscara alpha (`smooth(0.15, 0.40, m)`): el grano claro del muro pintado
  daba alphas de 0.1-0.3 que antes se mezclaban invisibles y ahora escribirían profundidad.

### Encuadre vertical rehecho

Con 2.4 m de pieza el `hero.movil` de la sesión 12 mostraba media pieza cortada. Nuevo:
`pos (-1.90, 1.25, -3.80)`, `target (0.67, 0.12, -0.74)`, fov 60 (cámara al fondo del cuarto, en
la esquina delantera izquierda, mirando 40° hacia +X). Grafiti entero arriba a la izquierda
(solo la punta de la flecha de la S sale del cuadro), personaje de perfil a la derecha, el h1
apenas roza las gotas de abajo. Elegido entre 4 variantes con `tools/hero_shot.mjs` (nuevo:
hero escritorio + vertical + dos primeros planos del grafiti en ~40 s, a `generated/renders/
sweep/hero_*.png`).

### Verificación

`node tools/landing_probe.mjs` → `LANDING OK` (60 fps, 5 secciones, sin desborde, plan B ok);
`node tools/preview_probe.mjs` → `PROBE OK errors []`; `node tools/make_poster.mjs` → poster y og
regenerados con la pieza ancha. `tools/build_site.sh` → `dist/`. Capturas de aprobación:
`generated/renders/landing_hibrido_hero.png`, `landing_hibrido_movil_hero.png`,
`graffiti_relieve_close.png`, `graffiti_relieve_escorzo.png`.

### Pendiente / abierto

- El h1 "Sebastián Escobar" sigue duplicando el nombre de la pared (abierto desde la sesión 12).
- En primer plano extremo (a < 1 m) la pila deja ver escalones en los bordes de los paneles
  cian y el colibrí; desde cualquier cámara de la landing no se nota. Si molesta: más capas
  (`LAYERS`) o menos profundidad (`?gdepth=0.04`).

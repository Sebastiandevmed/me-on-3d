# HANDOFF — Avatar 3D "Me on 3D"

Documento de traspaso para continuar en una conversación nueva con el mismo flujo de trabajo. Se actualiza en cada hito.

**Última actualización:** 2026-09-03 (sesión 2, en curso)

## Cómo retomar

1. Leer este archivo, la spec y el plan:
   - Spec: `docs/superpowers/specs/2026-09-03-avatar-3d-design.md`
   - Plan: `docs/superpowers/plans/2026-09-03-avatar-3d.md` (14 tareas)
   - Ledger de ejecución: `.superpowers/sdd/2026-09-03-avatar-3d/progress.md` (qué tareas están completas, rulings tomados)
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
| 9 Animaciones (animate.py, checks/check_anim.py, anim_strip.py → character_anim.blend) | ✅ completa (bde74c3) | 7 acciones + 7 pistas NLA; sin dedos (typing = bob de manos/antebrazos); idle solo spine001/002/003/005; vibe con ojos cerrados f7..f112 y cabeceo -16..+14°; tiras en generated/renders/strip_*.png. Regla de mezcla para el visor: idle base, typing superpuesto (huesos disjuntos), vibe/lookAround en exclusiva con idle fundido a 0. Exportar con SIT aplicada (los huesos sin clip toman la pose exportada) |
| 11 Ensamblaje + HDR (assemble.py, render_hdr.py → avatar.blend, export/night.hdr) | ✅ completa (fc797d1 + fix 0011ced) | 48 214 tris; colocación por muslos (importa sit_test.py); moto 0.25 m yaw -30° textura 1k; HDR 169 KB; avatar.blend guardado NEUTRO (frame 1, sin acción, pistas muted, emisión 0, rutas relativas). Render de aprobación generated/renders/assembled_v1.png. Typing corregido (655cf7f) para no atravesar el escritorio |
| 12 Exportación GLB (export_glb.py) | ✅ completa (22f7210) | export/avatar.glb 1.94 MB Draco, JPEG q85, 48 390 tris, 7 clips con solo sus huesos (keep_anim_armature=False), pose base = SIT (export_reset_pose_bones=False, pistas muted al exportar), pantallas con emissiveTexture; avatar_uncompressed.glb 4.3 MB; generated/avatar_inspect.json. Material Character trae emisión (el visor puede bajarla) |
| 13 Visor (export/preview.html, tools/serve_preview.sh) | ✅ implementado (13b0bed), revisión en curso | three.js 0.170 + Draco + night.hdr como entorno; intro → idle+typing+Blink; vibe/lookAround exclusivos; seguimiento de cursor en spine006 (restaura el cuaternión del clip cada frame); captura generated/renders/preview_shot.png (YAVG 45). Prueba manual pendiente del usuario: `tools/serve_preview.sh` → http://localhost:8765/preview.html |
| 14 Cierre (README.md, créditos, memoria) | 🔄 sesión principal | README escrito; credits.log cerrado; memoria actualizada |
| 10 Moto + ventana Medellín (Higgsfield) | ✅ completa | generated/moto/dr150.glb (v2a: cortavientos Acerbis, sin baúl; 7958 tris, 4 MB, textura a reducir a 1k en ensamblaje/export), previews moto_preview_0..2.png. Ventana: recorte 16:9 de medellin_a → generated/window/medellin.png, plano corregido (90°,0,180°) en build_scene.py |
| 14 Cierre / README | ⏳ | |

## Créditos Higgsfield

Saldo inicial 186. Balance real consultado antes de la Tarea 10: 94.8 (≈91 gastados; el log contaba 80). Tarea 10 gastó 38 (ventana x2 = 2, moto v1 = 2, moto v2 x2 = 4, malla Meshy = 30, autorizada por el usuario) → balance real 54.8 (consultado), ≈131 gastados. Log en `generated/credits.log`. El límite de 100 ya se superó con autorización; avisar antes de cualquier gasto nuevo.

## Archivos generados clave

- `refs/face/` frames del video del usuario; `refs/style/moto_gorra_puente.png`.
- `generated/sheet/sheet_a..d.png` láminas; `media_ids.json` ids subidos a Higgsfield (caducan, resubir si hace falta).
- `generated/screens/{code,logo,stack}.png` (logo = logo de la empresa del usuario).
- `refs/logo.png` logo de la empresa (RGBA transparente, laurel + globo + lanza morada). Va en el monitor derecho y reemplaza el monograma SE del hoodie (Task 6b, `blender/scripts/apply_chest_logo.py`).

## Pendiente del usuario

- Aprobar el logo en el pecho (generated/renders/chest_logo.png) — versión clara por defecto; si prefiere la tinta oscura original: chest_logo_dark.png.
- Aprobar la pose sentada (generated/renders/sit_v_final.png) y la cara (face_parts_open.png / face_parts_closed_browup.png).
- Vista de ventana: 'a' recortada (cambiar a 'b' si lo pide).
- Opcional: dejar `refs/code/*.ts` para la pantalla de código (si no, código de ejemplo). Logo ya entregado.
- Fotos definitivas de cara (opcional) para afinar el parecido al final (Tarea 14).

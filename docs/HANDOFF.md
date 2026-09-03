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
| 7-9, 11-13 Blender (pose, cara, animaciones, ensamblaje, export, visor) | ⏳ | |
| 10 Moto + ventana Medellín (Higgsfield) | ⏳ | |
| 14 Cierre / README | ⏳ | |

## Créditos Higgsfield

Saldo inicial 186. Gastados: 80 (10 en láminas + 35 malla v1 + 35 malla v2). Log en `generated/credits.log`. Límite acordado: avisar antes de pasar de 100.

## Archivos generados clave

- `refs/face/` frames del video del usuario; `refs/style/moto_gorra_puente.png`.
- `generated/sheet/sheet_a..d.png` láminas; `media_ids.json` ids subidos a Higgsfield (caducan, resubir si hace falta).
- `generated/screens/{code,logo,stack}.png` (logo = logo de la empresa del usuario).
- `refs/logo.png` logo de la empresa (RGBA transparente, laurel + globo + lanza morada). Va en el monitor derecho y reemplaza el monograma SE del hoodie (Task 6b, `blender/scripts/apply_chest_logo.py`).

## Pendiente del usuario

- Aprobar el logo en el pecho (generated/renders/chest_logo.png) — versión clara por defecto; si prefiere la tinta oscura original: chest_logo_dark.png.
- Opcional: dejar `refs/code/*.ts` para la pantalla de código (si no, código de ejemplo). Logo ya entregado.
- Fotos definitivas de cara (opcional) para afinar el parecido al final (Tarea 14).

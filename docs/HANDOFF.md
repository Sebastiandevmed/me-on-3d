# HANDOFF — Avatar 3D "Me on 3D"

Documento de traspaso para continuar en una conversación nueva con el mismo flujo de trabajo. Se actualiza en cada hito.

**Última actualización:** 2026-09-03 (sesión 1, en curso)

## Cómo retomar

1. Leer este archivo, la spec y el plan:
   - Spec: `docs/superpowers/specs/2026-09-03-avatar-3d-design.md`
   - Plan: `docs/superpowers/plans/2026-09-03-avatar-3d.md` (14 tareas)
   - Ledger de ejecución: `.superpowers/sdd/2026-09-03-avatar-3d/progress.md` (qué tareas están completas, rulings tomados)
2. Flujo de trabajo acordado: skill **superpowers:subagent-driven-development** sobre el plan. Un subagente implementador por tarea + revisor por tarea. Las tareas marcadas [SESIÓN PRINCIPAL] (4, 5, 10, 14) las hace el agente principal porque usan Higgsfield y necesitan aprobación de Sebastián.
3. Rama git: `avatar-3d` (main solo tiene docs). Identidad git configurada localmente.
4. Hablar en español. Mostrar renders/láminas al usuario con SendUserFile y con `open` antes de cada punto de aprobación.

## Quién es el usuario (resumen)

Sebastián Escobar, desarrollador web de Medellín (Campo Valdés). Moda urbana, ropa ancha, gorras flexfit (visera curva, puesta normal, NUNCA al revés), barba completa, piel clara-oliva (no morena), pelo rizado con corte "7" (lados cortos, más largo y crespo atrás, tipo brócoli). Dos candongas en CADA oreja (obligatorio). Rap: gesto característico = cabecear con ojos cerrados. Gamer. Moto Suzuki DR150 blanca/azul con baúl negro. Stack: Shopify, Supabase, Cloudflare. Ropa con diseño estilo Dynamo (dynamobrand.co): tipografía gótica en pecho, letras en mangas, ángel barroco en la espalda.

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
| 3 Escena del escritorio (build_scene.py) | 🔄 en curso (subagente) | ruling: cámara al FRENTE del personaje; ventana y barras RGB detrás como fondo; monitores bajos en arco |
| 4 Lámina del personaje (Higgsfield) | 🔄 iterando con el usuario | sheet_b aprobada en look base; v2 = piel clara + ropa Dynamo (sheet_d recomendada); v3 pendiente = pelo corte "7" más crespo atrás |
| 5 Malla rigueada Meshy | ⏳ | espera aprobación final de la lámina |
| 6-9, 11-13 Blender (import, pose, cara, animaciones, ensamblaje, export, visor) | ⏳ | |
| 10 Moto + ventana Medellín (Higgsfield) | ⏳ | |
| 14 Cierre / README | ⏳ | |

## Créditos Higgsfield

Saldo inicial 186. Gastados: 4 (dos rondas de lámina). Log en `generated/credits.log`. Límite acordado: avisar antes de pasar de 100.

## Archivos generados clave

- `refs/face/` frames del video del usuario; `refs/style/moto_gorra_puente.png`.
- `generated/sheet/sheet_a..d.png` láminas; `media_ids.json` ids subidos a Higgsfield (caducan, resubir si hace falta).
- `generated/screens/{code,logo,stack}.png`.

## Pendiente del usuario

- Aprobar la lámina definitiva (con corte "7").
- Opcional: dejar `refs/code/*.ts` y `refs/logo.png` para las pantallas (si no, se usan placeholders "SE").
- Fotos definitivas de cara (opcional) para afinar el parecido al final (Tarea 14).

# Spec — Avatar 3D "más profesional y didáctico": cel-shading + landing de portafolio

Fecha: 2026-09-03 · Sesión 6 · Continúa `2026-09-03-avatar-3d-design.md` y el plan de pulido `2026-09-03-avatar-polish.md`.

## Problema

El prototipo funciona de punta a punta (GLB 3.81 MiB / 47 663 tris / 7 clips, visor con seguimiento de cursor suave, todos los checks OK), pero se lee como **demo técnica de un modelo IA con defectos**, no como pieza de portafolio:

1. **Personaje.** La malla de Meshy tiene rendijas residuales (> 3 mm, las que `close_gaps.py` no pudo cerrar), cara abollada y gorra facetada. El sombreado PBR con `night.hdr` los ilumina y los subraya.
2. **Escena.** Luces correctas pero sin intención: nada separa al personaje del fondo, los monitores y las barras RGB no "brillan", no hay encuadre narrativo.
3. **Presentación.** `preview.html` es un arnés de depuración (botones sin diseño, texto de FPS, ayuda en gris). No hay nada que muestre quién es Sebastián ni qué hace.

## Decisiones tomadas con el usuario

- El personaje **NO se remodela ni se regenera en Meshy**: se **estiliza**. Los defectos de malla IA dejan de leerse como error y pasan a leerse como estilo.
- El entregable crece: además del `.blend` + GLB + visor, se construye una **landing completa de portafolio** en español, con hero 3D a pantalla completa y contenido debajo.
- El contenido de proyectos y contacto es **real**, entregado por el usuario. Hasta que llegue, la landing usa un bloque `DATA` con marcadores explícitos.

## Enfoque: por qué contorno por post-proceso

Se descartaron dos alternativas:

- **Todo horneado en Blender** (luz plana a la textura + contorno como *inverted hull*): itera lentísimo y el casco invertido se rompe justo donde más se ve — la malla tiene 8 563 vértices de borde y el contorno saldría agujereado en la cara.
- **`MeshToonMaterial` a secas en el visor**: es lo ya probado con `?mat=toon`, que viró el hoodie a morado. La causa no es el toon: es que las luces de la escena son azules (`key` 0xcfe0ff, `win` 0x8fb8ff, hemisférica 0x33405c) y sin base ambiental un hoodie casi negro multiplicado por luz azul da morado.

**Elegido: cel-shading por material + contorno por post-proceso.** El contorno se calcula sobre los búferes de profundidad y normales (Sobel a pantalla completa), así que **no depende de la topología**: dibuja el borde igual con rendijas, y de paso contornea monitores, escritorio y moto, que es lo que unifica el look como ilustración.

El GLB **no cambia**: cero riesgo sobre rig, pesos, clips, landmarks de cara y audífonos. Todo el trabajo de esta spec vive en `export/`.

## Arquitectura

Hoy `export/preview.html` es un solo archivo con todo dentro. Se extrae a módulos con una responsabilidad cada uno, y `preview.html` queda como arnés delgado encima:

```
export/
  lib/
    scene.js        createAvatarScene(canvas, opts) -> carga GLB+HDR, luces, mixer, mezcla de
                    clips, seguimiento de cursor. Expone { scene, camera, controls, play, status }.
    toon.js         applyToon(root, opts) -> materiales cel + rampa de bandas + luz de borde;
                    toonLights(scene) -> paleta de luces para cel.
    postfx.js       createComposer(renderer, scene, camera) -> Render → Bloom → Contorno →
                    Viñeta → Output. Contorno = Sobel sobre profundidad + normales.
    camera-path.js  Estados de cámara con nombre (hero, sobre-mi, stack, proyectos, contacto)
                    e interpolación suavizada.
  preview.html      Arnés de depuración. CONSERVA window.__status y window.__view.
  index.html        Landing: canvas fijo de fondo + secciones que scrollean encima.
```

**Restricción dura:** `tools/preview_probe.mjs` es la red de regresión de todo lo anterior (cabeza sigue al cursor, cuello acompaña, `hpQ` no nulo, sombras, sin errores de consola). El refactor **debe** conservar la API `window.__status` / `window.__view` / `window.__vibe`, y la sonda se amplía en vez de reescribirse.

### Bloque 1 — Look cel-shaded (`toon.js`, `postfx.js`)

- **Materiales.** Cada malla pasa a `MeshToonMaterial` conservando su `map`; rampa de 3 bandas por `DataTexture` con `NearestFilter`. Pantallas y barras RGB quedan emisivas (no se tocan). Los materiales originales se guardan para poder volver con `?fx=off`.
- **Luz de borde.** *Fresnel* inyectado por `onBeforeCompile` sobre el fragmento del toon, sumado al color final. Es lo que despega al personaje del fondo oscuro sin depender de la geometría.
- **Paleta de luces para cel.** Base ambiental fuerte (para que el color de la textura se lea en la zona en sombra) + una key que define la banda + acentos de pantallas/RGB. Sin esto vuelve el morado.
- **Post-proceso.** `EffectComposer` con RT `HalfFloatType`: `RenderPass` → `UnrealBloomPass` (umbral alto: solo monitores y barras RGB) → pase de contorno → viñeta → `OutputPass` (tonemapping y espacio de color se hacen aquí, no en el `RenderPass`).
- **Pase de contorno.** Pre-pase con `scene.overrideMaterial = MeshNormalMaterial` a un RT con `DepthTexture` adjunta; luego un cruce de Roberts/Sobel sobre profundidad linealizada y normales, con umbrales separados para borde de silueta (profundidad) y borde de pliegue (normal).

**Parámetros por query, todos afirmables por la sonda:** `?fx=off` (look anterior completo), `?toon=0`, `?outline=0`, `?bloom=0`, y los umbrales del contorno. Se conservan los `?mat=` existentes.

**Plan B declarado (no se construye por adelantado):** si al ver las capturas el sombreado plano deja ver demasiado el ruido de la malla, se añade una pasada de AO suave horneada a la textura en Blender. Se decide **con capturas en la mano**, no antes.

### Bloque 2 — Escena y cámara (`camera-path.js`)

Estados de cámara con nombre `{ pos, target, fov }` e interpolación con suavizado exponencial por tiempo (mismo patrón que el seguimiento de cursor: `TAU`, no por frame). En `preview.html` los disparan botones; en `index.html` los dispara el scroll.

### Bloque 3 — Landing (`index.html`)

- Canvas fijo a pantalla completa como fondo; el contenido scrollea encima: **hero** (nombre + rol) → **sobre mí** → **stack** → **proyectos** → **contacto**.
- `IntersectionObserver` por sección: cambia el estado de cámara y dispara clips (entrar a "sobre mí" = `vibe`).
- Pantalla de carga con progreso real del `LoadingManager` (no un spinner falso).
- **Móvil:** táctil, `pixelRatio` limitado, post-proceso apagado si la GPU no da, `prefers-reduced-motion` = cámara quieta y sin `vibe` automático.
- Un objeto `DATA` al inicio del archivo con nombre, rol, bio, stack, proyectos y links de contacto. Es el único sitio que el usuario edita.

## Verificación

- **Blender:** sin cambios. Los checks existentes (`check_rig`, `check_anim`, `check_scene`, `check_character_material`, `check_face_export`, `glb_inspect`) siguen siendo la verdad del GLB y deben seguir pasando.
- **Visor:** `tools/preview_probe.mjs` se amplía. Aserciones nuevas: composer activo, número de pases esperado, el contorno cambia la imagen (diferencia de píxeles medible contra `?outline=0`), sin errores de consola en cada variante. Las aserciones actuales (`headDist >= 0.1`, `neckDist >= 0.03`, `hpQ` no nulo, sombras) se conservan; la de `lights === 9` pasa a rango porque la paleta cel cambia el conteo.
- **Landing:** la sonda recorre `index.html`, captura por sección, afirma que la cámara efectivamente se movió entre secciones, y hace un pase en 375×812 sin desbordes horizontales.
- Cada fase termina con capturas enviadas al usuario y **espera aprobación** antes de la siguiente.

## Fases

1. **Cel-shading + contorno + bloom** sobre `preview.html` tal como está (sin refactor). Salida: capturas comparativas → aprobación del usuario.
2. **Refactor a `lib/`** + sonda ampliada. `preview.html` pasa a arnés delgado sin perder ninguna capacidad de depuración.
3. **Landing** `index.html` con secciones y coreografía de cámara.
4. **Móvil, rendimiento, accesibilidad y docs** (README + HANDOFF).

## Fuera de alcance

- Remodelar el personaje a mano o regenerarlo en Meshy (el usuario eligió estilizar).
- Cambiar el GLB, el rig, los clips o cualquier script de Blender — salvo el plan B de AO, si las capturas lo piden.
- Desplegar la landing (no hay URL de portafolio todavía; sigue pendiente del usuario).
- Gastar créditos de Higgsfield (quedan 54.8; no se toca nada sin preguntar).

## Pendiente del usuario

- Los 3-4 proyectos reales (nombre, una línea, link) y los links de contacto para el `DATA` de la landing. No bloquea las fases 1 y 2.

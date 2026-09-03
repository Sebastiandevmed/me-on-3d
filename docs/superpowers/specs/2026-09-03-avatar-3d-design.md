# Avatar 3D personal "Me on 3D" — Diseño

Fecha: 2026-09-03
Estado: aprobado por Sebastián en conversación, pendiente de revisión del documento.

## 1. Objetivo

Crear un avatar 3D estilizado de Sebastián, sentado en su escritorio tecleando, rigueado y animado en Blender, exportado como GLB listo para integrarse en una web con three.js. La referencia de calidad e interacción es el personaje de https://www.moncy.dev/, pero con la identidad de Sebastián.

Entregable: archivo `.blend` maestro + GLB (Draco) + visor de prueba. No se construye la web.

## 2. Análisis de la referencia (moncy.dev)

- Stack web: React + Vite, three.js vanilla, GSAP ScrollTrigger. GLB comprimido con Draco, cifrado como `character.enc` (AES-CBC, clave en el JS).
- Personaje estilizado, sentado en escritorio con laptop. Rig hecho en Blender con nombres Rigify (`spine005`, `spine006`, `thighL`, `f_pinky01L`, `eyebrow_L`...).
- Clips en el GLB: `introAnimation` (una vez), `key1/key2/key5/key6` (loop), `typing` (filtrado a brazos/manos/piernas), `Blink`, `browup` (hover).
- Interacción: `spine006` rota hacia el mouse con lerp, límite ±30°. Al hacer scroll la cámara se aleja, el personaje rota, la pantalla del laptop se enciende (material emisivo con parpadeo que alimenta una luz puntual). HDR propio + luz direccional con sombras.
- Estética: fondo negro, acento morado/rosa, fuentes ClashDisplay y Geist.

## 3. Identidad del avatar

Fuente: video y foto de referencia en `refs/`.

- Rasgos: barba completa cerrada unida al bigote, cejas gruesas y rectas, pelo corto rizado oscuro, piel tono medio, ojos marrones.
- **Obligatorio:** dos candongas (aros) en cada oreja.
- Gorra flexfit negra de visera curva, puesta normal (nunca al revés).
- Ropa: hoodie negro ancho con capucha caída, pantalón negro ancho, sneakers blancas con detalle naranja. Audífonos over-ear colgados en el cuello. Variante opcional: hoodie camo de peluche (ver `refs/style/`).
- Gesto característico: cabeceo rap con ojos cerrados y sonrisa leve, disfrutando la música.
- Contexto: desarrollador web en Medellín (Campo Valdés), gamer, moto Suzuki DR150 blanca y azul con baúl negro.

## 4. Sección 1 — El personaje (malla)

- Estilo cartoon tipo moncy: cabeza ~1/4 de la altura, cuerpo compacto, manos algo grandes. Altura de referencia 1.75 m.
- Generado en pose A de pie, boca cerrada, expresión neutra. Se sienta en Blender con el rig.
- Malla ~30k triángulos, topología quad, texturas PBR 2k. Sin geometría oculta dentro del hoodie.
- Sin textos ni logos en la ropa.
- Candongas modeladas como toros metálicos aparte (no dependen de la textura IA).

## 5. Sección 2 — Rig y cara

- Esqueleto humanoide generado por Meshy junto con la malla (pesos ya ajustados a la geometría), renombrado en Blender a la convención de moncy/Rigify. Se descartó encajar un metarig a mano porque es el paso más frágil sobre una malla IA. Nombres de huesos compatibles con moncy: `spine005`/`spine006` (cuello/cabeza), `upper_armL/R`, `forearmL/R`, `handL/R`, dedos `f_index01L`... `thumb01L`..., `thighL/R`, `shinL/R`, `footL/R`. Solo se exportan huesos de deformación.
- Hueso de cabeza libre de las animaciones base para que el código web lo rote hacia el cursor.
- Ojos: se conservan los ojos pintados en la textura de Meshy (sin mirada independiente; la mirada la da la cabeza siguiendo el cursor). Párpados: casquetes de geometría separada con huesos `eyelidL`, `eyelidR` (rotación = cerrar).
- Cejas: piezas separadas con huesos `eyebrow_L`, `eyebrow_R`.
- Boca: sin shape keys (la malla IA no tiene topología facial editable). El gesto `vibe` se expresa con ojos cerrados, cabeceo y hombros.
- Pesos: los de Meshy. Corrección por script solo si el render sentado muestra artefactos en cuello u hombros.
- Gorra, candongas y audífonos pegados al hueso de cabeza/cuello sin deformación.

## 6. Sección 3 — Animaciones (clips en el GLB)

| Clip | Contenido | Modo |
|---|---|---|
| `introAnimation` | Entra, se acomoda, empieza a teclear (~3 s) | Una vez al cargar |
| `typing` | Dedos y antebrazos tecleando, leve balanceo de hombros. Solo brazos y manos | Loop |
| `idle` | Respiración y micro-movimientos de torso, se mezcla con `typing` | Loop |
| `Blink` | Parpadeo cada 3-5 s con variación | Loop |
| `browup` | Levanta cejas, abre un poco los ojos | Hover, una vez |
| `vibe` | Deja de teclear, cierra ojos, cabecea ~4 s a ~90 BPM con hombros, retoma teclear | Cada 20-40 s o al clic |
| `lookAround` | Mira los monitores de lado a lado | Ocasional |

Reglas de mezcla: `typing` + `idle` siempre activas; `vibe` funde `typing` a 0 en 0.5 s y lo retoma al final; `Blink` se apaga durante `vibe`. Solo `vibe` y `lookAround` tocan el hueso de la cabeza.

## 7. Sección 4 — Escena

- Escritorio ancho oscuro mate. Silla gamer sencilla vista de espaldas.
- Mac laptop al centro + 3 monitores detrás (central más grande). Texturas emisivas: código real del usuario (izq.), logo del usuario (centro), logos de Shopify/Supabase/Cloudflare (der.). Se encienden con fundido al cargar. Placeholders si el usuario no entrega código/logo: código plausible y logo con iniciales.
- Dos barras RGB verticales detrás de los monitores, emisivas azul/blanco. El ciclo de color es responsabilidad del código web, no del GLB.
- Objetos: control de consola, taza/vaso negro, mini Suzuki DR150 blanca/azul con baúl negro en repisa flotante a la izquierda.
- Ventana: plano grande con imagen generada de Medellín de noche, Puente de la 4 Sur con pilares de colores. Dos capas con paralaje suave.
- Iluminación: pantallas y barras RGB como luz principal, luz clave fría frontal, HDR nocturno de baja resolución para reflejos.
- Paleta: negro, blanco, azul de la moto como acento, naranja de los sneakers como único cálido. Sin el morado de moncy.

## 8. Sección 5 — Entrega, verificación y presupuesto

Estructura de carpeta:

```
Me on 3D/
  refs/                     referencias (face/, style/)
  generated/                láminas, texturas y mallas crudas de Higgsfield
  blender/avatar.blend      archivo maestro
  blender/scripts/          scripts Python que construyen rig, animaciones y escena
  export/avatar.glb         entregable final (Draco)
  export/avatar_uncompressed.glb
  export/preview.html       visor three.js mínimo con botones por animación y seguimiento de cursor
  docs/superpowers/specs/   este documento
```

Límites: GLB final < 10 MB; personaje < 40k tris; escena completa < 80k tris; texturas 2k personaje, 1k resto.

Verificación: render desde Blender (headless) mostrado al usuario en cada punto de aprobación: lámina del personaje → malla 3D cruda → personaje rigueado y sentado → animaciones → escena completa → GLB en el visor.

Orden de trabajo: escena y rig primero con personaje placeholder; la lámina se genera con las referencias actuales y se regenera si las fotos definitivas cambian algo.

Créditos Higgsfield: estimado 40-80 de 186 disponibles. Consultar costo (`get_cost`) antes de cada generación. No superar 100 sin avisar al usuario.

## 9. Pipeline técnico (opción 1 aprobada)

1. Higgsfield `generate_image` con referencias del rostro → lámina de personaje estilizado (frente, lado, espalda, pose A).
2. Higgsfield `generate_3d` modelo `multi_image_to_3d` (Meshy): quad, pose A, texturizado, PBR, ~30k tris, con `enable_rigging` (altura 1.75 m).
3. Mini DR150: `generate_3d` desde la foto de la moto (o `sam_3_3d`), decimada.
4. Imagen de Medellín de noche: `generate_image`.
5. Blender 5.2 headless por script: importar, renombrar huesos, párpados/cejas/candongas con huesos, sentar, animaciones en pistas NLA, escena, materiales, export GLB Draco.
6. Visor `preview.html` con three.js desde CDN para validar clips y look-at.

Riesgo principal: deformación pobre de la malla IA en articulaciones. Mitigación: pose sentada, remesh quad, pesos de Meshy calculados sobre la propia malla. Fallback: generar el personaje ya sentado y riggear solo tronco, brazos y cabeza.

## 10. Fuera de alcance

- La página web final (hero, scroll, cursor). Solo el visor de prueba.
- Habla, visemas, clonación de voz.
- Guitarra, mascota, plantas.

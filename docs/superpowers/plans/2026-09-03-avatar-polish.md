# Avatar 3D — pulido de calidad, escena, animaciones y visor (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `export/avatar.glb` + `export/preview.html` se vean al nivel de moncy.dev: personaje sin motas cafés y con sombreado real, habitación con paredes e iluminación con sombras, repisa creíble, ventana nítida, typing convincente, cabeza que mira al cursor, y un `vibe` en el que el personaje se pone los audífonos con las manos antes de cabecear.

**Architecture:** Todo sigue siendo pipeline por script en Blender headless (`tools/run_blender.sh`) + un visor three.js estático. Se añaden tres scripts nuevos al pipeline del personaje (`fix_character_material.py`, `hide_neck_headphones.py`, `add_headphones.py`), se modifican `build_scene.py`, `animate.py`, `assemble.py`, `export_glb.py`, los checks, `poses.py` y `export/preview.html`, y se añade una sonda headless del visor (`tools/preview_probe.mjs`). Regeneración completa al final.

**Tech Stack:** Blender 4.x/5.x (`/Applications/Blender.app`), Python 3 + numpy (dentro de Blender), Pillow (fuera), three.js 0.170 (importmap jsdelivr), Google Chrome headless + CDP (Node 22+, `WebSocket` y `fetch` nativos).

**Spec:** No hay spec aparte: el diseño aprobado por el usuario es la sección "Diseño aprobado" de este documento (conversación 2026-09-03). Contexto del proyecto: `docs/HANDOFF.md`, `README.md`, `docs/superpowers/specs/2026-09-03-avatar-3d-design.md`.

## Global Constraints

- Idioma de comentarios, prints y docs: español (sin tildes en los scripts de Blender es aceptable, como los existentes).
- NO gastar créditos de Higgsfield/Meshy. Balance 54.8; no se regenera ningún insumo.
- Presupuesto GLB: `avatar.glb` < 10 MB (hoy 1.94 MB), < 80 000 tris (hoy 48 390). Texturas ≤ 2048.
- Convención de ejes en Blender: personaje mira a +Y, su izquierda en −X, pies en z=0 (character.blend: de pie, rest pose A). En glTF/three.js: Y arriba, personaje mira a −Z; Blender (x, y, z) → glTF (x, z, −y).
- Los clips existentes siguen llamándose igual: `introAnimation`, `typing`, `idle`, `Blink`, `browup`, `vibe`, `lookAround`. Solo cambian la duración de `vibe` (120 → 216 frames) y los huesos que anima.
- Orden del pipeline (README "Regenerar todo") pasa a ser:
  `build_scene.py` → `import_character.py` → `apply_chest_logo.py` → **`fix_character_material.py`** → `render_face_grid.py` → `add_face_parts.py` → **`hide_neck_headphones.py`** → **`add_headphones.py`** → `checks/check_rig.py` → `checks/check_face_export.py` → `animate.py` → `checks/check_anim.py` → `render_hdr.py` → `assemble.py` → `export_glb.py`.
- Scripts que modifican `character.blend` en sitio deben ser idempotentes (patrón `cleanup()` de `add_face_parts.py`, o bandera en propiedad custom).
- Cada tarea termina con render/captura de verificación en `generated/renders/` y commit en la rama `avatar-3d`.
- Commits terminan con:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01XqaUJELRbH78XMbnZw3JoQ
  ```

---

## Diseño aprobado (resumen para el implementador)

Diagnóstico verificado en la sesión:

1. **Motas cafés / calidad plana del personaje.** `generated/meshy/character_rigged.glb` trae el material con `Metallic=1.0`, `Roughness=1.0`, `Emission Strength=1.0` con la textura base enchufada en Emission Color y `Specular IOR Level` que exporta `specularColorFactor 2.0`. El GLB final hereda eso (`Character`: sin `metallicFactor` → glTF asume 1.0). three.js lo pinta como metal rugoso que refleja el HDR y no responde a luces. Además la textura de Meshy es un atlas de miles de islas con relleno color piel en los canales (sin alfa: `generated/character_texture_logo.png` es RGBA con alfa=255 en todo), y ese relleno sangra en bordes con mipmaps/JPEG → puntitos color piel/café sobre el hoodie.
2. **Seguimiento de cursor.** Funciona en Chrome (probado con CDP: spine006 gira ≈ ±24°). Es tímido: rango ±30°/±15°, lineal con la posición del mouse, sin acompañamiento del pecho. Se rehace como "mirar al punto del cursor".
3. **Habitación oscura.** `build_scene.py` no crea paredes ni techo: solo `floor`, ventana y muebles. Sombras apagadas en el visor.
4. **Repisa.** `shelf` es una tabla flotando en (−1.25, −0.6, 1.49), sin pared detrás ni soportes; la moto mide 0.25 m.
5. **Ventana borrosa.** `export_glb.py` reescala `medellin` (1504×846) a 1024 de ancho (`OTHER_TEX`).
6. **Typing "masajes".** Sin dedos; el clip actual mueve las manos enteras arriba/abajo con seno puro, amplitud 0.30, a contratiempo perfecto.
7. **Audífonos.** Están fundidos en la malla `Body` alrededor del cuello (copas a los lados del cuello, z≈1.34–1.42, |x|≈0.10–0.17, y≈0.0–0.12 en character.blend). No existe pieza aparte.

Decisiones:

- Material del personaje: Metallic 0, Roughness 0.85, Emission Strength 0 y Emission Color desconectado, Specular IOR Level 0.5. Textura: máscara de islas rasterizada desde las UV de `Body`, dilatado de color de isla sobre los canales (16 px) y suavizado (mediana 3×3, dos pasadas) SOLO en píxeles oscuros (luminancia < 0.25) para no emborronar la cara. Se guarda `generated/character_texture_clean.png` y el material apunta a ella. Calidad JPEG del personaje sube a 92 en la exportación.
- Escena: paredes traseras alrededor de la ventana (4 cajas), paredes laterales, techo, material `Wall` mate azul-gris. La ventana se desplaza a x∈[−1.9, 1.3] y la repisa va sobre la pared trasera derecha (x=+2.0), con dos soportes en L; moto a 0.32 m. `medellin` se exporta sin reescalar (≤ 2048).
- Visor: sombras PCFSoft, spot principal con sombra, luz rectangular azulada desde la ventana, 4 luces puntuales de pantalla ligadas al fundido, 2 luces puntuales con el color de las barras RGB, hemisférica; cabeza mira al punto 3D del cursor (yaw ±45°, pitch −20°..+25°) y `spine003` acompaña el 30 % del yaw; el nodo `headphones` cancela el giro del cursor (los audífonos del cuello no deben girar con la cabeza).
- Typing v2: golpes irregulares por mano (6 por ciclo de 48 frames), manos bajas (hover 0.35 de la carrera anterior), bajada rápida de 2 frames, deriva lateral lenta.
- Audífonos: (a) `hide_neck_headphones.py` encoge hacia el eje del cuello los vértices de las copas fundidas (región calibrada por constantes + render de aprobación); (b) `add_headphones.py` crea la pieza (arco elíptico + 2 copas), material `Headphones`, hueso `headphones` HIJO de `spine006` con cabeza en la cabeza de `spine006` (así el nodo glTF hijo tiene traslación 0 y el visor puede cancelar el giro del cursor sin desplazamiento), pieza parentada al hueso en su posición de REPOSO = colgando del cuello; estado "puestos" = rotación (−80°, 0, 0) + traslación local calculada; (c) `vibe` v2 de 216 frames: manos suben a las copas, llevan los audífonos a la cabeza, vuelven al teclado, cabeceo con ojos cerrados, manos suben, bajan los audífonos al cuello, vuelven al teclado. IK analítica de dos huesos para colocar las muñecas.
- Si (a) no queda limpio tras 3 calibraciones (render con artefactos visibles: agujeros o picos), el implementador lo reporta y DEJA el script sin aplicar (bandera `--dry-run`), y `vibe` se hace igual: el reporte lo decide el usuario.
- Portafolio: fuera de este plan (falta el repo del usuario).

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `blender/scripts/fix_character_material.py` | Corrige el material `Character` y limpia la textura (máscara UV, dilatado, mediana en oscuros); guarda `generated/character_texture_clean.png` y `character.blend` | Crear |
| `blender/scripts/checks/check_character_material.py` | Verifica material y textura en `character.blend` | Crear |
| `blender/scripts/build_scene.py` | Habitación (paredes, techo), ventana desplazada, repisa con soportes | Modificar |
| `blender/scripts/checks/check_scene.py` | Exige los objetos nuevos | Modificar |
| `blender/scripts/assemble.py` | `MOTO_LENGTH = 0.32` | Modificar |
| `blender/scripts/export_glb.py` | Límites de textura por imagen (`medellin` 2048), JPEG 92 para el personaje, checks del material `Character` y del nodo `headphones` | Modificar |
| `blender/scripts/hide_neck_headphones.py` | Encoge las copas fundidas hacia el cuello; idempotente por propiedad custom `Body['neck_headphones_hidden']` | Crear |
| `blender/scripts/add_headphones.py` | Pieza de audífonos + hueso `headphones`; escribe `blender/headphones.json` (offsets de las copas en espacio del hueso y estado ON_HEAD) | Crear |
| `blender/scripts/poses.py` | `apply()` acepta `loc` para huesos con traslación; constante `HEADPHONES_ON` | Modificar |
| `blender/scripts/animate.py` | `typing` v2, `vibe` v2 (216 frames) con `reach()` IK | Modificar |
| `blender/scripts/checks/check_anim.py` | `vibe` 216 frames; `vibe` puede tocar brazos y `headphones` | Modificar |
| `export/preview.html` | Luces/sombras, mirar al cursor, pecho, cancelación en `headphones` | Modificar |
| `tools/preview_probe.mjs` | Sonda CDP: carga el visor, mueve el mouse, dispara vibe, captura PNGs, imprime errores | Crear |
| `tools/serve_preview.sh` | sin cambios | — |
| `README.md`, `docs/HANDOFF.md` | Pipeline nuevo, clips, nodos, estado | Modificar |

Dependencias entre tareas: 1 → 4 → 5 → 6 (personaje); 2 y 3 son independientes de 1/4/5 pero 7 (regeneración) las necesita todas; 6 (visor) puede empezar en paralelo con 2–5 porque solo toca `preview.html` y `tools/`, pero su ajuste fino de luces se hace en la tarea 7 con el GLB nuevo.

---

### Task 1: Material y textura del personaje (`fix_character_material.py`)

**Files:**
- Create: `blender/scripts/fix_character_material.py`
- Create: `blender/scripts/checks/check_character_material.py`
- Modify: `blender/scripts/export_glb.py` (líneas 60–66 `OTHER_TEX`/`LADDER`; sección 6 verificación)

**Interfaces:**
- Consumes: `blender/character.blend` con material `Character` (nodos `Image Texture.001` → Base Color, `Image Texture` → Emission Color, ambos con la imagen `character_texture_logo`), objeto `Body`.
- Produces: `generated/character_texture_clean.png` (2048×2048 RGB), material `Character` con Metallic 0 / Roughness 0.85 / Emission Strength 0 / sin enlace a Emission Color; `Body['texture_clean'] = True`. `export_glb.py` exporta `Character` con `metallicFactor 0`, `roughnessFactor ≈ 0.85`, sin `emissiveTexture`, sin `KHR_materials_specular`.

- [ ] **Step 1: Escribir el check (falla antes de implementar)**

`blender/scripts/checks/check_character_material.py`:

```python
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
```

- [ ] **Step 2: Correr el check y confirmar que falla**

Run: `tools/run_blender.sh blender/character.blend blender/scripts/checks/check_character_material.py 2>&1 | grep -E 'CHECK|Error|Traceback'`
Expected: `CHECK FAILED: Metallic 1.0 != 0`

- [ ] **Step 3: Medir la fracción de piel ANTES (para el informe)**

```bash
python3 - <<'EOF'
from PIL import Image; import numpy as np
t = np.asarray(Image.open('generated/character_texture_logo.png').convert('RGB')).astype(np.float32) / 255
skin = (t[...,0] > 0.75) & (t[...,1] > 0.45) & (t[...,1] < 0.72) & (t[...,2] < 0.60)
print('skin_frac antes', round(float(skin.mean()), 4))
EOF
```
Expected: un valor claramente > 0.12 (los canales son color piel). Anotarlo en el reporte.

- [ ] **Step 4: Implementar `fix_character_material.py`**

```python
# blender/scripts/fix_character_material.py
# Corrige el material del personaje (Meshy lo exporta como METAL rugoso autoiluminado:
# Metallic 1, Roughness 1, Emission 1 con la textura base, specular x2) y limpia la textura:
#   1. mascara de islas UV rasterizada desde los triangulos de Body (2048x2048);
#   2. dilatado del color de cada isla sobre los canales (PAD px): el relleno color piel de
#      Meshy sangra en los bordes con mipmaps/JPEG y se ve como motas cafes en el hoodie;
#   3. mediana 3x3 (dos pasadas) SOLO en pixeles oscuros (luminancia < DARK): quita el ruido
#      de la ropa negra sin tocar la cara.
# Guarda generated/character_texture_clean.png, apunta el material a ella y guarda character.blend.
# Idempotente: parte SIEMPRE de generated/character_texture_logo.png (salida de apply_chest_logo.py).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/fix_character_material.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
import numpy as np

SRC = os.path.join(common.GEN, 'character_texture_logo.png')
OUT = os.path.join(common.GEN, 'character_texture_clean.png')
SIZE = 2048
PAD = 16          # px de dilatado sobre los canales
DARK = 0.25       # luminancia por debajo de la cual se aplica la mediana
MEDIAN_PASSES = 2
ROUGHNESS = 0.85


def uv_mask(body, size):
    """Mascara booleana (size x size) con True en los texeles cubiertos por triangulos UV."""
    me = body.data
    uv = me.uv_layers.active.data
    mask = np.zeros((size, size), dtype=bool)
    tris = []
    for poly in me.polygons:
        li = list(poly.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append((uv[li[0]].uv, uv[li[k]].uv, uv[li[k + 1]].uv))
    # rasterizado por baricentricas en la caja de cada triangulo (numpy, sin PIL)
    for a, b, c in tris:
        xs = np.array([a.x, b.x, c.x]) * size; ys = (1.0 - np.array([a.y, b.y, c.y])) * size
        x0, x1 = int(max(0, np.floor(xs.min()) - 1)), int(min(size - 1, np.ceil(xs.max()) + 1))
        y0, y1 = int(max(0, np.floor(ys.min()) - 1)), int(min(size - 1, np.ceil(ys.max()) + 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(d) < 1e-9: continue
        w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / d
        w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / d
        w2 = 1.0 - w0 - w1
        eps = -0.002
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside
    return mask


def dilate_colors(rgb, mask, steps):
    """Rellena los pixeles fuera de la mascara con el color del vecino de isla mas cercano
    (iterativo: cada paso copia desde los 8 vecinos ya rellenos)."""
    rgb = rgb.copy(); filled = mask.copy()
    for _ in range(steps):
        new_rgb = rgb.copy(); new_filled = filled.copy()
        acc = np.zeros_like(rgb); cnt = np.zeros(mask.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0: continue
                sh = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                fm = np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
                acc += sh * fm[..., None]; cnt += fm
        take = (~filled) & (cnt > 0)
        new_rgb[take] = acc[take] / cnt[take][:, None]
        new_filled |= take
        rgb, filled = new_rgb, new_filled
    return rgb


def median3(rgb):
    stack = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            stack.append(np.roll(np.roll(rgb, dy, axis=0), dx, axis=1))
    return np.median(np.stack(stack, axis=0), axis=0)


def main():
    common.ensure_dirs()
    if not os.path.exists(SRC):
        common.fail(f'falta {SRC} (ejecutar apply_chest_logo.py antes)')
    body = bpy.data.objects['Body']
    m = bpy.data.materials['Character']
    bsdf = m.node_tree.nodes['Principled BSDF']

    # --- 1. textura de origen (siempre la de apply_chest_logo.py)
    src = bpy.data.images.load(SRC, check_existing=True)
    src.reload()
    w, h = src.size
    px = np.empty(w * h * 4, dtype=np.float32); src.pixels.foreach_get(px)
    img = px.reshape(h, w, 4)[::-1, :, :3]          # bpy guarda de abajo a arriba; se voltea a "arriba primero"
    if (w, h) != (SIZE, SIZE):
        common.fail(f'textura de origen {w}x{h}, esperada {SIZE}x{SIZE}')

    # --- 2. mascara UV y dilatado
    mask = uv_mask(body, SIZE)
    print('TEXCLEAN mascara islas', round(float(mask.mean()), 4), 'de la textura')
    if not (0.15 < mask.mean() < 0.95):
        common.fail('la mascara UV cubre una fraccion improbable de la textura')
    rgb = dilate_colors(img, mask, PAD)
    # lo que queda sin rellenar (canales anchos) toma el color medio de la ropa (oscuro) en vez de piel
    filled = mask.copy()
    for _ in range(PAD):
        filled |= np.roll(filled, 1, 0) | np.roll(filled, -1, 0) | np.roll(filled, 1, 1) | np.roll(filled, -1, 1)
    dark_mean = np.median(img[mask & (img.mean(axis=2) < DARK)], axis=0)
    rgb[~filled] = dark_mean
    print('TEXCLEAN color de relleno lejano', [round(float(c), 3) for c in dark_mean])

    # --- 3. mediana en oscuros (solo dentro de islas)
    lum = rgb.mean(axis=2)
    dark = mask & (lum < DARK)
    for _ in range(MEDIAN_PASSES):
        med = median3(rgb)
        rgb[dark] = med[dark]
    print('TEXCLEAN pixeles suavizados', int(dark.sum()))

    # --- 4. guardar PNG y apuntar el material
    out = bpy.data.images.get('character_texture_clean') or bpy.data.images.new('character_texture_clean', SIZE, SIZE, alpha=False)
    out.scale(SIZE, SIZE)
    buf = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    buf[..., :3] = np.clip(rgb[::-1], 0, 1)
    out.pixels.foreach_set(buf.ravel())
    out.filepath_raw = OUT; out.file_format = 'PNG'
    out.save(); out.reload()
    print('TEXCLEAN guardada', OUT)
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None and n.image.name.startswith('character_texture'):
            n.image = out

    # --- 5. material
    for l in list(m.node_tree.links):
        if l.to_node == bsdf and l.to_socket.name == 'Emission Color':
            m.node_tree.links.remove(l)
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Roughness'].default_value = ROUGHNESS
    bsdf.inputs['Emission Strength'].default_value = 0.0
    bsdf.inputs['Emission Color'].default_value = (0, 0, 0, 1)
    bsdf.inputs['Specular IOR Level'].default_value = 0.5
    body['texture_clean'] = True
    print('MATERIAL Character metallic 0 roughness', ROUGHNESS, 'emission 0')

    # --- 6. render de aprobacion (misma camara que apply_chest_logo: torso de frente)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.add_camera((0.0, 1.6, 1.25), (0.0, 0.0, 1.25), lens=70)
    common.add_light('k', 'AREA', (-1.0, 1.5, 2.0), 250, (0.85, 0.9, 1.0), size=1.2)
    common.add_light('f', 'AREA', (1.2, 1.2, 1.0), 80, (1.0, 0.95, 0.9), size=1.5)
    common.render(os.path.join(common.RENDERS, 'material_fix.png'), res=(900, 900), samples=48)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Ejecutar y verificar**

Run:
```bash
tools/run_blender.sh blender/character.blend blender/scripts/fix_character_material.py 2>&1 | grep -E 'TEXCLEAN|MATERIAL|RENDER|SAVED|Error|Traceback'
tools/run_blender.sh blender/character.blend blender/scripts/checks/check_character_material.py 2>&1 | grep -E 'CHECK|Error|Traceback'
```
Expected: `TEXCLEAN mascara islas` entre 0.15 y 0.95, `CHECK_CHARACTER_MATERIAL OK`, y `generated/renders/material_fix.png` muestra el hoodie negro mate sin motas claras (comparar con `generated/renders/chest_logo.png`). Mirar también `generated/character_texture_clean.png` reducido: los canales entre islas deben ser oscuros, no rosados. Si la máscara sale < 0.15, el UV activo no es el de la textura: imprimir `me.uv_layers.keys()` y usar la capa que usa el nodo (normalmente la única).

- [ ] **Step 6: `export_glb.py`: límites por imagen, JPEG 92 para el personaje y checks del material**

Reemplazar `OTHER_TEX = 1024` y `LADDER` por:

```python
OTHER_TEX = 1024
TEX_LIMITS = {'medellin': 2048}      # la ventana se ve enorme en pantalla: no reescalar (1504x846)
CHAR_QUALITY = 92                    # el atlas del personaje tiene miles de bordes: JPEG alto
# escalera de calidad (formato de imagen, calidad JPEG del resto, lado maximo de la textura del personaje)
LADDER = [
    dict(fmt='AUTO', quality=85, char=2048),
    dict(fmt='JPEG', quality=85, char=2048),
    dict(fmt='JPEG', quality=70, char=2048),
    dict(fmt='JPEG', quality=70, char=1536),
]
```

En `limit_textures`, cambiar `limit = char_limit if img in char_imgs else OTHER_TEX` por
`limit = char_limit if img in char_imgs else TEX_LIMITS.get(img.name, OTHER_TEX)`.

El exportador glTF de Blender no permite calidad JPEG por imagen; se aplica la calidad del personaje a todo el archivo cuando cabe: en `do_export`, usar `quality = max(step['quality'], CHAR_QUALITY) if step is LADDER[0] else step['quality']` y pasarlo en `export_jpeg_quality` y `export_image_quality`. (El primer intento exporta todo a 92; si supera el presupuesto, la escalera baja como antes.)

En la sección 6 (verificación), después del bucle de pantallas, añadir:

```python
ch = mats.get('Character', {})
pbr = ch.get('pbrMetallicRoughness', {})
check(pbr.get('metallicFactor', 1.0) == 0, f"Character metallicFactor={pbr.get('metallicFactor', 'ausente=1.0')}")
check(0.7 <= pbr.get('roughnessFactor', 1.0) <= 0.95, f"Character roughnessFactor={pbr.get('roughnessFactor', 'ausente=1.0')}")
check('emissiveTexture' not in ch, 'Character sin emissiveTexture')
check('KHR_materials_specular' not in ch.get('extensions', {}), 'Character sin KHR_materials_specular')
win = next((w for n, _, w, h, _ in imgs if n == 'medellin'), None)
check(win == 1504, f'medellin exportada a {win} de ancho (esperado 1504, sin reescalar)')
```

- [ ] **Step 7: Commit**

```bash
git add blender/scripts/fix_character_material.py blender/scripts/checks/check_character_material.py blender/scripts/export_glb.py
git commit -m "feat: material del personaje sin metal/emision y textura limpia (mascara UV, dilatado, mediana en oscuros)"
```

(La exportación completa se verifica en la Tarea 7; aquí no se corre `export_glb.py` porque `avatar.blend` todavía no incluye el material nuevo.)

---

### Task 2: Habitación, ventana desplazada, repisa con soportes

**Files:**
- Modify: `blender/scripts/build_scene.py` (bloques "piso y escritorio", "repisa", "ventana")
- Modify: `blender/scripts/checks/check_scene.py`
- Modify: `blender/scripts/assemble.py:15` (`MOTO_LENGTH`)

**Interfaces:**
- Produces: objetos nuevos en `scene.blend`: `wall_back_L`, `wall_back_R`, `wall_back_top`, `wall_back_bottom`, `wall_left`, `wall_right`, `ceiling`, `shelf_bracket_0`, `shelf_bracket_1`, `shelf_arm_0`, `shelf_arm_1`; material `Wall`. Renombra `window_post_-2`/`window_post_2` → `window_post_L`/`window_post_R`. `moto_anchor` en (2.0, −1.52, 1.465). `shelf` en (2.0, −1.52, 1.45).
- Consumes: nada nuevo.

- [ ] **Step 1: Actualizar `check_scene.py` (falla antes de implementar)**

Reemplazar la lista `need` por:

```python
need = ['desk', 'chair_seat', 'laptop_base', 'screen_laptop', 'monitor_L', 'monitor_C', 'monitor_R',
        'screen_left', 'screen_center', 'screen_right', 'rgb_bar_L', 'rgb_bar_R', 'shelf',
        'shelf_bracket_0', 'shelf_bracket_1', 'shelf_arm_0', 'shelf_arm_1', 'mug',
        'controller', 'window_far', 'window_near', 'window_post_L', 'window_post_R',
        'wall_back_L', 'wall_back_R', 'wall_back_top', 'wall_back_bottom', 'wall_left', 'wall_right',
        'ceiling', 'floor', 'seat_anchor', 'moto_anchor']
```

Y después del bucle de materiales añadir:

```python
if 'Wall' not in bpy.data.materials: common.fail('falta material Wall')
sh = bpy.data.objects['shelf']; an = bpy.data.objects['moto_anchor']
if abs(an.location.z - (sh.location.z + 0.015)) > 1e-3: common.fail('moto_anchor no apoya sobre la repisa')
wl = bpy.data.objects['wall_back_R']
if not (wl.location.y < sh.location.y < wl.location.y + 0.3): common.fail('la repisa no esta contra la pared trasera')
```

Run: `tools/run_blender.sh blender/scene.blend blender/scripts/checks/check_scene.py 2>&1 | grep -E 'CHECK|Error'`
Expected: `CHECK FAILED: faltan objetos [...]`

- [ ] **Step 2: Implementar en `build_scene.py`**

Añadir tras `m_floor`:

```python
m_wall = mat('Wall', (0.10, 0.11, 0.14, 1), roughness=0.92)
```

Reemplazar el bloque `# --- repisa flotante ...` por:

```python
# --- habitacion: paredes y techo (antes no existian y el visor quedaba negro)
ROOM_X, ROOM_Y_BACK, ROOM_H = 2.8, -1.7, 2.8          # medias anchuras / pared trasera / altura
WIN_X0, WIN_X1, WIN_Z0, WIN_Z1 = -1.9, 1.3, 0.6, 2.4  # hueco de la ventana (3.2 x 1.8 = 16:9)
WALL_T = 0.10
yb = ROOM_Y_BACK - WALL_T / 2                          # centro de las cajas de la pared trasera
box('wall_back_L', (WIN_X0 + ROOM_X, WALL_T, ROOM_H), ((WIN_X0 - ROOM_X) / 2, yb, ROOM_H / 2), m_wall, col)
box('wall_back_R', (ROOM_X - WIN_X1, WALL_T, ROOM_H), ((WIN_X1 + ROOM_X) / 2, yb, ROOM_H / 2), m_wall, col)
box('wall_back_top', (WIN_X1 - WIN_X0, WALL_T, ROOM_H - WIN_Z1), ((WIN_X0 + WIN_X1) / 2, yb, (WIN_Z1 + ROOM_H) / 2), m_wall, col)
box('wall_back_bottom', (WIN_X1 - WIN_X0, WALL_T, WIN_Z0), ((WIN_X0 + WIN_X1) / 2, yb, WIN_Z0 / 2), m_wall, col)
box('wall_left', (WALL_T, 8.0, ROOM_H), (-ROOM_X - WALL_T / 2, 1.0, ROOM_H / 2), m_wall, col)
box('wall_right', (WALL_T, 8.0, ROOM_H), (ROOM_X + WALL_T / 2, 1.0, ROOM_H / 2), m_wall, col)
box('ceiling', (2 * ROOM_X + 2 * WALL_T, 8.0, WALL_T), (0, 1.0, ROOM_H + WALL_T / 2), m_wall, col)

# --- repisa con soportes en L sobre la pared trasera derecha (+X = izquierda de la camara)
SHELF_X, SHELF_Z = 2.0, DESK_Z + 0.71
SHELF_D = 0.24
shelf_y = ROOM_Y_BACK + SHELF_D / 2                     # pegada a la cara interior de la pared
box('shelf', (0.55, SHELF_D, 0.03), (SHELF_X, shelf_y, SHELF_Z), m_dark, col)
for i, dx in enumerate((-0.18, 0.18)):
    box(f'shelf_bracket_{i}', (0.025, 0.025, 0.16), (SHELF_X + dx, ROOM_Y_BACK + 0.0125, SHELF_Z - 0.095), m_alu, col)
    box(f'shelf_arm_{i}', (0.025, SHELF_D - 0.02, 0.025), (SHELF_X + dx, shelf_y - 0.01, SHELF_Z - 0.0275), m_alu, col)
bpy.ops.object.empty_add(location=(SHELF_X, shelf_y, SHELF_Z + 0.015)); bpy.context.active_object.name = 'moto_anchor'
```

Reemplazar el bloque de la ventana (desde `plane('window_far', ...)` hasta el bucle de `window_post_`) por:

```python
wcx, wcz = (WIN_X0 + WIN_X1) / 2, (WIN_Z0 + WIN_Z1) / 2
plane('window_far', (WIN_X1 - WIN_X0, WIN_Z1 - WIN_Z0), (wcx, ROOM_Y_BACK - 0.02, wcz),
      rotation=(math.radians(90), 0, math.radians(180)), material=m_far, collection=col)
m_frame = mat('Window_Frame', (0.03, 0.03, 0.035, 1), roughness=0.6)
box('window_near', (WIN_X1 - WIN_X0 + 0.16, 0.08, 0.06), (wcx, ROOM_Y_BACK + 0.04, WIN_Z0 - 0.03), m_frame, col)   # antepecho
for tag, x in (('L', WIN_X0 - 0.04), ('R', WIN_X1 + 0.04)):
    box(f'window_post_{tag}', (0.08, 0.08, WIN_Z1 - WIN_Z0 + 0.12), (x, ROOM_Y_BACK + 0.04, wcz), m_frame, col)
box('window_head', (WIN_X1 - WIN_X0 + 0.16, 0.08, 0.06), (wcx, ROOM_Y_BACK + 0.04, WIN_Z1 + 0.03), m_frame, col)
```

Las barras RGB (`rgb_bar_L/R` en y=−1.3) quedan delante de la pared trasera: no tocarlas.

En `assemble.py` cambiar `MOTO_LENGTH = 0.25` por `MOTO_LENGTH = 0.32`. Verificar que el comentario de la línea "moto 0.25 m" del HANDOFF se actualiza en la Tarea 7.

- [ ] **Step 3: Regenerar la escena y verificar**

Run:
```bash
tools/run_blender.sh - blender/scripts/build_scene.py 2>&1 | grep -E 'SCENE_TRIS|WARNING|RENDER|SAVED|Error|Traceback'
tools/run_blender.sh blender/scene.blend blender/scripts/checks/check_scene.py 2>&1 | grep -E 'CHECK|TEX|Error'
```
Expected: `CHECK_SCENE OK tris= <15000`, sin `WARNING PLACEHOLDER`. Abrir `generated/renders/scene_v1.png`: paredes visibles alrededor de la ventana, repisa con soportes a la izquierda del encuadre, sin agujeros entre pared y ventana. Si la repisa queda fuera del encuadre, bajar `SHELF_X` a 1.8 (nunca dentro del hueco de la ventana: `SHELF_X - 0.275 > WIN_X1`).

- [ ] **Step 4: Commit**

```bash
git add blender/scripts/build_scene.py blender/scripts/checks/check_scene.py blender/scripts/assemble.py
git commit -m "feat: habitacion con paredes y techo, ventana desplazada, repisa con soportes y moto de 0.32 m"
```

---

### Task 3: Typing v2

**Files:**
- Modify: `blender/scripts/animate.py` (bloque `# --- 1) typing`)

**Interfaces:**
- Produces: acción `typing` de 48 frames (sin cambio de interfaz).

- [ ] **Step 1: Reemplazar el bloque de `typing`**

```python
# --------------------------------------------------------------------------- 1) typing
# 48 frames en bucle. Sin dedos: cada mano "golpea" 6 veces por ciclo en instantes irregulares
# (no a contratiempo perfecto) con una bajada rapida de 2 frames desde un hover bajo; entre
# golpes las manos apenas flotan (HOVER) y derivan lateralmente despacio como si buscaran
# teclas. La carrera maxima (0.18) es menor que la version 1 (0.30), que parecia dar masajes.
# `up` = 0 es la pose SIT (palma sobre el laptop); 1 = mano arriba.
STRIKES = {'L': (3, 11, 17, 27, 35, 43), 'R': (7, 13, 21, 31, 39, 45)}
HOVER, STROKE, DIP_FRAMES = 0.35, 0.18, 2.0


def typing_up(side, f):
    """0..1: hover entre golpes, cae a 0 en el frame del golpe (ventana triangular de 2 frames)."""
    fc = ((f - 1) % 48) + 1
    best = min(min(abs(fc - s), 48 - abs(fc - s)) for s in STRIKES[side])
    dip = max(0.0, 1.0 - best / DIP_FRAMES)
    return HOVER * (1.0 - dip)


act = new_action('typing', ARM_BONES)
for f in range(1, 50, 2):                       # 1..49; el 49 repite el 1 (bucle limpio)
    t = (f - 1) / 48.0 * 2 * math.pi
    drift = 0.02 * math.sin(t)                  # deriva lateral lenta (m, en la direccion de la mano)
    up = lambda s: typing_up(s, f)
    key_pose(f, solve_arms(
        upper=lambda s: (-SX[s] * 0.06 + drift * 0.3, 0.0 + 0.012 * up(s), -0.998),
        fore=lambda s: (SX[s] * 0.13 + drift, 0.99, 0.02 + 0.05 * up(s)),
        hand=lambda s: (SX[s] * 0.05 + drift, 0.995, STROKE * up(s)),
    ))
finish(act, 48, cyclic=True)
```

- [ ] **Step 2: Regenerar animaciones, check y tira**

Run:
```bash
tools/run_blender.sh blender/character.blend blender/scripts/animate.py 2>&1 | grep -E 'CLIP|SIT_ARMS|ACTIONS|Error|Traceback'
tools/run_blender.sh blender/character_anim.blend blender/scripts/checks/check_anim.py 2>&1 | grep -E 'CHECK|CLIP|Error'
tools/run_blender.sh blender/character_anim.blend blender/scripts/anim_strip.py -- typing 2>&1 | grep -E 'STRIP|RENDER|Error'
```
Expected: `CHECK_ANIM OK` (la Tarea 3 puede correr antes que la 5; `check_anim.py` todavía espera `vibe` 120, y sigue pasando porque `vibe` no cambia aquí). Mirar `generated/renders/strip_typing.png` (ver `anim_strip.py` para los argumentos exactos: acepta el nombre del clip y los frames): las manos deben quedar bajas, con caídas puntuales distintas por mano. Si la muñeca atraviesa el tablero, subir `HOVER` a 0.45 (el hallazgo de la Tarea 11 original: la carrera simétrica metía las yemas 3.4 cm en el escritorio; aquí la carrera nunca baja de `up=0` = SIT, así que no debería).

- [ ] **Step 3: Commit**

```bash
git add blender/scripts/animate.py
git commit -m "feat: typing v2 con golpes irregulares, hover bajo y deriva lateral"
```

---

### Task 4: Audífonos como pieza aparte (ocultar los fundidos + crear la pieza y su hueso)

**Files:**
- Create: `blender/scripts/hide_neck_headphones.py`
- Create: `blender/scripts/add_headphones.py`
- Create (generado, versionado): `blender/headphones.json`
- Modify: `blender/scripts/poses.py` (`apply()` con traslación; `HEADPHONES_ON`)
- Modify: `blender/scripts/checks/check_rig.py` (exigir el hueso `headphones` y los objetos `headphones_band`, `headphones_cup_L`, `headphones_cup_R`)
- Modify: `blender/scripts/checks/check_face_export.py` (si enumera los objetos parentados a hueso: añadir los tres nuevos; leerlo antes)

**Interfaces:**
- Consumes: `character.blend` tras `add_face_parts.py` (huesos `spine005`, `spine006`, `Body`, `blender/landmarks.json` con `ear_L/R`).
- Produces:
  - Hueso `headphones`: hijo de `spine006`, `head` = `spine006.head` (armature space), `tail = head + (0, 0, 0.05)`, `roll 0`, `use_deform True`. Con esta orientación: X local = +X mundo, Y local = +Z mundo, Z local = −Y mundo. Una traslación mundo (dx, dy, dz) en local es `(dx, dz, -dy)`.
  - Objetos `headphones_band`, `headphones_cup_L`, `headphones_cup_R` (material `Headphones`, negro mate con un detalle gris) parentados al hueso (`parent_to_bone` como en `add_face_parts.py`), modelados en su posición de REPOSO = colgando del cuello.
  - `blender/headphones.json`:
    ```json
    {"on_head": {"rotation_deg": [-80, 0, 0], "location": [0.0, 0.147, 0.05]},
     "cup_offset_rest": {"L": [-0.13, -0.06, 0.02], "R": [0.13, -0.06, 0.02]},
     "cup_offset_head": {"L": [-0.118, 0.02, 0.03], "R": [0.118, 0.02, 0.03]}}
    ```
    (`location` y offsets en ESPACIO LOCAL DEL HUESO; los valores exactos los escribe el script midiendo la geometría; los de arriba son el orden de magnitud esperado). `poses.HEADPHONES_ON = (rotation_euler_rad, location)` se lee de ahí.
  - `poses.apply(arm, pose, frame=None, loc=None)`: `loc` = `{hueso: (x, y, z)}` que se asigna a `pb.location` (y keyframea si `frame`).

- [ ] **Step 1: Probe de la región de las copas fundidas (sin guardar)**

Escribir y correr `blender/scripts/hide_neck_headphones.py` primero en modo `--probe`: renderiza dos primeros planos del cuello (frente y lado) con la región candidata pintada de rojo (asignando un segundo material temporal a las caras cuyos vértices caen dentro), a `generated/renders/headphones_probe_front.png` / `_side.png`. No guarda el .blend.

```python
# blender/scripts/hide_neck_headphones.py
# Los audifonos que Meshy modelo alrededor del cuello estan FUNDIDOS en Body. Para que la
# pieza nueva (add_headphones.py) pueda subir a la cabeza sin dejar un duplicado en el cuello,
# este script encoge radialmente hacia el eje del cuello los vertices de las copas fundidas
# (quedan escondidos dentro del cuello/hoodie). Region en coordenadas de mundo de character.blend
# (de pie, mira a +Y): copas a los lados del cuello. Se calibra con `--probe` (pinta la region
# de rojo en dos renders, no guarda) y se aplica sin argumentos (guarda character.blend).
# Idempotente: si Body['neck_headphones_hidden'] ya esta puesto, no hace nada.
# `--dry-run`: hace todo menos guardar (para comparar renders).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/hide_neck_headphones.py [-- --probe|--dry-run]
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector

# Region (mundo): |x| en X_RANGE, y en Y_RANGE, z en Z_RANGE, y ademas radio XY al eje del
# cuello > R_MIN (para no tocar el cuello ni el collar interior).
X_RANGE = (0.085, 0.185)
Y_RANGE = (-0.06, 0.13)
Z_RANGE = (1.31, 1.445)
R_MIN = 0.115
NECK_AXIS = (0.0, 0.01)        # (x, y) del eje del cuello en mundo
TARGET_R = 0.085               # radio al que se encogen (dentro de la piel del cuello/collar)
FEATHER = 0.015                # m: transicion suave en el borde de la region (evita picos)

args = common.args()
PROBE, DRY = '--probe' in args, '--dry-run' in args
body = bpy.data.objects['Body']
if body.get('neck_headphones_hidden') and not PROBE:
    print('HP_HIDE ya aplicado; nada que hacer'); sys.exit(0)
mw = body.matrix_world; mwi = mw.inverted()


def weight(p):
    """1 dentro de la region, 0 fuera, rampa lineal de FEATHER en cada borde."""
    def ramp(v, lo, hi):
        return max(0.0, min(1.0, (v - lo) / FEATHER, (hi - v) / FEATHER))
    r = math.hypot(p.x - NECK_AXIS[0], p.y - NECK_AXIS[1])
    return min(ramp(abs(p.x), *X_RANGE), ramp(p.y, *Y_RANGE), ramp(p.z, *Z_RANGE),
               max(0.0, min(1.0, (r - R_MIN) / FEATHER)))


sel = {}
for v in body.data.vertices:
    p = mw @ v.co
    w = weight(p)
    if w > 0: sel[v.index] = (p, w)
print('HP_HIDE vertices en la region', len(sel), 'de', len(body.data.vertices))
if not sel: common.fail('la region no selecciona ningun vertice: recalibrar X/Y/Z_RANGE')

if PROBE:
    m_red = common.mat('HP_probe', (1.0, 0.02, 0.02, 1), roughness=0.9)
    body.data.materials.append(m_red)
    idx = len(body.data.materials) - 1
    for poly in body.data.polygons:
        if any(vi in sel for vi in poly.vertices):
            poly.material_index = idx
else:
    for vi, (p, w) in sel.items():
        r = math.hypot(p.x - NECK_AXIS[0], p.y - NECK_AXIS[1])
        if r <= 1e-6: continue
        k = 1.0 - w * (1.0 - TARGET_R / r)          # factor radial: 1 (sin cambio) .. TARGET_R/r
        q = Vector((NECK_AXIS[0] + (p.x - NECK_AXIS[0]) * k, NECK_AXIS[1] + (p.y - NECK_AXIS[1]) * k, p.z))
        body.data.vertices[vi].co = mwi @ q
    body.data.update()
    body['neck_headphones_hidden'] = True

for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
common.add_light('k', 'AREA', (-0.8, 1.2, 1.9), 200, (0.9, 0.9, 1.0), size=1.0)
common.add_light('f', 'AREA', (1.0, 0.8, 1.4), 60, (1.0, 0.95, 0.9), size=1.0)
tag = 'probe' if PROBE else 'hidden'
cam = common.add_camera((0.0, 0.9, 1.45), (0.0, 0.0, 1.40), lens=60)
common.render(os.path.join(common.RENDERS, f'headphones_{tag}_front.png'), res=(900, 700), samples=48)
cam.location = (0.9, 0.15, 1.45); common.look_at(cam, (0.0, 0.0, 1.40))
common.render(os.path.join(common.RENDERS, f'headphones_{tag}_side.png'), res=(900, 700), samples=48)
if PROBE:
    body.data.materials.pop(index=idx)
    print('HP_HIDE probe renderizado; no se guarda')
elif DRY:
    print('HP_HIDE dry-run; no se guarda')
else:
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
```

Run: `tools/run_blender.sh blender/character.blend blender/scripts/hide_neck_headphones.py -- --probe 2>&1 | grep -E 'HP_HIDE|RENDER|Error|Traceback'`
Expected: dos PNG con la región roja cubriendo SOLO las copas de los audífonos (no el cuello, no la barbilla, no los hombros del hoodie). Ajustar las constantes (máximo 3 iteraciones) hasta que la máscara roja coincida con las copas. Anotar los valores finales.

- [ ] **Step 2: Aplicar en dry-run y aprobar visualmente**

Run: `tools/run_blender.sh blender/character.blend blender/scripts/hide_neck_headphones.py -- --dry-run 2>&1 | grep -E 'HP_HIDE|RENDER|Error'`
Expected: `headphones_hidden_front.png` / `_side.png` sin copas, sin agujeros ni picos. Si hay picos, subir `FEATHER` a 0.025; si quedan restos, ampliar la región 1 cm. Si tras 3 intentos no queda limpio: reportar con los renders y NO aplicar (dejar el script, seguir con el Step 3 igual; la pieza nueva se modela de todas formas).

- [ ] **Step 3: Aplicar de verdad**

Run: `tools/run_blender.sh blender/character.blend blender/scripts/hide_neck_headphones.py 2>&1 | grep -E 'HP_HIDE|SAVED|Error'`
Luego una segunda vez: debe imprimir `HP_HIDE ya aplicado`.

- [ ] **Step 4: `poses.py`: traslación en `apply()` y `HEADPHONES_ON`**

Reemplazar `apply()` por:

```python
def apply(arm, pose, frame=None, loc=None):
    """Asigna eulers (y opcionalmente traslaciones locales `loc={hueso: (x,y,z)}`); keyframea si `frame`."""
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
    for name, e in pose.items():
        pb = arm.pose.bones.get(name)
        if not pb: continue
        pb.rotation_euler = e
        if frame is not None:
            pb.keyframe_insert('rotation_euler', frame=frame)
    for name, l in (loc or {}).items():
        pb = arm.pose.bones.get(name)
        if not pb: continue
        pb.location = l
        if frame is not None:
            pb.keyframe_insert('location', frame=frame)
```

Y añadir al final del módulo:

```python
# --- audifonos (hueso 'headphones', hijo de spine006; reposo = colgando del cuello).
# Estado "puestos": lo escribe add_headphones.py en blender/headphones.json (rotacion en grados
# y traslacion en espacio local del hueso). Se carga perezosamente para que poses.py siga
# importable antes de que exista el archivo.
import json as _json, os as _os
_HP_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'headphones.json')


def headphones_on():
    """(euler_rad, location_local) del estado 'puestos'; None si aun no existe headphones.json."""
    if not _os.path.exists(_HP_JSON):
        return None
    with open(_HP_JSON) as f:
        d = _json.load(f)['on_head']
    return (tuple(math.radians(v) for v in d['rotation_deg']), tuple(d['location']))
```

- [ ] **Step 5: `add_headphones.py`**

```python
# blender/scripts/add_headphones.py
# Pieza de audifonos (arco eliptico + dos copas) movida por el hueso 'headphones'.
# Convencion que animate.py y el visor dan por cierta:
#   * hueso 'headphones' hijo de spine006 con head = head de spine006 (traslacion 0 en glTF),
#     tail = head + (0,0,0.05), roll 0  ->  X local = +X mundo, Y local = +Z mundo, Z local = -Y mundo.
#   * reposo (rotacion 0, traslacion 0) = audifonos COLGANDO DEL CUELLO (arco detras de la nuca,
#     copas delante-abajo del menton).
#   * "puestos" = rotation_euler ON_ROT + location ON_LOC (espacio local), escritos en
#     blender/headphones.json junto con los centros de las copas en ambos estados (espacio local
#     del hueso) para que animate.py pueda llevar las manos a ellos.
# La pieza se modela en su posicion PUESTA (sobre la cabeza, encima de la gorra, centrada en las
# orejas de landmarks.json), se parenta al hueso, y luego se le aplica la transformacion inversa
# de ON para que el reposo quede en el cuello. Idempotente (borra lo suyo al empezar).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/add_headphones.py
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector, Matrix, Euler
from add_face_parts import obj_mode, parent_to_bone, shade_smooth, load_landmarks

BONE, PARENT = 'headphones', 'spine006'
OBJS = ('headphones_band', 'headphones_cup_L', 'headphones_cup_R')
BAND_A, BAND_B = 0.128, 0.245      # semiejes del arco (x: media distancia entre orejas + holgura; z: hasta encima de la gorra)
BAND_R = 0.009                     # radio del tubo del arco
CUP_R, CUP_D = 0.045, 0.032        # radio y grosor de la copa
ON_ROT_DEG = (-80.0, 0.0, 0.0)     # giro local X: de "sobre la cabeza" a "detras de la nuca" (ver cabecera)
NECK_CENTER = (0.0, 0.03, 1.375)   # centro del arco cuando cuelga del cuello (mundo, de pie)
OUT_JSON = os.path.join(common.BLEND_DIR, 'headphones.json')


def cleanup(arm):
    obj_mode()
    for o in list(bpy.data.objects):
        if o.name in OBJS: bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones.get(BONE)
    if eb: arm.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')
    for m in list(bpy.data.meshes):
        if m.users == 0: bpy.data.meshes.remove(m)


def add_bone(arm):
    obj_mode(); bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    par = arm.data.edit_bones[PARENT]
    eb = arm.data.edit_bones.new(BONE)
    eb.head = par.head.copy(); eb.tail = par.head + Vector((0, 0, 0.05)); eb.roll = 0.0
    eb.parent = par; eb.use_connect = False; eb.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')


def tube(name, path, radius, material, segs=8):
    """Tubo a lo largo de una polilinea (lista de Vector mundo)."""
    verts, faces = [], []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        n = t.cross(Vector((0, 1, 0))).normalized() if abs(t.dot(Vector((0, 1, 0)))) < 0.9 else t.cross(Vector((1, 0, 0))).normalized()
        b = t.cross(n)
        for k in range(segs):
            a = 2 * math.pi * k / segs
            verts.append(p + (n * math.cos(a) + b * math.sin(a)) * radius)
    for i in range(len(path) - 1):
        for k in range(segs):
            a, b2 = i * segs + k, i * segs + (k + 1) % segs
            faces.append((a, b2, b2 + segs, a + segs))
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def cup(name, centre, sx, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=CUP_R, depth=CUP_D, location=centre,
                                        rotation=(0, math.radians(90), 0))
    ob = bpy.context.active_object; ob.name = name
    ob.data.materials.append(material)
    bev = ob.modifiers.new('bevel', 'BEVEL'); bev.width = 0.008; bev.segments = 3
    bpy.ops.object.modifier_apply(modifier=bev.name)
    return ob


def main():
    common.ensure_dirs()
    lm = load_landmarks()
    arm = bpy.data.objects['Armature']
    cleanup(arm)
    add_bone(arm)
    m = common.mat('Headphones', (0.012, 0.012, 0.014, 1), roughness=0.55)
    ear_L, ear_R = Vector(lm['ear_L']), Vector(lm['ear_R'])
    centre = (ear_L + ear_R) / 2 + Vector((0, 0.005, 0.0))       # centro del arco = entre orejas
    # arco eliptico de oreja a oreja por encima de la gorra
    path = [centre + Vector((BAND_A * math.cos(a), 0, BAND_B * math.sin(a))) for a in
            [math.pi * i / 24 for i in range(25)]]
    band = tube('headphones_band', path, BAND_R, m)
    cups = [cup('headphones_cup_L', (centre.x - BAND_A, centre.y, centre.z), -1, m),
            cup('headphones_cup_R', (centre.x + BAND_A, centre.y, centre.z), 1, m)]
    for o in [band] + cups: shade_smooth(o)
    objs = [band] + cups

    # parentar en la posicion PUESTA (rotacion/traslacion del hueso = 0) ...
    bpy.context.view_layer.update()
    for o in objs: parent_to_bone(arm, o, BONE)
    pb = arm.pose.bones[BONE]; pb.rotation_mode = 'XYZ'
    # ... y calcular ON = (rotacion, traslacion) tal que el reposo (0,0) sea el cuello:
    # el hueso en reposo lleva la pieza al cuello; en ON la trae de vuelta a la cabeza.
    # Se resuelve numericamente: se pone la pieza en el cuello aplicando al hueso el estado
    # NECK (giro +80 y traslacion a NECK_CENTER), se lee el matrix_world de cada objeto, se
    # vuelve el hueso a 0 y se reasigna ese matrix_world como nueva pose base de la pieza.
    head_w = arm.matrix_world @ arm.data.bones[BONE].head_local
    neck_rot = Euler(tuple(-math.radians(v) for v in ON_ROT_DEG), 'XYZ')
    delta_world = Vector(NECK_CENTER) - centre                    # el centro del arco baja al cuello
    # el giro es alrededor de la cabeza del hueso: el centro del arco tambien gira; se compensa
    rot_m = neck_rot.to_matrix()                                   # local == mundo salvo permutacion de ejes:
    R = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))                 # local (x, y, z) -> mundo (x, -z, y)
    Rw = R @ rot_m @ R.inverted()
    centre_rot = head_w + Rw @ (centre - head_w)
    move_world = Vector(NECK_CENTER) - centre_rot
    pb.rotation_euler = neck_rot
    pb.location = R.inverted() @ move_world                        # mundo -> local
    bpy.context.view_layer.update()
    neck_mats = {o.name: o.matrix_world.copy() for o in objs}
    pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
    bpy.context.view_layer.update()
    for o in objs:
        parent_to_bone(arm, o, BONE)          # re-parentar conservando la matriz actual...
        o.matrix_world = neck_mats[o.name]    # ...y fijar la posicion del cuello como reposo
    bpy.context.view_layer.update()
    on_rot = tuple(-v for v in neck_rot)      # ON deshace NECK
    on_loc = tuple(-v for v in (R.inverted() @ move_world))
    # OJO: la inversa de (R, t) no es (-R, -t) cuando hay rotacion: se calcula con matrices.
    M_neck = Matrix.Translation(R.inverted() @ move_world) @ neck_rot.to_matrix().to_4x4()
    M_on = M_neck.inverted()
    on_rot = tuple(M_on.to_euler('XYZ')); on_loc = tuple(M_on.to_translation())
    pb.rotation_euler = on_rot; pb.location = on_loc
    bpy.context.view_layer.update()
    cup_head = {s: tuple((arm.matrix_world @ pb.matrix).inverted() @ (cups[i].matrix_world.translation) for i, s in enumerate('LR')) }
    err = max((cups[i].matrix_world.translation - (centre + Vector(((-1, 1)[i] * BAND_A, 0, 0)))).length for i in range(2))
    print('HP on_head reproduce la posicion puesta, error', round(err, 4), 'm')
    if err > 0.005: common.fail('la transformacion ON no devuelve la pieza a la cabeza')
    pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
    bpy.context.view_layer.update()
    cup_rest = {s: tuple((arm.matrix_world @ pb.matrix).inverted() @ cups[i].matrix_world.translation) for i, s in enumerate('LR')}
    with open(OUT_JSON, 'w') as f:
        json.dump({'on_head': {'rotation_deg': [round(math.degrees(v), 3) for v in on_rot],
                               'location': [round(v, 5) for v in on_loc]},
                   'cup_offset_rest': {s: [round(v, 5) for v in c] for s, c in cup_rest.items()},
                   'cup_offset_head': {s: [round(v, 5) for v in c] for s, c in cup_head.items()},
                   'cup_radius': CUP_R}, f, indent=1)
    print('HP json', OUT_JSON)

    # renders: reposo (cuello) y puestos
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.add_light('k', 'AREA', (-0.8, 1.2, 1.9), 200, (0.9, 0.9, 1.0), size=1.0)
    common.add_light('f', 'AREA', (1.0, 0.8, 1.4), 60, (1.0, 0.95, 0.9), size=1.0)
    cam = common.add_camera((0.35, 1.1, 1.5), (0.0, 0.0, 1.45), lens=55)
    common.render(os.path.join(common.RENDERS, 'headphones_rest.png'), res=(900, 800), samples=48)
    pb.rotation_euler = on_rot; pb.location = on_loc; bpy.context.view_layer.update()
    common.render(os.path.join(common.RENDERS, 'headphones_on.png'), res=(900, 800), samples=48)
    pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0); bpy.context.view_layer.update()
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))


if __name__ == '__main__':
    main()
```

Notas para el implementador: (1) `parent_to_bone` de `add_face_parts.py` parenta a la COLA del hueso; el reparentado con `matrix_world` fijado funciona porque conserva la matriz de mundo dada. (2) Las líneas con `on_rot = tuple(-v ...)` son un borrador que la línea `M_on = M_neck.inverted()` sustituye: dejar solo la versión con matrices. (3) Si el arco atraviesa la gorra, subir `BAND_B` en pasos de 0.01; si las copas no tocan las orejas, bajar `BAND_A`. (4) Verificar en `headphones_rest.png` que la pieza del cuello tapa cualquier resto de las copas fundidas.

- [ ] **Step 6: Checks**

En `check_rig.py` añadir `headphones` a los huesos obligatorios y los tres objetos a la lista de objetos parentados a hueso (leer el script: tiene listas `NEED_BONES`/similar; añadir sin cambiar el resto). En `check_face_export.py`, si comprueba que todos los objetos parentados a hueso exportan como hijos del hueso, añadir `('headphones_band', 'headphones'), ('headphones_cup_L', 'headphones'), ('headphones_cup_R', 'headphones')` a su lista.

Run:
```bash
tools/run_blender.sh blender/character.blend blender/scripts/add_headphones.py 2>&1 | grep -E 'HP|RENDER|SAVED|Error|Traceback'
tools/run_blender.sh blender/character.blend blender/scripts/add_headphones.py 2>&1 | grep -E 'HP|Error'    # idempotencia
tools/run_blender.sh blender/character.blend blender/scripts/checks/check_rig.py 2>&1 | grep -E 'CHECK|Error'
tools/run_blender.sh blender/character.blend blender/scripts/checks/check_face_export.py 2>&1 | grep -E 'CHECK|Error'
cat blender/headphones.json
```
Expected: `HP on_head ... error < 0.005`, checks OK, `headphones_rest.png` con los audífonos colgando del cuello (arco detrás de la nuca) y `headphones_on.png` con el arco sobre la gorra y las copas en las orejas.

- [ ] **Step 7: Commit**

```bash
git add blender/scripts/hide_neck_headphones.py blender/scripts/add_headphones.py blender/headphones.json blender/scripts/poses.py blender/scripts/checks/check_rig.py blender/scripts/checks/check_face_export.py
git commit -m "feat: audifonos como pieza aparte con hueso headphones; copas fundidas del cuello encogidas"
```

---

### Task 5: `vibe` v2 — ponerse los audífonos, cabecear, quitárselos

**Files:**
- Modify: `blender/scripts/animate.py` (bloque `# --- 5) vibe`; nuevas funciones `reach()`, `cup_world()`)
- Modify: `blender/scripts/checks/check_anim.py` (`NEED['vibe'] = 216`; permitir brazos + `headphones` en vibe)
- Modify: `blender/scripts/export_glb.py` (`NODES` += `'headphones'`; check "solo vibe/lookAround mueven spine006" sigue igual; nuevo check: `headphones` solo en `vibe`)
- Modify: `export/preview.html` (nada aquí; la Tarea 6 lo adapta)

**Interfaces:**
- Consumes: hueso `headphones`, `poses.headphones_on()`, `blender/headphones.json` (`cup_offset_rest/head`, espacio local del hueso `headphones`).
- Produces: acción `vibe` de 216 frames que anima `spine006, spine005, spine003, shoulderL/R, eyelidL/R, upper_armL/R, forearmL/R, handL/R, headphones` (rotación + `location` de `headphones`).

- [ ] **Step 1: Actualizar `check_anim.py` (falla antes)**

`NEED['vibe'] = 216`. Añadir tras `IDLE_OK`:

```python
VIBE_OK = {'spine006', 'spine005', 'spine003', 'shoulderL', 'shoulderR', 'eyelidL', 'eyelidR',
           'upper_armL', 'upper_armR', 'forearmL', 'forearmR', 'handL', 'handR', 'headphones'}
```
y al final, antes de `print('CHECK_ANIM OK')`:
```python
extra = bones_in(bpy.data.actions['vibe']) - VIBE_OK
if extra: common.fail(f'vibe toca huesos inesperados: {sorted(extra)}')
if 'headphones' not in bones_in(bpy.data.actions['vibe']): common.fail('vibe no mueve headphones')
for n in NEED:
    if n != 'vibe' and 'headphones' in bones_in(bpy.data.actions[n]):
        common.fail(f'{n} mueve headphones; solo vibe puede')
```
Run: `tools/run_blender.sh blender/character_anim.blend blender/scripts/checks/check_anim.py 2>&1 | grep CHECK` → Expected: falla por duración 120 ≠ 216 (character_anim.blend de la Tarea 3).

- [ ] **Step 2: Añadir `reach()` y `cup_world()` en `animate.py` (después de `solve_arms`)**

```python
HP = 'headphones'
HP_JSON = os.path.join(common.BLEND_DIR, 'headphones.json')
with open(HP_JSON) as _f:
    HP_DATA = json.load(_f)
HP_ON = poses.headphones_on()
if HP_ON is None:
    common.fail('falta blender/headphones.json (ejecutar add_headphones.py)')


def hp_state(u):
    """Interpola el hueso headphones entre reposo (u=0, cuello) y puestos (u=1)."""
    rot = tuple(lerp(0.0, HP_ON[0][i], u) for i in range(3))
    loc = tuple(lerp(0.0, HP_ON[1][i], u) for i in range(3))
    return rot, loc


def cup_world(side, u):
    """Centro de la copa `side` en mundo con el hueso headphones en el estado u (0..1).
    Requiere que el resto de la pose (torso, cabeza) ya este aplicada."""
    pb = arm.pose.bones[HP]
    rot, loc = hp_state(u)
    pb.rotation_mode = 'XYZ'; pb.rotation_euler = rot; pb.location = loc
    bpy.context.view_layer.update()
    off = HP_DATA['cup_offset_rest' if u < 0.5 else 'cup_offset_head'][side]
    # los offsets son fijos respecto a la pieza; en estados intermedios se toma el mas cercano
    return arm.matrix_world @ (pb.matrix @ Vector(off))


def reach(side, wrist_world, hand_dir, elbow_hint=None):
    """IK analitica de dos huesos: coloca la muneca (cabeza de hand<side>) en `wrist_world`.
    Devuelve {upper_arm, forearm, hand: euler}. El resto de la pose debe estar aplicada."""
    s = side
    ua, fa, ha = f'upper_arm{s}', f'forearm{s}', f'hand{s}'
    for b in (ua, fa, ha):
        arm.pose.bones[b].rotation_euler = SIT[b]
    bpy.context.view_layer.update()
    S = arm.matrix_world @ arm.pose.bones[ua].head
    L1 = arm.data.bones[ua].length; L2 = arm.data.bones[fa].length
    T = Vector(wrist_world)
    d = (T - S); dist = min(d.length, (L1 + L2) * 0.995); d.normalize()
    # angulo del brazo respecto a la recta hombro-muneca (ley de cosenos)
    cos_a = max(-1.0, min(1.0, (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)))
    a = math.acos(cos_a)
    hint = Vector(elbow_hint or (SX[s] * -1.0, -0.6, -0.5)).normalized()   # codo afuera, atras y abajo
    perp = (hint - d * hint.dot(d)); perp.normalize()
    E = S + (d * math.cos(a) + perp * math.sin(a)) * L1
    out = {ua: poses.aim(arm, ua, tuple(E - S))}
    out[fa] = poses.aim(arm, fa, tuple(T - E))
    out[ha] = poses.aim(arm, ha, tuple(Vector(hand_dir)))
    return out
```
(`import json` arriba junto a `sys, os, math`.)

- [ ] **Step 3: Reemplazar el bloque `# --- 5) vibe`**

```python
# --------------------------------------------------------------------------- 5) vibe
# 216 frames (9 s a 24 fps). Fases:
#   f1-20    manos suben del teclado a las copas (audifonos colgando del cuello)
#   f20-44   las manos llevan los audifonos a la cabeza (hueso headphones: reposo -> puestos)
#   f44-52   ajuste (pausa)
#   f52-76   manos vuelven al teclado
#   f60-152  cabeceo de rap (ojos cerrados f66..f146), envolvente de 14 frames
#   f152-168 manos suben a las copas (en la cabeza)
#   f168-192 bajan los audifonos al cuello
#   f192-216 manos vuelven al teclado; f216 = SIT exacto (empalma con idle/typing)
# Muneca objetivo: al lado de la copa (afuera 4 cm, 8 cm abajo), mano apuntando hacia arriba y
# un poco adentro, como sujetando la copa por debajo.
VIBE_BONES = [HEAD, NECK, 'spine003', 'shoulderL', 'shoulderR'] + LIDS + ARM_BONES + [HP]
VIBE_LEN = 216
act = new_action('vibe', VIBE_BONES)
key(HP, 1, euler=(0, 0, 0), loc=(0, 0, 0))
WRIST_OFF = lambda s: Vector((SX[s] * -0.04, 0.0, -0.08))       # L esta en -X: afuera = -X para L
HAND_DIR = lambda s: (SX[s] * 0.25, 0.15, 0.95)
BEAT = 15.0


def smooth(u):
    return u * u * (3 - 2 * u)


def hands_to_cups(f, u_hp):
    """Coloca ambas manos en las copas con headphones en el estado u_hp y keyframea todo."""
    poses.apply(arm, SIT)
    arm.pose.bones[HEAD].rotation_euler = SIT[HEAD]
    rot, loc = hp_state(u_hp)
    key(HP, f, euler=rot, loc=loc)
    for s in 'LR':
        cw = cup_world(s, u_hp)
        key_pose(f, reach(s, cw + WRIST_OFF(s), HAND_DIR(s)))


def hands_home_blend(f, u):
    """u=0 manos en las copas del ultimo estado clavado (no se recalcula), u=1 teclado (SIT)."""
    # interpolacion en el espacio de direcciones (como intro): de la ultima pose de brazos a SIT
    pass  # ver abajo: se resuelve con keyframes bezier entre el ultimo key de copas y SIT


def key_arms_sit(f):
    for b in ARM_BONES:
        key(b, f, SIT[b])


def nod(f, env):
    t = (f - 60) / BEAT * 2 * math.pi
    pulse = max(0.0, math.sin(t)) ** 1.5
    nod_deg = -8 + env * (30 * pulse - 8)
    key(HEAD, f, rot(HEAD, nod_deg, side_deg=env * 5.0 * math.sin(t / 2)))
    key(NECK, f, neck(4 + env * 6.0 * pulse, env * 2.5 * math.sin(t / 2)))
    key('spine003', f, rot('spine003', 6 + env * 4.5 * math.sin(t)))
    key('shoulderL', f, rot('shoulderL', env * 6.0 * math.sin(t)))
    key('shoulderR', f, rot('shoulderR', env * 6.0 * math.sin(t + math.pi)))


# fase 1: teclado -> copas en el cuello (bezier entre SIT en f1 y copas en f20; paso por f12 con las manos mas altas que el destino para no rozar el escritorio)
key_arms_sit(1)
hands_to_cups(20, 0.0)
# fase 2: subir los audifonos (5 keys)
for f, u in ((26, 0.15), (32, 0.45), (38, 0.8), (44, 1.0)):
    hands_to_cups(f, smooth(u))
# fase 3: ajuste
hands_to_cups(52, 1.0)
# fase 4: manos al teclado (los audifonos se quedan puestos)
key_arms_sit(76)
key(HP, 76, euler=HP_ON[0], loc=HP_ON[1])
# fase 5: cabeceo (la cabeza vuelve a SIT justo antes de la fase 6)
for f in range(60, 153, 2):
    env = min(1.0, (f - 60) / 14.0) * min(1.0, (152 - f) / 14.0)
    nod(f, env)
key(HP, 152, euler=HP_ON[0], loc=HP_ON[1])
# fase 6: manos a las copas (en la cabeza)
hands_to_cups(168, 1.0)
# fase 7: bajar los audifonos
for f, u in ((174, 0.8), (180, 0.45), (186, 0.15), (192, 0.0)):
    hands_to_cups(f, smooth(u))
# fase 8: manos al teclado, todo en SIT
key_arms_sit(216)
key(HP, 216, euler=(0, 0, 0), loc=(0, 0, 0))
for b in (HEAD, NECK, 'spine003'):
    key(b, 1, SIT[b]); key(b, 58, SIT[b]); key(b, 154, SIT[b]); key(b, 216, SIT[b])
for b in ('shoulderL', 'shoulderR'):
    key(b, 1, (0, 0, 0)); key(b, 58, (0, 0, 0)); key(b, 154, (0, 0, 0)); key(b, 216, (0, 0, 0))
lids(1, 0); lids(60, 0); lids(66, 70); lids(146, 70); lids(152, 0); lids(216, 0)
finish(act, VIBE_LEN, cyclic=False)
```

Quitar la función `hands_home_blend` (placeholder del borrador): las fases 1, 4, 6 y 8 se resuelven con la interpolación bezier entre el último key de copas y el key SIT. Nota: `hands_to_cups` aplica `SIT` a todo el rig para resolver la IK con el torso en SIT; durante el cabeceo (f60-152) las manos están en el teclado y no se recalculan, así que la mezcla es coherente. Mientras la cabeza cabecea con los audífonos puestos, el hueso `headphones` es hijo de `spine006` y acompaña solo.

- [ ] **Step 4: Regenerar, check y tiras**

Run:
```bash
tools/run_blender.sh blender/character.blend blender/scripts/animate.py 2>&1 | grep -E 'CLIP|SIT_ARMS|ACTIONS|Error|Traceback'
tools/run_blender.sh blender/character_anim.blend blender/scripts/checks/check_anim.py 2>&1 | grep -E 'CHECK|CLIP|Error'
tools/run_blender.sh blender/character_anim.blend blender/scripts/anim_strip.py -- vibe 2>&1 | grep -E 'STRIP|RENDER|Error'
```
Expected: `CHECK_ANIM OK`; la tira de `vibe` (elegir frames 1, 20, 32, 44, 76, 100, 168, 186, 216 si `anim_strip.py` acepta lista; si no, adaptar sus constantes) muestra: manos en las copas del cuello (f20), audífonos a media altura con manos (f32), puestos (f44), manos en el teclado con audífonos puestos (f76), cabeceo (f100), bajada (f186), SIT (f216). Criterios: las manos no atraviesan la cabeza ni la gorra (si pasa, aumentar el componente −X/+X de `WRIST_OFF` a 0.06), los codos no se meten en el torso (ajustar `elbow_hint`), y la pieza no atraviesa la cara.

- [ ] **Step 5: `export_glb.py`**

`NODES` += `'headphones'`. Añadir junto al check de `spine006`:
```python
check({n for n, b in clip_bones.items() if 'headphones' in b} == {'vibe'}, 'solo vibe mueve headphones')
```
(No se ejecuta aún; Tarea 7.)

- [ ] **Step 6: Commit**

```bash
git add blender/scripts/animate.py blender/scripts/checks/check_anim.py blender/scripts/export_glb.py
git commit -m "feat: vibe v2 (216 f): se pone los audifonos con IK de brazos, cabecea y se los quita"
```

---

### Task 6: Visor — luces con sombras, mirar al cursor, pecho, audífonos, sonda CDP

**Files:**
- Modify: `export/preview.html`
- Create: `tools/preview_probe.mjs`

**Interfaces:**
- Consumes: GLB con nodos `spine006`, `spine003`, `headphones` (si falta `headphones`, el visor sigue funcionando), mallas `wall_*`, `ceiling`, `floor`, `screen_*`, `rgb_bar_*`, `window_far`.
- Produces: `window.__status` con `headQ()`, `chestQ()`, `hpQ()`, `lights` (número de luces), `shadows` (bool). `tools/preview_probe.mjs` escribe `generated/renders/preview_shot.png`, `preview_shot_look.png` (mouse a la izquierda), `preview_shot_vibe.png` (frame ~2 s dentro del vibe) e imprime `PROBE status {...}` y `PROBE errors [...]`.

- [ ] **Step 1: Sonda CDP (primero, para tener test)**

`tools/preview_probe.mjs`:

```js
#!/usr/bin/env node
// Sonda headless del visor: sirve export/, abre Chrome headless con CDP, espera la carga,
// mueve el mouse, dispara vibe y guarda capturas en generated/renders/. Imprime PROBE ... y
// sale con 1 si hubo errores en pagina o no cargo el GLB.
// Uso: node tools/preview_probe.mjs   (requiere Google Chrome y Node >= 22)
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const PORT = 8766, DBG = 9334;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-probe')}`,
  '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('PROBE no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html` });
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }); return r.result?.result?.value; };
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); console.log('PROBE shot', name); };
const mv = (x, y) => ev(`dispatchEvent(new MouseEvent('mousemove',{clientX:${x},clientY:${y}}));1`);

let loaded = false;
for (let i = 0; i < 60 && !loaded; i++) { await sleep(500); loaded = await ev('!!(window.__status && __status.loaded && __status.env)'); }
await sleep(4500);                                  // intro (3 s) + fundido de pantallas
await mv(720, 420); await sleep(1500);
const status = await ev('JSON.stringify({loaded:__status.loaded,env:__status.env,fps:__status.fps,shadows:__status.shadows,lights:__status.lights,clips:__status.clips(),headQ:__status.headQ(),chestQ:__status.chestQ(),hpQ:__status.hpQ()})');
console.log('PROBE status', status);
await shot('preview_shot.png');
await mv(40, 300); await sleep(2000);
const headLeft = await ev('JSON.stringify(__status.headQ())');
console.log('PROBE headQ izquierda', headLeft);
await shot('preview_shot_look.png');
await mv(720, 420); await ev('window.__vibe && window.__vibe(); 1'); await sleep(2200);
console.log('PROBE vibe', await ev('JSON.stringify({ex:__status.exclusive,clips:__status.clips(),hpQ:__status.hpQ()})'));
await shot('preview_shot_vibe.png');
const errors = await ev('JSON.stringify(window.__errors)');
console.log('PROBE errors', errors);
ws.close(); cleanup();
process.exit(loaded && errors === '[]' ? 0 : 1);
```

Run: `node tools/preview_probe.mjs` (con el `preview.html` actual): Expected: `PROBE status {...}` con `shadows` undefined todavía, `PROBE errors []` y exit 0. Si Chrome no arranca por `SingletonLock`, borrar `$(node -e "console.log(require('os').tmpdir())")/me3d-probe`.

- [ ] **Step 2: `preview.html` — luces y sombras**

Reemplazar el bloque de luces (desde `const key = new THREE.SpotLight` hasta `scene.add(new THREE.AmbientLight(...))`) por:

```js
// ---- luces. Coordenadas glTF (x, y, z) = Blender (x, z, -y).
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMappingExposure = 1.15;
const lights = [];
const key = new THREE.SpotLight(0xcfe0ff, 40, 0, Math.PI / 3.4, 0.7, 2);   // key azulada desde arriba-izquierda, con sombra
key.position.set(-1.2, 2.5, -2.3); key.target.position.copy(CAM_TGT);
key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
key.shadow.camera.near = 0.5; key.shadow.camera.far = 12;
scene.add(key, key.target); lights.push(key);
const ceil = new THREE.PointLight(0xffe0c0, 6, 7, 2); ceil.position.set(0.6, 2.6, 0.2); scene.add(ceil); lights.push(ceil);   // calida del techo
const win = new THREE.RectAreaLight(0x8fb8ff, 5, 3.2, 1.8); win.position.set(-0.3, 1.5, 1.7); win.lookAt(-0.3, 1.2, 0); scene.add(win); lights.push(win);
scene.add(new THREE.HemisphereLight(0x33405c, 0x0b0b0e, 0.5));
// luz de las pantallas (se enciende con el fundido) y de las barras RGB (siguen el ciclo de color)
const SCREEN_POS = { screen_left: [-0.6, 0.95, -1.35], screen_center: [0, 0.95, -1.35], screen_right: [0.6, 0.95, -1.35], screen_laptop: [0, 0.9, -1.0] };
const screenLights = {};
for (const [n, p] of Object.entries(SCREEN_POS)) { const l = new THREE.PointLight(0xbfd4ff, 0, 2.2, 2); l.position.set(...p); scene.add(l); screenLights[n] = l; lights.push(l); }
const barLights = [];
for (const x of [-1.05, 1.05]) { const l = new THREE.PointLight(0x4090ff, 3, 4, 2); l.position.set(x, 1.3, 1.2); scene.add(l); barLights.push(l); lights.push(l); }
status.lights = lights.length; status.shadows = true;
```
Añadir `import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';` y llamar `RectAreaLightUniformsLib.init();` antes de crear `win`.

En el `traverse` del `loader.load`, añadir:
```js
if (o.isMesh) { o.castShadow = !/^(screen_|window_far|floor|ceiling|wall_)/.test(o.name); o.receiveShadow = !/^(screen_|window_far)/.test(o.name); }
```
En `animate()`, junto al fundido de pantallas: `for (const [n, l] of Object.entries(screenLights)) l.intensity = 1.6 * k * k;` y en el ciclo de barras: `barLights[i] && barLights[i].color.copy(b.material.emissive);`.

- [ ] **Step 3: `preview.html` — mirar al cursor, pecho y audífonos**

Reemplazar la sección `// ---- seguimiento de cursor en spine006 ...` (constantes, `applyHeadFollow`) y el trío `undoFollow`/`headClipQ` por un sistema de "huesos seguidos":

```js
// ---- seguimiento de cursor: la cabeza (spine006) MIRA al punto 3D del cursor (a la profundidad de
// la cabeza), el pecho (spine003) acompana el 30 % del yaw y el nodo headphones (hijo de la cabeza,
// audifonos colgando del cuello) cancela el giro para no columpiarse. Se aplica DESPUES del mixer y
// se deshace antes del siguiente update (los clips base no escriben estos huesos cada frame).
const YAW_MAX = Math.PI / 4, PITCH_UP = Math.PI / 7.2, PITCH_DOWN = Math.PI / 9;   // 45 / 25 / 20 grados
const follow = { head: null, chest: null, hp: null };            // Object3D
const saved = { head: null, chest: null, hp: null };             // cuaternion tal como lo dejan los clips
const look = { yaw: 0, pitch: 0 };
let followWeight = 0;
const undoFollow = () => { for (const k in follow) if (follow[k] && saved[k]) follow[k].quaternion.copy(saved[k]); };
const saveFollow = () => { for (const k in follow) if (follow[k]) saved[k] = (saved[k] || new THREE.Quaternion()).copy(follow[k].quaternion); };
const ray = new THREE.Raycaster();
const vHead = new THREE.Vector3(), vTarget = new THREE.Vector3(), vDir = new THREE.Vector3(), vCam = new THREE.Vector3();
const qWorld = new THREE.Quaternion(), qParent = new THREE.Quaternion(), qTmp = new THREE.Quaternion(), qHeadOld = new THREE.Quaternion(), qYaw = new THREE.Quaternion(), qPitch = new THREE.Quaternion();
const AX_X = new THREE.Vector3(1, 0, 0), AX_Y = new THREE.Vector3(0, 1, 0);
function worldRotate(obj, q, weight) {   // newLocal = parent^-1 * slerp(I, q, w) * parent * local
  obj.parent.getWorldQuaternion(qParent);
  qTmp.identity().slerp(q, weight);
  qTmp.copy(qParent).invert().multiply(qTmp).multiply(qParent);   // (reusa qTmp: parent^-1 * qW * parent)
  obj.quaternion.premultiply(qTmp);
}
function applyHeadFollow() {
  const active = !(exclusive === 'vibe' || exclusive === 'lookAround');
  followWeight += ((active ? 1 : 0) - followWeight) * 0.08;
  if (!follow.head) return;
  follow.head.getWorldPosition(vHead);
  camera.getWorldPosition(vCam);
  ray.setFromCamera(new THREE.Vector2(mouse.x, mouse.y), camera);
  vTarget.copy(ray.ray.origin).addScaledVector(ray.ray.direction, vHead.distanceTo(vCam));
  vDir.subVectors(vTarget, vHead);
  if (vDir.length() > 0.05) {
    vDir.normalize();
    const yaw = Math.atan2(-vDir.x, -vDir.z);          // el personaje mira a -Z
    const pitch = Math.asin(Math.max(-1, Math.min(1, vDir.y)));
    look.yaw += (Math.max(-YAW_MAX, Math.min(YAW_MAX, yaw)) - look.yaw) * 0.08;
    look.pitch += (Math.max(-PITCH_DOWN, Math.min(PITCH_UP, pitch)) - look.pitch) * 0.08;
  }
  if (followWeight < 0.001) return;
  qYaw.setFromAxisAngle(AX_Y, look.yaw); qPitch.setFromAxisAngle(AX_X, look.pitch);
  qWorld.copy(qYaw).multiply(qPitch);
  if (follow.chest) { qTmp.setFromAxisAngle(AX_Y, look.yaw * 0.3); worldRotate(follow.chest, qTmp, followWeight); }
  // el pecho ya giro: la cabeza aplica el resto (el giro de mundo se compone igual, la cabeza es hija)
  qHeadOld.copy(follow.head.quaternion);
  qTmp.setFromAxisAngle(AX_Y, look.yaw * 0.7).multiply(qPitch);
  worldRotate(follow.head, qTmp, followWeight);
  if (follow.hp) {   // hp_new = head_old^-1 * head_new^-1 ... => conservar el mundo: hp_local = head_new^-1 * head_old * hp_old
    qTmp.copy(follow.head.quaternion).invert().multiply(qHeadOld);
    follow.hp.quaternion.premultiply(qTmp);
  }
}
```
`worldRotate` debe usar un cuaternión propio para el slerp para no pisar `qTmp` a mitad: declarar `const qW = new THREE.Quaternion();` y escribir `qW.identity().slerp(q, weight); qTmp.copy(qParent).invert().multiply(qW).multiply(qParent);`.

En el `traverse`: `if (o.name === 'spine006') follow.head = o; if (o.name === 'spine003') follow.chest = o; if (o.name === 'headphones') follow.hp = o;` y tras el traverse `saveFollow();`. En `animate()`: `undoFollow(); if (mixer) mixer.update(dt); saveFollow(); applyHeadFollow();`. Las llamadas a `undoFollow()` en `playLoop`/`playOnce` se mantienen. En `status`: `headQ: () => follow.head && follow.head.quaternion.toArray(), chestQ: () => follow.chest && follow.chest.quaternion.toArray(), hpQ: () => follow.hp && follow.hp.quaternion.toArray()`. Exponer `window.__vibe = vibe;` tras definir `vibe`. Ajustar el texto de `#help`: "La cabeza mira al cursor. Clic sobre el personaje = vibe (se pone los audífonos y cabecea; también automático cada 30-50 s)". Cambiar el temporizador automático a `30000 + Math.random() * 20000` (el clip ahora dura 9 s).

- [ ] **Step 4: Sonda**

Run: `tools/serve_preview.sh` NO hace falta; `node tools/preview_probe.mjs`
Expected: `PROBE errors []`, `shadows: true`, `lights: 10`, `headQ` distinto entre centro e izquierda (componente y ≈ ±0.3), `hpQ` presente si el GLB ya trae `headphones` (con el GLB viejo será `null`: aceptable en esta tarea). Mirar `preview_shot.png`: con el GLB viejo todavía sin paredes se verá oscuro; lo que se valida aquí es que no hay errores, que hay sombra del personaje/escritorio sobre el piso y que la cabeza gira más que antes.

- [ ] **Step 5: Commit**

```bash
git add export/preview.html tools/preview_probe.mjs
git commit -m "feat(visor): sombras y luces de escena, cabeza mira al cursor con pecho, cancelacion en headphones, sonda CDP"
```

---

### Task 7: Regeneración completa, ajuste fino y documentación

**Files:**
- Modify: `README.md` (secciones "Regenerar todo", "Huesos y clips", "Nodos útiles", snippet three.js), `docs/HANDOFF.md`
- Modify (ajustes finos si hacen falta): `export/preview.html`

- [ ] **Step 1: Pipeline completo del personaje y escena**

```bash
B=tools/run_blender.sh
$B - blender/scripts/build_scene.py 2>&1 | grep -E 'SCENE_TRIS|WARNING|Error|Traceback'
$B blender/scene.blend blender/scripts/checks/check_scene.py 2>&1 | grep -E 'CHECK|Error'
$B - blender/scripts/import_character.py 2>&1 | grep -E 'FACING|CHAR_TRIS|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/apply_chest_logo.py 2>&1 | grep -E 'CHEST|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/fix_character_material.py 2>&1 | grep -E 'TEXCLEAN|MATERIAL|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/checks/check_character_material.py 2>&1 | grep -E 'CHECK|Error'
$B blender/character.blend blender/scripts/add_face_parts.py 2>&1 | grep -E 'CLEANUP|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/hide_neck_headphones.py 2>&1 | grep -E 'HP_HIDE|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/add_headphones.py 2>&1 | grep -E 'HP|SAVED|Error|Traceback'
$B blender/character.blend blender/scripts/checks/check_rig.py 2>&1 | grep -E 'CHECK|Error'
$B blender/character.blend blender/scripts/checks/check_face_export.py 2>&1 | grep -E 'CHECK|Error'
$B blender/character.blend blender/scripts/animate.py 2>&1 | grep -E 'CLIP|SIT_ARMS|Error|Traceback'
$B blender/character_anim.blend blender/scripts/checks/check_anim.py 2>&1 | grep -E 'CHECK|Error'
$B - blender/scripts/assemble.py 2>&1 | grep -E 'CHAR|SEAT|MOTO|HDR|TOTAL_TRIS|INTERSECCIONES|NEUTRAL|SAVED|Error|Traceback'
$B blender/avatar.blend blender/scripts/export_glb.py 2>&1 | grep -E 'EXPORT_CHECK|GLB OK|CHECK FAILED|Error|Traceback'
python3 tools/glb_inspect.py export/avatar.glb | head -5
```
Expected: todos los checks OK, `INTERSECCIONES 0`, `GLB OK` con 7 clips y `headphones` en nodos. Si `import_character.py` no es necesario (character.blend ya está bien), igual se corre: la regla del README es que tras `import_character.py` hay que repetir todo; aquí se hace completo para probar la reproducibilidad. OJO: `add_face_parts.py` va ANTES que `hide_neck_headphones.py` porque los párpados se apoyan por raycast sobre la cara, y el encogido no toca la cara.

- [ ] **Step 2: Sonda del visor y ajuste de luces**

Run: `node tools/preview_probe.mjs`
Expected: `PROBE errors []`. Abrir `generated/renders/preview_shot.png`, `preview_shot_look.png`, `preview_shot_vibe.png`. Criterios visuales:
- hoodie negro mate sin motas claras; cara con volumen (sombra bajo la visera);
- paredes visibles con gradiente de luz, sombra del personaje y escritorio sobre el piso, luz azul de la ventana en la pared/techo, halo de las pantallas en la cara y las manos;
- repisa con soportes contra la pared, moto legible;
- en `_look.png` la cabeza gira claramente hacia la izquierda de la pantalla y el pecho un poco;
- en `_vibe.png` (≈2.2 s dentro del clip) los audífonos van hacia la cabeza con las manos.
Ajustar intensidades en `preview.html` (`key` 30–60, `ceil` 4–10, `win` 3–8, `toneMappingExposure` 1.0–1.3) hasta que la captura tenga luminancia media (YAVG) entre 55 y 80: medir con
```bash
python3 -c "from PIL import Image; import numpy as np; print('YAVG', np.asarray(Image.open('generated/renders/preview_shot.png').convert('L')).mean())"
```

- [ ] **Step 3: Enviar capturas al usuario**

Enviar `preview_shot.png`, `preview_shot_look.png`, `preview_shot_vibe.png`, `material_fix.png`, `headphones_on.png`, `strip_typing.png`, `strip_vibe.png` con SendUserFile (y `open`).

- [ ] **Step 4: README y HANDOFF**

README: pipeline nuevo (orden de la sección Global Constraints), tabla de clips (`vibe` 216 frames, "se pone los audífonos, cabecea, se los quita"), huesos (`headphones`: hijo de `spine006`, reposo = cuello), nodos útiles (`headphones`, `wall_*`, `ceiling`), snippet three.js (mencionar que el material `Character` YA NO trae emisión, que `medellin` va a 1504 px y que el visor de referencia enciende sombras). HANDOFF: nueva sección "Sesión 3 (2026-09-03): pulido" con tabla de tareas 15–21 (este plan), estado, renders de aprobación y pendientes: (1) repo del portafolio (URL) para la integración; (2) aprobaciones visuales del usuario; (3) decisión de archivado (sigue pendiente).

- [ ] **Step 5: Commit final**

```bash
git add README.md docs/HANDOFF.md export/preview.html
git commit -m "docs: README y HANDOFF con el pipeline de pulido (material, habitacion, typing v2, audifonos, visor)"
```

---

## Self-review

- **Cobertura del diseño aprobado:** motas/material (T1), habitación + luces + sombras (T2, T6), repisa (T2), ventana nítida (T1 export + T2), typing (T3), cursor (T6), audífonos en vibe (T4, T5), regeneración/docs (T7). Portafolio: fuera de alcance declarado (falta el repo).
- **Placeholders:** el borrador de `hands_home_blend` y las líneas `on_rot = tuple(-v ...)` están marcados explícitamente para eliminarse; no hay "TBD".
- **Consistencia de nombres:** `headphones` (hueso y nodo), `headphones_band/cup_L/cup_R`, `poses.headphones_on()`, `HP_ON`, `blender/headphones.json` con claves `on_head.rotation_deg`, `on_head.location`, `cup_offset_rest`, `cup_offset_head`; `Body['texture_clean']`, `Body['neck_headphones_hidden']`; `window.__status.{headQ,chestQ,hpQ,lights,shadows}`, `window.__vibe`; `TEX_LIMITS`, `CHAR_QUALITY`; `VIBE_OK`, `NEED['vibe']=216`.

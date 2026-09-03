# Me on 3D — avatar 3D de Sebastián

Avatar cartoon de Sebastián sentado tecleando en su escritorio (Mac + tres monitores, barras RGB, mini Suzuki DR150 en la repisa y Medellín de noche por la ventana), listo para usar en una web con three.js. Estilo de referencia: [moncy.dev](https://www.moncy.dev/).

Entregables:

- `export/avatar.glb` — escena completa con Draco, 7 clips de animación, ~48k triángulos, < 2 MB.
- `export/avatar_uncompressed.glb` — la misma escena sin Draco (depuración).
- `export/night.hdr` — entorno nocturno 1024×512 para la iluminación.
- `export/preview.html` + `tools/serve_preview.sh` — visor local de referencia (three.js).
- `blender/*.blend` — archivos fuente (se regeneran con los scripts; no se versionan).

## Carpetas

| Carpeta | Contenido |
|---|---|
| `blender/scripts/` | Pipeline completo por script para Blender headless (ver "Regenerar"). `checks/` contiene las verificaciones automáticas. |
| `blender/` | `scene.blend` (escritorio), `character.blend` (personaje rigueado + logo + partes faciales), `character_anim.blend` (+ animaciones), `avatar.blend` (todo ensamblado). |
| `refs/` | Referencias: frames de la cara (`face/`), foto de la moto y estilo (`style/`), logo de la empresa (`logo.png`). |
| `generated/` | Salidas intermedias (ignorado por git): láminas de Higgsfield, malla Meshy, texturas, renders de aprobación, `credits.log`. |
| `export/` | Entregables. Los `.glb` están ignorados por git; se regeneran con `export_glb.py`. |
| `tools/` | `run_blender.sh` (lanzador headless), `glb_inspect.py` (inspección de GLB), `screens/` (texturas de pantalla con Chrome headless), `serve_preview.sh`. |
| `docs/` | Spec, plan y `HANDOFF.md` (estado del proyecto y decisiones). |

## Regenerar todo

Requisitos: Blender 4.x/5.x en `/Applications/Blender.app`, Google Chrome, Python 3 con Pillow, ffmpeg (solo para las tiras de animación).

```bash
B=tools/run_blender.sh
tools/screens/make_screens.sh                                   # texturas de las pantallas (usa refs/logo.png)
$B - blender/scripts/build_scene.py                              # blender/scene.blend
$B - blender/scripts/import_character.py                         # blender/character.blend desde generated/meshy/character_rigged.glb
$B blender/character.blend blender/scripts/apply_chest_logo.py   # logo en el pecho (textura)
$B blender/character.blend blender/scripts/checks/check_rig.py
$B blender/character.blend blender/scripts/render_face_grid.py   # rejilla para generated/landmarks.json
$B blender/character.blend blender/scripts/add_face_parts.py     # párpados, cejas y candongas con huesos
$B blender/character.blend blender/scripts/checks/check_face_export.py
$B blender/character.blend blender/scripts/animate.py            # blender/character_anim.blend (7 clips)
$B blender/character_anim.blend blender/scripts/checks/check_anim.py
$B - blender/scripts/render_hdr.py                               # export/night.hdr
$B - blender/scripts/assemble.py                                 # blender/avatar.blend (+ generated/renders/assembled_v1.png)
$B blender/avatar.blend blender/scripts/export_glb.py            # export/avatar.glb y avatar_uncompressed.glb
python3 tools/glb_inspect.py export/avatar.glb
```

Orden importante: `import_character.py` reconstruye `character.blend` desde cero, así que después hay que repetir `apply_chest_logo.py` y `add_face_parts.py`. `apply_chest_logo.py` es idempotente (parte siempre de `generated/character_texture_original.png`). `add_face_parts.py` también (borra lo que creó antes).

Pasos que usan Higgsfield (créditos) y no se repiten salvo que cambie el personaje: lámina del personaje (nano_banana_pro), malla rigueada (Meshy `multi_image_to_3d`), imágenes de la moto y la ventana, malla de la moto (`image_to_3d`). Los resultados están en `generated/`.

La pose sentada se calibra con `pose_probe.py` (12 renders de sonda) y vive en `poses.py`; `sit_test.py` la prueba dentro de la escena y sus funciones de colocación las reutiliza `assemble.py`.

## Huesos y clips

Huesos de deformación (convención tipo Rigify sin puntos):

`spine`, `spine001`, `spine002`, `spine003`, `spine005`, `spine006` (cabeza), `shoulderL/R`, `upper_armL/R`, `forearmL/R`, `handL/R`, `thighL/R`, `shinL/R`, `footL/R`, `toeL/R`, `eyelidL/R`, `eyebrow_L/R`. No hay dedos (el rig de Meshy no los trae).

Convenciones faciales: `eyelidL/R` girado +70° en X local = ojo cerrado; `eyebrow_L/R` desplazado +0.012 en Z local = ceja levantada.

Clips (24 fps), todos empiezan en el frame 1:

| Clip | Frames | Uso |
|---|---|---|
| `introAnimation` | 72 | una vez al cargar: de reclinado a teclear |
| `typing` | 48 | loop; solo brazos y manos |
| `idle` | 96 | loop; respiración (solo columna) |
| `Blink` | 240 | loop; dos parpadeos |
| `browup` | 18 | una vez; cejas arriba y vuelta |
| `vibe` | 120 | una vez; cabeceo rap con ojos cerrados |
| `lookAround` | 96 | una vez; mira a los lados y arriba |

Regla de mezcla: `idle` es la base continua; `typing` y `Blink` se superponen (huesos disjuntos); `vibe` y `lookAround` se reproducen en exclusiva (fundir `idle`/`typing` a 0 y volver); `browup` se superpone a todo. Solo `vibe` y `lookAround` mueven `spine006`.

Nodos útiles en el GLB: `spine006` (cabeza, para el seguimiento del cursor), `screen_left`, `screen_center`, `screen_right`, `screen_laptop` (pantallas: materiales con `emissiveTexture`, encenderlas subiendo `emissiveIntensity`), `rgb_bar_L`, `rgb_bar_R` (barras de luz, cambiar `emissive`), `moto_mini`, `seat_anchor`, `moto_anchor`. Los materiales `Character` y `Window_Far` también traen `emissiveTexture` (piel/ropa y ciudad de noche): no tratarlos como pantallas.

## Usar el GLB en three.js

El personaje mira hacia −Z (Y arriba). Una cámara equivalente a la de los renders de aprobación es `(-1.3, 1.95, -3.7)` mirando a `(0, 1.0, -0.6)`.

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

const draco = new DRACOLoader();
draco.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/');
const loader = new GLTFLoader().setDRACOLoader(draco);

new RGBELoader().load('night.hdr', (hdr) => {
  hdr.mapping = THREE.EquirectangularReflectionMapping;
  scene.environment = hdr;            // solo iluminación, fondo oscuro
});

loader.load('avatar.glb', (gltf) => {
  scene.add(gltf.scene);
  const head = gltf.scene.getObjectByName('spine006');
  const screens = ['screen_left', 'screen_center', 'screen_right', 'screen_laptop']
    .map((n) => gltf.scene.getObjectByName(n));
  screens.forEach((s) => { s.material = s.material.clone(); s.material.emissiveIntensity = 0; }); // luego fundir a 2.5
  const bars = ['rgb_bar_L', 'rgb_bar_R'].map((n) => gltf.scene.getObjectByName(n));            // ciclar bar.material.emissive

  const mixer = new THREE.AnimationMixer(gltf.scene);
  const act = Object.fromEntries(gltf.animations.map((c) => [c.name, mixer.clipAction(c)]));
  act.introAnimation.setLoop(THREE.LoopOnce).clampWhenFinished = true;
  act.introAnimation.play();
  mixer.addEventListener('finished', (e) => {
    if (e.action === act.introAnimation) ['idle', 'typing', 'Blink'].forEach((n) => act[n].reset().fadeIn(0.5).play());
  });
  // en el bucle de render: mixer.update(dt); después, girar `head` hacia el cursor (±30°, lerp 0.08)
});
```

`export/preview.html` contiene la versión completa (fundido de pantallas, ciclo de color de las barras, botones `vibe`/`browup`/`lookAround`, `vibe` automático y seguimiento del cursor). Para verlo: `tools/serve_preview.sh` y abrir <http://localhost:8765/preview.html>.

## Créditos Higgsfield

Registro en `generated/credits.log`. Saldo inicial 186; gastado en el proyecto ≈131 (láminas 10, mallas del personaje 70, moto e imágenes de ventana 8, malla de la moto 30, más ajustes de coste exacto del servicio). Balance final consultado: 54.8.

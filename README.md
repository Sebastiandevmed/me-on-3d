# Me on 3D — avatar 3D de Sebastián

Avatar cartoon de Sebastián sentado tecleando en su escritorio, dentro de una habitación cerrada (paredes, techo y piso) con Mac + tres monitores, barras RGB, repisa con soportes y mini Suzuki DR150, y Medellín de noche por la ventana. Listo para usar en una web con three.js. Estilo de referencia: [moncy.dev](https://www.moncy.dev/).

Entregables:

- `export/avatar.glb` — escena completa con Draco, 7 clips de animación, 47 663 triángulos, **3.81 MiB (3.9 MB en disco)** contra el `BUDGET` de 10 MiB de `export_glb.py`. Casi todo el peso son texturas, todas en JPEG: el atlas del personaje horneado a 4096 (`repack_uvs.py`, `CHAR_QUALITY = 92`), la ventana `medellin` a 1504 px sin reescalar vía `TEX_LIMITS`, el resto a 1024.
- `export/avatar_uncompressed.glb` — la misma escena sin Draco (depuración).
- `export/night.hdr` — entorno nocturno 1024×512 para la iluminación.
- `export/preview.html` + `tools/serve_preview.sh` — visor local de referencia (three.js).
- `blender/*.blend` — archivos fuente (se regeneran con los scripts; no se versionan).

## Carpetas

| Carpeta | Contenido |
|---|---|
| `blender/scripts/` | Pipeline completo por script para Blender headless (ver "Regenerar"). `checks/` contiene las verificaciones automáticas. |
| `blender/` | `scene.blend` (habitación + escritorio), `character.blend` (personaje rigueado + logo + material limpio + partes faciales + audífonos), `character_anim.blend` (+ animaciones), `avatar.blend` (todo ensamblado). También `landmarks.json` y `headphones.json`, versionados. |
| `refs/` | Referencias: frames de la cara (`face/`), foto de la moto y estilo (`style/`), logo de la empresa (`logo.png`). |
| `generated/` | Salidas intermedias (ignorado por git): láminas de Higgsfield, malla Meshy, texturas, renders de aprobación, `credits.log`. |
| `export/` | Entregables. Los `.glb` están ignorados por git; se regeneran con `export_glb.py`. |
| `tools/` | `run_blender.sh` (lanzador headless), `glb_inspect.py` (inspección de GLB), `screens/` (texturas de pantalla con Chrome headless), `serve_preview.sh`, `preview_probe.mjs` (sonda headless del visor con CDP). |
| `docs/` | Spec, plan y `HANDOFF.md` (estado del proyecto y decisiones). |

## Regenerar todo

Requisitos: Blender 4.x/5.x en `/Applications/Blender.app`, Google Chrome, Python 3 con Pillow, ffmpeg (solo para las tiras de animación).

```bash
B=tools/run_blender.sh
tools/screens/make_screens.sh                                   # texturas de las pantallas (usa refs/logo.png)
$B - blender/scripts/build_scene.py                               # blender/scene.blend (habitación + escritorio + repisa)
$B blender/scene.blend blender/scripts/checks/check_scene.py
$B - blender/scripts/import_character.py                          # blender/character.blend desde generated/meshy/character_rigged.glb
$B blender/character.blend blender/scripts/apply_chest_logo.py    # logo en el pecho (textura)
$B blender/character.blend blender/scripts/fix_character_material.py            # material y textura limpios (SIEMPRE después del logo)
$B blender/character.blend blender/scripts/checks/check_character_material.py
$B blender/character.blend blender/scripts/render_face_grid.py    # rejilla de verificación; blender/landmarks.json ya está calibrado
$B blender/character.blend blender/scripts/add_face_parts.py      # párpados, cejas y candongas con huesos (lee blender/landmarks.json)
$B blender/character.blend blender/scripts/hide_neck_headphones.py  # esconde los audífonos fundidos en el cuello (--probe para calibrar)
$B blender/character.blend blender/scripts/add_headphones.py      # audífonos como pieza aparte + hueso 'headphones' (escribe blender/headphones.json)
$B blender/character.blend blender/scripts/fix_head_weights.py    # la cabeza gira rígida: el cuello deja de pesar por encima de la barbilla (--probe para ver el defecto)
$B blender/character.blend blender/scripts/close_gaps.py          # cierra las rendijas de 0.5-3 mm entre islas de Meshy (rayas negras en cara/gorra/hoodie); renders gaps_before/after.png
$B blender/character.blend blender/scripts/repack_uvs.py          # suelda la malla, re-desenvuelve (Smart UV 66°) y hornea la textura a 4096 (quita las vetas de mipmap del visor)
$B blender/character.blend blender/scripts/fix_character_material.py            # SEGUNDA pasada: máscara y canales sobre el layout nuevo (PAD 32)
$B blender/character.blend blender/scripts/checks/check_character_material.py
$B blender/character.blend blender/scripts/texture_touchup.py     # borra las cejas pintadas (browup mostraba cuatro cejas) y las rayas de costura del horneado; renders touchup_face/browup.png
$B blender/character.blend blender/scripts/face_features.py       # cierra la barba sobre el mentón y pinta los labios (--probe / --flat para ver la cara)
$B blender/character.blend blender/scripts/smooth_normals.py      # normales alisadas desde una copia remallada (quita el look de plastilina sin mover vértices)
$B blender/character.blend blender/scripts/checks/check_rig.py    # después de add_face_parts y add_headphones: exige sus huesos y objetos
$B blender/character.blend blender/scripts/checks/check_face_export.py
$B blender/character.blend blender/scripts/animate.py             # blender/character_anim.blend (7 clips)
$B blender/character_anim.blend blender/scripts/checks/check_anim.py
$B - blender/scripts/render_hdr.py                                # export/night.hdr
$B - blender/scripts/assemble.py                                  # blender/avatar.blend (+ generated/renders/assembled_v1.png)
$B blender/avatar.blend blender/scripts/export_glb.py             # export/avatar.glb y avatar_uncompressed.glb
python3 tools/glb_inspect.py export/avatar.glb
node tools/preview_probe.mjs                                      # sonda del visor: PROBE errors [] + capturas preview_shot*.png
```

Atajo: **`tools/rebuild_character.sh`** ejecuta toda esta cadena (de `import_character.py` a `glb_inspect.py`) en el orden correcto y para al primer fallo. Hace falta siempre que se toque algo que vive ANTES del reempaquetado de UV — por ejemplo `apply_chest_logo.py`, que trabaja en el UV ORIGINAL de Meshy y por eso no se puede reejecutar sobre un `character.blend` ya reempaquetado.

Orden importante: `import_character.py` reconstruye `character.blend` desde cero, así que después hay que repetir `apply_chest_logo.py`, `fix_character_material.py`, `add_face_parts.py`, `hide_neck_headphones.py`, `add_headphones.py`, `fix_head_weights.py`, `close_gaps.py`, `repack_uvs.py`, otra vez `fix_character_material.py` (sobre el UV nuevo), `texture_touchup.py` y `smooth_normals.py`, en ese orden. `close_gaps.py` va ANTES de `repack_uvs.py` porque mueve vértices de borde y suelda (cambia la topología, y el desenvolvido depende de ella); si el .blend ya estaba reempaquetado, `repack_uvs.py -- --force` lo repite. `texture_touchup.py` y `face_features.py` van DESPUÉS de la segunda pasada de `fix_character_material.py` porque esa pasada regenera `character_texture_clean.png` desde cero y borraría el retoque (y `face_features.py` después de `texture_touchup.py`, que también reescribe esa textura). `repack_uvs.py` va DESPUÉS de `hide_neck_headphones.py` porque este selecciona por islas de la malla SIN soldar, y antes de la segunda pasada de `fix_character_material.py`, que rasteriza la máscara desde el UV activo (elige la textura de origen por `Body['uv_repacked']`, no por la existencia del archivo). `apply_chest_logo.py` va SIEMPRE antes que `fix_character_material.py` (el primero escribe `generated/character_texture_logo.png` y el segundo parte de ese archivo para producir `generated/character_texture_clean.png`; al revés, el logo repuntaría el material a la textura sucia). `add_face_parts.py` va antes que `hide_neck_headphones.py` porque los párpados se apoyan por raycast sobre la cara y el encogido del cuello no la toca. `apply_chest_logo.py` es idempotente (parte siempre de `generated/character_texture_original.png`) y `fix_character_material.py` también (parte siempre de `character_texture_logo.png`). `add_face_parts.py` y `add_headphones.py` borran lo que crearon antes; `hide_neck_headphones.py` se marca con la propiedad `Body['neck_headphones_hidden']` y no se aplica dos veces; `fix_head_weights.py` igual, con `Body['head_weights_fixed']`; `repack_uvs.py` con `Body['uv_repacked']` (guarda el UV de Meshy en el atributo de esquina `uv_meshy`, así que borrando la marca se puede repetir con otro ángulo) y `smooth_normals.py` con `Body['normals_smoothed']` (que `repack_uvs.py` borra porque la soldadura cambia la topología). `check_rig.py` y `check_face_export.py` van después porque exigen los huesos y objetos faciales y los de los audífonos.

Material del personaje: Meshy exporta `Character` como metal rugoso autoiluminado (Metallic 1, Roughness 1, Emission con la textura base, Specular Tint x2) y con relleno color piel entre las islas UV, que sangra en los bordes y se ve como motas claras sobre el hoodie negro. `fix_character_material.py` deja Metallic 0 / Roughness 0.85 / sin emisión / Specular Tint blanco (si no, el GLB sale con `KHR_materials_specular` y el hoodie brilla como plástico) y limpia la textura: dilata el color de cada isla 16 px sobre los canales y aplica una mediana 3×3 solo en los píxeles oscuros. `checks/check_character_material.py` mide la fracción de color piel MÁS ALLÁ del halo de 16 px (`skin_frac_far`, objetivo < 0.01) usando la máscara UV `generated/character_uv_mask.png`.

Audífonos: los que trae la malla de Meshy están fundidos alrededor del cuello, así que `hide_neck_headphones.py` los encoge hacia el eje del cuello (quedan escondidos dentro de la piel) y `add_headphones.py` modela una pieza aparte (`headphones_band`, `headphones_cup_L/R`) movida por el hueso `headphones`, hijo de `spine006`. Reposo = colgando del cuello; "puestos" = la rotación y la traslación que `add_headphones.py` escribe en `blender/headphones.json` (versionado) y que `poses.headphones_on()` lee. La región que se encoge se calibra con `hide_neck_headphones.py -- --probe`, que pinta la selección y renderiza `generated/renders/headphones_probe_*.png` sin guardar.

Landmarks de la cara: `blender/landmarks.json` está versionado y calibrado a mano (posición de ojos, cejas y lóbulos, tono de piel). `render_face_grid.py` solo escribe una versión automática (con las orejas en `[0,0,0]`) si el archivo no existe, y sirve para producir los renders con rejilla (`generated/renders/face_grid_*.png`) con los que se calibra. `add_face_parts.py` falla si falta una clave o si las orejas siguen en `[0,0,0]`.

Pasos que usan Higgsfield (créditos) y no se repiten salvo que cambie el personaje: lámina del personaje (nano_banana_pro), malla rigueada (Meshy `multi_image_to_3d`), imágenes de la moto y la ventana, malla de la moto (`image_to_3d`). Los resultados están en `generated/` (ver "Insumos irremplazables").
Si falta alguno, `build_scene.py` imprime `WARNING PLACEHOLDER ...` (y `check_scene.py` falla), y `assemble.py` falla al no encontrar la moto.

## Insumos irremplazables

`generated/` está ignorado por git, pero parte de su contenido salió de Higgsfield y NO se puede regenerar sin gastar créditos. Hay que respaldarlos aparte (copia fuera del repo o un bucket) antes de clonar en otra máquina:

| Archivo | Origen | Regenerable |
|---|---|---|
| `generated/meshy/character_rigged.glb` | Meshy `multi_image_to_3d` (70 créditos) | no |
| `generated/moto/dr150.glb` | Meshy `image_to_3d` (30 créditos) | no |
| `generated/window/medellin.png` | imagen Higgsfield | no |
| `generated/sheet/*` | láminas del personaje (nano_banana_pro) | no (son la fuente de la malla) |
| `generated/screens/*` | `tools/screens/make_screens.sh` (Chrome headless) | sí |
| `export/avatar.glb`, `export/avatar_uncompressed.glb` | `export_glb.py` | sí, pero también están ignorados: guardar una copia del entregable |

El registro de decisiones y reportes de tareas del proceso SDD vive en `.superpowers/` y es solo local (ignorado por git); el estado del proyecto para continuar está en `docs/HANDOFF.md`.

La pose sentada se calibra con `pose_probe.py` (12 renders de sonda) y vive en `poses.py`; `sit_test.py` la prueba dentro de la escena y sus funciones de colocación las reutiliza `assemble.py`.

## Huesos y clips

Huesos de deformación (convención tipo Rigify sin puntos):

`spine`, `spine001`, `spine002`, `spine003`, `spine005`, `spine006` (cabeza), `shoulderL/R`, `upper_armL/R`, `forearmL/R`, `handL/R`, `thighL/R`, `shinL/R`, `footL/R`, `toeL/R`, `eyelidL/R`, `eyebrow_L/R`, `headphones`. No hay dedos (el rig de Meshy no los trae). `headphones` es hijo de `spine006` con la misma cabeza, apunta a +Z y roll 0: en reposo los audífonos cuelgan del cuello y el estado "puestos" es la rotación/traslación local guardada en `blender/headphones.json` (`on_head.rotation_deg` ≈ (−70°, 0, 0), `on_head.location`). El skin del GLB incluye además dos articulaciones de deformación heredadas de Meshy, `headfront` y `head_end`, hijas de `spine006`: no las anima ningún clip, pero siguen a la cabeza y hay que dejarlas (tienen pesos).

Convenciones faciales: `eyelidL/R` girado +70° en X local = ojo cerrado; `eyebrow_L/R` desplazado +0.012 en Z local = ceja levantada.

Clips (24 fps), todos empiezan en el frame 1:

| Clip | Frames | Uso |
|---|---|---|
| `introAnimation` | 72 | una vez al cargar: de reclinado a teclear |
| `typing` | 48 | loop; solo brazos y manos |
| `idle` | 96 | loop; respiración (solo columna) |
| `Blink` | 240 | loop; dos parpadeos |
| `browup` | 18 | una vez; cejas arriba y vuelta |
| `vibe` | 216 | una vez; se pone los audífonos con las manos, cabecea con los ojos cerrados y se los quita |
| `lookAround` | 96 | una vez; mira a los lados y arriba |

Regla de mezcla: `idle` es la base continua; `typing` y `Blink` se superponen (huesos disjuntos); `vibe` y `lookAround` se reproducen en exclusiva (fundir `idle`/`typing` a 0 y volver); `browup` se superpone a todo. Solo `vibe` y `lookAround` mueven `spine006`, y solo `vibe` mueve `headphones` (lo verifica `export_glb.py`).

Nodos útiles en el GLB: `spine006` (cabeza, para el seguimiento del cursor), `spine003` (pecho, para acompañar el giro), `headphones` (hueso de los audífonos; si se gira la cabeza a mano hay que cancelar el giro aquí para que no se despeguen), `screen_left`, `screen_center`, `screen_right`, `screen_laptop` (pantallas: materiales con `emissiveTexture`, encenderlas subiendo `emissiveIntensity`), `rgb_bar_L`, `rgb_bar_R` (barras de luz, cambiar `emissive`), `moto_mini`, `seat_anchor`, `moto_anchor`, la habitación (`wall_back_L`, `wall_back_R`, `wall_back_top`, `wall_back_bottom`, `wall_left`, `wall_right`, `ceiling`, `floor`) y la ventana (`window_far`, `window_near`, `window_head`, `window_post_L/R`). El material `Window_Far` trae `emissiveTexture` (la ciudad de noche): no tratarlo como pantalla. El material `Character` YA NO trae emisión (`fix_character_material.py` la apaga), así que la piel y la ropa dependen solo de las luces de la escena.

## Usar el GLB en three.js

El personaje mira hacia −Z (Y arriba). Una cámara equivalente a la de los renders de aprobación es `(-1.3, 1.95, -3.7)` mirando a `(0, 1.0, -0.6)` con 38° de FOV vertical.

Tres cosas que cambian respecto a versiones anteriores del GLB:

- El material `Character` **ya no trae emisión** (`fix_character_material.py` la apaga y deja Metallic 0 / Roughness 0.85 / Specular Tint blanco): el personaje se ve solo con las luces de la escena, así que hace falta iluminarlo (el visor de referencia usa un spot azulado, un point cálido de techo, un `RectAreaLight` en la ventana, una hemisférica y luces puntuales por pantalla y por barra RGB).
- La textura de la ventana (`medellin`) se exporta a **1504 px de ancho sin reescalar** (ocupa media pantalla; el resto de texturas van a 1024 y la del personaje a 2048).
- El visor de referencia **enciende sombras** (`renderer.shadowMap.enabled = true`, `PCFSoftShadowMap`) y excluye de `castShadow` a las pantallas, el plano de la vista de Medellín (`window_far`), el piso, el techo y las paredes; el marco de la ventana (`window_near`, `window_head`, `window_post_*`) sí proyecta sombra. Si no se encienden, la habitación se ve plana.


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

  renderer.shadowMap.enabled = true;           // sin sombras la habitación se ve plana
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = !/^(screen_|window_far|floor|ceiling|wall_)/.test(o.name);
    o.receiveShadow = !/^(screen_|window_far)/.test(o.name);
  });

  const mixer = new THREE.AnimationMixer(gltf.scene);
  const act = Object.fromEntries(gltf.animations.map((c) => [c.name, mixer.clipAction(c)]));
  act.introAnimation.setLoop(THREE.LoopOnce).clampWhenFinished = true;
  act.introAnimation.play();
  mixer.addEventListener('finished', (e) => {
    if (e.action === act.introAnimation) ['idle', 'typing', 'Blink'].forEach((n) => act[n].reset().fadeIn(0.5).play());
  });
  // en el bucle de render: mixer.update(dt); después, girar `head` (y `spine003` un 30%) hacia el cursor
  // (yaw ±45°, pitch −20°/+25°; ver YAW_MAX / PITCH_UP / PITCH_DOWN en preview.html).
  // Los audífonos cuelgan del hueso 'headphones', hijo de la cabeza: tras girarla hay que premultiplicar
  // hp.quaternion por (head_nuevo^-1 · head_viejo) para que no se despeguen del cuello.
});
```

`export/preview.html` contiene la versión completa (luces y sombras de la habitación, fundido de pantallas, ciclo de color de las barras, botones `vibe`/`browup`/`lookAround`, `vibe` automático, clic sobre el personaje = `vibe` y seguimiento del cursor con cabeza + pecho). Para verlo: `tools/serve_preview.sh` y abrir <http://localhost:8765/preview.html>.

`node tools/preview_probe.mjs` lo abre en Chrome headless (CDP) y falla (salida 1 con `PROBE FAIL ...`) si el visor no carga, si hay errores de página (`PROBE errors []`), si el nodo `headphones` no llega del GLB (`hpQ` null), si no hay sombras, si no hay 9 luces o si la cabeza no gira al mover el cursor (distancia entre cuaterniones < 0.1). Guarda `generated/renders/preview_shot.png`, `preview_shot_look.png` (cabeza girada hacia el cursor) y `preview_shot_vibe.png` (audífonos subiendo). La sonda desactiva el caché HTTP: el perfil de Chrome sobrevive entre corridas y, sin eso, mide un `avatar.glb` viejo.

## Créditos Higgsfield

Registro en `generated/credits.log`. Saldo inicial 186; gastado en el proyecto ≈131 (láminas 10, mallas del personaje 70, moto e imágenes de ventana 8, malla de la moto 30, más ajustes de coste exacto del servicio). Balance final consultado: 54.8.

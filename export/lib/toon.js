// Cel-shading del avatar: materiales por bandas + luz de borde + paleta de luces.
//
// Por que toon y no PBR: la malla del personaje viene de Meshy (IA) y tiene rendijas
// residuales, cara abollada y gorra facetada. El sombreado PBR con night.hdr los ILUMINA
// y los subraya; el sombreado por bandas los aplana y el defecto deja de leerse.
//
// Por que MeshToonMaterial y no un ShaderMaterial propio: hereda gratis skinning, sombras,
// niebla y mapas del pipeline de three, que es justo lo que el personaje necesita (es un
// SkinnedMesh con 7 clips y recibe la sombra de la key).
import * as THREE from 'three';

// Rampa de bandas para el gradientMap: una fila de N texeles con NearestFilter, o sea que
// dot(N,L) cae en un escalon y no interpola. 3 bandas = sombra / medio / luz.
export function bandRamp(stops = [0.35, 0.72, 1.0]) {
  const data = new Uint8Array(stops.length * 4);
  stops.forEach((v, i) => {
    const c = Math.round(Math.max(0, Math.min(1, v)) * 255);
    data[i * 4] = data[i * 4 + 1] = data[i * 4 + 2] = c; data[i * 4 + 3] = 255;
  });
  const t = new THREE.DataTexture(data, stops.length, 1, THREE.RGBAFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.generateMipmaps = false; t.needsUpdate = true;
  return t;
}

// Luz de borde (fresnel) sumada al color final del fragmento. Es lo que despega al personaje
// del fondo oscuro SIN depender de la geometria: no hay halo de malla, es puro sombreado.
// Se inyecta antes de <opaque_fragment>, donde meshtoon_frag ya tiene `outgoingLight`,
// `normal` (de normal_fragment_begin) y `vViewPosition`.
function injectRim(mat, { color = 0x9fc4ff, power = 3.2, strength = 0.14 } = {}) {
  const uni = { rimColor: { value: new THREE.Color(color) }, rimPower: { value: power }, rimStrength: { value: strength } };
  mat.userData.rimUniforms = uni;
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uni);
    shader.fragmentShader = 'uniform vec3 rimColor;\nuniform float rimPower;\nuniform float rimStrength;\n' + shader.fragmentShader.replace(
      '#include <opaque_fragment>',
      `{ float rimF = 1.0 - clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0);
         outgoingLight += rimColor * pow(rimF, rimPower) * rimStrength; }
       #include <opaque_fragment>`);
  };
  // Sin esto three reusa el programa cacheado del toon SIN la inyeccion (misma cache key).
  mat.customProgramCacheKey = () => 'toon-rim';
}

// Cambia los materiales de root a toon conservando textura y color. Devuelve un `undo()`
// que restaura los originales, para que ?fx=off compare contra el look anterior EXACTO.
//
// skip: expresion regular de nombres que NO se convierten. Por omision pantallas y barras
// RGB, que son paneles emisivos: el bucle de animacion muta su material clonado (emissive,
// emissiveIntensity) y ademas son la fuente del bloom, que necesita valores > 1 en lineal.
export function applyToon(root, { bands, skip = /^(screen_|rgb_bar_)/, rim = {}, rimSkip = /^(wall_|ceiling|floor|window_far)/ } = {}) {
  const ramp = bandRamp(bands);
  const saved = [];
  root.traverse((o) => {
    if (!o.isMesh || !o.material || Array.isArray(o.material) || skip.test(o.name)) return;
    const old = o.material;
    saved.push([o, old]);
    const m = new THREE.MeshToonMaterial({
      map: old.map || null,
      color: old.color ? old.color.clone() : new THREE.Color(0xffffff),
      gradientMap: ramp,
      side: THREE.FrontSide,   // la malla de Meshy son islas: con doubleSided el interior asoma por las rendijas
      transparent: old.transparent, opacity: old.opacity, alphaTest: old.alphaTest,
      alphaMap: old.alphaMap || null,
      emissive: old.emissive ? old.emissive.clone() : new THREE.Color(0x000000),
      emissiveMap: old.emissiveMap || null,
      emissiveIntensity: old.emissiveIntensity ?? 1,
    });
    m.name = old.name + '_toon';
    // El rim en paredes/techo/suelo delata que son cajas: solo lo llevan los objetos.
    if (!rimSkip.test(o.name)) injectRim(m, rim);
    o.material = m;
  });
  return () => { for (const [o, old] of saved) o.material = old; };
}

// Paleta de luces para cel. Sin esto vuelve el morado del intento anterior (?mat=toon):
// las luces de la escena son azules (key 0xcfe0ff, ventana 0x8fb8ff, hemisferica 0x33405c)
// y un hoodie casi negro multiplicado por luz azul sin base ambiental da morado.
//
// Tres cambios: (1) base ambiental calida fuerte para que la textura se lea en la zona en
// sombra, (2) la key baja y se vuelve neutra — con bandas ya no hace falta intensidad para
// modelar, solo para marcar el escalon — y (3) la ventana pasa de RectAreaLight a
// direccional porque RectAreaLight NO ilumina MeshToonMaterial (solo Standard/Physical).
// Los niveles salen del barrido de la fase 1 (tools/look_sweep.mjs, variante u3). Ojo con
// dos trampas que costaron varias pasadas:
//  - el hoodie es casi negro y es lo primero que se lava: con ambiental 0.85 y key 16 el
//    personaje salia blanco entero;
//  - las puntuales de las pantallas estan a ~0.5 m de la cara y con decay 2 le pegan con
//    fuerza efectiva ~6, o sea que la piel se quemaba aunque estas luces estuvieran bajas.
//    Se atenuan aparte en el visor (LIT.screen), no aqui.
export function toonLights(scene, refs, opts = {}) {
  const added = [];
  const before = {};

  const amb = new THREE.AmbientLight(0xffeedd, opts.ambient ?? 0.30); scene.add(amb); added.push(amb);
  const winDir = new THREE.DirectionalLight(0x9fc4ff, opts.window ?? 0.40);   // reemplazo de la RectAreaLight de la ventana
  winDir.position.set(-0.3, 1.8, 2.6); winDir.target.position.set(-0.3, 1.1, 0);
  scene.add(winDir, winDir.target); added.push(winDir);

  if (refs.key) { before.key = { intensity: refs.key.intensity, color: refs.key.color.clone() }; refs.key.intensity = opts.key ?? 8; refs.key.color.set(0xfff4e8); }
  if (refs.win) { before.win = { intensity: refs.win.intensity }; refs.win.intensity = 0; }   // no ilumina toon; su trabajo lo hace winDir
  if (refs.hemi) { before.hemi = { intensity: refs.hemi.intensity }; refs.hemi.intensity = opts.hemi ?? 0.15; }
  if (refs.ceil) { before.ceil = { intensity: refs.ceil.intensity }; refs.ceil.intensity = opts.ceil ?? 3; }

  return () => {
    for (const l of added) scene.remove(l);
    if (before.key) { refs.key.intensity = before.key.intensity; refs.key.color.copy(before.key.color); }
    if (before.win) refs.win.intensity = before.win.intensity;
    if (before.hemi) refs.hemi.intensity = before.hemi.intensity;
    if (before.ceil) refs.ceil.intensity = before.ceil.intensity;
  };
}

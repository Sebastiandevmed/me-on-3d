// Motor del avatar: escena, luces, carga del GLB, mezcla de clips, seguimiento de cursor y
// bucle de dibujo. Es el mismo codigo que vivia dentro de preview.html; se saco aqui para que
// el arnes de depuracion (preview.html) y la landing (index.html) compartan UNA sola
// implementacion. Todo lo que es de depuracion (los ?mat=, el panel de FPS) se queda fuera.
//
// Coordenadas glTF (x, y, z) = Blender (x, z, -y). El personaje se sienta en el origen y mira
// a -Z; escritorio y monitores en z ~ -1.0..-1.35, ventana y barras RGB en z ~ +1.7.
//
// Contrato con las sondas: el objeto devuelto trae `status`, `follow`, `vibe()`, `browup()` e
// `inkFrac()`. preview.html los publica como window.__status / __view / __vibe / __inkFrac,
// que es lo que afirma tools/preview_probe.mjs. No cambiar esos nombres sin tocar la sonda.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { applyToon, toonLights } from './toon.js';
import { createComposer } from './postfx.js';
import { applyWindowGlass } from './glass.js';
import { addGraffiti } from './graffiti.js';

// Camara de aprobacion de la sesion 2: Blender (-1.3, 3.7, 1.95) mirando a (0, 0.6, 1.0).
// Lente 35 mm ~ 38 grados verticales.
export const CAM_POS = [-1.3, 1.95, -3.7], CAM_TGT = [0, 1.0, -0.6];

/** three r170 ya no soporta WebGL1: sin contexto webgl2 el constructor del renderer LANZA.
 *  La landing pregunta antes de construir nada para poder servir la version plana. */
export function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGL2RenderingContext && c.getContext('webgl2'));
  } catch { return false; }
}

/**
 * @param {object} opts
 *   container    donde se cuelga el canvas (por omision document.body)
 *   query        URLSearchParams con los interruptores de depuracion (por omision los de la URL)
 *   assets       prefijo de avatar.glb y night.hdr (por omision './')
 *   controls     true = OrbitControls (arnes); false = la camara la mueve quien llama (landing)
 *   autoVibe     vibe solo cada 30-50 s
 *   pointerVibe  clic sobre el personaje = vibe
 *   followMouse  true = escucha mousemove global; false = el llamador usa setMouse()
 *   onReady(api) se llama una vez cargado el GLB y montados los materiales
 *   onProgress(f) fraccion 0..1 de la carga del GLB (para la pantalla de carga de la landing)
 *   onError(err)  la carga fallo: quien llama decide el plan B (la landing cae a version plana)
 *   pointerTarget donde se escucha el clic (por omision el canvas). La landing pasa document
 *                 porque su canvas vive DEBAJO del contenido y nunca recibiria el clic.
 *   bustCache    true = ?v=<ahora> en los assets (solo el arnes, para no ver el GLB viejo)
 */
export function createAvatarScene(opts = {}) {
  const container = opts.container || document.body;
  const Q = opts.query || new URLSearchParams(location.search);
  const BASE_URL = opts.assets ?? './';
  const useControls = opts.controls !== false;
  // El arnes regenera el GLB cada rato y python http.server no manda Cache-Control, asi que ahi
  // hace falta romper el cache. En la landing NO: son 4 MB que el visitante volveria a bajar
  // en cada visita.
  const VER = opts.bustCache ? '?v=' + Date.now() : '';

  // ---- interruptores del look. ?fx=off vuelve al PBR anterior completo; ?toon=0 / ?outline=0 /
  // ?bloom=0 / ?vignette=0 apagan una pieza cada uno para comparar.
  const flag = (n) => Q.get(n) !== '0' && Q.get(n) !== 'off';
  const FX = { on: flag('fx'), toon: flag('fx') && flag('toon'), outline: flag('fx') && flag('outline'),
               bloom: flag('fx') && flag('bloom'), vignette: flag('fx') && flag('vignette') };
  // Todos los numeros del look son ajustables por query para barrerlos con la sonda sin tocar
  // el codigo: ?amb=.3&key=7&rim=.14&nbias=1.25&bloomt=1.05&exp=1.15 ...
  const num = (n, d) => (Q.has(n) ? parseFloat(Q.get(n)) : d);
  // Las puntuales de pantallas y barras estan a ~0.5 m de la cara. En toon pegan mucho mas
  // fuerte que en PBR (no hay rugosidad que reparta la energia ni entorno que compense) y
  // quemaban la piel a blanco puro: se atenuan solo en modo cel.
  const LIT = { screen: num('slit', FX.toon ? 0.30 : 1), bar: num('blit', FX.toon ? 0.70 : 1) };
  const LOOK = {
    lights: { ambient: num('amb', undefined), key: num('key', undefined), window: num('win', undefined), hemi: num('hemi', undefined), ceil: num('ceil', undefined) },
    rim: { strength: num('rim', undefined), power: num('rimp', undefined) },
    fx: { thickness: num('thick', undefined), depthBias: num('dbias', undefined), depthMin: num('dmin', undefined), normalBias: num('nbias', undefined),
          strength: num('ostr', undefined), ramp: num('oramp', undefined), bloomStrength: num('bloomstr', undefined),
          bloomThreshold: num('bloomt', undefined), vignetteDarkness: num('vign', undefined) },
  };
  // Sensibilidad a tinta de las mallas de Meshy (personaje y moto). Sus normales traen ruido de
  // alta frecuencia y el contorno lo entintaba como rayones que ademas parpadeaban al animar; el
  // resto de la escena son cajas de Blender y se quedan en 1, donde los pliegues se leen.
  // ?isens=1 devuelve el comportamiento anterior para comparar.
  const INK_SENS = num('isens', 0.2), MESHY = /^(Body|Mesh_0)$/;
  const inkSensitivity = (o) => (MESHY.test(o.name) ? INK_SENS : 1);

  const status = { loaded: false, env: false, fps: 0, frames: 0, screen: 0, exclusive: null, clips: () => '',
    headQ: () => follow.head && follow.head.quaternion.toArray(), neckQ: () => follow.neck && follow.neck.quaternion.toArray(),
    chestQ: () => follow.chest && follow.chest.quaternion.toArray(), hpQ: () => follow.hp && follow.hp.quaternion.toArray(),
    barHex: () => bars[0] && bars[0].material.emissive.getHexString() };

  const size = () => (container === document.body
    ? { w: innerWidth, h: innerHeight }
    : { w: container.clientWidth || innerWidth, h: container.clientHeight || innerHeight });
  let { w: W, h: H } = size();

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: Q.has('pdb') });
  renderer.setPixelRatio(Math.min(devicePixelRatio, opts.maxPixelRatio ?? 2));
  renderer.setSize(W, H);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  container.appendChild(renderer.domElement);
  { const gl = renderer.getContext(), d = gl.getExtension('WEBGL_debug_renderer_info'); status.gpu = d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : '?'; }   // que GPU/driver dibuja (la sonda lo imprime)

  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x05060a);
  const camera = new THREE.PerspectiveCamera(38, W / H, 0.05, 100);
  const camTarget = new THREE.Vector3(...CAM_TGT);

  let controls = null;
  if (useControls) {
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.minDistance = 0.6; controls.maxDistance = 12;
  }
  const resetCamera = () => {
    camera.position.set(...CAM_POS);
    camTarget.set(...CAM_TGT);
    if (controls) { controls.target.copy(camTarget); controls.update(); } else camera.lookAt(camTarget);
  };
  resetCamera();

  // ---- luces
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMappingExposure = num('exp', 1.15);
  RectAreaLightUniformsLib.init();
  const lights = [];
  const key = new THREE.SpotLight(0xcfe0ff, 40, 0, Math.PI / 3.4, 0.7, 2);   // key azulada desde arriba-izquierda, con sombra
  key.position.set(-1.2, 2.5, -2.3); key.target.position.set(...CAM_TGT);
  key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
  key.shadow.camera.near = 0.5; key.shadow.camera.far = 12;
  if (Q.has('nb')) key.shadow.normalBias = parseFloat(Q.get('nb'));
  if (Q.has('bias')) key.shadow.bias = parseFloat(Q.get('bias'));
  if (Q.get('shadow') === 'off') key.castShadow = false;   // pruebas con la sonda
  scene.add(key, key.target); lights.push(key);
  const ceil = new THREE.PointLight(0xffe0c0, 6, 7, 2); ceil.position.set(0.6, 2.6, 0.2); scene.add(ceil); lights.push(ceil);   // calida del techo
  const win = new THREE.RectAreaLight(0x8fb8ff, 5, 3.2, 1.8); win.position.set(-0.3, 1.5, 1.7); win.lookAt(-0.3, 1.2, 0); scene.add(win); lights.push(win);
  const hemi = new THREE.HemisphereLight(0x33405c, 0x0b0b0e, 0.5); scene.add(hemi);
  // luz de las pantallas (se enciende con el fundido) y de las barras RGB (siguen el ciclo de color)
  const SCREEN_POS = { screen_left: [-0.6, 0.95, -1.35], screen_center: [0, 0.95, -1.35], screen_right: [0.6, 0.95, -1.35], screen_laptop: [0, 0.9, -1.0] };
  const screenLights = {};
  for (const [n, p] of Object.entries(SCREEN_POS)) { const l = new THREE.PointLight(0xbfd4ff, 0, 2.2, 2); l.position.set(...p); scene.add(l); screenLights[n] = l; lights.push(l); }
  const barLights = [];
  for (const x of [-1.05, 1.05]) { const l = new THREE.PointLight(0x4090ff, 3 * LIT.bar, 4, 2); l.position.set(x, 1.3, 1.2); scene.add(l); barLights.push(l); lights.push(l); }
  if (FX.toon) toonLights(scene, { key, ceil, win, hemi }, LOOK.lights);   // ver lib/toon.js: +ambiental y +direccional de ventana
  status.lights = lights.length + (FX.toon ? 2 : 0); status.shadows = true;

  // Cadena de post-proceso. El contorno es lo que convierte el render en ilustracion; el bloom
  // solo prende monitores y barras RGB.
  const composer = FX.on ? createComposer(renderer, scene, camera, { outline: FX.outline, bloom: FX.bloom, vignette: FX.vignette, sensitivity: inkSensitivity, ...LOOK.fx }) : null;
  status.fx = { ...FX, passes: composer ? composer.passes.length : 0 };

  new RGBELoader().load(BASE_URL + 'night.hdr' + VER, (t) => { t.mapping = THREE.EquirectangularReflectionMapping; scene.environment = t; scene.environmentIntensity = 0.5; status.env = true; },
    undefined, (e) => console.error('night.hdr: ' + (e.message || e)));

  const draco = new DRACOLoader(); draco.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/');
  const loader = new GLTFLoader(); loader.setDRACOLoader(draco);

  let mixer = null, actions = {}, screens = [], bars = [], character = null, glass = null, graffiti = null;
  const clock = new THREE.Clock();
  const mouse = { x: 0, y: 0 };
  const ray = new THREE.Raycaster();

  // ---- mezcla de clips ----
  // idle = base continua; typing y Blink se superponen (huesos disjuntos); browup se superpone a
  // todo. vibe / lookAround / intro son EXCLUSIVOS: apagan idle+typing (vibe tambien Blink),
  // corren una vez y luego vuelve la base.
  const BASE = ['idle', 'typing', 'Blink'];
  const EXCLUSIVE = { vibe: { fade: 0.5, dropBlink: true }, lookAround: { fade: 0.4, dropBlink: false }, introAnimation: { fade: 0.5, dropBlink: false } };
  let exclusive = null;            // nombre del clip exclusivo en curso
  let screensOnAt = Infinity;      // instante (performance.now) en que empieza el fundido de las pantallas

  const playLoop = (n, fade = 0.5) => { const a = actions[n]; if (!a) return; undoFollow(); a.enabled = true; a.setLoop(THREE.LoopRepeat, Infinity); a.clampWhenFinished = false; a.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(fade).play(); };
  const playOnce = (n, fade, cb) => {
    const a = actions[n]; if (!a) return;
    undoFollow(); a.enabled = true; a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true;
    a.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(fade).play();
    const onEnd = (e) => { if (e.action === a) { mixer.removeEventListener('finished', onEnd); cb && cb(); } };
    mixer.addEventListener('finished', onEnd);
  };
  const startBase = (fade, skipBlink = false) => { for (const n of BASE) { if (skipBlink && n === 'Blink') continue; if (actions[n] && !actions[n].isRunning()) playLoop(n, fade); } };
  // fadeOut arranca desde 1: fijar el peso actual evita un salto si se pide en mitad de un fadeIn
  const stopBase = (fade, dropBlink) => { for (const n of BASE) { if (n === 'Blink' && !dropBlink) continue; if (actions[n] && actions[n].isRunning()) { const a = actions[n]; a.setEffectiveWeight(a.getEffectiveWeight()); a.fadeOut(fade); } } };
  const playExclusive = (n) => {
    if (exclusive || !actions[n]) return false;
    const cfg = EXCLUSIVE[n]; exclusive = n;
    stopBase(cfg.fade, cfg.dropBlink);
    playOnce(n, cfg.fade, () => { actions[n].fadeOut(cfg.fade); startBase(cfg.fade); exclusive = null; });
    return true;
  };
  const vibe = () => playExclusive('vibe');
  const browup = () => { const a = actions.browup; if (!a || a.isRunning()) return; playOnce('browup', 0.1, () => a.fadeOut(0.15)); };

  loader.load(BASE_URL + 'avatar.glb' + VER, (gltf) => {
    scene.add(gltf.scene);
    gltf.scene.traverse(o => {
      if (o.isMesh) { o.frustumCulled = false; o.castShadow = !/^(screen_|window_far|window_glass|floor|ceiling|wall_)/.test(o.name); o.receiveShadow = !/^(screen_|window_far|window_glass)/.test(o.name); }
      if (/^screen_/.test(o.name) && o.isMesh) screens.push(o);
      if (/^rgb_bar_/.test(o.name) && o.isMesh) bars.push(o);
      if (o.name === 'spine006') follow.head = o;
      if (o.name === 'spine005') follow.neck = o;
      if (o.name === 'spine003') follow.chest = o;
      if (o.name === 'headphones') follow.hp = o;
      if (o.name === 'Body') character = o;
      if (o.isMesh && o.material && o.material.map) { o.material.map.anisotropy = renderer.capabilities.getMaxAnisotropy(); o.material.map.needsUpdate = true; }   // texturas nitidas en escorzo
    });
    // Cel-shading. Pantallas y barras RGB quedan fuera: son paneles emisivos que el bucle de
    // animacion muta y que alimentan el bloom. Conserva el `map` (y por tanto la anisotropia).
    if (FX.toon) applyToon(gltf.scene, { rim: LOOK.rim });
    // Vidrio de la ventana. Va DESPUES de applyToon: el plano no debe volverse toon (es aditivo).
    glass = Q.get('glass') === '0' ? null : applyWindowGlass(gltf.scene, {
      bandStrength: num('gband', undefined), fresnelStrength: num('gfres', undefined),
    });
    status.glass = !!glass;
    // Grafiti del nombre con paneles de neon (lib/graffiti.js). Va fuera de gltf.scene y despues
    // de applyToon: la calcomania es Standard a proposito (emisivo propio para el bloom).
    // ?graffiti=0 lo quita; ?gwall=back lo pasa a la pared trasera; ?gglow= ?glit= ?gsize= ?gdepth= ?gink= calibran.
    graffiti = Q.get('graffiti') === '0' ? null : addGraffiti(scene, {
      base: BASE_URL, ver: VER, wall: Q.get('gwall') || 'side',
      size: num('gsize', undefined), glow: num('gglow', undefined), light: num('glit', undefined), depth: num('gdepth', undefined), ink: num('gink', undefined),
      maxAnisotropy: renderer.capabilities.getMaxAnisotropy(),
    });
    status.graffiti = graffiti ? graffiti.wall : null;
    if (graffiti) status.lights += graffiti.lights.length;
    saveFollow();
    mixer = new THREE.AnimationMixer(gltf.scene);
    for (const clip of gltf.animations) actions[clip.name] = mixer.clipAction(clip);
    status.loaded = true;
    status.clips = () => Object.entries(actions).filter(([, a]) => a.isRunning()).map(([n, a]) => n + (a.getEffectiveWeight() < 0.99 ? '(' + a.getEffectiveWeight().toFixed(2) + ')' : '')).join(' + ') || '—';
    // intro una vez, luego fundido a idle + typing + Blink
    if (actions.introAnimation) playExclusive('introAnimation'); else startBase(0.3);
    // pantallas: apagadas al cargar, fundido de encendido hasta 2.5
    screens.forEach(s => { s.material = s.material.clone(); s.material.emissiveIntensity = 0; });
    screensOnAt = performance.now() + 1500;   // el fundido se aplica en animate()
    bars.forEach(b => { b.material = b.material.clone(); });
    if (opts.autoVibe !== false) { const schedule = () => setTimeout(() => { vibe(); schedule(); }, 30000 + Math.random() * 20000); schedule(); }
    if (opts.pointerVibe !== false) {
      const tgt = opts.pointerTarget || renderer.domElement;
      let downAt = null;
      tgt.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
      tgt.addEventListener('pointerup', (e) => {
        if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return;   // fue un arrastre de la camara
        if (e.target && e.target.closest && e.target.closest('a,button,input,textarea')) return;   // el clic era para la pagina
        ray.setFromCamera(new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
        if (character && ray.intersectObject(character, true).length) vibe();
      });
    }
    opts.onReady && opts.onReady(api);
  }, (e) => { opts.onProgress && e.total && opts.onProgress(e.loaded / e.total); },
     (err) => { console.error('avatar.glb: ' + (err.message || err)); opts.onError && opts.onError(err); });

  // ---- seguimiento de cursor: la cabeza MIRA al punto 3D del cursor (a la profundidad de la
  // cabeza). El giro se reparte por la columna para que no parezca una cabeza rigida sobre un
  // cuello tieso: pecho (spine003) y cuello (spine005) ponen parte del yaw, la cabeza (spine006)
  // el resto. Como cada hueso es hijo del anterior, las partes se suman en mundo. El nodo
  // headphones (hijo de la cabeza, audifonos colgando del cuello) cancela el giro para no
  // columpiarse. Se aplica DESPUES del mixer y se deshace antes del siguiente update (los clips
  // base no escriben estos huesos cada frame).
  // Limites cortos y giro parcial: a 45/25/20 grados la cara se deformaba (la barba se hundia en
  // el collar al mirar abajo y el cuello se retorcia a los lados).
  const YAW_MAX = Math.PI / 6.4, PITCH_UP = Math.PI / 15, PITCH_DOWN = Math.PI / 20;   // 28 / 12 / 9 grados
  const GAIN = 0.6;            // fraccion del angulo geometrico que recorre la cabeza
  const TAU = 0.35;            // s: constante de tiempo del suavizado (independiente del framerate)
  const DEAD = 0.02;           // rad: zona muerta para que el temblor del mouse no mueva la cabeza
  // El cuello NO recibe pitch: el collar y la capucha llevan ~30 % de peso de spine005 y al
  // cabecear con el cuello la cabeza se hunde en el collar.
  const SHARE = { chest: { yaw: 0.25, pitch: 0 }, neck: { yaw: 0.2, pitch: 0 } };   // la cabeza pone lo que falta hasta 1
  const follow = { head: null, neck: null, chest: null, hp: null };   // Object3D
  const saved = { head: null, neck: null, chest: null, hp: null };    // cuaternion tal como lo dejan los clips
  const look = { yaw: 0, pitch: 0 };
  let followWeight = 0;
  const undoFollow = () => { for (const k in follow) if (follow[k] && saved[k]) follow[k].quaternion.copy(saved[k]); };
  const saveFollow = () => { for (const k in follow) if (follow[k]) saved[k] = (saved[k] || new THREE.Quaternion()).copy(follow[k].quaternion); };
  const vHead = new THREE.Vector3(), vTarget = new THREE.Vector3(), vDir = new THREE.Vector3(), vCam = new THREE.Vector3();
  const qParent = new THREE.Quaternion(), qTmp = new THREE.Quaternion(), qW = new THREE.Quaternion(), qHeadOld = new THREE.Quaternion(), qPitch = new THREE.Quaternion();
  const AX_X = new THREE.Vector3(1, 0, 0), AX_Y = new THREE.Vector3(0, 1, 0);
  function worldRotate(obj, q, weight) {   // newLocal = parent^-1 * slerp(I, q, w) * parent * local
    obj.parent.getWorldQuaternion(qParent);
    qW.identity().slerp(q, weight);
    qTmp.copy(qParent).invert().multiply(qW).multiply(qParent);   // parent^-1 * qW * parent
    obj.quaternion.premultiply(qTmp);
  }
  function applyHeadFollow(dt) {
    const active = !(exclusive === 'vibe' || exclusive === 'lookAround');
    followWeight += ((active ? 1 : 0) - followWeight) * (1 - Math.exp(-dt / 0.4));
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
      const ty = Math.max(-YAW_MAX, Math.min(YAW_MAX, yaw * GAIN)), tp = Math.max(-PITCH_DOWN, Math.min(PITCH_UP, pitch * GAIN));
      const k = 1 - Math.exp(-dt / TAU);   // suavizado exponencial por tiempo, no por frame
      if (Math.abs(ty - look.yaw) > DEAD) look.yaw += (ty - look.yaw) * k;
      if (Math.abs(tp - look.pitch) > DEAD) look.pitch += (tp - look.pitch) * k;
    }
    if (followWeight < 0.001) return;
    let yawLeft = 1, pitchLeft = 1;
    for (const k of ['chest', 'neck']) {
      if (!follow[k]) continue;
      qPitch.setFromAxisAngle(AX_X, look.pitch * SHARE[k].pitch);
      qTmp.setFromAxisAngle(AX_Y, look.yaw * SHARE[k].yaw).multiply(qPitch);
      worldRotate(follow[k], qTmp, followWeight);
      yawLeft -= SHARE[k].yaw; pitchLeft -= SHARE[k].pitch;
    }
    // pecho y cuello ya giraron: la cabeza aplica el resto (la cabeza es hija, se compone igual)
    qHeadOld.copy(follow.head.quaternion);
    qPitch.setFromAxisAngle(AX_X, look.pitch * pitchLeft);
    qTmp.setFromAxisAngle(AX_Y, look.yaw * yawLeft).multiply(qPitch);
    worldRotate(follow.head, qTmp, followWeight);
    if (follow.hp) {   // conservar el mundo: hp_local = head_new^-1 * head_old * hp_old
      qTmp.copy(follow.head.quaternion).invert().multiply(qHeadOld);
      follow.hp.quaternion.premultiply(qTmp);
    }
  }

  // ---- entradas y tamano
  const setMouse = (x, y) => { mouse.x = x; mouse.y = y; };
  // pointermove y no mousemove: en un telefono no hay raton, pero arrastrar el dedo si mueve la
  // cabeza, que es la unica forma de que el seguimiento exista en movil.
  if (opts.followMouse !== false) addEventListener('pointermove', e => setMouse((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), { passive: true });
  const setSize = (w, h) => { W = w; H = h; camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h); if (composer) composer.setSize(w, h); };
  addEventListener('resize', () => { const s = size(); setSize(s.w, s.h); });

  // ?pdb=1: densidad de LINEAS de tinta (pixeles mas oscuros que sus dos vecinos).
  // No sirve contar pixeles oscuros a secas: la escena es nocturna y ya tiene ~58 % casi negro,
  // asi que esa medida satura. A escala 1:1 el contorno mide 1-1.5 px y al reducir la imagen se
  // difumina y deja de contarse, por eso se mide a 1600 px como maximo.
  const inkFrac = () => {
    const W2 = Math.min(1600, renderer.domElement.width), H2 = Math.round(W2 * renderer.domElement.height / renderer.domElement.width), D = 2, TH = 14;
    const c = document.createElement('canvas'); c.width = W2; c.height = H2;
    const g = c.getContext('2d', { willReadFrequently: true });
    g.drawImage(renderer.domElement, 0, 0, W2, H2);
    const d = g.getImageData(0, 0, W2, H2).data;
    const lum = new Float32Array(W2 * H2);
    for (let i = 0, j = 0; i < d.length; i += 4, j++) lum[j] = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
    let n = 0, tot = 0;
    for (let y = D; y < H2 - D; y++) for (let x = D; x < W2 - D; x++) {
      const v = lum[y * W2 + x]; tot++;
      if ((v + TH < lum[y * W2 + x - D] && v + TH < lum[y * W2 + x + D]) ||
          (v + TH < lum[(y - D) * W2 + x] && v + TH < lum[(y + D) * W2 + x])) n++;
    }
    return n / tot;
  };

  // ---- bucle
  const frameCbs = [];
  let frames = 0, fpsT = performance.now(), watchdog = 0, rafId = 0, running = false;
  // requestAnimationFrame con respaldo por temporizador: en Chrome headless (sin display link)
  // rAF nunca dispara.
  function nextFrame() { rafId = requestAnimationFrame(animate); clearTimeout(watchdog); watchdog = setTimeout(() => { cancelAnimationFrame(rafId); animate(); }, 120); }
  function animate() {
    clearTimeout(watchdog);
    if (!running) return;
    nextFrame();
    const dt = Math.min(clock.getDelta(), 0.1), t = clock.elapsedTime;
    undoFollow();
    if (mixer) mixer.update(dt);
    saveFollow();
    applyHeadFollow(dt);
    if (screens.length) {
      const k = Math.max(0, Math.min(1, (performance.now() - screensOnAt) / 2000));
      screens.forEach(s => s.material.emissiveIntensity = 2.5 * k * k);
      for (const l of Object.values(screenLights)) l.intensity = 1.6 * LIT.screen * k * k;
    }
    bars.forEach((b, i) => { const h = (t * 0.05 + i * 0.5) % 1; b.material.emissive.setHSL(0.55 + 0.1 * Math.sin(h * Math.PI * 2), 0.9, 0.55); b.material.emissiveIntensity = 4; barLights[i] && barLights[i].color.copy(b.material.emissive); });
    if (graffiti) graffiti.update(dt, t);
    for (const cb of frameCbs) cb(dt, t);          // la landing mueve aqui la camara
    if (controls) controls.update(); else camera.lookAt(camTarget);
    if (composer) composer.render(dt); else renderer.render(scene, camera);
    frames++; status.frames++; status.exclusive = exclusive; status.screen = screens.length ? screens[0].material.emissiveIntensity : 0;
    const now = performance.now();
    if (now - fpsT > 500) { status.fps = Math.round(frames * 1000 / (now - fpsT)); frames = 0; fpsT = now; }
  }

  const api = {
    THREE, renderer, scene, camera, controls, composer, status, follow, mouse, actions,
    get character() { return character; },
    get glass() { return glass; },
    get graffiti() { return graffiti; },
    camTarget,
    vibe, browup, playExclusive, resetCamera, setMouse, setSize, inkFrac,
    onFrame(cb) { frameCbs.push(cb); return () => { const i = frameCbs.indexOf(cb); if (i >= 0) frameCbs.splice(i, 1); }; },
    start() { if (running) return; running = true; clock.getDelta(); animate(); },
    stop() { running = false; cancelAnimationFrame(rafId); clearTimeout(watchdog); },
  };
  if (opts.autoStart !== false) api.start();
  return api;
}

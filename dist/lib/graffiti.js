// Grafiti del nombre pintado en la pared del cuarto, con RELIEVE y paneles de neon REALES delante.
//
// La pieza (img/graffiti.webp, wildstyle "SEBASTIAN ESCOBAR" 3:2 generado en Higgsfield, sesion
// 13; antes era cuadrada) se pega a la pared lateral grande y la cubre de punta a punta: desde
// el borde del encuadre del hero hasta la esquina con la ventana.
//
// Por que ya no es una calcomania plana (pedido de la sesion 13: "mas 3D, menos plano"):
//  - Extrusion real por CAPAS APILADAS: la misma silueta (mascara alpha calculada de la imagen)
//    se dibuja N veces separadas unos milimetros, de la pared hacia el cuarto, con la pintura
//    oscurecida en las capas de abajo y la imagen completa en la de arriba. De frente se ve solo
//    la de arriba; en escorzo (la camara del hero mira la pared a ~60 grados) asoman los lados
//    de la extrusion, oscuros, y las letras se leen como bloques de 4 cm que salen del muro.
//    Es el truco de "sprite stacking": 9 planos de 2 triangulos, nada de geometria pesada.
//  - Sombra de contacto sobre el muro: una copia desenfocada y desplazada de la silueta,
//    negra y semitransparente, pegada a la pared debajo de la pila. Sin ella los bloques
//    "flotan".
//  - La capa de arriba conserva la mascara emisiva (solo los pixeles saturados y claros: tubos
//    rosa del contorno y paneles cian pintados) para cruzar el umbral del bloom (2.5 lineal, ver
//    postfx.js) y brillar como las barras RGB.
//
// Los paneles de neon fisicos (dos tubos cian verticales en los extremos y un panel magenta
// arriba, ahora tan ancho como la pieza) son geometria emisiva propia con una puntual cada
// uno: proyectan luz de color sobre la pared, el suelo y el personaje.
//
// No toca el GLB ni Blender: todo vive en el visor. Se apaga con ?graffiti=0, se mueve de pared
// con ?gwall=side|back (ver WALLS) y ?gdepth= calibra la profundidad del relieve (0 = plano).
// Coordenadas glTF: (x, y, z) = Blender (x, z, -y).
import * as THREE from 'three';

// Donde vive la pieza. `right` es hacia donde apunta la DERECHA de la imagen en el mundo y
// `normal` sale de la pared hacia el cuarto. `size` es la ALTURA en metros; el ancho lo da el
// aspecto de la imagen (3:2 → 2.4 m). La pared lateral +X queda a la IZQUIERDA de la camara del
// hero (mira hacia +Z) y va de z = -4 (detras de la camara) a z = 1.445 (esquina con la pared
// trasera); el hero de escritorio ve de z ≈ -1.1 en adelante, asi que la pieza va de -1.08 a 1.32.
export const WALLS = {
  side: { center: [2.045, 1.18, 0.12], size: 1.6, aspect: 1.5, right: [0, 0, 1], normal: [-1, 0, 0] },
  // franja de la pared trasera a la derecha de la ventana, debajo de la repisa de la moto
  back: { center: [1.475, 0.76, 1.445], size: 0.7, aspect: 1.5, right: [-1, 0, 0], normal: [0, 0, -1] },
};

const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// Lienzo del tamano de la imagen (lado mayor = `max`) con la imagen ya dibujada.
function canvasOf(img, max) {
  const s = Math.min(1, max / Math.max(img.width, img.height));
  const c = document.createElement('canvas');
  c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0, c.width, c.height);
  return { c, g };
}

// Mascara emisiva: conserva el color solo donde la pintura es neon (saturada y clara). El cromo
// (gris) y el muro (oscuro) salen negros.
function glowFromImage(img, max = 1024) {
  const { c, g } = canvasOf(img, max);
  const id = g.getImageData(0, 0, c.width, c.height), d = id.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255;
    const mx = Math.max(r, gg, b), mn = Math.min(r, gg, b);
    const sat = mx > 0 ? (mx - mn) / mx : 0;
    const w = smooth(0.35, 0.70, sat) * smooth(0.62, 0.92, mx);
    d[i] = r * w * 255; d[i + 1] = gg * w * 255; d[i + 2] = b * w * 255; d[i + 3] = 255;
  }
  g.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// Mascara de opacidad: la PINTURA queda opaca y el muro oscuro que trae la imagen se vuelve
// transparente, asi las letras se ven sobre la pared real del cuarto (con su luz y sus bandas
// de cel) en vez de sobre un rectangulo mas oscuro que delata el plano. Por que en dos pasos:
// las lineas negras del contorno y los bloques 3D oscuros son tan oscuros como el muro, y con
// un umbral de luminancia a secas se hacian agujeros; la mascara desenfocada (radio ~1 % del
// lado) los tapa porque siempre estan pegados a pintura clara. Un borde difuminado remata por
// si algun resto de textura del muro llega a la orilla. Devuelve el lienzo (la sombra lo reusa).
function paintAlphaCanvas(img, max = 1536, feather = 0.06) {
  const { c: a, g } = canvasOf(img, max);
  const W = a.width, H = a.height;
  const id = g.getImageData(0, 0, W, H), d = id.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255;
    const lum = 0.2126 * r + 0.7152 * gg + 0.0722 * b, sat = Math.max(r, gg, b) - Math.min(r, gg, b);
    const m = Math.max(smooth(0.16, 0.30, lum), smooth(0.18, 0.35, sat));
    d[i] = d[i + 1] = d[i + 2] = m * 255; d[i + 3] = 255;
  }
  g.putImageData(id, 0, 0);
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const h = c.getContext('2d', { willReadFrequently: true });
  h.filter = `blur(${Math.round(Math.max(W, H) * 0.012)}px)`; h.drawImage(a, 0, 0); h.filter = 'none';
  const id2 = h.getImageData(0, 0, W, H), e = id2.data;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4;
    const u = Math.abs((x + 0.5) / W * 2 - 1), v = Math.abs((y + 0.5) / H * 2 - 1);
    const edge = smooth(1, 1 - feather, Math.max(u, v));
    // suelo de ruido: el grano claro del muro pintado daba alphas de 0.1-0.3 que, con la pila
    // en relieve, escribian profundidad y el contorno cel dibujaba el RECTANGULO del plano
    const m = smooth(0.15, 0.40, Math.max(d[i] / 255, smooth(0.22, 0.55, e[i] / 255))) * edge;
    e[i] = e[i + 1] = e[i + 2] = m * 255; e[i + 3] = 255;
  }
  h.putImageData(id2, 0, 0);
  return c;
}

// Sombra de contacto: la silueta desenfocada y corrida hacia abajo y hacia la derecha de la
// imagen, como si la luz viniera de arriba a la izquierda. Sale como alphaMap de un plano negro.
function shadowFromAlpha(alphaCanvas, dx = 0.006, dy = 0.02, blur = 0.014) {
  const W = alphaCanvas.width, H = alphaCanvas.height;
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  g.filter = `blur(${Math.round(Math.max(W, H) * blur)}px)`;
  g.drawImage(alphaCanvas, dx * W, dy * H); g.filter = 'none';
  return new THREE.CanvasTexture(c);
}

// Equivalente a MeshNormalMaterial (normal de vista empaquetada en RGB, `opacity` en la alfa
// = sensibilidad a tinta, ver postfx.js) pero recortado por una mascara: MeshNormalMaterial no
// admite alphaMap. Los texeles descartados no escriben profundidad ni normal.
function normalCutout(alphaMap, opacity) {
  return new THREE.ShaderMaterial({
    uniforms: { alphaMap: { value: alphaMap }, opacity: { value: opacity } },
    vertexShader: `varying vec3 vN; varying vec2 vUv;
      void main() { vN = normalize(normalMatrix * normal); vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform sampler2D alphaMap; uniform float opacity; varying vec3 vN; varying vec2 vUv;
      void main() { if (texture2D(alphaMap, vUv).g < 0.5) discard; gl_FragColor = vec4(normalize(vN) * 0.5 + 0.5, opacity); }`,
  });
}

/**
 * @param scene  escena de three
 * @param opts   base   prefijo de img/ (por omision './')
 *               ver    sufijo anti-cache ('' o '?v=...')
 *               wall   'side' | 'back' (clave de WALLS)
 *               size   ALTURA del plano en metros (por omision la de la pared)
 *               glow   intensidad emisiva de la pintura neon (3.0)
 *               light  multiplicador de las puntuales de los paneles (1)
 *               depth  profundidad del relieve en metros (0.06; 0 = calcomania plana)
 *               ink    sensibilidad del contorno cel sobre las letras en relieve (0.6)
 *               maxAnisotropy  para que las letras no se emborronen en escorzo
 * @returns { group, lights, wall, update(dt, t), ready }
 */
export function addGraffiti(scene, opts = {}) {
  const base = opts.base ?? './', ver = opts.ver ?? '';
  const wallName = WALLS[opts.wall] ? opts.wall : 'side';
  const W = WALLS[wallName];
  const H = opts.size ?? W.size, GLOW = opts.glow ?? 3.0, LIT = opts.light ?? 1;
  const DEPTH = opts.depth ?? 0.06, LAYERS = DEPTH > 0 ? 14 : 0;
  let SW = H * W.aspect;   // ancho; se corrige con el aspecto real de la imagen al cargar
  const C = new THREE.Vector3(...W.center), R = new THREE.Vector3(...W.right), N = new THREE.Vector3(...W.normal), U = new THREE.Vector3(0, 1, 0);
  const at = (a, b, c) => C.clone().addScaledVector(R, a).addScaledVector(U, b).addScaledVector(N, c);
  const group = new THREE.Group(); group.name = 'graffiti';
  const lights = [];
  // orientacion comun: +Z local = normal de la pared, +X local = derecha de la imagen
  const basis = new THREE.Matrix4().makeBasis(R, U, N);
  const quat = new THREE.Quaternion().setFromRotationMatrix(basis);

  // ---- la pintura: pila de planos con la misma silueta. Todos comparten geometria; al cargar la
  // imagen se les pone el alpha y se les escala el ancho al aspecto real.
  const geo = new THREE.PlaneGeometry(1, 1);
  const stack = [];   // planos de la pila, de la pared hacia afuera
  const top = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: 0.95, metalness: 0,
    emissive: 0xffffff, emissiveIntensity: 0,   // sin mapa, emissive blanco x GLOW quemaria el plano
    transparent: true, opacity: 0, alphaTest: 0.1,   // los texeles casi transparentes no escriben profundidad (contorno cel)
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  // lados de la extrusion: la misma imagen oscurecida, recortada a la silueta (alphaTest, sin
  // mezcla: asi las capas se ordenan por profundidad sin depender del orden de dibujo)
  const side = new THREE.MeshStandardMaterial({
    color: 0x2a2530, roughness: 0.9, metalness: 0, alphaTest: 0.5,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  const z0 = 0.006;   // separacion de la pared (sin z-fighting)
  for (let i = 0; i <= LAYERS; i++) {
    const isTop = i === LAYERS;
    const m = new THREE.Mesh(geo, isTop ? top : side);
    m.name = isTop ? 'graffiti_decal' : 'graffiti_layer_' + i;
    m.position.copy(at(0, 0, z0 + (LAYERS ? DEPTH * i / LAYERS : 0))); m.quaternion.copy(quat);
    m.scale.set(SW, H, 1);
    m.castShadow = false; m.receiveShadow = isTop;
    m.visible = false;   // hasta que llegue la imagen y su mascara
    group.add(m); stack.push(m);
  }
  // sombra de contacto sobre el muro (debajo de la pila)
  const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
  const shadow = new THREE.Mesh(geo, shadowMat); shadow.name = 'graffiti_shadow';
  shadow.position.copy(at(0, 0, 0.003)); shadow.quaternion.copy(quat); shadow.scale.set(SW, H, 1);
  shadow.castShadow = false; shadow.receiveShadow = false;
  shadow.userData.outline = false;   // no existe para el contorno
  for (const m of stack) m.userData.outline = false;   // hasta que llegue la mascara (ver abajo)
  if (LAYERS) group.add(shadow);

  const api = { group, lights, wall: wallName, ready: false, update: null };
  new THREE.TextureLoader().load(base + 'img/graffiti.webp' + ver, (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    if (opts.maxAnisotropy) tex.anisotropy = opts.maxAnisotropy;
    const img = tex.image;
    SW = H * (img.width / img.height);
    for (const m of [...stack, shadow]) m.scale.set(SW, H, 1);
    const alphaCanvas = paintAlphaCanvas(img);
    const alpha = new THREE.CanvasTexture(alphaCanvas);
    if (opts.maxAnisotropy) alpha.anisotropy = opts.maxAnisotropy;
    top.map = tex; top.alphaMap = alpha; top.opacity = 1;
    top.emissiveMap = glowFromImage(img);
    if (opts.maxAnisotropy) top.emissiveMap.anisotropy = opts.maxAnisotropy;
    top.emissiveIntensity = GLOW; top.needsUpdate = true;
    side.map = tex; side.alphaMap = alpha; side.needsUpdate = true;
    // Pre-pase del contorno (postfx.js): un material de normales recortado por la misma
    // silueta, para que la tinta cel siga el borde de las letras en relieve y no el del plano.
    const outlineMat = normalCutout(alpha, opts.ink ?? 0.6);
    for (const m of stack) { m.visible = true; m.userData.outline = true; m.userData.outlineMaterial = outlineMat; }
    if (LAYERS) { shadowMat.alphaMap = shadowFromAlpha(alphaCanvas); shadowMat.opacity = 0.75; shadowMat.needsUpdate = true; }
    api.ready = true;
  }, undefined, (e) => console.error('graffiti.webp: ' + (e.message || e)));

  // ---- paneles de neon fisicos. Mismo esquema que las barras RGB del GLB: material emisivo
  // > 2.5 en lineal para alimentar el bloom, mas una puntual del mismo color. Se colocan con el
  // ancho nominal de la pared (WALLS.aspect); la imagen real es 3:2, asi que coinciden.
  const neon = (color) => new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.4, emissive: color, emissiveIntensity: 4 });
  const bracket = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.6, metalness: 0.3 });
  const tubes = [];
  const gap = 0.08, off = 0.045;   // separacion del borde de la pieza / distancia a la pared
  const tubeLen = H * 0.88, tubeR = 0.017;
  for (const s of [-1, 1]) {
    const t = new THREE.Mesh(new THREE.CylinderGeometry(tubeR, tubeR, tubeLen, 14), neon(0x36f0ff));
    t.name = 'graffiti_neon_' + (s < 0 ? 'L' : 'R');
    t.position.copy(at(s * (SW / 2 + gap), 0, off)); t.quaternion.copy(quat);
    t.castShadow = false; t.receiveShadow = false;
    group.add(t); tubes.push(t);
    for (const dy of [-0.4, 0.4]) {   // soportes: dos cajitas contra la pared
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.03, off + 0.01), bracket);
      b.position.copy(at(s * (SW / 2 + gap), dy * tubeLen, (off + 0.01) / 2)); b.quaternion.copy(quat);
      b.castShadow = false; group.add(b);
    }
    const l = new THREE.PointLight(0x36f0ff, 0.6 * LIT, 3.5, 2);
    l.position.copy(at(s * (SW / 2 + gap), 0, off + 0.08)); group.add(l); lights.push(l);
  }
  // panel magenta horizontal sobre la pieza: una lamina, no un tubo, para que se lea "panel"
  const panelLen = SW * 0.8;
  const panel = new THREE.Mesh(new THREE.BoxGeometry(panelLen, 0.05, 0.018), neon(0xff3fbf));
  panel.name = 'graffiti_neon_top';
  panel.position.copy(at(0, H / 2 + gap, off)); panel.quaternion.copy(quat);
  panel.castShadow = false; panel.receiveShadow = false;
  group.add(panel); tubes.push(panel);
  for (const dx of [-0.45, 0, 0.45]) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.04, off + 0.01), bracket);
    b.position.copy(at(dx * panelLen, H / 2 + gap, (off + 0.01) / 2)); b.quaternion.copy(quat);
    b.castShadow = false; group.add(b);
  }
  const lp = new THREE.PointLight(0xff3fbf, 0.8 * LIT, 3.2, 2);
  lp.position.copy(at(0, H / 2 + gap, off + 0.08)); group.add(lp); lights.push(lp);

  scene.add(group);

  // Respiracion lenta de los tubos cian y un parpadeo ligero del panel magenta (neon de verdad).
  api.update = (dt, t) => {
    const breathe = 3.7 + 0.35 * Math.sin(t * 0.9);
    tubes[0].material.emissiveIntensity = breathe; tubes[1].material.emissiveIntensity = breathe;
    const flick = 3.6 + 0.3 * Math.sin(t * 6.3) * Math.sin(t * 11.7) + (Math.random() < 0.004 ? -1.2 : 0);
    panel.material.emissiveIntensity = flick;
    lp.intensity = 0.8 * LIT * (flick / 3.6);
  };
  return api;
}

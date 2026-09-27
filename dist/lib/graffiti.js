// Grafiti del nombre pintado en la pared del cuarto, con paneles de neon REALES delante.
//
// La pieza (img/graffiti.webp, wildstyle "SEBASTIAN ESCOBAR" generado en Higgsfield, sesion 12)
// va como calcomania: un plano pegado a la pared con la imagen de albedo y, ademas, una mascara
// emisiva calculada aqui mismo a partir de la propia imagen (solo los pixeles saturados y
// claros: los tubos rosa del contorno y los paneles cian pintados). Asi el neon PINTADO cruza el
// umbral del bloom (2.5 en lineal, ver postfx.js) y brilla como las barras RGB, mientras el
// cromo de las letras y el muro se quedan como pintura mate.
//
// Los paneles de neon fisicos (dos tubos cian verticales y un panel magenta arriba) son
// geometria emisiva propia con una puntual cada uno: proyectan luz de color sobre la pared, el
// suelo y el personaje, que es lo que hace que la pieza pertenezca al cuarto y no parezca un
// poster pegado.
//
// No toca el GLB ni Blender: todo vive en el visor. Se apaga con ?graffiti=0 y se mueve de pared
// con ?gwall=side|back (ver WALLS). Coordenadas glTF: (x, y, z) = Blender (x, z, -y).
import * as THREE from 'three';

// Donde vive la pieza. `right` es hacia donde apunta la DERECHA de la imagen en el mundo y
// `normal` sale de la pared hacia el cuarto. La pared lateral +X queda a la IZQUIERDA de la
// camara del hero (la camara mira hacia +Z) y es el muro vacio grande junto a la ventana.
export const WALLS = {
  side: { center: [2.045, 1.18, 0.42], size: 1.6, right: [0, 0, 1], normal: [-1, 0, 0] },
  // franja de la pared trasera a la derecha de la ventana, debajo de la repisa de la moto
  back: { center: [1.475, 0.76, 1.445], size: 1.0, right: [-1, 0, 0], normal: [0, 0, -1] },
};

const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// Mascara emisiva: conserva el color solo donde la pintura es neon (saturada y clara). El cromo
// (gris) y el muro (oscuro) salen negros. Se calcula a 1024 para que tarde ~30 ms.
function glowFromImage(img, size = 1024) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0, size, size);
  const id = g.getImageData(0, 0, size, size), d = id.data;
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
// si algun resto de textura del muro llega a la orilla.
function paintAlpha(img, size = 1024, feather = 0.10) {
  const a = document.createElement('canvas'); a.width = a.height = size;
  const g = a.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0, size, size);
  const id = g.getImageData(0, 0, size, size), d = id.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255;
    const lum = 0.2126 * r + 0.7152 * gg + 0.0722 * b, sat = Math.max(r, gg, b) - Math.min(r, gg, b);
    const m = Math.max(smooth(0.16, 0.30, lum), smooth(0.18, 0.35, sat));
    d[i] = d[i + 1] = d[i + 2] = m * 255; d[i + 3] = 255;
  }
  g.putImageData(id, 0, 0);
  const c = document.createElement('canvas'); c.width = c.height = size;
  const h = c.getContext('2d', { willReadFrequently: true });
  h.filter = `blur(${Math.round(size * 0.012)}px)`; h.drawImage(a, 0, 0); h.filter = 'none';
  const id2 = h.getImageData(0, 0, size, size), e = id2.data;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const i = (y * size + x) * 4;
    const u = Math.abs((x + 0.5) / size * 2 - 1), v = Math.abs((y + 0.5) / size * 2 - 1);
    const edge = smooth(1, 1 - feather, Math.max(u, v));
    const m = Math.max(d[i] / 255, smooth(0.22, 0.55, e[i] / 255)) * edge;
    e[i] = e[i + 1] = e[i + 2] = m * 255; e[i + 3] = 255;
  }
  h.putImageData(id2, 0, 0);
  return new THREE.CanvasTexture(c);
}

/**
 * @param scene  escena de three
 * @param opts   base   prefijo de img/ (por omision './')
 *               ver    sufijo anti-cache ('' o '?v=...')
 *               wall   'side' | 'back' (clave de WALLS)
 *               size   lado del plano en metros (por omision el de la pared)
 *               glow   intensidad emisiva de la pintura neon (3.2)
 *               light  multiplicador de las puntuales de los paneles (1)
 *               maxAnisotropy  para que las letras no se emborronen en escorzo
 * @returns { group, lights, wall, update(dt, t), ready }
 */
export function addGraffiti(scene, opts = {}) {
  const base = opts.base ?? './', ver = opts.ver ?? '';
  const wallName = WALLS[opts.wall] ? opts.wall : 'side';
  const W = WALLS[wallName];
  const S = opts.size ?? W.size, GLOW = opts.glow ?? 3.0, LIT = opts.light ?? 1;
  const C = new THREE.Vector3(...W.center), R = new THREE.Vector3(...W.right), N = new THREE.Vector3(...W.normal), U = new THREE.Vector3(0, 1, 0);
  const at = (a, b, c) => C.clone().addScaledVector(R, a).addScaledVector(U, b).addScaledVector(N, c);
  const group = new THREE.Group(); group.name = 'graffiti';
  const lights = [];
  // orientacion comun: +Z local = normal de la pared, +X local = derecha de la imagen
  const basis = new THREE.Matrix4().makeBasis(R, U, N);
  const quat = new THREE.Quaternion().setFromRotationMatrix(basis);

  // ---- la pintura
  const mat = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: 0.95, metalness: 0,
    emissive: 0xffffff, emissiveIntensity: GLOW,
    transparent: true, opacity: 0,   // invisible hasta que llegue la imagen y su mascara
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,   // pegado a la pared sin z-fighting
  });
  mat.emissiveMap = null;   // hasta que cargue la imagen: sin mapa, emissive blanco x GLOW quemaria el plano
  mat.emissiveIntensity = 0;
  const decal = new THREE.Mesh(new THREE.PlaneGeometry(S, S), mat);
  decal.name = 'graffiti_decal';
  decal.position.copy(at(0, 0, 0.006)); decal.quaternion.copy(quat);
  decal.castShadow = false; decal.receiveShadow = true;
  group.add(decal);

  const api = { group, lights, wall: wallName, ready: false, update: null };
  new THREE.TextureLoader().load(base + 'img/graffiti.webp' + ver, (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    if (opts.maxAnisotropy) tex.anisotropy = opts.maxAnisotropy;
    mat.map = tex;
    mat.alphaMap = paintAlpha(tex.image);
    mat.opacity = 1;
    mat.emissiveMap = glowFromImage(tex.image);
    if (opts.maxAnisotropy) mat.emissiveMap.anisotropy = opts.maxAnisotropy;
    mat.emissiveIntensity = GLOW;
    mat.needsUpdate = true;
    api.ready = true;
  }, undefined, (e) => console.error('graffiti.webp: ' + (e.message || e)));

  // ---- paneles de neon fisicos. Mismo esquema que las barras RGB del GLB: material emisivo
  // > 2.5 en lineal para alimentar el bloom, mas una puntual del mismo color.
  const neon = (color) => new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.4, emissive: color, emissiveIntensity: 4 });
  const bracket = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.6, metalness: 0.3 });
  const tubes = [];
  const gap = 0.10, off = 0.045;   // separacion del borde de la pieza / distancia a la pared
  const tubeLen = S * 0.88, tubeR = 0.017;
  for (const side of [-1, 1]) {
    const t = new THREE.Mesh(new THREE.CylinderGeometry(tubeR, tubeR, tubeLen, 14), neon(0x36f0ff));
    t.name = 'graffiti_neon_' + (side < 0 ? 'L' : 'R');
    t.position.copy(at(side * (S / 2 + gap), 0, off)); t.quaternion.copy(quat);
    t.castShadow = false; t.receiveShadow = false;
    group.add(t); tubes.push(t);
    for (const dy of [-0.4, 0.4]) {   // soportes: dos cajitas contra la pared
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.03, off + 0.01), bracket);
      b.position.copy(at(side * (S / 2 + gap), dy * tubeLen, (off + 0.01) / 2)); b.quaternion.copy(quat);
      b.castShadow = false; group.add(b);
    }
    const l = new THREE.PointLight(0x36f0ff, 0.6 * LIT, 3.5, 2);
    l.position.copy(at(side * (S / 2 + gap), 0, off + 0.08)); group.add(l); lights.push(l);
  }
  // panel magenta horizontal sobre la pieza: una lamina, no un tubo, para que se lea "panel"
  const panelLen = S * 0.72;
  const panel = new THREE.Mesh(new THREE.BoxGeometry(panelLen, 0.05, 0.018), neon(0xff3fbf));
  panel.name = 'graffiti_neon_top';
  panel.position.copy(at(0, S / 2 + gap, off)); panel.quaternion.copy(quat);
  panel.castShadow = false; panel.receiveShadow = false;
  group.add(panel); tubes.push(panel);
  for (const dx of [-0.42, 0.42]) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.04, off + 0.01), bracket);
    b.position.copy(at(dx * panelLen, S / 2 + gap, (off + 0.01) / 2)); b.quaternion.copy(quat);
    b.castShadow = false; group.add(b);
  }
  const lp = new THREE.PointLight(0xff3fbf, 0.8 * LIT, 3.2, 2);
  lp.position.copy(at(0, S / 2 + gap, off + 0.08)); group.add(lp); lights.push(lp);

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

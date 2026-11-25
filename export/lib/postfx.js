// Post-proceso del visor: contorno de tinta + bloom de pantallas + viñeta.
//
// El contorno es lo que convierte el modelo en ilustracion. Se calcula sobre los BUFERES de
// profundidad y normales, no sobre la malla: por eso funciona con la geometria de Meshy
// (8563 vertices de borde, rendijas de hasta 3 mm) donde un inverted hull saldria agujereado
// justo en la cara. De paso contornea escritorio, monitores y moto, que es lo que unifica el
// look — sin eso el personaje pareceria un sticker pegado sobre un render.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { Pass, FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { VignetteShader } from 'three/addons/shaders/VignetteShader.js';

// --- pase de contorno --------------------------------------------------------------------
// Pre-pase: la escena entera con MeshNormalMaterial a un RT con DepthTexture adjunta.
// Luego un cruce de 4 vecinos sobre profundidad linealizada (silueta) y sobre normales
// (pliegues). Dos umbrales separados porque son dos bordes distintos: el salto de
// profundidad marca el contorno externo y el giro de normal marca los dobleces internos.
//
// El umbral de normales NO puede ser un numero fijo para toda la escena: se midio (ver
// tools/ink_probe.mjs) que con uno solo el termino entinta el ruido de la malla del
// personaje — rayones sueltos en gorra, frente y mejilla que ademas PARPADEAN al animar,
// porque cada pixel dudoso cruza el escalon del smoothstep en un frame y vuelve al
// siguiente. Con `outline=0` los rayones desaparecian por completo, o sea que salian de
// aqui y no del sombreado ni de la textura. El umbral se modula por dos factores:
//
//   sens   sensibilidad a tinta POR OBJETO, que el pre-pase escribe en la alfa del buffer
//          de normales (ver `_normalMaterial`). El cuarto son cajas de normales limpias y
//          quiere sensibilidad alta; el personaje y la moto vienen de Meshy y la quieren
//          baja. Antes esto obligaba a elegir: con nbias 0.8 el personaje salia rayado y
//          con 2.0 el cuarto perdia los pliegues.
//   facing |N·V| aproximado por la componente z de la normal en espacio de vista. En
//          escorzo la normal gira muy rapido de un pixel al siguiente aunque la superficie
//          sea lisa, asi que ahi el mismo umbral produce bordes falsos; se sube 1/facing.
//
// Y la rampa del smoothstep se ensancha (`ramp`): un pixel dudoso se desvanece en vez de
// encenderse de golpe, que es lo que se veia como lineas que aparecen y desaparecen.
const OUTLINE_FRAG = /* glsl */`
#include <packing>
uniform sampler2D tDiffuse, tNormal, tDepth;
uniform vec2 texel;
uniform float cameraNear, cameraFar;
uniform float thickness, depthBias, normalBias, strength, ramp, depthMin;
uniform vec3 outlineColor;
varying vec2 vUv;

float linearDepth(vec2 uv) {
  float z = texture2D(tDepth, uv).x;
  return viewZToOrthographicDepth(perspectiveDepthToViewZ(z, cameraNear, cameraFar), cameraNear, cameraFar);
}
vec4 nrm(vec2 uv) { vec4 t = texture2D(tNormal, uv); return vec4(t.xyz * 2.0 - 1.0, t.a); }

void main() {
  vec4 base = texture2D(tDiffuse, vUv);
  vec2 o = texel * thickness;
  float dc = linearDepth(vUv);
  float dR = abs(linearDepth(vUv + vec2(o.x, 0.0)) - dc), dL = abs(linearDepth(vUv - vec2(o.x, 0.0)) - dc);
  float dU = abs(linearDepth(vUv + vec2(0.0, o.y)) - dc), dD = abs(linearDepth(vUv - vec2(0.0, o.y)) - dc);
  float de = dR + dL + dU + dD;
  // Relativo a la profundidad: sin esto los objetos del fondo salen con un contorno mucho
  // mas grueso que los de delante, porque el mismo salto en metros pesa menos de cerca.
  de /= max(dc, 1e-4);
  // Suelo ABSOLUTO en metros: un salto menor que depthMin no es un borde. Existe por la cascara
  // interior de la cabeza (blender/scripts/add_gap_shell.py): las rendijas de la malla de Meshy
  // ya no muestran negro sino piel 2.5-6 mm mas honda, y ese escalon, relativo a la
  // profundidad, entintaba igual en primer plano. Un pliegue real (nariz, capucha, visera)
  // salta 1 cm o mas.
  if (max(max(dR, dL), max(dU, dD)) * (cameraFar - cameraNear) < depthMin) de = 0.0;

  vec4 ncs = nrm(vUv);
  vec3 nc = ncs.xyz;
  float sens = max(ncs.a, 0.04);              // 0 en el fondo: alli no se buscan pliegues
  float facing = clamp(abs(nc.z), 0.14, 1.0);
  float ne = (1.0 - dot(nc, nrm(vUv + vec2(o.x, 0.0)).xyz)) + (1.0 - dot(nc, nrm(vUv - vec2(o.x, 0.0)).xyz))
           + (1.0 - dot(nc, nrm(vUv + vec2(0.0, o.y)).xyz)) + (1.0 - dot(nc, nrm(vUv - vec2(0.0, o.y)).xyz));

  // La silueta tambien se corrige por escorzo: un escritorio o un suelo vistos casi de canto
  // tienen un gradiente de profundidad enorme sin que haya borde alguno.
  float dThr = depthBias / facing;
  float nThr = normalBias / (sens * facing);
  float edge = max(smoothstep(dThr, dThr * ramp, de), smoothstep(nThr, nThr * ramp, ne));
  gl_FragColor = vec4(mix(base.rgb, outlineColor, edge * strength), base.a);
}`;

class OutlinePass extends Pass {
  constructor(scene, camera, opts = {}) {
    super();
    this.scene = scene; this.camera = camera;
    // Sensibilidad a tinta por malla: 1 = como antes, valores bajos = solo pliegues fuertes.
    // `sensitivity(mesh)` la decide; el visor la usa para bajarsela a las mallas de Meshy.
    this.sensitivity = opts.sensitivity ?? (() => 1);
    this.normalMaterials = new Map();   // sens redondeada -> MeshNormalMaterial con esa opacity
    this.hidden = [];                   // mallas escondidas durante el pre-pase (userData.outline === false)
    this.swapped = [];
    // LinearFilter en el buffer de normales: cada muestra promedia sus cuatro texeles, lo que
    // atenua el ruido de un pixel de ancho sin tocar los pliegues, que ocupan varios. La
    // DepthTexture se queda en Nearest porque DEPTH_COMPONENT24 no es filtrable en WebGL2.
    this.rt = new THREE.WebGLRenderTarget(1, 1, { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter });
    this.rt.depthTexture = new THREE.DepthTexture(1, 1, THREE.UnsignedIntType);   // DEPTH_COMPONENT24: legible desde el shader
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: null }, tNormal: { value: this.rt.texture }, tDepth: { value: this.rt.depthTexture },
        texel: { value: new THREE.Vector2() },
        cameraNear: { value: camera.near }, cameraFar: { value: camera.far },
        thickness: { value: opts.thickness ?? 1.4 },
        depthBias: { value: opts.depthBias ?? 0.003 },
        depthMin: { value: opts.depthMin ?? 0.008 },      // m: ver el shader; ?dmin= en el visor
        // Umbral BASE, el del cuarto (sens 1, de frente). El personaje lo recibe multiplicado
        // por 1/sens, asi que ya no hay que subirlo aqui para librarse de sus rayones.
        normalBias: { value: opts.normalBias ?? 0.8 },
        strength: { value: opts.strength ?? 0.9 },
        // Ancho de la rampa del smoothstep, en multiplos del umbral. 2.0 era practicamente un
        // escalon y hacia parpadear los bordes dudosos al animar; 2.8 los funde.
        ramp: { value: opts.ramp ?? 2.8 },
        outlineColor: { value: new THREE.Color(opts.color ?? 0x0a0c12) },
      },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
      fragmentShader: OUTLINE_FRAG,
    });
    this.fsQuad = new FullScreenQuad(this.material);
  }
  setSize(w, h) {
    this.rt.setSize(w, h);
    this.material.uniforms.texel.value.set(1 / w, 1 / h);
  }
  // MeshNormalMaterial escribe `opacity` en la alfa del fragmento y, al no ser `transparent`,
  // three deja la mezcla apagada: la alfa llega intacta al buffer. Ese es el canal por el que
  // viaja la sensibilidad a tinta de cada malla.
  _normalMaterial(sens) {
    const k = Math.round(Math.max(0, Math.min(1, sens)) * 100) / 100;
    let m = this.normalMaterials.get(k);
    if (!m) { m = new THREE.MeshNormalMaterial({ opacity: k }); this.normalMaterials.set(k, m); }
    return m;
  }
  // scene.overrideMaterial no sirve aqui: es UN material para toda la escena y necesitamos una
  // alfa distinta por malla. Se intercambian y se restauran alrededor del pre-pase.
  // Dos excepciones por malla via userData: `outlineMaterial` es un material propio para el
  // pre-pase (el grafiti lo usa para recortar sus planos con la mascara alpha: sin esto el
  // plano entero escribia profundidad y salia dibujado el RECTANGULO) y `outline: false` la
  // esconde del pre-pase (calcomanias que no deben marcar borde ni normal).
  _swapMaterials() {
    this.swapped.length = 0; this.hidden.length = 0;
    this.scene.traverse((o) => {
      if (!o.isMesh || !o.material) return;
      if (o.userData.outline === false) { if (o.visible) { o.visible = false; this.hidden.push(o); } return; }
      this.swapped.push([o, o.material]);
      o.material = o.userData.outlineMaterial || this._normalMaterial(this.sensitivity(o));
    });
  }
  _restoreMaterials() {
    for (const [o, m] of this.swapped) o.material = m; this.swapped.length = 0;
    for (const o of this.hidden) o.visible = true; this.hidden.length = 0;
  }
  render(renderer, writeBuffer, readBuffer) {
    const prevBg = this.scene.background;
    this.scene.background = null;   // el fondo debe quedar a profundidad 1 para que la silueta marque borde
    this._swapMaterials();
    renderer.setRenderTarget(this.rt);
    renderer.clear(true, true, false);
    renderer.render(this.scene, this.camera);
    this._restoreMaterials(); this.scene.background = prevBg;

    const u = this.material.uniforms;
    u.tDiffuse.value = readBuffer.texture;
    u.cameraNear.value = this.camera.near; u.cameraFar.value = this.camera.far;

    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    if (this.clear) renderer.clear();
    this.fsQuad.render(renderer);
  }
  dispose() { this.rt.dispose(); this.material.dispose(); this.fsQuad.dispose(); for (const m of this.normalMaterials.values()) m.dispose(); }
}

// --- cadena ------------------------------------------------------------------------------
// Orden: Render -> Bloom -> Contorno -> Viñeta -> Output.
// El contorno va DESPUES del bloom a proposito: al reves, el desenfoque del bloom come la
// tinta y el borde queda lechoso. Asi la linea sale limpia encima del resplandor.
// OutputPass es quien aplica tonemapping y sRGB: al renderizar a un RT three los omite.
export function createComposer(renderer, scene, camera, opts = {}) {
  const size = renderer.getDrawingBufferSize(new THREE.Vector2());
  const target = new THREE.WebGLRenderTarget(size.x, size.y, {
    type: THREE.HalfFloatType,                  // el bloom necesita valores > 1 (pantallas emisivas)
    samples: opts.samples ?? 4,                 // MSAA: el antialias del renderer no aplica al RT
  });
  const composer = new EffectComposer(renderer, target);
  composer.setPixelRatio(renderer.getPixelRatio());
  composer.setSize(renderer.domElement.clientWidth || size.x, renderer.domElement.clientHeight || size.y);

  const passes = {};
  composer.addPass(passes.render = new RenderPass(scene, camera));
  if (opts.bloom !== false) {
    // Umbral 2.5: solo pasan los emisivos (pantallas a 2.5 y barras RGB a 4 en lineal).
    // A 0.85 el personaje entero entraba en el bloom y salia blanco, y a 1.05 seguia
    // lechoso: con base ambiental el difuso de las zonas claras ya roza 1 en lineal.
    passes.bloom = new UnrealBloomPass(new THREE.Vector2(size.x, size.y), opts.bloomStrength ?? 0.25, opts.bloomRadius ?? 0.5, opts.bloomThreshold ?? 2.5);
    composer.addPass(passes.bloom);
  }
  if (opts.outline !== false) composer.addPass(passes.outline = new OutlinePass(scene, camera, opts));
  if (opts.vignette !== false) {
    passes.vignette = new ShaderPass(VignetteShader);
    passes.vignette.uniforms.offset.value = opts.vignetteOffset ?? 1.1;
    passes.vignette.uniforms.darkness.value = opts.vignetteDarkness ?? 1.05;
    composer.addPass(passes.vignette);
  }
  composer.addPass(passes.output = new OutputPass());

  composer.passesByName = passes;
  return composer;
}

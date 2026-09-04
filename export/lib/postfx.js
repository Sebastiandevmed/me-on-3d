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
const OUTLINE_FRAG = /* glsl */`
#include <packing>
uniform sampler2D tDiffuse, tNormal, tDepth;
uniform vec2 texel;
uniform float cameraNear, cameraFar;
uniform float thickness, depthBias, normalBias, strength;
uniform vec3 outlineColor;
varying vec2 vUv;

float linearDepth(vec2 uv) {
  float z = texture2D(tDepth, uv).x;
  return viewZToOrthographicDepth(perspectiveDepthToViewZ(z, cameraNear, cameraFar), cameraNear, cameraFar);
}
vec3 nrm(vec2 uv) { return texture2D(tNormal, uv).xyz * 2.0 - 1.0; }

void main() {
  vec4 base = texture2D(tDiffuse, vUv);
  vec2 o = texel * thickness;
  float dc = linearDepth(vUv);
  float de = abs(linearDepth(vUv + vec2(o.x, 0.0)) - dc) + abs(linearDepth(vUv - vec2(o.x, 0.0)) - dc)
           + abs(linearDepth(vUv + vec2(0.0, o.y)) - dc) + abs(linearDepth(vUv - vec2(0.0, o.y)) - dc);
  // Relativo a la profundidad: sin esto los objetos del fondo salen con un contorno mucho
  // mas grueso que los de delante, porque el mismo salto en metros pesa menos de cerca.
  de /= max(dc, 1e-4);

  vec3 nc = nrm(vUv);
  float ne = (1.0 - dot(nc, nrm(vUv + vec2(o.x, 0.0)))) + (1.0 - dot(nc, nrm(vUv - vec2(o.x, 0.0))))
           + (1.0 - dot(nc, nrm(vUv + vec2(0.0, o.y)))) + (1.0 - dot(nc, nrm(vUv - vec2(0.0, o.y))));

  float edge = max(smoothstep(depthBias, depthBias * 2.0, de), smoothstep(normalBias, normalBias * 2.0, ne));
  gl_FragColor = vec4(mix(base.rgb, outlineColor, edge * strength), base.a);
}`;

class OutlinePass extends Pass {
  constructor(scene, camera, opts = {}) {
    super();
    this.scene = scene; this.camera = camera;
    this.normalMaterial = new THREE.MeshNormalMaterial();
    this.rt = new THREE.WebGLRenderTarget(1, 1, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    this.rt.depthTexture = new THREE.DepthTexture(1, 1, THREE.UnsignedIntType);   // DEPTH_COMPONENT24: legible desde el shader
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: null }, tNormal: { value: this.rt.texture }, tDepth: { value: this.rt.depthTexture },
        texel: { value: new THREE.Vector2() },
        cameraNear: { value: camera.near }, cameraFar: { value: camera.far },
        thickness: { value: opts.thickness ?? 1.4 },
        depthBias: { value: opts.depthBias ?? 0.003 },
        // Por debajo de ~0.6 el contorno empieza a dibujar el RUIDO de la malla de Meshy
        // (pecas negras en la gorra y en la cara); por encima de ~1.1 se pierden los pliegues.
        normalBias: { value: opts.normalBias ?? 0.8 },
        strength: { value: opts.strength ?? 0.9 },
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
  render(renderer, writeBuffer, readBuffer) {
    const prevOverride = this.scene.overrideMaterial, prevBg = this.scene.background;
    this.scene.overrideMaterial = this.normalMaterial;
    this.scene.background = null;   // el fondo debe quedar a profundidad 1 para que la silueta marque borde
    renderer.setRenderTarget(this.rt);
    renderer.clear(true, true, false);
    renderer.render(this.scene, this.camera);
    this.scene.overrideMaterial = prevOverride; this.scene.background = prevBg;

    const u = this.material.uniforms;
    u.tDiffuse.value = readBuffer.texture;
    u.cameraNear.value = this.camera.near; u.cameraFar.value = this.camera.far;

    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    if (this.clear) renderer.clear();
    this.fsQuad.render(renderer);
  }
  dispose() { this.rt.dispose(); this.material.dispose(); this.fsQuad.dispose(); }
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

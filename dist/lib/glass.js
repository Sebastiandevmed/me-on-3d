// Vidrio de la ventana: destello aditivo sobre el plano `window_glass` que build_scene.py deja
// delante de la imagen nocturna de Medellin.
//
// POR QUE UN DESTELLO Y NO UNA REFLEXION REAL. La escena es cel-shaded con contorno de tinta.
// En ilustracion una ventana se lee como vidrio por el BRILLO diagonal, no porque devuelva la
// habitacion: la reflexion planar cuesta una pasada de render entera (segunda camara espejada
// + render target del tamano de la pantalla) y en un look de bandas se ve sucia, porque el
// reflejo llega con su propio banding y compite con el contorno. Un cubemap tampoco sirve: el
// plano es casi coplanar con la pared y capturaria sobre todo pared.
//
// El material es ADITIVO y sin escritura de profundidad, asi que no tapa la ciudad de detras
// ni participa en el contorno (no tiene borde propio que dibujar).
//
// Tres capas, todas en el fragmento:
//   1. dos bandas diagonales suaves (el reflejo clasico de ventana);
//   2. realce fresnel en angulo rasante, que es lo que delata que hay una superficie;
//   3. un gradiente vertical tenue, porque el vidrio real recoge mas luz arriba.
import * as THREE from 'three';

const VERT = `
varying vec2 vUvG;
varying vec3 vViewG;
varying vec3 vNormG;
void main() {
  vUvG = uv;
  vNormG = normalize(normalMatrix * normal);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vViewG = -mv.xyz;
  gl_Position = projectionMatrix * mv;
}`;

const FRAG = `
uniform vec3  tint;
uniform float bandStrength;
uniform float fresnelStrength;
uniform float fresnelPower;
uniform float bandAngle;
uniform float opacityG;
varying vec2 vUvG;
varying vec3 vViewG;
varying vec3 vNormG;

// banda suave centrada en c y de medio ancho w a lo largo de la coordenada t
// (sin comillas invertidas: este GLSL vive dentro de un template literal y las cerrarian)
float band(float t, float c, float w) {
  return smoothstep(w, 0.0, abs(t - c));
}

void main() {
  // coordenada diagonal: gira el UV para que las bandas crucen el vidrio en oblicuo
  float s = sin(bandAngle), c = cos(bandAngle);
  vec2 p = vUvG - 0.5;
  float t = p.x * c - p.y * s + 0.5;

  // dos bandas de anchos distintos: una ancha y tenue, otra fina y viva (asi no se lee simetrico)
  float streak = band(t, 0.34, 0.16) * 0.55 + band(t, 0.62, 0.055) * 1.0;

  // fresnel: el vidrio se enciende cuando lo miras de canto.
  // La normal llega como varying del vertice y NO se deduce con dFdx/dFdy del vector de vista:
  // en un plano esas derivadas son casi paralelas, su producto cruzado tiende a cero y el
  // fresnel sale con ruido en los bordes del triangulo.
  float f = 1.0 - clamp(abs(dot(normalize(vNormG), normalize(vViewG))), 0.0, 1.0);
  float fres = pow(f, fresnelPower) * fresnelStrength;

  // el vidrio recoge mas luz en la parte alta
  float vgrad = mix(0.45, 1.0, vUvG.y);

  float a = (streak * bandStrength + fres) * vgrad * opacityG;
  gl_FragColor = vec4(tint * a, a);
}`;

// Monta el destello sobre la malla llamada `window_glass`. Devuelve { material, uniforms, undo }
// o null si el GLB no trae el plano (visores viejos siguen funcionando sin el).
export function applyWindowGlass(root, opts = {}) {
  let mesh = null;
  root.traverse((o) => { if (o.isMesh && o.name === 'window_glass') mesh = o; });
  if (!mesh) return null;

  const uniforms = {
    tint: { value: new THREE.Color(opts.tint ?? 0xbcd8ff) },
    bandStrength: { value: opts.bandStrength ?? 0.16 },
    fresnelStrength: { value: opts.fresnelStrength ?? 0.30 },
    fresnelPower: { value: opts.fresnelPower ?? 2.6 },
    bandAngle: { value: opts.bandAngle ?? 0.62 },   // rad
    opacityG: { value: opts.opacity ?? 1.0 },
  };
  const material = new THREE.ShaderMaterial({
    uniforms, vertexShader: VERT, fragmentShader: FRAG,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,     // no debe tapar la ciudad ni escribir profundidad para el contorno
    depthTest: true,
    side: THREE.DoubleSide,
    toneMapped: false,
  });
  material.name = 'Window_Glass_fx';

  const old = mesh.material;
  mesh.material = material;
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.renderOrder = 2;    // despues de la ciudad emisiva

  return { mesh, material, uniforms, undo: () => { mesh.material = old; } };
}

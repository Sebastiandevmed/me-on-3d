// Estados de camara con nombre e interpolacion suavizada.
//
// Coordenadas glTF (x, y, z) = Blender (x, z, -y). El personaje se sienta en el origen y mira
// a -Z; el escritorio y los monitores estan en z ~ -1.0..-1.35 (delante de el), la ventana y las
// barras RGB en z ~ +1.7 (detras) y la repisa con la moto en x ~ +1.5.
//
// Por eso "ver las pantallas" NO es girar los monitores: hay que rodear hasta quedar DETRAS del
// personaje, porque las caras emisivas apuntan hacia el (+Z).
//
// La interpolacion es suavizado exponencial por TIEMPO (1 - exp(-dt/tau)), igual que el
// seguimiento de cursor. Por frame se sentiria distinto a 30 y a 120 fps.

export const CAMERA_STATES = {
  // Encuadre de aprobacion de la sesion 2 (equivale a la camara de Blender -1.3, 3.7, 1.95).
  // Rama ajuste-velo-camara: posiciones ~0.45 m mas cerca y fov +3 grados para que el personaje
  // ocupe mas cuadro sin invadir la columna de texto (la derecha); stack NO se toca porque su
  // angulo es el unico desde el que se leen los monitores encendidos.
  // Vertical (sesion 12): la camara se va a la esquina delantera izquierda del cuarto y mira
  // en diagonal hacia +X, para que el grafiti del nombre (pared +X, lib/graffiti.js) entre
  // ENTERO a la izquierda y el personaje quede de perfil a la derecha, todo en el 40 % de
  // arriba, que es lo que deja libre la columna de texto. De frente (encuadre anterior) el
  // grafiti no entraba en cuadro: con 375 px de ancho el fov horizontal es de ~28 grados.
  // Elegido con capturas (scratchpad movil_hero.mjs, variantes A-I y H2/H3).
  hero:      { pos: [-1.35, 1.90, -3.25], target: [0.00, 1.00, -0.60], fov: 41,
               movil: { pos: [-1.75, 1.25, -2.95], target: [1.00, 0.30, 0.20], fov: 58 } },
  // Retrato 3/4: el personaje se va al tercio izquierdo y deja sitio a la columna de texto.
  sobreMi:   { pos: [-0.95, 1.62, -2.15], target: [-0.10, 1.30, -0.35], fov: 34,
               movil: { pos: [-0.80, 1.66, -2.10], target: [-0.05, 0.95, -0.35], fov: 48 } },
  // Sobre el hombro: unica posicion desde la que se leen los monitores encendidos.
  stack:     { pos: [ 0.62, 1.80,  0.85], target: [0.00, 1.12, -1.30], fov: 42,
               movil: { pos: [ 0.12, 2.15,  1.15], target: [0.00, 0.35, -1.40], fov: 46 } },
  // Plano general desde la derecha: entra la repisa con la DR150, la ventana y el escritorio
  // entero, y el tercio derecho queda oscuro para la columna de texto.
  // Ojo: este estado estaba en x = 2.35, que cae FUERA de la pared derecha del cuarto, y la
  // seccion salia en negro. Se eligio con capturas (scratchpad camtest), no a ojo.
  proyectos: { pos: [ 1.45, 1.85, -3.10], target: [0.20, 1.10, -0.60], fov: 40,
               movil: { pos: [ 1.15, 1.80, -2.95], target: [0.15, 0.70, -0.60], fov: 52 } },
  // Primer plano frontal para cerrar.
  contacto:  { pos: [-0.30, 1.58, -1.70], target: [0.00, 1.32, -0.30], fov: 31,
               movil: { pos: [-0.25, 1.60, -1.80], target: [0.00, 1.05, -0.30], fov: 43 } },
};

// En vertical (375 x 812 = aspecto 0.46 contra el 1.6 del escritorio) el fov es VERTICAL, asi que
// el encuadre horizontal se derrumba: con los numeros de escritorio el personaje sale cortado y
// pegado al borde. Cada estado lleva por eso una variante `movil` con mas angulo y el punto de
// mira mas bajo (mirar mas abajo sube al personaje en el cuadro, que es donde tiene que estar
// porque el texto ocupa la mitad de abajo). Se eligieron con capturas de tools/landing_probe.mjs.
export const esMovil = () => matchMedia('(max-width: 820px)').matches;

// La camara no salta al estado: lo persigue. tau alto = viaje largo y perezoso.
const TAU = 0.9;

export function createCameraPath(camera, states = CAMERA_STATES, opts = {}) {
  const tau = opts.tau ?? TAU;
  const V = (a) => ({ x: a[0], y: a[1], z: a[2] });
  // `variante` elige entre el encuadre de escritorio y el vertical del propio estado.
  let variante = opts.variant || null;
  const pick = (s) => (variante && s[variante] ? s[variante] : s);
  const clone = (st) => { const s = pick(st); return { pos: V(s.pos), target: V(s.target), fov: s.fov }; };

  let name = opts.start && states[opts.start] ? opts.start : Object.keys(states)[0];
  const goal = clone(states[name]);
  const now = clone(states[name]);          // estado que se dibuja este frame
  // Paralaje: desplazamiento pequeño de la camara con el cursor. Va aparte del estado para que
  // no contamine la interpolacion (si se sumara al goal, cada movimiento de mouse reiniciaria el viaje).
  const par = { x: 0, y: 0 }, parGoal = { x: 0, y: 0 };
  const PAR = opts.parallax ?? 0;

  const lerp = (a, b, k) => a + (b - a) * k;

  return {
    get state() { return name; },
    states,
    /** Cambia entre encuadre de escritorio (null) y vertical ('movil') y re-apunta al estado
     *  actual. Se llama en el resize: girar el telefono cambia el encuadre correcto. */
    setVariant(v) {
      if ((v || null) === variante) return false;
      variante = v || null;
      const s = clone(states[name]);
      goal.pos = s.pos; goal.target = s.target; goal.fov = s.fov;
      return true;
    },
    /** Cambia el estado destino. Devuelve false si el nombre no existe (asi la landing no rompe
     *  si una seccion queda sin estado). */
    goTo(next) {
      if (!states[next]) return false;
      if (next === name) return true;
      name = next;
      const s = clone(states[next]);
      goal.pos = s.pos; goal.target = s.target; goal.fov = s.fov;
      return true;
    },
    /** Coloca la camara en el estado sin viaje (carga inicial, prefers-reduced-motion). */
    snap(next) {
      if (next) { if (!states[next]) return false; name = next; const s = clone(states[next]); goal.pos = s.pos; goal.target = s.target; goal.fov = s.fov; }
      now.pos = { ...goal.pos }; now.target = { ...goal.target }; now.fov = goal.fov;
      return true;
    },
    /** mx, my en [-1, 1] (mismo espacio que el cursor del visor). */
    setParallax(mx, my) { parGoal.x = mx * PAR; parGoal.y = my * PAR; },
    /** Escribe camera.position / fov y devuelve el target para OrbitControls o camera.lookAt(). */
    update(dt, target) {
      const k = 1 - Math.exp(-dt / tau);
      now.pos.x = lerp(now.pos.x, goal.pos.x, k); now.pos.y = lerp(now.pos.y, goal.pos.y, k); now.pos.z = lerp(now.pos.z, goal.pos.z, k);
      now.target.x = lerp(now.target.x, goal.target.x, k); now.target.y = lerp(now.target.y, goal.target.y, k); now.target.z = lerp(now.target.z, goal.target.z, k);
      now.fov = lerp(now.fov, goal.fov, k);
      par.x = lerp(par.x, parGoal.x, 1 - Math.exp(-dt / 0.5));
      par.y = lerp(par.y, parGoal.y, 1 - Math.exp(-dt / 0.5));
      camera.position.set(now.pos.x + par.x, now.pos.y + par.y, now.pos.z);
      if (Math.abs(camera.fov - now.fov) > 1e-3) { camera.fov = now.fov; camera.updateProjectionMatrix(); }
      if (target) target.set(now.target.x, now.target.y, now.target.z);
      return now;
    },
    /** Distancia que falta hasta el estado destino: la sonda lo usa para esperar a que llegue. */
    get distance() { return Math.hypot(goal.pos.x - now.pos.x, goal.pos.y - now.pos.y, goal.pos.z - now.pos.z); },
  };
}

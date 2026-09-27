import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);

window.__muroGsap = true;

// Colores de marca de cada proyecto, sin la -x hex para interpolar rgb.
const COLORES = ['#e03989', '#9db26f', '#4090ff'];
const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];

export function animaProyectos() {
  const sec = document.getElementById('proyectos');
  const tint = document.getElementById('tintabg');
  const muros = gsap.utils.toArray('.muro');
  if (!muros.length || !sec || !tint) return;
  window.__muroST = muros.length;

  const quieto = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // En movil la galeria no tiene margen y el tilt de una pieza de 2000 px desborda:
  // viajes mas cortos y un penduleo sutil. Escritorio conserva el viaje completo.
  const angosto = matchMedia('(max-width:820px)').matches;
  const ESC = angosto ? 0.55 : 1;   // factor de viajes (entrada + parallax) en movil
  const AMP = angosto ? 4 : 10;     // grados del penduleo en movil / escritorio

  // El fondo de proyectos no pinta negro: el tinte de color se ve detras.
  const centro = () => innerHeight / 2;

  // ---- Tinte de fondo: interpola el color central del gradiente segun cual muro domina el
  // centro de la ventana. Es un cambio de COLOR, no movimiento: se conserva en modo reducido.
  const ACTUAL = { a: hex(COLORES[0]), b: hex(COLORES[0]), c: hex(COLORES[0]) };
  ScrollTrigger.create({
    trigger: sec,
    start: 'top center',
    end: 'bottom center',
    scrub: true,
    onUpdate() {
      const pro = muros.map((m) => {
        const r = m.getBoundingClientRect();
        const d = Math.abs((r.top + r.height / 2) - centro());
        return Math.max(0, 1 - d / (innerHeight * 0.75));
      });
      let total = pro.reduce((a, b) => a + b, 1e-6);
      const mezcla = [0, 0, 0];
      for (let i = 0; i < muros.length; i++) {
        const w = pro[i] / total;
        const c = hex(COLORES[i]);
        mezcla[0] += c[0] * w; mezcla[1] += c[1] * w; mezcla[2] += c[2] * w;
      }
      ACTUAL.a = ACTUAL.b; ACTUAL.b = ACTUAL.c; ACTUAL.c = [Math.round(mezcla[0]), Math.round(mezcla[1]), Math.round(mezcla[2])];
      // Oscurecer para legibilidad: el centro del gradiente mezcla el color con el negro base.
      const final = ACTUAL.c.map((v) => Math.round(v * 0.5));
      tint.style.background =
        `radial-gradient(90% 65% at 50% 55%,rgb(${final[0]},${final[1]},${final[2]}),var(--noche) 82%)`;
    },
  });

  // Reposo total: nada de transforms ni parallax, el contenido entra ya montado.
  if (quieto) return;

  muros.forEach((muro) => {
    const dir = Number(muro.dataset.dir || -1);
    const num = muro.querySelector('.num-fondo');
    const titulo = muro.querySelector('.muro-titulo');
    const medios = muro.querySelector('.medios');
    const cuerpo = muro.querySelector('.cuerpo');
    const inner = muro.querySelector('.muro-inner');
    if (!num || !titulo || !medios || !cuerpo || !inner) return;

    // ---- ENTRADA. Cada capa viaja en X (signo por data-dir) y hace fade; el numero y los
    // mockups crecen desde el centro. El eje Y NO se anima aqui a proposito: lo escribe el
    // parallax de abajo, que corre SIEMPRE (incluso antes de que la entrada arranque), y si dos
    // tweens pelearan por el mismo eje el segundo se tragaba el viaje de otros y salia roto.
    gsap.timeline({
      scrollTrigger: { trigger: muro, start: 'top 92%', end: 'center 40%', scrub: 0.7 },
    })
      .fromTo(inner,
        { y: 110 * ESC, scale: 0.98, opacity: 0, transformOrigin: '50% 60%' },
        { y: 0, scale: 1, opacity: 1, ease: 'none' }, 0)
      .fromTo(num,
        { x: 160 * dir * ESC, opacity: 0 },
        { x: 0, opacity: 1, ease: 'none' }, 0)
      .fromTo(titulo,
        { x: 120 * dir * ESC, opacity: 0 },
        { x: 0, opacity: 1, ease: 'none' }, 0.12)
      .fromTo(medios,
        { scale: 0.9, opacity: 0 },
        { scale: 1, opacity: 1, ease: 'none' }, 0.28)
      .fromTo(cuerpo,
        { x: 100 * -dir * ESC, opacity: 0 },
        { x: 0, opacity: 1, ease: 'none' }, 0.44);

    // ---- PARALLAX mientras el muro cruza la pantalla. Cada capa viaja en Y a velocidad
    // distinta: el numero (el mas atras) se queda, el cuerpo (delante) se adelanta. Sobre eso,
    // el muro pendula en rotationY al pasar por el centro: se siente como un plano que gira.
    ScrollTrigger.create({
      trigger: muro,
      start: 'top bottom',
      end: 'bottom top',
      scrub: true,
      onUpdate(self) {
        const enCentro = (muro.getBoundingClientRect().top + muro.getBoundingClientRect().height / 2) - centro();
        const lejos = Math.max(-1, Math.min(1, enCentro / innerHeight)) * ESC;

        gsap.set(num, { y: lejos * -150 });
        gsap.set(titulo, { y: lejos * -45 });
        gsap.set(medios, { y: lejos * 25 });
        gsap.set(cuerpo, { y: lejos * 90 });

        // El penduleo arranca en 0 al asomarse y vuelve a 0 al salir: solo pendula cerca del
        // centro. La perspectiva la da el padre (.galeria), un solo contexto 3D para todo.
        const swing = Math.sin(self.progress * Math.PI) * AMP * dir;
        gsap.set(muro, { rotationY: swing });
      },
    });
  });
}
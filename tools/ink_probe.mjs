#!/usr/bin/env node
// Sonda de TINTA: mide y fotografia los trazos negros que el pase de contorno pinta sobre el
// personaje, en primer plano y en varias poses de la cabeza.
//
// Para que existe. En la sesion 9 el reporte fue "al moverse se crean pequenas lineas y rayas
// negras que luego desaparecen, y hay rayones abstractos por el resto del avatar". La causa no
// eran ni las sombras ni el bloom (apagarlos no cambiaba nada) sino el termino de NORMALES del
// contorno, que entintaba el ruido de la malla de Meshy: con ?outline=0 los rayones desaparecian
// por completo. Parpadeaban porque cada pixel dudoso cruzaba el escalon del umbral en un frame y
// volvia al siguiente. Esta sonda es la que permite comprobarlo sin tener que mirar el visor a
// ojo, y la que hay que volver a correr si se tocan los umbrales del contorno.
//
// Que mide: __inkFrac(), la fraccion de pixeles mas oscuros que sus dos vecinos, o sea la
// densidad de TRAZOS finos. En este encuadre casi todo es personaje. Ojo al interpretarla: sube
// tanto si hay mas rayones como si los trazos legitimos son mas anchos (una rampa mas suave los
// ensancha), asi que la cifra sirve para comparar variantes del MISMO parametro y las capturas
// son la prueba de verdad.
//
// Uso: node tools/ink_probe.mjs                     -> variante por defecto
//      VARIANTS='["","isens=1","outline=0"]' node tools/ink_probe.mjs
//        ""          el look actual
//        isens=1     sensibilidad a tinta plana: el comportamiento anterior al arreglo
//        outline=0   sin contorno: lo que quede en pantalla NO lo pinta este pase
//      DIR=<carpeta> para servir otra copia de export/ (comparar contra otra version)
// Salida: generated/renders/ink_<variante>_p<pose>.png y una linea INK por variante.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const DIR = process.env.DIR || join(ROOT, 'export');
const PORT = 8776, DBG = 9346;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: DIR, stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-ink')}`,
  '--window-size=1000,1000', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('INK no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });   // sin esto se mide un GLB viejo del cache
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;

// Cuatro poses del cursor: la cabeza gira y con ella el buffer de normales, que es lo que
// decide donde cae la tinta. Un rayon que solo aparece en una pose es justo el que parpadea.
const POSES = [[500, 400], [120, 400], [880, 400], [500, 760]];
const VARIANTS = JSON.parse(process.env.VARIANTS || '[""]');
const fails = [];
for (const q of VARIANTS) {
  const tag = (q || 'base').replace(/[^a-z0-9]/gi, '_');
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html?pdb=1` + (q ? '&' + q : '') });
  let loaded = false;
  for (let i = 0; i < 60 && !loaded; i++) { await sleep(500); loaded = await ev('!!(window.__status && __status.loaded && __status.env)'); }
  if (!loaded) { fails.push(`[${tag}] el visor no cargo: ${await ev('JSON.stringify(window.__errors || [])')}`); continue; }
  await sleep(5200);   // deja pasar el intro
  // Encuadre de la cara leyendo la posicion del hueso de la cabeza, como en face_shot.mjs.
  await ev(`(() => { const v = window.__view, T = v.THREE, h = v.follow().head, p = new T.Vector3();
    h.getWorldPosition(p); p.y += 0.02; v.controls.target.copy(p);
    v.camera.position.set(p.x + 0.10, p.y + 0.06, p.z - 0.85); v.controls.update(); return 1; })()`);
  const vals = [];
  for (let i = 0; i < POSES.length; i++) {
    await ev(`dispatchEvent(new PointerEvent('pointermove',{clientX:${POSES[i][0]},clientY:${POSES[i][1]}}));1`);
    await sleep(2200);   // el seguimiento de cabeza tiene TAU 0.35 s: hay que dejarlo asentar
    vals.push(await ev('window.__inkFrac()'));
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(OUT, `ink_${tag}_p${i}.png`), Buffer.from(sh.result.data, 'base64'));
  }
  const errs = await ev('JSON.stringify(window.__errors)');
  if (errs !== '[]') fails.push(`[${tag}] errores de pagina: ${errs}`);
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  console.log(`INK ${tag.padEnd(12)} poses: ${vals.map((v) => (v * 100).toFixed(2) + '%').join('  ')}   media ${(avg * 100).toFixed(2)}%`);
}
ws.close(); cleanup();
if (fails.length) { for (const f of fails) console.error('INK FAIL', f); process.exit(1); }
console.log('INK OK');
process.exit(0);

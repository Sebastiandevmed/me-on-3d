#!/usr/bin/env node
// Primer plano de la CARA en el visor real (cel-shading + contorno + bloom), que es donde de
// verdad se juzgan barba, cejas y boca: los renders de Blender son PBR y mienten sobre el look
// final — un tono que en PBR se ve gris medio, con bandas y contorno colapsa a negro plano.
//
// Reusa el arnes de tools/preview_probe.mjs (Chrome headless por CDP) pero en vez de las
// capturas de conjunto encuadra la cabeza usando window.__view, que preview.html expone
// justo para esto.
//
// Uso: node tools/face_shot.mjs            -> generated/renders/cara_cel.png
//      PREVIEW_QUERY="fx=off" node ...     -> para comparar contra el look anterior
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const PORT = 8767, DBG = 9335;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-face')}`,
  '--window-size=1100,1100', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('FACE no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });
const EXTRA = (process.env.PREVIEW_QUERY || '').replace(/^[?&]/, '');
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html?pdb=1` + (EXTRA ? '&' + EXTRA : '') });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); console.log('FACE shot', name); };

let loaded = false;
for (let i = 0; i < 60 && !loaded; i++) { await sleep(500); loaded = await ev('!!(window.__status && __status.loaded && __status.env)'); }
if (!(await ev('!!window.__status'))) {
  console.error('FACE el modulo del visor NO se ejecuto:', await ev('JSON.stringify(window.__errors || [])'));
  process.exit(1);
}
if (!loaded) { console.error('FACE el GLB no cargo a tiempo'); process.exit(1); }
await sleep(5000);   // deja pasar el intro para que la cabeza este en reposo

// Encuadre: la camara se pone delante de la cabeza a `dist` metros y mira a ella. La cabeza es
// el hueso spine006, cuya posicion de mundo se lee del propio visor.
const frame = (dist, dy) => `(() => {
  const v = window.__view, THREE = v.THREE;
  const head = v.follow().head;
  const p = new THREE.Vector3(); head.getWorldPosition(p);
  p.y += ${dy};
  // El personaje mira a -Z en glTF: la camara va DELANTE, o sea restando en z.
  v.camera.position.set(p.x + 0.09, p.y + 0.04, p.z - ${dist});
  v.controls.target.copy(p);
  v.camera.fov = 26; v.camera.updateProjectionMatrix();
  v.controls.update();
  return JSON.stringify([p.x, p.y, p.z].map(n => +n.toFixed(3)));
})()`;
console.log('FACE cabeza en', await ev(frame(0.55, -0.01)));
await sleep(1200);
await shot('cara_cel.png');

// segundo encuadre: cejas levantadas, para ver la forma nueva en movimiento
await ev('window.__view.browup()');
await sleep(350);
await shot('cara_cel_browup.png');

console.log('FACE errores', await ev('JSON.stringify(window.__errors || [])'));
console.log('FACE OK');
cleanup(); process.exit(0);

#!/usr/bin/env node
// Barrido de parametros del look: abre preview.html una vez por variante y guarda una captura
// de cada una en generated/renders/sweep/. Sirve para calibrar el cel-shading sin editar
// codigo entre pruebas (todos los numeros del look se aceptan por query, ver preview.html).
//
// Uso:  node tools/look_sweep.mjs "amb=0.3&key=7" "amb=0.15&key=4" ...
//       node tools/look_sweep.mjs --name base "" --name apagado "fx=off"
// Con --zoom acerca la camara a la cabeza (encuadre de detalle via window.__view).
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders', 'sweep'); mkdirSync(OUT, { recursive: true });
const PORT = 8767, DBG = 9335;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// argumentos: [--zoom] [--name X] query ...
const args = process.argv.slice(2);
const ZOOM = args.includes('--zoom');
const variants = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--zoom') continue;
  if (args[i] === '--name') { variants.push({ name: args[++i], q: args[++i] ?? '' }); continue; }
  variants.push({ name: null, q: args[i] });
}
if (!variants.length) variants.push({ name: 'base', q: '' });
variants.forEach((v, i) => { v.name = v.name || (v.q.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'base') || `v${i}`; });

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-sweep')}`,
  '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('SWEEP no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;

let bad = 0;
for (const v of variants) {
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html?pdb=1${v.q ? '&' + v.q : ''}` });
  let ok = false;
  for (let i = 0; i < 40 && !ok; i++) { await sleep(400); ok = await ev('!!(window.__status && __status.loaded && __status.env)'); }
  await sleep(4200);   // intro + fundido de pantallas
  await ev(`dispatchEvent(new MouseEvent('mousemove',{clientX:720,clientY:420}));1`);
  if (ZOOM) {   // encuadre de detalle de la cabeza
    await ev(`(() => { const v = window.__view; const h = v.follow().head; if (!h) return 0;
      const p = new v.THREE.Vector3(); h.getWorldPosition(p);
      v.controls.target.copy(p); v.camera.position.set(p.x - 0.45, p.y + 0.06, p.z - 0.95); v.controls.update(); return 1; })()`);
  }
  await sleep(1200);
  const r = await send('Page.captureScreenshot', { format: 'png' });
  const file = `${v.name}${ZOOM ? '_zoom' : ''}.png`;
  writeFileSync(join(OUT, file), Buffer.from(r.result.data, 'base64'));
  const ink = await ev('window.__inkFrac ? __inkFrac().toFixed(4) : "-"');
  const errs = await ev('JSON.stringify(window.__errors)');
  if (!ok || errs !== '[]') bad++;
  console.log(`SWEEP ${file.padEnd(34)} loaded=${ok} ink=${ink} errors=${errs}`);
}
ws.close(); cleanup();
console.log(bad ? `SWEEP ${bad} variante(s) con problemas` : 'SWEEP OK');
process.exit(bad ? 1 : 0);

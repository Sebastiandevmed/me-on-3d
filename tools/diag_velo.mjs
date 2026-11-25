#!/usr/bin/env node
// Diagnostico A/B: ?por que el 3D en la landing se ve con menos definicion y luz que en el
// visor (preview.html)? Hipotesis: (1) el velo de legibilidad .escena::before oscurece la mitad
// derecha de la escena (donde esta la ventana y las barras RGB) y (2) la camara bloqueada queda
// mas lejos que el encuadre de orbit del visor, asi que el personaje ocupa menos cuadro.
// Genera en generated/renders/:
//   landing_hero_actual.png   lo que ve el usuario hoy
//   landing_hero_sinvelo.png  igual pero sin el darkening de legibilidad
//   landing_hero_cerca.png    sin velo y con la camara acercada (como al orbitar en el visor)
// Uso: node tools/diag_velo.mjs
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const PORT = 8787, DBG = 9349;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-diagvelo')}`,
  '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable');
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); console.log('¡' + name); };
const irA = async (s) => { await ev(`document.getElementById('${s}').scrollIntoView({behavior:'instant',block:'start'});1`); await sleep(2600); };

await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html?modo=hibrido` });
let listo = false;
for (let i = 0; i < 60 && !listo; i++) { await sleep(500); listo = await ev('!!(window.__landing && __landing.status.loaded && __landing.status.env)'); }
if (!listo) { console.error('no cargo la escena'); process.exit(1); }
await sleep(4000); // intro + fundido de pantallas

await irA('hero');
await shot('landing_hero_actual.png');
await ev(`document.querySelector('style').insertAdjacentHTML('beforebegin','<style id="diagvelo">.escena::before{display:none!important}</style>');1`); await sleep(600);
await shot('landing_hero_sinvelo.png');

// La camara acercada imita lo que hace uno al orbitar en el visor (preview.html).
await ev(`__landing.camara.states.hero = { pos:[-1.35,1.55,-2.1], target:[0,1.05,-0.6], fov:46, movil:{ pos:[-0.9,1.7,-2.0], target:[0.05,0.7,-0.55], fov:52 } };
  __landing.camara.snap('hero');1`); await sleep(1200);
await shot('landing_hero_cerca.png');

await irA('stack');
await shot('landing_stack_actual.png');
await shot('landing_stack_sinvelo.png');

process.exit(0);
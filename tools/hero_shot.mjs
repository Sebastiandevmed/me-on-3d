#!/usr/bin/env node
// Captura rapida del hero de la landing (escritorio 1440x900 y vertical 375x812) mas dos primeros
// planos del grafiti via preview.html (camara libre). Es la vuelta corta para calibrar la pared:
// tarda ~40 s contra los ~3 min de landing_probe.mjs, que sigue siendo la verificacion oficial.
//
// Uso: node tools/hero_shot.mjs ["gdepth=0.08&gink=0.4"]     (query extra para index y preview)
//      TAG=_v2 node tools/hero_shot.mjs                        (sufijo de los archivos)
// Salida: generated/renders/sweep/hero_desk.png, hero_movil.png, hero_close.png, hero_close2.png
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = process.env.OUT || join(ROOT, 'generated', 'renders', 'sweep'); mkdirSync(OUT, { recursive: true });
const TAG = process.env.TAG || '';
const EXTRA = process.argv[2] ? '&' + process.argv[2] : '';
const PORT = 8781, DBG = 9351;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: ROOT + '/export', stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${tmpdir()}/me3d-hero`, '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);
let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(`${OUT}/${name}${TAG}.png`, Buffer.from(r.result.data, 'base64')); };
const metrics = (w, h, movil) => send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: movil ? 2 : 1, mobile: movil });

await metrics(1440, 900, false);
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html?modo=hibrido${EXTRA}` });
let listo = false;
for (let i = 0; i < 60 && !listo; i++) { await sleep(500); listo = await ev('!!(window.__landing && __landing.status.loaded && __landing.status.env)'); }
await sleep(4500);
await shot('hero_desk');
await metrics(375, 812, true); await sleep(3000);
await shot('hero_movil');
console.log('errores landing:', await ev('JSON.stringify(window.__errors||[])'));

// primer plano del grafiti en preview.html (camara libre)
await metrics(1440, 900, false);
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html?pdb=1${EXTRA}` });
let ok = false;
for (let i = 0; i < 40 && !ok; i++) { await sleep(400); ok = await ev('!!(window.__status && __status.loaded && __status.env)'); }
await sleep(4000);
await ev(`(() => { const v = window.__view; v.controls.target.set(2.045, 1.2, 0.1); v.camera.position.set(-0.3, 1.35, -1.9); v.controls.update(); return 1; })()`);
await sleep(800);
await shot('hero_close');
await ev(`(() => { const v = window.__view; v.controls.target.set(2.045, 1.3, 0.6); v.camera.position.set(1.2, 1.4, -0.9); v.controls.update(); return 1; })()`);
await sleep(800);
await shot('hero_close2');
console.log('errores preview:', await ev('JSON.stringify(window.__errors||[])'));
ws.close(); cleanup(); process.exit(0);

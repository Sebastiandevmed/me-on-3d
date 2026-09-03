#!/usr/bin/env node
// Sonda headless del visor: sirve export/, abre Chrome headless con CDP, espera la carga,
// mueve el mouse, dispara vibe y guarda capturas en generated/renders/. Imprime PROBE ... y
// sale con 1 si hubo errores en pagina o no cargo el GLB.
// Uso: node tools/preview_probe.mjs   (requiere Google Chrome y Node >= 22)
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const PORT = 8766, DBG = 9334;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-probe')}`,
  '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('PROBE no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable');
// El perfil de Chrome (--user-data-dir) sobrevive entre corridas: sin esto el navegador reusa
// avatar.glb / preview.html del cache HTTP y la sonda mide un modelo VIEJO (sintoma tipico:
// hpQ null porque el GLB cacheado no tiene el hueso 'headphones').
await send('Network.enable'); await send('Network.setCacheDisabled', { cacheDisabled: true });
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/preview.html` });
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }); return r.result?.result?.value; };
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); console.log('PROBE shot', name); };
const mv = (x, y) => ev(`dispatchEvent(new MouseEvent('mousemove',{clientX:${x},clientY:${y}}));1`);

let loaded = false;
for (let i = 0; i < 60 && !loaded; i++) { await sleep(500); loaded = await ev('!!(window.__status && __status.loaded && __status.env)'); }
await sleep(4500);                                  // intro (3 s) + fundido de pantallas
await mv(720, 420); await sleep(1500);
const status = await ev('JSON.stringify({loaded:__status.loaded,env:__status.env,fps:__status.fps,shadows:__status.shadows,lights:__status.lights,clips:__status.clips(),headQ:__status.headQ(),neckQ:__status.neckQ(),chestQ:__status.chestQ(),hpQ:__status.hpQ()})');
console.log('PROBE status', status);
const st = JSON.parse(status);
await shot('preview_shot.png');
await mv(40, 300); await sleep(2000);
const headLeft = await ev('JSON.stringify(__status.headQ())');
const neckLeft = await ev('JSON.stringify(__status.neckQ())');
console.log('PROBE headQ izquierda', headLeft);
// distancia euclidea entre el cuaternion de la cabeza en el centro y a la izquierda: el
// seguimiento del cursor gira ~0.2-0.3 en el componente y, asi que < 0.1 = no se movio.
const qd = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));
const headDist = (st.headQ && headLeft) ? qd(st.headQ, JSON.parse(headLeft)) : 0;
console.log('PROBE headQ dist', headDist.toFixed(4));
const neckDist = (st.neckQ && neckLeft) ? qd(st.neckQ, JSON.parse(neckLeft)) : 0;
console.log('PROBE neckQ dist', neckDist.toFixed(4));
await shot('preview_shot_look.png');
await mv(720, 420); await ev('window.__vibe && window.__vibe(); 1'); await sleep(2200);
console.log('PROBE vibe', await ev('JSON.stringify({ex:__status.exclusive,clips:__status.clips(),hpQ:__status.hpQ()})'));
await shot('preview_shot_vibe.png');
const errors = await ev('JSON.stringify(window.__errors)');
console.log('PROBE errors', errors);
ws.close(); cleanup();

// Aserciones sobre lo que produjo la Task 6 del plan de pulido: sin esto la sonda pasaba con
// solo "cargo y no hubo excepciones", que no cubre audifonos, sombras, luces ni seguimiento.
const fails = [];
if (!loaded) fails.push('el visor no cargo (window.__status.loaded/env)');
if (errors !== '[]') fails.push(`errores de pagina: ${errors}`);
if (st.hpQ === null || st.hpQ === undefined) fails.push('hpQ es null: el GLB no trae el nodo headphones');
if (st.shadows !== true) fails.push(`shadows=${st.shadows} (esperado true)`);
if (st.lights !== 9) fails.push(`lights=${st.lights} (esperado 9)`);
if (!(headDist >= 0.1)) fails.push(`la cabeza no sigue al cursor: dist(headQ centro, izquierda)=${headDist.toFixed(4)} < 0.1`);
if (!(neckDist >= 0.03)) fails.push(`el cuello no acompana a la cabeza: dist(neckQ centro, izquierda)=${neckDist.toFixed(4)} < 0.03`);
if (fails.length) { for (const f of fails) console.error('PROBE FAIL', f); process.exit(1); }
console.log('PROBE OK');
process.exit(0);

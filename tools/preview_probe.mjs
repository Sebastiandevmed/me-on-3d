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
// pdb=1 enciende preserveDrawingBuffer para poder medir la imagen final con __inkFrac().
const EXTRA = (process.env.PREVIEW_QUERY || '').replace(/^[?&]/, '');
const url = (q) => `http://127.0.0.1:${PORT}/preview.html?pdb=1` + (EXTRA ? '&' + EXTRA : '') + (q ? '&' + q : '');
await send('Page.navigate', { url: url() });   // PREVIEW_QUERY="mat=toon" para probar variantes
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }); return r.result?.result?.value; };
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); console.log('PROBE shot', name); };
// pointermove y no mousemove: lib/scene.js escucha el primero para que el seguimiento tambien
// funcione arrastrando el dedo en un telefono. Un raton real dispara los dos.
const mv = (x, y) => ev(`dispatchEvent(new PointerEvent('pointermove',{clientX:${x},clientY:${y}}));1`);

let loaded = false;
for (let i = 0; i < 60 && !loaded; i++) { await sleep(500); loaded = await ev('!!(window.__status && __status.loaded && __status.env)'); }
// Si el modulo del visor no llega ni a EJECUTARSE (un error de sintaxis en preview.html o en
// cualquier lib/*.js, o un import que da 404) entonces window.__status ni siquiera existe, y la
// linea de abajo reventaba con un opaco `"undefined" is not valid JSON`. Se distingue ese caso
// del "cargo pero tardo" y se imprimen los errores que la pagina haya recogido en window.__errors.
if (!(await ev('!!window.__status'))) {
  const errs = await ev('JSON.stringify(window.__errors || [])');
  console.error('PROBE el modulo del visor NO se ejecuto: window.__status no existe.');
  console.error('PROBE errores de la pagina:', errs);
  console.error('PROBE revisar sintaxis de export/preview.html y export/lib/*.js '
                + '(node --check sobre una copia .mjs de cada modulo)');
  process.exit(1);
}
await sleep(4500);                                  // intro (3 s) + fundido de pantallas
await mv(720, 420); await sleep(1500);
const status = await ev('JSON.stringify({gpu:__status.gpu,loaded:__status.loaded,env:__status.env,fps:__status.fps,shadows:__status.shadows,lights:__status.lights,fx:__status.fx,clips:__status.clips(),headQ:__status.headQ(),neckQ:__status.neckQ(),chestQ:__status.chestQ(),hpQ:__status.hpQ()})');
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

// --- A/B del look: misma escena con fx=off (PBR anterior). Sirve de comparativa para el
// usuario y de medida: el contorno tiene que subir la fraccion de pixeles casi negros.
await mv(720, 420); await sleep(800);
const inkFx = await ev('window.__inkFrac ? __inkFrac() : -1');
await send('Page.navigate', { url: url('fx=off') });
let loadedOff = false;
for (let i = 0; i < 60 && !loadedOff; i++) { await sleep(500); loadedOff = await ev('!!(window.__status && __status.loaded && __status.env)'); }
await sleep(4500); await mv(720, 420); await sleep(1500);
await shot('preview_shot_pbr.png');
const inkOff = await ev('window.__inkFrac ? __inkFrac() : -1');
const errorsOff = await ev('JSON.stringify(window.__errors)');
console.log('PROBE ink fx=on', inkFx, 'fx=off', inkOff);
console.log('PROBE errors fx=off', errorsOff);
ws.close(); cleanup();

// Aserciones sobre lo que produjo la Task 6 del plan de pulido: sin esto la sonda pasaba con
// solo "cargo y no hubo excepciones", que no cubre audifonos, sombras, luces ni seguimiento.
const fails = [];
if (!loaded) fails.push('el visor no cargo (window.__status.loaded/env)');
if (errors !== '[]') fails.push(`errores de pagina: ${errors}`);
if (st.hpQ === null || st.hpQ === undefined) fails.push('hpQ es null: el GLB no trae el nodo headphones');
if (st.shadows !== true) fails.push(`shadows=${st.shadows} (esperado true)`);
if (!(st.lights >= 9)) fails.push(`lights=${st.lights} (esperado >= 9)`);
// El look cel: materiales toon + cadena de 5 pases (render, bloom, contorno, viñeta, output).
if (!st.fx || st.fx.on !== true) fails.push(`fx apagado: ${JSON.stringify(st.fx)}`);
else if (st.fx.passes !== 5) fails.push(`pases del composer=${st.fx.passes} (esperado 5)`);
if (!loadedOff) fails.push('el visor no cargo con fx=off (comparativa PBR)');
if (errorsOff !== '[]') fails.push(`errores de pagina con fx=off: ${errorsOff}`);
// El contorno pinta tinta: sin el, la imagen tiene bastantes menos pixeles casi negros.
if (!(inkFx > 0 && inkOff >= 0)) fails.push(`__inkFrac no midio (fx=${inkFx}, off=${inkOff}); falta ?pdb=1`);
else if (!(inkFx > inkOff * 1.1)) fails.push(`el contorno no cambia la imagen: tinta fx=${inkFx.toFixed(4)} vs off=${inkOff.toFixed(4)}`);
if (!(headDist >= 0.1)) fails.push(`la cabeza no sigue al cursor: dist(headQ centro, izquierda)=${headDist.toFixed(4)} < 0.1`);
if (!(neckDist >= 0.03)) fails.push(`el cuello no acompana a la cabeza: dist(neckQ centro, izquierda)=${neckDist.toFixed(4)} < 0.03`);
if (fails.length) { for (const f of fails) console.error('PROBE FAIL', f); process.exit(1); }
console.log('PROBE OK');
process.exit(0);

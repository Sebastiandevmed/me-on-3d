#!/usr/bin/env node
// Saca del propio motor las dos imagenes estaticas que la landing necesita:
//
//   export/poster.jpg  el cuarto SIN texto, 1920x1080. Es el plan B del hero: lo que ve quien
//                      no tiene WebGL2 (three r170 ya no soporta WebGL1), quien tiene la GPU
//                      bloqueada o quien entra con el GLB caido. Sin esto esa gente ve negro.
//   export/og.jpg      el render + nombre en una capa aparte, 1800x945 (1200x630 @1.5), para
//                      WhatsApp/LinkedIn.
//
// Se generan desde la escena en vivo a proposito: cualquier cambio de luces, de camara o del
// personaje se refleja volviendo a correr esto, y no hay una captura vieja mintiendo en el
// preview social. Uso: node tools/make_poster.mjs
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const PORT = 8779, DBG = 9349;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-poster')}`,
  '--window-size=1600,900', '--no-first-run', '--use-angle=metal', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('POSTER no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; } };
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;

// El texto del hero esta pensado para una pantalla, no para una tarjeta de 1200x630: al
// recortar a ese alto la columna cae encima del personaje. La tarjeta social lleva por eso su
// propia capa, corta y anclada abajo, sobre el render limpio.
const OVERLAY = `
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;inset:0;z-index:99;display:flex;flex-direction:column;' +
    'justify-content:flex-end;padding:52px 60px;font-family:Bricolage Grotesque,sans-serif;' +
    'background:linear-gradient(270deg,transparent 30%,rgba(5,6,10,.5) 58%,rgba(5,6,10,.88)),' +
    'linear-gradient(0deg,rgba(5,6,10,.9),transparent 46%)';
  d.innerHTML = '<div style="font-weight:800;font-size:76px;line-height:.94;letter-spacing:-.03em;color:#e8ecf4">Sebasti\\u00e1n Escobar</div>' +
    '<div style="font-family:Instrument Sans,sans-serif;font-size:25px;line-height:1.45;color:#c8d4e6;margin-top:16px;max-width:24ch">Desarrollo web desde Medell\\u00edn. Tiendas Shopify, agentes de WhatsApp y sistemas que sostienen un negocio real.</div>';
  document.body.appendChild(d); 1`;

async function captura(archivo, w, h, dsf, overlay) {
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: dsf, mobile: false });
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html` });
  let listo = false;
  for (let i = 0; i < 80 && !listo; i++) { await sleep(500); listo = await ev('!!(window.__landing && __landing.status.loaded && __landing.status.env)'); }
  if (!listo) { console.error(`POSTER ${archivo}: la escena no cargo`); process.exit(1); }
  // El fundido de encendido de los monitores dura 2.5 s desde 1.5 s tras la carga, y la intro
  // deja al personaje en la pose de tecleo. Antes de eso la captura sale con las pantallas
  // apagadas y el cuarto se ve muerto.
  await sleep(6000);
  await ev(`for (const s of ['main','#hilo','#carga']) document.querySelector(s).style.display='none'; 1`);
  if (overlay) await ev(OVERLAY);
  await sleep(700);
  const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 84, captureBeyondViewport: false });
  writeFileSync(join(ROOT, 'export', archivo), Buffer.from(r.result.data, 'base64'));
  const kb = Math.round(Buffer.from(r.result.data, 'base64').length / 1024);
  console.log(`POSTER ${archivo.padEnd(11)} ${w * dsf}x${h * dsf} · ${kb} KB`);
}

await captura('poster.jpg', 1920, 1080, 1, false);
await captura('og.jpg', 1200, 630, 1.5, true);
ws.close(); cleanup();
console.log('POSTER OK');
process.exit(0);

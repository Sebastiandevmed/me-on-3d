#!/usr/bin/env node
// Sonda de la landing. El sitio ES el modo hibrido: el 3D acompana hero / como trabajo /
// pantallas y se retira al entrar a los proyectos. Por eso la corrida por omision recorre solo
// ese modo, en escritorio Y en vertical, mas la version sin 3D (plan B).
//
// Afirma, seccion por seccion: que la camara viaja de verdad, que el 3D se apaga donde el modo
// dice, que no hay desborde horizontal a 375 px, que la pantalla de carga se quita y que no hay
// errores de consola. Y aparte: que el plan B deja la pagina legible sin WebGL, y que las
// etiquetas sociales apuntan a archivos que existen.
//
// Uso: node tools/landing_probe.mjs                 hibrido (escritorio + vertical) + plan B
//      MODOS='["fondo","hero","hibrido"]' node ...   vuelve a comparar los tres esquemas
// Salida: generated/renders/landing_<modo>_<seccion>.png y landing_<modo>_movil_<seccion>.png
import { spawn } from 'node:child_process';
import { writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'generated', 'renders'); mkdirSync(OUT, { recursive: true });
const PORT = 8777, DBG = 9347;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SECCIONES = ['hero', 'sobreMi', 'stack', 'proyectos', 'contacto'];
const MODOS = JSON.parse(process.env.MODOS || '["hibrido"]');
// hasta que seccion sigue vivo el 3D en cada modo (tiene que coincidir con index.html)
const HASTA = { fondo: 'contacto', hero: 'hero', hibrido: 'stack' };

const server = spawn('python3', ['-m', 'http.server', '--bind', '127.0.0.1', String(PORT)], { cwd: join(ROOT, 'export'), stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--user-data-dir=${join(tmpdir(), 'me3d-landing')}`,
  '--window-size=1440,900', '--no-first-run', '--use-angle=metal', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { server.kill(); } catch {} };
process.on('exit', cleanup);

let target = null;
for (let i = 0; i < 40 && !target; i++) { await sleep(250); try { const l = await (await fetch(`http://127.0.0.1:${DBG}/json`)).json(); target = l.find((p) => p.type === 'page'); } catch {} }
if (!target) { console.error('LANDING no se pudo conectar a Chrome'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = {};
const send = (m, p = {}) => new Promise((r) => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
// Se cuentan las peticiones de red para cazar una descarga doble del GLB (4 MB) si el preload
// del <head> no casa con la que hace GLTFLoader.
let pedidos = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.method === 'Network.requestWillBeSent') pedidos.push(d.params.request.url);
  if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
};
await new Promise((r) => (ws.onopen = r));
await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
await send('Network.setCacheDisabled', { cacheDisabled: true });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(OUT, name), Buffer.from(r.result.data, 'base64')); };
const metrics = (w, h, movil) => send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: movil ? 2 : 1, mobile: movil });
const irA = async (s) => { await ev(`document.getElementById('${s}').scrollIntoView({behavior:'instant',block:'start'});1`); await sleep(2600); };  // el viaje de camara tiene tau 0.9 s
const desborde = () => ev('document.documentElement.scrollWidth - document.documentElement.clientWidth');

const fails = [];

// ---- los archivos que anuncian las etiquetas sociales tienen que existir de verdad: una
// og:image rota es invisible hasta que alguien comparte el enlace.
for (const f of ['og.jpg', 'poster.jpg', 'avatar.glb', 'night.hdr']) {
  if (!existsSync(join(ROOT, 'export', f))) fails.push(`falta export/${f} (og.jpg y poster.jpg los genera tools/make_poster.mjs)`);
}

for (const modo of MODOS) {
  await metrics(1440, 900, false);
  pedidos = [];
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html?modo=${modo}` });
  let listo = false;
  for (let i = 0; i < 60 && !listo; i++) { await sleep(500); listo = await ev('!!(window.__landing && __landing.status.loaded && __landing.status.env)'); }
  if (!listo) { fails.push(`[${modo}] no cargo: ${await ev('JSON.stringify(window.__errors||[])')}`); continue; }
  await sleep(4000);   // intro + fundido de pantallas
  // la pantalla de carga tiene que haberse quitado sola
  if (await ev('!document.getElementById("carga").hidden')) fails.push(`[${modo}] la pantalla de carga sigue puesta`);
  const veces = pedidos.filter((u) => /avatar\.glb/.test(u)).length;
  if (veces !== 1) fails.push(`[${modo}] avatar.glb se pidio ${veces} veces (el preload del <head> no casa con GLTFLoader)`);
  const meta = await ev(`JSON.stringify({og:document.querySelector('meta[property="og:image"]')?.content,
    t:document.querySelector('meta[property="og:title"]')?.content, d:document.querySelector('meta[name=description]')?.content})`);
  if (!/og\.jpg/.test(meta)) fails.push(`[${modo}] og:image no apunta a og.jpg: ${meta}`);

  const pos = {};
  for (const s of SECCIONES) {
    await irA(s);
    pos[s] = await ev('JSON.stringify(__landing.camPos)');
    const tresD = await ev('__landing.tresD');
    const esperado = SECCIONES.indexOf(s) <= SECCIONES.indexOf(HASTA[modo]) ? 'on' : 'off';
    if (tresD !== esperado) fails.push(`[${modo}] en ${s} el 3D esta ${tresD} y se esperaba ${esperado}`);
    if (await ev(`__landing.seccion !== '${s}'`)) fails.push(`[${modo}] el hilo dice ${await ev('__landing.seccion')} estando en ${s}`);
    await shot(`landing_${modo}_${s}.png`);
  }
  // la camara tiene que haber viajado de verdad dentro del tramo con 3D
  const d = (a, b) => { const A = JSON.parse(a), B = JSON.parse(b); return Math.hypot(A[0] - B[0], A[1] - B[1], A[2] - B[2]); };
  if (d(pos.hero, pos.stack) < 1.0) fails.push(`[${modo}] la camara no viajo: dist(hero, stack)=${d(pos.hero, pos.stack).toFixed(2)}`);
  const dsk = await desborde();
  if (dsk > 1) fails.push(`[${modo}] desborde horizontal en 1440 px: ${dsk}px`);

  // ---- vertical: encuadre propio de camera-path.js, seccion por seccion
  await metrics(375, 812, true);
  await sleep(1500);
  let peorDesborde = 0;
  for (const s of SECCIONES) {
    await irA(s);
    peorDesborde = Math.max(peorDesborde, await desborde());
    await shot(`landing_${modo}_movil_${s}.png`);
  }
  if (peorDesborde > 1) fails.push(`[${modo}] desborde horizontal en 375 px: ${peorDesborde}px`);
  const errs = await ev('JSON.stringify(window.__errors)');
  if (errs !== '[]') fails.push(`[${modo}] errores de pagina: ${errs}`);
  console.log(`LANDING ${modo.padEnd(8)} 5 secciones · escritorio y vertical · fps ${await ev('__landing.status.fps')} · desborde ${dsk}/${peorDesborde} px`);
}

// ---- plan B. Dos formas de quedarse sin escena, y las dos tienen que dejar un sitio legible
// en vez de la pantalla de carga tapandolo todo:
//   1. sin WebGL2 (?3d=off lo simula sin tener que romper la GPU del headless)
//   2. con el CDN de three caido, que es peor: el <script type="module"> NO LLEGA A CORRER,
//      asi que el plan B tiene que vivir fuera del modulo. Se prueba bloqueando jsdelivr.
async function planB(nombre, url, bloquear) {
  await send('Network.setBlockedURLs', { urls: bloquear || [] });
  await metrics(1440, 900, false);
  await send('Page.navigate', { url });
  let listo = false;
  // 12 s de margen: el respaldo de arranque salta a los 8 s.
  for (let i = 0; i < 30 && !listo; i++) { await sleep(400); listo = await ev('document.getElementById("carga").hidden === true'); }
  if (!listo) fails.push(`[${nombre}] la pantalla de carga sigue tapando la pagina`);
  if (await ev('document.body.dataset["3d"] !== "none"')) fails.push(`[${nombre}] data-3d=${await ev('document.body.dataset["3d"]')}`);
  if (await ev('getComputedStyle(document.getElementById("hero")).backgroundImage.indexOf("poster") < 0')) fails.push(`[${nombre}] el hero no cae al poster estatico`);
  // el contenido tiene que estar visible y a ancho completo, no escondido tras el velo
  if (await ev('getComputedStyle(document.querySelector("#proyectos h2")).visibility !== "visible"')) fails.push(`[${nombre}] los proyectos no se ven`);
  await shot(`landing_${nombre}_hero.png`);
  await ev(`document.getElementById('proyectos').scrollIntoView({behavior:'instant',block:'start'});1`); await sleep(800);
  await shot(`landing_${nombre}_proyectos.png`);
  console.log(`LANDING ${nombre.padEnd(8)} pagina legible · motivo ${await ev('String(window.__plano)')} · desborde ${await desborde()} px`);
}
await planB('plano', `http://127.0.0.1:${PORT}/index.html?3d=off`, []);
// El timeout de dentro del modulo es de 20 s; aqui el modulo ni corre, asi que el respaldo que
// se prueba es el del script clasico.
await planB('sincdn', `http://127.0.0.1:${PORT}/index.html`, ['*jsdelivr*']);
await send('Network.setBlockedURLs', { urls: [] });

// ---- sin JavaScript no corre ni el script clasico: el respaldo es el <noscript><style>.
// Si esa hoja se desincroniza de las reglas de body[data-3d="none"], la pantalla de carga
// vuelve a tapar el sitio entero y nadie se entera hasta que alguien entra con JS apagado.
await send('Emulation.setScriptExecutionDisabled', { value: true });
await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/index.html` });
await sleep(2500);
const vis = (sel, prop) => ev(`getComputedStyle(document.querySelector('${sel}')).${prop}`);
if (await vis('#carga', 'display') !== 'none') fails.push('[nojs] la pantalla de carga tapa el sitio sin JavaScript');
if (await vis('#escena', 'display') !== 'none') fails.push('[nojs] el lienzo 3D sigue puesto sin JavaScript');
if (!/poster/.test(await vis('#hero', 'backgroundImage'))) fails.push('[nojs] el hero no cae al poster estatico');
if (await vis('#proyectos h2', 'visibility') !== 'visible') fails.push('[nojs] los proyectos no se ven');
await shot('landing_nojs_hero.png');
console.log(`LANDING nojs     pagina legible · <noscript> al dia · desborde ${await desborde()} px`);
await send('Emulation.setScriptExecutionDisabled', { value: false });

ws.close(); cleanup();
if (fails.length) { for (const f of fails) console.error('LANDING FAIL', f); process.exit(1); }
console.log('LANDING OK');
process.exit(0);

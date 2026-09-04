#!/bin/zsh
# Arma dist/ con TODO lo que el sitio necesita para publicarse, y nada mas.
#
# Existe porque publicar tiene una trampa: `export/*.glb` esta en .gitignore (son 4 MB que se
# regeneran con export_glb.py), asi que quien clone el repo y suba `export/` publica un sitio sin
# personaje. Este script copia el GLB explicitamente y avisa si falta.
#
# Uso: tools/build_site.sh   → dist/  (arrastrable a Netlify, Cloudflare Pages, Vercel...)
set -e
cd "$(dirname "$0")/.."

if [[ ! -f export/avatar.glb ]]; then
  echo "FALTA export/avatar.glb — regeneralo con:  tools/run_blender.sh blender/scripts/export_glb.py" >&2
  exit 1
fi
for f in export/poster.jpg export/og.jpg; do
  [[ -f $f ]] || { echo "FALTA $f — generalo con:  node tools/make_poster.mjs" >&2; exit 1; }
done

rm -rf dist && mkdir -p dist/lib
cp export/index.html export/avatar.glb export/night.hdr export/poster.jpg export/og.jpg dist/
cp export/lib/*.js dist/lib/

# Caches largas para lo que va con nombre estable y es pesado. Netlify y Cloudflare Pages leen
# este archivo; en otro host hay que traducirlo a su forma (nginx, S3, ...).
cat > dist/_headers <<'HEAD'
/avatar.glb
  Cache-Control: public, max-age=604800
/night.hdr
  Cache-Control: public, max-age=604800
/*.jpg
  Cache-Control: public, max-age=604800
/lib/*
  Cache-Control: public, max-age=86400
/index.html
  Cache-Control: public, max-age=300
HEAD

echo "dist/ listo — $(du -sh dist | cut -f1)"
du -h dist/* dist/lib/* 2>/dev/null | sort -h | tail -8
echo
echo "Para verlo antes de subir:  (cd dist && python3 -m http.server 8090)  →  http://localhost:8090/"
echo "OJO: <link rel=\"canonical\"> en index.html apunta a sebastianescobar.dev — cambialo al dominio real."

#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/generated/screens"; mkdir -p "$OUT"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -x "$CHROME" ]; then
  echo "Error: Google Chrome no encontrado en $CHROME" >&2
  exit 1
fi
[ -f "$ROOT/refs/logo.png" ] && cp "$ROOT/refs/logo.png" "$ROOT/tools/screens/logo.png"
for n in code logo stack; do
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1024,576 \
    --screenshot="$OUT/$n.png" "file://$ROOT/tools/screens/$n.html" >/dev/null 2>&1
  echo "$n -> $(sips -g pixelWidth -g pixelHeight "$OUT/$n.png" | tail -2 | tr '\n' ' ')"
done

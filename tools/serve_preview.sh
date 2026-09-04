#!/bin/zsh
# Sirve export/ solo en local (http://127.0.0.1:8765).
#   /            la landing (modo hibrido; ?modo=fondo|hero para comparar, ?3d=off para el plan B)
#   /preview.html el arnes de depuracion del avatar (?mat=, ?fx=off, ?outline=0 ...)
# Ctrl+C o `pkill -f "http.server 8765"` para parar.
cd "$(dirname "$0")/../export" && python3 -m http.server --bind 127.0.0.1 8765

#!/bin/zsh
# Sirve export/ solo en local (http://127.0.0.1:8765) (abrir /preview.html). Ctrl+C o `pkill -f "http.server 8765"` para parar.
cd "$(dirname "$0")/../export" && python3 -m http.server --bind 127.0.0.1 8765

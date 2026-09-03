#!/bin/zsh
# Sirve export/ en http://localhost:8765 (abrir /preview.html). Ctrl+C o `pkill -f "http.server 8765"` para parar.
cd "$(dirname "$0")/../export" && python3 -m http.server 8765

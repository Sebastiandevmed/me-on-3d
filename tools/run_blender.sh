#!/bin/zsh
# Uso: tools/run_blender.sh [archivo.blend|-] script.py [args...]
set -e
# Se puede apuntar a otro Blender con la variable de entorno BLENDER.
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
BLEND="$1"; shift
SCRIPT="$1"; shift
if [ "$BLEND" = "-" ]; then
  "$BLENDER" -b --python "$SCRIPT" -- "$@"
else
  "$BLENDER" -b "$BLEND" --python "$SCRIPT" -- "$@"
fi

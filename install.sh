#!/usr/bin/env bash
# wallp Wallpaper — plasmóide unificado imagem+vídeo
# Instala com ou sem ECM/CMake: tenta cmake, cai para kpackagetool6 ou cp direto
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/plasma/wallpapers/com.wallp.wallpaper"

if command -v cmake >/dev/null 2>&1; then
  echo "==> cmake build"
  cmake -B "$DIR/build" --install-prefix "$HOME/.local" >/dev/null
  cmake --install "$DIR/build" >/dev/null
  echo "OK: instalado em $DEST (cmake)"
  exit 0
fi

if command -v kpackagetool6 >/dev/null 2>&1; then
  echo "==> kpackagetool6"
  kpackagetool6 -t Plasma/Wallpaper --install "$DIR" 2>&1 | tail
  echo "OK: instalado via kpackagetool6"
  exit 0
fi

echo "==> cp direto"
mkdir -p "$DEST/contents"
cp -a "$DIR/metadata.json" "$DEST/"
cp -a "$DIR/contents/"* "$DEST/contents/"
echo "OK: instalado em $DEST (cp)"

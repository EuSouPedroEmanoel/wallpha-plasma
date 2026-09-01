#!/usr/bin/env bash
# wallp-plasma — backend Plasma do wallp: plasmóide + daemon (systemd --user)
# Uso: ./install.sh [-y] [--check]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/plasma/wallpapers/com.wallp.wallpaper"
YES=0; CHECK=0
for a in "$@"; do case "$a" in -y|--yes) YES=1 ;; --check) CHECK=1 ;; *) echo "uso: $0 [-y] [--check]"; exit 1 ;; esac; done
have(){ command -v "$1" >/dev/null 2>&1; }
ask(){ [ "$YES" = 1 ] && return 0; read -r -p "  Instalar agora? [s/N] " r; [ "${r,,}" = s ] || [ "${r,,}" = sim ]; }
step(){ printf '\n==> %s\n' "$1"; }
ok(){ printf '  OK   %s\n' "$1"; }
no(){ printf '  FALTA %s\n' "$1"; }

step "Plasmóide com.wallp.wallpaper"
if [ -d "/usr/share/plasma/wallpapers/com.wallp.wallpaper" ] || [ -d "$DEST" ]; then
  ok "plasmoid com.wallp.wallpaper"
else
  no "plasmoid com.wallp.wallpaper"
  if [ "$CHECK" = 1 ]; then ok "rodar sem --check instala"; else
    if command -v cmake >/dev/null 2>&1; then
      echo "  cmake build -> $DEST"
      cmake -B "$DIR/build" --install-prefix "$HOME/.local" >/dev/null && cmake --install "$DIR/build" >/dev/null && ok "plasmoid instalado (cmake)"
    elif have kpackagetool6; then kpackagetool6 -t Plasma/Wallpaper --install "$DIR" 2>&1 | tail && ok "plasmoid instalado (kpackagetool6)"
    else mkdir -p "$DEST/contents" && cp -a "$DIR/metadata.json" "$DEST/" && cp -a "$DIR/contents/"* "$DEST/contents/" && ok "plasmoid instalado (cp)"; fi
  fi
fi

step "Daemon Python (wallp-plasma)"
if python3 -c "import yaml, dbus" 2>/dev/null; then ok "python3:dbus, yaml"; else no "python3:dbus,yaml (pacman -S python-dbus python-yaml)"; fi
if [ "$CHECK" != 1 ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$DIR/bin/wallp" "$HOME/.local/bin/wallp"
  ln -sf "$DIR/bin/wallp-plasma-daemon" "$HOME/.local/bin/wallp-plasma-daemon"
  ok "bin wallp -> $HOME/.local/bin/wallp (via wallp-plasma)"
  # opcional venv
  if [ ! -d "$DIR/.venv" ]; then python3 -m venv "$DIR/.venv" 2>/dev/null && "$DIR/.venv/bin/pip" install -q pytest pyyaml 2>/dev/null || true; fi
fi

step "Daemon systemd (wallp-daemon.service)"
UNIT="wallp-daemon.service"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
if [ "$CHECK" != 1 ]; then
  cat > "$UNIT_DIR/$UNIT" <<EOF
[Unit]
Description=wallp Plasma — daemon de wallpaper (agenda + com.wallp.wallpaper)
After=plasma-plasmashell.service
PartOf=plasma-plasmashell.service

[Service]
Type=simple
ExecStart=$HOME/.local/bin/wallp-plasma-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload 2>/dev/null || true
  systemctl --user enable "$UNIT" 2>/dev/null || true
  ok "daemon habilitado ($UNIT_DIR/$UNIT -> $HOME/.local/bin/wallp-plasma-daemon)"
else
  if systemctl --user is-enabled "$UNIT" >/dev/null 2>&1; then ok "daemon habilitado"; else no "daemon não habilitado"; fi
fi

if [ "$CHECK" != 1 ]; then
  echo ""
  echo "Comandos (daemon agora em wallp-plasma):"
  echo "  wallp -c [caminho|nome]  (via wallp-plasma)"
  echo "  wallp -a / wallp -x / wallp -r"
else
  echo ""
  echo "--check ok"
fi

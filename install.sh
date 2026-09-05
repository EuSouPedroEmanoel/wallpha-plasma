#!/usr/bin/env bash
# wallpha-plasma — backend Plasma do wallpha: plasmóide + daemon (systemd --user)
# Uso: ./install.sh [-y] [--check]
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/plasma/wallpapers/com.wallpha.wallpaper"
LEGACY_DEST="$HOME/.local/share/plasma/wallpapers/com.wallp.wallpaper"
YES=0; CHECK=0
for a in "$@"; do case "$a" in -y|--yes) YES=1 ;; --check) CHECK=1 ;; *) echo "uso: $0 [-y] [--check]"; exit 1 ;; esac; done
have(){ command -v "$1" >/dev/null 2>&1; }
ask(){ [ "$YES" = 1 ] && return 0; read -r -p "  Instalar agora? [s/N] " r; [ "${r,,}" = s ] || [ "${r,,}" = sim ]; }
step(){ printf '\n==> %s\n' "$1"; }
ok(){ printf '  OK   %s\n' "$1"; }
no(){ printf '  FALTA %s\n' "$1"; }
detect_pm(){ if have pacman; then echo "pacman"; elif have apt-get; then echo "apt"; elif have dnf; then echo "dnf"; elif have zypper; then echo "zypper"; elif have emerge; then echo "emerge"; else echo ""; fi; }
PM="$(detect_pm)"
install_pkg(){
    if [ "$CHECK" = 1 ]; then return 0; fi
    if [ -z "$PM" ]; then no "$* (instale manualmente)"; return 1; fi
    if ! ask; then no "$*"; return 1; fi
    case "$PM" in
        pacman) sudo pacman -S --needed "$@" ;;
        apt) sudo apt-get update -qq 2>/dev/null; sudo apt-get install -y "$@" ;;
        dnf) sudo dnf install -y "$@" ;;
        zypper) sudo zypper install -y "$@" ;;
        emerge) sudo emerge "$@" ;;
        *) no "$* (gerenciador $PM não suportado)"; return 1 ;;
    esac
}

pkg_installed() {
    case "$PM" in
        pacman) pacman -Q "$1" >/dev/null 2>&1 ;;
        apt) dpkg -l "$1" 2>/dev/null | grep -q "^ii" ;;
        dnf|zypper) rpm -q "$1" >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}

check_pkg() {
    if pkg_installed "$1"; then ok "$1"; else no "$1"; install_pkg "$1" || true; fi
}

check_qtmultimedia_qml() {
    local qtpaths qml_root
    qtpaths="$(command -v qtpaths6 || command -v qtpaths || true)"
    if [ -n "$qtpaths" ]; then
        qml_root="$($qtpaths --query QT_INSTALL_QML 2>/dev/null || true)"
        if [ -n "$qml_root" ] && [ -f "$qml_root/QtMultimedia/qmldir" ]; then
            ok "QtMultimedia QML ($qml_root/QtMultimedia)"
            return 0
        fi
    fi
    # Algumas distribuições não expõem qtpaths no PATH do usuário; cubra os
    # diretórios de instalação usuais sem depender da ferramenta de dev Qt.
    for qml_root in /usr/lib/qt6/qml /usr/lib/qt/qml /usr/lib64/qt6/qml /usr/lib64/qt/qml; do
        if [ -f "$qml_root/QtMultimedia/qmldir" ]; then
            ok "QtMultimedia QML ($qml_root/QtMultimedia)"
            return 0
        fi
    done
    no "QtMultimedia QML (módulo QtMultimedia não encontrado)"
    return 1
}

install_plasmoid() {
    # Sempre instala/atualiza a cópia local: somente detectar o diretório antigo
    # deixava o QML corrigido fora da sessão Plasma.
    if have cmake; then
        echo "  cmake install -> $DEST"
        cmake -B "$DIR/build" --install-prefix "$HOME/.local" >/dev/null
        cmake --install "$DIR/build" >/dev/null
        ok "plasmoid atualizado (cmake)"
    elif have kpackagetool6; then
        kpackagetool6 -t Plasma/Wallpaper --upgrade "$DIR" 2>&1 | tail
        ok "plasmoid atualizado (kpackagetool6)"
    else
        mkdir -p "$DEST/contents"
        cp -a "$DIR/metadata.json" "$DEST/"
        cp -a "$DIR/contents/." "$DEST/contents/"
        ok "plasmoid atualizado (cp)"
    fi
}

step "Plasmóide com.wallpha.wallpaper"
if [ "$CHECK" = 1 ]; then
  if [ -f "$DEST/contents/ui/main.qml" ] || [ -f "/usr/share/plasma/wallpapers/com.wallpha.wallpaper/contents/ui/main.qml" ]; then
    ok "plasmoid com.wallpha.wallpaper"
  else
    no "plasmoid com.wallpha.wallpaper"
  fi
else
  install_plasmoid
fi

step "Dependências (KDE Plasma 6 em qualquer distro)"
# cmake e extra-cmake-modules são só para build do plasmóide (pode remover depois)
if have cmake; then ok "cmake"; else no "cmake"; install_pkg "cmake" || true; fi
if [ "$PM" = "pacman" ]; then
    if pacman -Q extra-cmake-modules >/dev/null 2>&1; then ok "extra-cmake-modules"; else no "extra-cmake-modules"; install_pkg "extra-cmake-modules" || true; fi
    if pacman -Q qt6-declarative >/dev/null 2>&1; then ok "qt6-declarative"; else no "qt6-declarative"; install_pkg "qt6-declarative" || true; fi
elif [ "$PM" = "apt" ]; then
    if dpkg -l extra-cmake-modules 2>/dev/null | grep -q "^ii"; then ok "extra-cmake-modules"; else no "extra-cmake-modules"; install_pkg "extra-cmake-modules" || true; fi
    if dpkg -l qml6-module-qtquick 2>/dev/null | grep -q "^ii"; then ok "qml6-module-qtquick"; else no "qml6-module-qtquick"; install_pkg "qml6-module-qtquick" || true; fi
elif [ "$PM" = "dnf" ]; then
    if rpm -q extra-cmake-modules >/dev/null 2>&1; then ok "extra-cmake-modules"; else no "extra-cmake-modules"; install_pkg "extra-cmake-modules" || true; fi
    if rpm -q qt6-qtdeclarative >/dev/null 2>&1; then ok "qt6-qtdeclarative"; else no "qt6-qtdeclarative"; install_pkg "qt6-qtdeclarative" || true; fi
elif [ "$PM" = "zypper" ]; then
    if rpm -q extra-cmake-modules >/dev/null 2>&1; then ok "extra-cmake-modules"; else no "extra-cmake-modules"; install_pkg "extra-cmake-modules" || true; fi
fi

step "Vídeo Qt Multimedia / FFmpeg"
case "$PM" in
  pacman) check_pkg "qt6-multimedia"; check_pkg "qt6-multimedia-ffmpeg"; check_pkg "ffmpeg" ;;
  apt) check_pkg "qml6-module-qtmultimedia"; check_pkg "gstreamer1.0-plugins-bad"; check_pkg "ffmpeg" ;;
  dnf) check_pkg "qt6-qtmultimedia"; check_pkg "ffmpeg" ;;
  zypper) check_pkg "qt6-multimedia"; check_pkg "qt6-multimedia-ffmpeg"; check_pkg "ffmpeg" ;;
  *) no "Qt Multimedia/FFmpeg (instale manualmente para $PM)" ;;
esac
if have ffmpeg; then ok "ffmpeg ($(ffmpeg -version 2>/dev/null | head -n 1))"; else no "executável ffmpeg"; fi
check_qtmultimedia_qml || true

step "Daemon Python (wallpha-plasma) — funciona em Debian, Fedora, Arch, openSUSE"
if python3 -c "import yaml, dbus" 2>/dev/null; then ok "python3:dbus, yaml"; else
    no "python3:dbus,yaml"
    case "$PM" in
        apt) install_pkg "python3-dbus" "python3-yaml" || true ;;
        dnf|zypper) install_pkg "python3-dbus" "python3-pyyaml" || true ;;
        *) install_pkg "python-dbus" "python-yaml" || true ;;
    esac
fi
if [ "$CHECK" != 1 ]; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$DIR/bin/wallpha" "$HOME/.local/bin/wallpha"
  ln -sf "$DIR/bin/wallpha-plasma-daemon" "$HOME/.local/bin/wallpha-plasma-daemon"
  # compat
  ln -sf "$HOME/.local/bin/wallpha" "$HOME/.local/bin/wallp" 2>/dev/null || true
  ln -sf "$HOME/.local/bin/wallpha-plasma-daemon" "$HOME/.local/bin/wallp-plasma-daemon" 2>/dev/null || true
  # Remove o pacote legado inclusive do registro do KPackage; não deixe duas
  # implementações concorrendo por chamadas D-Bus.
  if [ -d "$LEGACY_DEST" ]; then
      rm -rf "$LEGACY_DEST"
      echo "  (removido plasmoid legado com.wallp.wallpaper)"
  fi
  if have kpackagetool6; then
      kpackagetool6 -t Plasma/Wallpaper --remove com.wallp.wallpaper >/dev/null 2>&1 || true
  fi
  ok "bin wallpha -> $HOME/.local/bin/wallpha (via wallpha-plasma, compat wallp)"
  # Ambiente de testes opcional. Recria também se o python interno ainda for
  # um symlink para um interpretador removido/antigo (comum após upgrade).
  VENV="$DIR/.venv"
  VENV_REBUILD=0
  if [ -d "$VENV" ]; then
      if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c 'import sys' >/dev/null 2>&1; then
          VENV_REBUILD=1
      elif [ "$(readlink -f "$VENV/bin/python")" != "$(readlink -f "$(command -v python3)")" ]; then
          VENV_REBUILD=1
      fi
  fi
  if [ ! -d "$VENV" ] || [ "$VENV_REBUILD" = 1 ]; then
      if [ "$VENV_REBUILD" = 1 ]; then
          rm -rf "$VENV"
          echo "  (recriando .venv com o interpretador atual)"
      fi
      python3 -m venv "$VENV" 2>/dev/null && "$VENV/bin/pip" install -q pytest pyyaml 2>/dev/null || true
  fi
fi

step "Daemon systemd (wallpha-daemon.service)"
UNIT="wallpha-daemon.service"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
if [ "$CHECK" != 1 ]; then
  cat > "$UNIT_DIR/$UNIT" <<EOF
[Unit]
Description=wallpha Plasma — daemon de wallpaper (agenda + com.wallpha.wallpaper)
After=plasma-plasmashell.service
PartOf=plasma-plasmashell.service

[Service]
Type=simple
ExecStart=$HOME/.local/bin/wallpha-plasma-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload 2>/dev/null || true
  systemctl --user enable "$UNIT" 2>/dev/null || true
  ok "daemon habilitado ($UNIT_DIR/$UNIT -> $HOME/.local/bin/wallpha-plasma-daemon)"
else
  if systemctl --user is-enabled "$UNIT" >/dev/null 2>&1; then ok "daemon habilitado"; else no "daemon não habilitado"; fi
fi

if [ "$CHECK" != 1 ]; then
  echo ""
  echo "Comandos (daemon agora em wallpha-plasma):"
  echo "  wallpha -c [caminho|nome]  (via wallpha-plasma)"
  echo "  wallpha -a / wallpha -x / wallpha -r"
else
  echo ""
  echo "--check ok"
fi

# wallp-plasma

Backend Plasma do `wallp` — plasmóide **unificado imagem + vídeo** para KDE Plasma 6, leve.

> `wallp` = wallpaper literalmente, então `wallp-plasma` já é o wallpaper no Plasma.

*   **KDE only** (Wayland/X11) — `WallpaperItem` QML + `QtMultimedia`/`ffmpeg`
*   **Sem painel de config** — tudo via `wallp.yml` + `wallp -c/-a/-r/-n/-x`
*   **Compatível** com `org.kde.image` (`Image`) e `luisbocanegra.smart.video.wallpaper.reborn` (`VideoUrls`)
*   **Novo preferido:** `Source` `file://` unificado

Este repo é o **backend de render**; a lógica de agenda/daemon/YouTube continua em [`wallp-cli`](../wallp-cli).

## Instalação

### 1. Dependências (Arch)
```bash
sudo pacman -S --needed extra-cmake-modules qt6-declarative qt6-multimedia qt6-multimedia-ffmpeg plasma-framework
```

### 2. Build + install local (sem root)
```bash
cmake -B build --install-prefix ~/.local
cmake --build build
cmake --install build
# -> ~/.local/share/plasma/wallpapers/com.wallp.wallpaper
kpackagetool6 -t Plasma/Wallpaper --list | grep wallp
```

### 3. Teste rápido (após instalar)
```bash
# via wallp-cli (recomendado)
wallp -c ~/Imagens/foto.jpg
wallp -c ~/Vídeos/a.mp4
wallp -c ~/Vídeos --type diretório  # se usar wallp.yml
# ou manual D-Bus:
qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.setWallpaper com.wallp.wallpaper '{"Source":"file:///home/pedro/Imagens/foto.jpg"}' 0
```

## Estrutura

```
metadata.json                 # KPlugin Id: com.wallp.wallpaper, Plasma/Wallpaper
contents/
  config/main.xml             # props: Image, Source, VideoUrls, MuteMode, Volume, Loop, FillMode
  ui/main.qml                 # Image + VideoOutput/MediaPlayer/AudioOutput, < 100 linhas
CMakeLists.txt                # install para ${KDE_INSTALL_PLASMAWALLPAPERDIR}
```

## Props `wallpaper.configuration`

| nome | tipo | wallp.yml | valor |
|------|------|-----------|-------|
| `Source` | String | `local` | `file://...` preferido |
| `Image` | String | `local` (imagem) | compat `org.kde.image` |
| `VideoUrls` | String | — | compat Reborn JSON `[{"filename":"file://...","loop":false}]` |
| `MuteMode` | Int | `som: true/false` | `4`=som, `5`=mudo (padrão) |
| `Volume` | Double | — | `1.0` |
| `Loop` | Bool | `repetir`/`loop` | `true`=MediaPlayer.Infinite |
| `FillMode` | Int | — | `2`=PreserveAspectCrop (KDE) |

`main.qml` resolve: `Source` > `VideoUrls` > `Image`, detecta vídeo por extensão e mostra `Image` ou `VideoOutput`.

## wallp-cli

Troque em `wallp-cli/src/wallp/apply.py`:
```py
PLUGIN = "com.wallp.wallpaper"
def plugin_for(p): return PLUGIN
```
`install.sh` deve chamar este build antes de `systemctl --user restart wallp-daemon.service`.

## Licença

MIT — ver `LICENSE`.

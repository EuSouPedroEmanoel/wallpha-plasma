# wallpha-plasma

> **Renomeado de `wallp-plasma` → `wallpha-plasma` em v2.0.0** para evitar colisão com outros projetos `wallp`. Plasmoid ID agora é `com.wallpha.wallpaper` (antigo `com.wallp.wallpaper` removido no install). Veja nota completa no `wallpha-cli`.

> ⚠️ **Aviso:** O motor legacy `org.kde.image` para imagens será **removido na v3.0**. A partir daí apenas `com.wallpha.wallpaper` será suportado.

> 🖥️ **Em breve:** `wallpha-gui` chega em **20/10/2026** — GUI para `wallpha.yml`.

Backend Plasma do `wallpha` — plasmóide **unificado imagem + vídeo** para KDE Plasma 6, leve.

> `wallpha` = wallpaper literalmente, então `wallpha-plasma` já é o wallpaper no Plasma.

*   **KDE only** (Wayland/X11) — `WallpaperItem` QML + `QtMultimedia`/`ffmpeg`
*   **Sem painel de config** — tudo via `wallpha.yml` + `wallpha -c/-a/-r/-n/-x`
*   **Compatível** com `org.kde.image` (`Image`) e `luisbocanegra.smart.video.wallpaper.reborn` (`VideoUrls`)
*   **Novo preferido:** `Source` `file://` unificado

Este repo é o **backend de render**; a lógica de agenda/daemon/YouTube continua em [`wallpha-cli`](../wallpha-cli).

## Desenvolvimento do runtime Python

`src/wallpha/` é compartilhado conceitualmente com `wallpha-cli/src/wallpha/`. O daemon do
Plasma é a implementação canônica; o CLI mantém uma camada de delegação/fallback. Antes de
alterar módulos compartilhados, valide que não surgiu divergência acidental:

```bash
./tools/check-runtime-sync.sh
```

As diferenças permitidas são `__init__.py`, `daemon.py`, `mode_ps.py` e `service.py`; qualquer
outra divergência deve ser aplicada nos dois componentes ou deliberadamente adicionada ao contrato.

## Publicação

Uma tag `vX.Y.Z` executa o build CMake, confere a paridade do runtime contra a tag equivalente de
`wallpha-cli`, gera os arquivos `.tar.gz` e `.zip` e publica a release. Publique a tag da CLI antes
da tag do Plasma para que essa verificação consiga baixar a mesma versão.

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
# -> ~/.local/share/plasma/wallpapers/com.wallpha.wallpaper
kpackagetool6 -t Plasma/Wallpaper --list | grep wallpha
```

### 3. Teste rápido (após instalar)
```bash
# via wallpha-cli (recomendado)
wallpha -c ~/Imagens/foto.jpg
wallpha -c ~/Vídeos/a.mp4
wallpha -c ~/Vídeos --type diretório  # se usar wallpha.yml
# ou manual D-Bus:
qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.setWallpaper com.wallpha.wallpaper '{"Source":"file:///home/pedro/Imagens/foto.jpg"}' 0
```

## Estrutura

```
metadata.json                 # KPlugin Id: com.wallpha.wallpaper, Plasma/Wallpaper
contents/
  config/main.xml             # props: Image, Source, VideoUrls, MuteMode, Volume, Loop, FillMode
  ui/main.qml                 # Image + VideoOutput/MediaPlayer/AudioOutput, < 100 linhas
CMakeLists.txt                # install para ${KDE_INSTALL_PLASMAWALLPAPERDIR}
```

## Props `wallpaper.configuration`

| nome | tipo | wallpha.yml | valor |
|------|------|-----------|-------|
| `Source` | String | `local` | `file://...` preferido |
| `Image` | String | `local` (imagem) | compat `org.kde.image` |
| `VideoUrls` | String | — | compat Reborn JSON `[{"filename":"file://...","loop":false}]` |
| `MuteMode` | Int | `som: true/false` | `4`=som, `5`=mudo (padrão) |
| `Volume` | Double | — | `1.0` |
| `Loop` | Bool | `repetir`/`loop` | `true`=MediaPlayer.Infinite |
| `FillMode` | Int | — | `2`=PreserveAspectCrop (KDE) |

`main.qml` resolve: `Source` > `VideoUrls` > `Image`, detecta vídeo por extensão e mostra `Image` ou `VideoOutput`.

## wallpha-cli

Troque em `wallpha-cli/src/wallpha/apply.py`:
```py
PLUGIN = "com.wallpha.wallpaper"
def plugin_for(p): return PLUGIN
```
`install.sh` deve chamar este build antes de `systemctl --user restart wallpha-daemon.service`.

## Licença

MIT — ver `LICENSE`.

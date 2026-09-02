import json
from pathlib import Path

PLUGIN = "com.wallpha.wallpaper"  # wallpha unificado imagem+vídeo (KDE Plasma 6)
PLUGIN_VIDEO = PLUGIN
PLUGIN_IMAGE = PLUGIN  # unifica: mesmo plasmóide resolve por extensão
# legado para fallback se novo plasmóide não estiver instalado
# DEPRECATED: PLUGIN_IMAGE_LEGACY (org.kde.image) será removido na v3.0 — imagens passarão a usar só com.wallpha.wallpaper
PLUGIN_VIDEO_LEGACY = "luisbocanegra.smart.video.wallpaper.reborn"
PLUGIN_IMAGE_LEGACY = "org.kde.image"  # DEPRECATED v3.0

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpeg", ".mpg", ".ogg", ".ogv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".avif"}


def _is_wallpha_plugin_installed():
    p1 = Path.home() / ".local/share/plasma/wallpapers" / PLUGIN
    p2 = Path("/usr/share/plasma/wallpapers") / PLUGIN
    return p1.is_dir() or p2.is_dir()


def _iface():
    import dbus

    bus = dbus.SessionBus()
    proxy = bus.get_object("org.kde.plasmashell", "/PlasmaShell")
    return dbus.Interface(proxy, "org.kde.PlasmaShell")


def _screens(iface):
    import dbus

    screens = []
    for n in range(0, 10):
        cur = iface.wallpaper(dbus.UInt32(n))
        if not cur:
            break
        screens.append(n)
    return screens


def plugin_for(path):
    # wallpha unificado: sempre PLUGIN; fallback só se novo não estiver instalado
    if _is_wallpha_plugin_installed():
        return PLUGIN
    ext = Path(path).suffix.lower()
    # log explícito para evitar falha silenciosa D-Bus + aviso de remoção v3.0 do motor legacy de imagem
    try:
        from . import log as _log

        if ext in VIDEO_EXTS:
            _log.err(f"plasmóide {PLUGIN} não encontrado — usando fallback {PLUGIN_VIDEO_LEGACY} (rode install.sh -y)")
        else:
            _log.err(f"[DEPRECATED v3.0] plasmóide {PLUGIN} não encontrado — usando fallback legacy {PLUGIN_IMAGE_LEGACY} para imagem; será removido na v3.0 (instale {PLUGIN} via install.sh -y)")
    except Exception:
        pass
    if ext in VIDEO_EXTS:
        return PLUGIN_VIDEO_LEGACY
    return PLUGIN_IMAGE_LEGACY


def _video_params(uri, loop=False, som=False, integro=False):
    video = {
        "filename": uri,
        "enabled": True,
        "duration": 0,
        "customDuration": 0,
        "playbackRate": 0,
        "alternativePlaybackRate": 0,
        "loop": bool(loop),
    }
    params = {
        "VideoUrls": json.dumps([video], ensure_ascii=False),
        "LastVideo": uri,
        "LastVideoPosition": 0,
        "ResumeLastVideo": True,
        "MuteMode": 4 if som else 5,
        "Volume": 1.0,
        # wallpha unificado: Source é preferido, VideoUrls/Image mantidos para compat
        "Source": uri,
        "Loop": bool(loop),
    }
    if integro:
        params["ChangeWallpaperMode"] = 1
    return params


def apply(path, screen=None, loop=False, som=False, integro=False):
    import dbus

    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {p}")
    uri = p.as_uri()
    plugin = plugin_for(p)
    # unificado wallpha: manda Source + compat Image/VideoUrls para o mesmo plugin
    if plugin == PLUGIN:
        is_video = p.suffix.lower() in VIDEO_EXTS
        if is_video:
            params = _video_params(uri, loop=loop, som=som, integro=integro)
            params["Image"] = uri  # compat fallback se QML ler Image
        else:
            params = {"Source": uri, "Image": uri, "VideoUrls": "[]", "Loop": bool(loop), "MuteMode": 4 if som else 5, "Volume": 1.0}
    elif plugin == PLUGIN_VIDEO_LEGACY:
        params = _video_params(uri, loop=loop, som=som, integro=integro)
    else:
        params = {"Image": uri}

    iface = _iface()
    screens = [screen] if screen is not None else _screens(iface)
    if not screens:
        raise RuntimeError("nenhuma tela de desktop encontrada (plasmashell rodando?)")

    for n in screens:
        cur = iface.wallpaper(dbus.UInt32(n))
        merged = dict(cur) if cur else {}
        merged.update(params)
        iface.setWallpaper(plugin, merged, dbus.UInt32(n))
    return plugin, p
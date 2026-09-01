import sys
from datetime import date
from pathlib import Path

from . import entries, log, media, parse, randomcfg, state, yt
from .msgs import _fim_txt, _fmt_secs, _fmt_tempo
from .service import _start_service

DEFAULT_TEMPO = "30m"


def _random_mode(opts):
    integro = bool(opts["integro"])
    tempo = None
    tsrc = opts["tempo"] or (None if integro else DEFAULT_TEMPO)
    if tsrc:
        tempo = parse.parse_tempo(tsrc)
        if tempo is None:
            log.err(f"tempo inválido: {tsrc!r}")
            sys.exit(1)
        if tempo.total_seconds() < 5:
            log.err("tempo mínimo de 5 segundos")
            sys.exit(1)

    loop = False
    if opts["loop"] is not None:
        try:
            loop = parse.parse_loop(opts["loop"])
        except ValueError as e:
            log.err(str(e))
            sys.exit(1)

    max_s = None
    qtd = None
    if loop:
        if opts["max"] is not None or opts["qtd"] is not None:
            log.err("o modo loop (-l true|N) não aceita -m nem -q")
            sys.exit(1)
    else:
        if opts["max"] is not None:
            mx = parse.parse_tempo(opts["max"])
            if mx is None or mx.total_seconds() <= 0:
                log.err(f"tempo máximo inválido: {opts['max']!r}")
                sys.exit(1)
            max_s = int(mx.total_seconds())
        elif integro:
            max_s = None
        else:
            max_s = int(parse.parse_tempo("1h").total_seconds())
        if opts["qtd"] is not None:
            try:
                qtd = int(opts["qtd"])
            except ValueError:
                log.err(f"quantidade inválida: {opts['qtd']!r}")
                sys.exit(1)
            if qtd < 1:
                log.err("quantidade deve ser >= 1")
                sys.exit(1)

    rdir = None
    single_file = None
    if opts["yt_list"]:
        try:
            url = opts["yt_list"]
            playlist_id = yt._extract_playlist_id(url) or "playlist"
            folder = yt.yt_dir() / playlist_id
            folder.mkdir(parents=True, exist_ok=True)
            marker = folder / ".playlist_url"
            try:
                marker.write_text(url, encoding="utf-8")
            except OSError:
                pass
            rdir = str(folder)
            has_videos = any(p.is_file() and p.suffix.lower() in {".mp4",".mkv",".webm",".mov",".avi",".m4v",".png",".jpg",".jpeg",".webp"} for p in folder.iterdir())
            if not has_videos:
                try:
                    first = yt.download_yt(url)
                    rdir = first if Path(first).is_dir() else str(Path(first).parent)
                except Exception as e:
                    log.err(f"falha ao baixar primeiro lote: {e}")
                    pass
            print(f"Playlist youtube-list pronta (buffer em RAM, some no logout): {rdir} — shuffle sob demanda, LRU 500MB")
        except Exception as e:
            log.err(str(e))
            sys.exit(1)
    elif opts["yt"]:
        try:
            downloaded = yt.download_yt(opts["yt"])
            if Path(downloaded).is_dir():
                rdir = downloaded
                print(f"Baixado playlist (buffer em RAM, some no logout): {downloaded} ({len(list(Path(downloaded).glob('*')))} vídeos)")
            else:
                single_file = downloaded
                print(f"Baixado (buffer em RAM, some no logout): {single_file}")
        except Exception as e:
            log.err(str(e))
            sys.exit(1)
    elif opts["target"]:
        p = Path(opts["target"]).expanduser()
        if not p.exists():
            log.err(f"caminho não existe: {p}")
            sys.exit(1)
        rdir = str(p if p.is_dir() else p.parent)

    if opts["images"]:
        tipo = "imagem"
    elif opts["videos"]:
        tipo = "video"
    else:
        tipo = None

    som = opts["som"] is not None and opts["som"].strip().lower() == "on"

    cfg = {
        "dir": rdir,
        "file": str(single_file) if single_file else None,
        "tempo": int(tempo.total_seconds()) if tempo else None,
        "max": max_s,
        "qtd": qtd,
        "loop": loop,
        "rep": bool(opts["rep"]),
        "tipo": tipo,
        "integro": integro,
        "som": som,
    }
    _, files, err = randomcfg.build_random_queue(cfg)
    if err:
        log.err(err)
        sys.exit(1)

    state.clear_pos()
    state.clear_list()
    state.set_random(cfg)
    state.set_on(True)
    _start_service()

    origem = (f"youtube ({Path(single_file).name})" if single_file else rdir) or "home (~)"
    filtro = {"imagem": " (só imagens)", "video": " (só vídeos)"}.get(tipo, "")
    snd = "" if som else ", mudo"
    extra = f", até {qtd} wallpapers" if qtd else ""
    if integro:
        if tempo:
            rep_txt = " repete até o tempo" if opts["rep"] else " fica no último frame até o tempo"
            desc = f"a cada {_fmt_tempo(tempo)} — vídeo toca inteiro; se terminar antes,{rep_txt}"
        else:
            desc = "vídeo toca inteiro e avança (imagem usa 30m)"
        limite = f", máx {_fmt_secs(max_s)}" if max_s is not None else ""
        log.info(f"Modo aleatório (integro) ativado: Fila com {len(files)} wallpapers, {origem}{filtro} — {desc}{limite}{extra}{snd}{_fim_txt(loop)}")
    elif loop is True:
        log.info(f"Modo aleatório (loop) ativado: Fila com {len(files)} wallpapers, {origem}{filtro} a cada {_fmt_tempo(tempo)}{snd}{_fim_txt(loop)}")
    elif parse.is_loop_n(loop):
        log.info(f"Modo aleatório ({loop} passadas) ativado: Fila com {len(files)} wallpapers, {origem}{filtro} a cada {_fmt_tempo(tempo)}{snd}{_fim_txt(loop)}")
    else:
        extra = f", até {qtd} wallpapers" if qtd else ""
        log.info(f"Modo aleatório ativado: Fila com {len(files)} wallpapers, {origem}{filtro} a cada {_fmt_tempo(tempo)}, máx {_fmt_secs(max_s)}{extra}{snd}{_fim_txt(loop)}")


def _random_next():
    cfg = state.get_random()
    salt = media.get_salt()
    day = date.today().isoformat()
    dir_key = cfg.get("dir")
    dir_path = Path(dir_key) if dir_key else None
    playlist_marker = dir_path / ".playlist_url" if dir_path else None
    is_yt_playlist = bool(playlist_marker and playlist_marker.is_file())
    if is_yt_playlist:
        try:
            url = playlist_marker.read_text(encoding="utf-8").strip()
            all_ids = yt.get_playlist_ids(url)
            if not all_ids:
                log.err("playlist vazia")
                sys.exit(1)
            order = media.day_shuffled(all_ids, salt)
            pos = state.get_pos()
            if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
                i = int(pos.get("idx", 0)) % len(order)
            else:
                i = 0
                state.set_pos({"idx": i, "day": day, "salt": salt, "dir": dir_key})
            chosen_id = order[i % len(order)]
            playlist_id = yt._extract_playlist_id(url) or "playlist"
            cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
            if cached:
                chosen = str(cached[0])
            else:
                chosen = yt.download_yt(f"https://youtu.be/{chosen_id}")
                if Path(chosen).is_dir():
                    files_in = [p for p in Path(chosen).iterdir() if p.is_file()]
                    chosen = str(files_in[0]) if files_in else chosen
            try:
                from . import apply
                plugin, path = apply.apply(
                    chosen,
                    loop=bool(cfg.get("rep") or cfg.get("loop") is True),
                    som=bool(cfg.get("som")),
                    integro=bool(cfg.get("integro")),
                )
                log.info(f"Wallpaper aplicado: {path} ({plugin}) [{i + 1}/{len(order)}] {chosen_id} (youtube-list)")
            except Exception as e:
                log.err(f"erro: {e}")
                sys.exit(1)
            new_i = i + 1
            raw_tempo = cfg.get("tempo")
            if raw_tempo is None and cfg.get("integro"):
                tempo_s = None
            else:
                tempo_s = max(randomcfg.cfg_seconds(raw_tempo, default=1800), 5)
            if cfg.get("integro") and media.match_tipo(chosen, "video"):
                dur = media.video_duration(path)
                if tempo_s is not None:
                    tempo_s = int(max(tempo_s, max(dur or 0, 5)))
                else:
                    tempo_s = int(max(dur or 5, 5))
            if cfg.get("loop") is True:
                if new_i >= len(order):
                    new_i = 0
                state.set_pos({"idx": new_i, "day": day, "salt": salt, "dir": dir_key})
                return
            loop = cfg.get("loop")
            ended = False
            qtd = cfg.get("qtd")
            max_s = cfg.get("max")
            if parse.is_loop_n(loop) and new_i >= len(order):
                passadas = int(cfg.get("passadas", 0)) + 1
                if passadas >= loop:
                    state.clear_random()
                    print(f"Slideshow encerrado ({loop} passadas) — voltando à agenda do yml.")
                    return
                cfg["passadas"] = passadas
                state.set_random(cfg)
                new_i = 0
            if qtd is not None:
                qtd = int(qtd) - 1
                if qtd <= 0:
                    ended = True
            if max_s is not None:
                max_s = int(max_s) - tempo_s
                if max_s <= 0:
                    ended = True
            if new_i >= len(order) and len(order) > 1:
                ended = True
            state.set_pos({"idx": new_i, "day": day, "salt": salt, "dir": dir_key})
            if ended:
                state.clear_random()
                print("Slideshow encerrado (limite atingido) — voltando à agenda do yml.")
            else:
                cfg["qtd"] = qtd
                cfg["max"] = max_s
                state.set_random(cfg)
            return
        except SystemExit:
            raise
        except Exception as e:
            log.err(str(e))
            sys.exit(1)

    _, files, err = randomcfg.build_random_queue(cfg)
    if err:
        log.err(err)
        sys.exit(1)
    order = media.day_shuffled(files, salt)
    pos = state.get_pos()
    if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
        i = int(pos.get("idx", 0)) % len(order)
    else:
        i = 0
        state.set_pos({"idx": i, "day": day, "salt": salt, "dir": dir_key})

    chosen = order[i % len(order)]
    try:
        from . import apply
        plugin, path = apply.apply(
            chosen,
            loop=bool(cfg.get("rep") or cfg.get("loop") is True),
            som=bool(cfg.get("som")),
            integro=bool(cfg.get("integro")),
        )
        log.info(f"Wallpaper aplicado: {path} ({plugin})")
    except Exception as e:
        log.err(f"erro: {e}")
        sys.exit(1)

    new_i = i + 1
    raw_tempo = cfg.get("tempo")
    if raw_tempo is None and cfg.get("integro"):
        tempo_s = None
    else:
        tempo_s = max(randomcfg.cfg_seconds(raw_tempo, default=1800), 5)
    if cfg.get("integro") and media.match_tipo(chosen, "video"):
        dur = media.video_duration(path)
        if tempo_s is not None:
            tempo_s = int(max(tempo_s, max(dur or 0, 5)))
        else:
            tempo_s = int(max(dur or 5, 5))
    else:
        tempo_s = tempo_s if tempo_s is not None else 5
    if cfg.get("loop") is True:
        if new_i >= len(order):
            new_i = 0
        state.set_pos({"idx": new_i, "day": day, "salt": salt, "dir": dir_key})
        return

    loop = cfg.get("loop")
    ended = False
    qtd = cfg.get("qtd")
    max_s = cfg.get("max")
    if parse.is_loop_n(loop) and new_i >= len(order):
        passadas = int(cfg.get("passadas", 0)) + 1
        if passadas >= loop:
            state.clear_random()
            print(f"Slideshow encerrado ({loop} passadas) — voltando à agenda do yml.")
            return
        cfg["passadas"] = passadas
        state.set_random(cfg)
        new_i = 0
    if qtd is not None:
        qtd = int(qtd) - 1
        if qtd <= 0:
            ended = True
    if max_s is not None:
        if tempo_s is None:
            tempo_s = 5
        max_s = int(max_s) - tempo_s
        if max_s <= 0:
            ended = True
    if new_i >= len(order) and len(order) > 1:
        ended = True
    state.set_pos({"idx": new_i, "day": day, "salt": salt, "dir": dir_key})
    if ended:
        state.clear_random()
        print("Slideshow encerrado (limite atingido) — voltando à agenda do yml.")
    else:
        cfg["qtd"] = qtd
        cfg["max"] = max_s
        state.set_random(cfg)

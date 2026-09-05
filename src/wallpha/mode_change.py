import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import apply, entries, log, media, parse, randomcfg, state, transitions, yt
from .msgs import _fim_txt, _fmt_secs
from .service import _start_service

from .mode_random import _random_next


def _toggle_playback():
    current = state.get_current() or {}
    path = current.get("path")
    if not path:
        last = state.get_last() or []
        path = last[2] if len(last) > 2 else None
    if not path or not Path(path).exists():
        log.err("nenhum vídeo atual para pausar/retomar (aplique um vídeo com -c primeiro)")
        sys.exit(1)
    if not media.match_tipo(path, "video"):
        log.err("-p só se aplica ao vídeo atual; imagens não possuem reprodução")
        return
    paused = not bool(current.get("paused", False))
    try:
        plugin, applied = apply.apply(path, loop=bool(current.get("loop", False)), som=bool(current.get("som", False)), paused=paused)
        log.info("Vídeo %s: %s (%s)" % ("pausado" if paused else "retomado", applied, plugin))
    except Exception as e:
        log.err(f"erro ao alternar reprodução: {e}")
        sys.exit(1)


def _edit_current_cycle(opts):
    current = state.get_current() or {}
    cfg = state.get_random() or state.get_list()
    if cfg is None and not current.get("path"):
        log.err("nenhum ciclo ativo para editar")
        sys.exit(1)
    if cfg is None:
        cfg = {}
    if opts.get("som") is not None:
        cfg["som"] = opts["som"].strip().lower() == "on"
    if opts.get("loop") is not None:
        raw = opts["loop"]
        if raw == "__toggle__":
            cfg["loop"] = not bool(cfg.get("loop"))
        else:
            try:
                cfg["loop"] = parse.parse_loop(raw)
            except ValueError as e:
                log.err(str(e)); sys.exit(1)
    if opts.get("tempo") is not None:
        duration = parse.parse_tempo(opts["tempo"])
        if duration is None or duration.total_seconds() < 5:
            log.err("tempo mínimo de 5 segundos"); sys.exit(1)
        cfg["tempo"] = int(duration.total_seconds())
        current["tempo"] = cfg["tempo"]
    if state.get_random() is not None:
        state.set_random(cfg)
    elif state.get_list() is not None:
        state.set_list(cfg)
    path = current.get("path")
    if path and Path(path).exists() and media.match_tipo(path, "video"):
        plugin, applied = apply.apply(path, loop=bool(cfg.get("loop", current.get("loop", False))), som=bool(cfg.get("som", current.get("som", False))), paused=bool(current.get("paused", False)))
        current.update({"path": path, "loop": bool(cfg.get("loop", False)), "som": bool(cfg.get("som", False))})
        state.set_current(current)
        log.info(f"Ciclo atual atualizado: {applied} ({plugin})")
    elif path:
        log.info("Ciclo atual atualizado; opções de vídeo foram ignoradas para imagem")
    _start_service()


def _change(target, opts=None):
    opts = opts or {}
    if opts.get("play_pause"):
        _toggle_playback()
        return
    if target is None and any(opts.get(k) is not None for k in ("som", "loop", "tempo")):
        _edit_current_cycle(opts)
        return
    if target:
        _change_target(target, opts)
        return
    if state.get_random():
        _random_next()
        return
    if state.get_list():
        _list_next()
        return
    _change_yml_next()


def _change_target(target, opts=None):
    opts = opts or {}
    entries_list = entries.load_checked()
    if entries_list is None:
        sys.exit(1)
    p = Path(target).expanduser()
    try:
        if "/" in target or "~" in target or p.exists():
            if p.is_dir():
                files = media.list_dir_files(str(p))
                if not files:
                    log.err(f"pasta sem mídia: {p}")
                    sys.exit(1)
                plugin, path = apply.apply(files[0])
                state.set_last([str(p), None, files[0]])
            else:
                loop = False
                if opts.get("loop") is not None:
                    raw_loop = opts["loop"]
                    try:
                        loop = True if raw_loop == "__toggle__" else parse.parse_loop(raw_loop)
                    except ValueError as e:
                        log.err(str(e)); sys.exit(1)
                som = opts.get("som", "off").strip().lower() == "on" if opts.get("som") is not None else False
                plugin, path = apply.apply(target, loop=bool(loop), som=som, paused=False)
                if opts.get("tempo") is not None:
                    duration = parse.parse_tempo(opts["tempo"])
                    if duration is None or duration.total_seconds() < 5:
                        log.err("tempo mínimo de 5 segundos"); sys.exit(1)
                    seconds = int(duration.total_seconds())
                    state.set_current({"path": str(p.resolve()), "loop": bool(loop), "som": som, "paused": False, "tempo": seconds})
                    # Quando a agenda está ativa, mantenha este arquivo manual
                    # pelo prazo solicitado e deixe o daemon retomar depois.
                    if state.is_on():
                        state.set_override({"path": str(p.resolve()), "until": (datetime.now() + timedelta(seconds=seconds)).isoformat()})
                state.set_last([None, None, str(p.resolve())])
            log.info(f"Wallpaper aplicado: {path} ({plugin})")
        else:
            e = transitions.find_by_name(entries_list, target)
            if e is None:
                lista = entries.find_list(target)
                if lista is not None:
                    _start_list(lista, opts)
                    return
                log.err(f"wallpaper '{target}' não encontrado no yml")
                nomes = ", ".join(f"'{x['nome']}'" for x in entries_list)
                if nomes:
                    log.err("disponíveis: " + nomes)
                sys.exit(1)
            if e.get("is_list"):
                _start_list(e, opts)
                return
            if (opts.get("tempo") is not None or opts.get("max") is not None or opts.get("qtd") is not None or opts.get("loop") is not None or opts.get("rep") or opts.get("images") or opts.get("videos") or opts.get("integro") or opts.get("som") is not None):
                log.err(f"'{target}' não é uma lista; essas opções só valem com -r ou -c <lista>")
                sys.exit(1)
            plugin, path = apply.apply(_yt_path(e), loop=bool(e.get("repetir") or e.get("loop")), som=e.get("som"), integro=e.get("integro"))
            state.set_last([e["local"], e["nome"], e["arquivo"]])
            log.info(f"Wallpaper aplicado: {path} ({plugin})")
    except FileNotFoundError as e:
        log.err(str(e))
        sys.exit(1)
    except Exception as e:
        log.err(f"erro: {e}")
        sys.exit(1)


def _start_list(lista, opts):
    """Roda uma lista do yml (uma passada, ou loop com -l)."""
    slideshow = (
        opts.get("tempo") is not None or opts.get("max") is not None or opts.get("qtd") is not None
        or opts.get("rep") or opts.get("images") or opts.get("videos") or opts.get("integro")
        or opts.get("som") is not None
    )
    loop = False
    if opts.get("loop") is not None:
        try:
            loop = True if opts["loop"] == "__toggle__" else parse.parse_loop(opts["loop"])
        except ValueError as e:
            log.err(str(e))
            sys.exit(1)

    tempo = None
    if opts.get("tempo"):
        tempo = parse.parse_tempo(opts["tempo"])
        if tempo is None or tempo.total_seconds() < 5:
            log.err("tempo inválido (mínimo 5s)")
            sys.exit(1)
    if slideshow:
        max_s = None
        qtd = None
        if loop:
            if opts.get("max") is not None or opts.get("qtd") is not None:
                log.err("o modo loop (-l true|N) não aceita -m nem -q")
                sys.exit(1)
        else:
            if opts.get("max") is not None:
                mx = parse.parse_tempo(opts["max"])
                if mx is None or mx.total_seconds() <= 0:
                    log.err(f"tempo máximo inválido: {opts['max']!r}")
                    sys.exit(1)
                max_s = int(mx.total_seconds())
            if opts.get("qtd") is not None:
                try:
                    qtd = int(opts["qtd"])
                except ValueError:
                    log.err(f"quantidade inválida: {opts['qtd']!r}")
                    sys.exit(1)
                if qtd < 1:
                    log.err("quantidade deve ser >= 1")
                    sys.exit(1)
    else:
        max_s = None
        qtd = None

    if opts.get("images"):
        tipo = "imagem"
    elif opts.get("videos"):
        tipo = "video"
    else:
        tipo = None
    som = opts.get("som") is not None and opts["som"].strip().lower() == "on"

    cfg = {
        "nome": lista["nome"],
        "tempo": int(tempo.total_seconds()) if tempo else None,
        "max": max_s, "qtd": qtd, "loop": loop,
        "rep": bool(opts.get("rep")), "tipo": tipo,
        "integro": bool(opts.get("integro")), "som": som,
        "slideshow": slideshow, "persist": False, "idx": 0,
        "shuffled": bool(lista.get("shuffled")),
    }
    state.clear_pos()
    state.clear_random()
    state.set_list(cfg)
    state.set_on(True)
    _start_service()

    n = len(lista.get("sub_entries") or [])
    if slideshow:
        qtd_txt = f", até {qtd}" if qtd else ""
        extra = f", máx {_fmt_secs(max_s)}" if max_s is not None else ""
        snd = "" if som else ", mudo"
        print(f"Lista '{lista['nome']}' (slideshow): {n} itens{qtd_txt}{extra}{snd}{_fim_txt(loop)}")
    else:
        fim = " — loop até: wallpha -x" if loop is True else (
            f" — {loop} passadas e volta à agenda" if parse.is_loop_n(loop) else " — uma passada e volta à agenda"
        )
        log.info(f"Lista '{lista['nome']}' ativada: {n} itens{fim}")


def _list_next():
    cfg = state.get_list()
    if not cfg:
        return
    entries_list = entries.load_checked()
    if entries_list is None:
        sys.exit(1)
    if not entries_list:
        log.err("nenhum wallpaper configurado. Rode: wallpha --init")
        sys.exit(1)

    lista = entries.find_list(cfg["nome"])
    if lista is not None:
        subs = lista["sub_entries"]
    else:
        e = transitions.find_by_name(entries_list, cfg["nome"])
        if e is None or e.get("is_list"):
            log.err(f"'{cfg['nome']}' não encontrado no yml")
            sys.exit(1)
        subs = [e]
    try:
        if cfg.get("slideshow"):
            _list_slideshow_next(cfg, lista)
            return
        if len(subs) == 1 or any(s["hora_start"] is not None for s in subs):
            now = datetime.now()
            active = entries.resolve_active if hasattr(entries, 'resolve_active') else None
            # resolve via schedule
            from . import schedule
            active = schedule.resolve_active(subs, now)
            nxt = transitions.next_entry(subs, active, now)
            if nxt is None:
                nxt = subs[0]
            _apply_named(nxt)
            return
        hoje = [s for s in subs if parse.matches_day(s, date.today())] or subs
        if cfg.get("shuffled"):
            hoje = media.day_shuffled(hoje, media.get_salt(), date.today())
        idx = int(cfg.get("idx", 0)) % len(hoje)
        if cfg.get("shuffled"):
            nxt_entry = hoje[(idx + 1) % len(hoje)]
            if nxt_entry.get("is_list"):
                nxt = transitions.next_sub_by_nome(nxt_entry, None)
            else:
                nxt = nxt_entry
        else:
            sub = hoje[idx]
            nxt = transitions.next_sub_by_nome(lista, sub["nome"]) if lista else dict(hoje[0])
        _apply_named(nxt)
        idx += 1
        if idx >= len(hoje):
            loop = cfg.get("loop")
            if parse.is_loop_n(loop):
                passadas = int(cfg.get("passadas", 0)) + 1
                if passadas >= loop:
                    state.clear_list()
                    print(f"Lista concluída ({loop} vezes) — voltando à agenda do yml.")
                    return
                cfg["passadas"] = passadas
                idx = 0
            elif not loop:
                state.clear_list()
                print("Lista concluída — voltando à agenda do yml.")
                return
        state.set_list({**cfg, "idx": idx})
    except Exception as e:
        log.err(f"erro: {e}")
        sys.exit(1)


def _apply_named(e):
    try:
        plugin, path = apply.apply(
            _yt_path(e),
            loop=bool(e.get("repetir") or e.get("loop")),
            som=e.get("som"),
            integro=bool(e.get("integro")),
        )
        log.info(f"Wallpaper aplicado: {path} ({plugin})")
    except Exception as e:
        log.err(f"erro: {e}")
        sys.exit(1)


def _list_slideshow_next(cfg, lista):
    if lista is None:
        log.err("lista não encontrada no yml")
        sys.exit(1)
    files = entries.list_media_queue(lista, cfg.get("tipo"))
    if not files:
        log.err("nenhuma mídia na lista")
        sys.exit(1)
    salt = media.get_salt()
    order = media.day_shuffled(files, salt) if cfg.get("shuffled") else files
    day = date.today().isoformat()
    dir_key = f"list:{cfg.get('nome')}"
    pos = state.get_pos()
    if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
        i = int(pos.get("idx", 0)) % len(order)
    else:
        i = int(cfg.get("idx", 0)) % len(order)
    chosen = order[i % len(order)]
    try:
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
    tempo_s = max(randomcfg.cfg_seconds(cfg.get("tempo"), default=1800), 5)
    if cfg.get("integro") and media.match_tipo(chosen, "video"):
        dur = media.video_duration(chosen)
        if cfg.get("tempo") is not None:
            tempo_s = int(max(tempo_s, max(dur or 0, 5)))
        else:
            tempo_s = int(max(dur or tempo_s, 5))
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
            state.clear_list()
            print(f"Lista concluída ({loop} passadas) — voltando à agenda do yml.")
            return
        cfg["passadas"] = passadas
        state.set_list(cfg)
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
        state.clear_list()
        print("Lista concluída (limite atingido) — voltando à agenda do yml.")
    else:
        cfg["qtd"] = qtd
        cfg["max"] = max_s
        state.set_list(cfg)


def _change_yml_next():
    entries_list = entries.load_checked()
    if entries_list is None:
        sys.exit(1)
    if not entries_list:
        log.err("nenhum wallpaper configurado. Rode: wallpha --init")
        sys.exit(1)

    now = datetime.now()
    last = state.get_last()
    nxt = transitions.next_from_last(entries_list, last, now)
    if nxt is None:
        from . import schedule
        active = schedule.resolve_active(entries_list, now)
        nxt = transitions.next_entry(entries_list, active, now)
    if nxt is None:
        log.err("nenhum wallpaper no yml")
        sys.exit(1)
    try:
        plugin, path = apply.apply(
            _yt_path(nxt),
            loop=bool(nxt.get("repetir") or nxt.get("loop")),
            som=nxt.get("som"),
            integro=nxt.get("integro"),
        )
    except Exception as e:
        log.err(f"erro: {e}")
        sys.exit(1)
    key = transitions.last_key(nxt)
    state.set_last(key)
    if state.is_on() and state.get_random() is None and state.get_list() is None:
        until = transitions.next_transition(entries_list, now)
        if until is not None:
            state.set_override({"key": key, "until": until.isoformat()})
        else:
            state.clear_override()
    log.info(f"Wallpaper aplicado: {path} ({plugin})")


def _yt_path(entry):
    """Se o entry for youtube, baixa pro buffer em RAM e devolve o caminho local."""
    if not entry.get("is_yt"):
        return entry["arquivo"]
    try:
        return yt.download_yt(entry["arquivo"])
    except Exception as e:
        log.err(str(e))
        sys.exit(1)

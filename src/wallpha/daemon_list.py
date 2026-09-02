import time
from datetime import date, datetime, timedelta
from pathlib import Path
from . import apply, entries, log, media, parse, randomcfg, schedule, state, transitions, yt, yt_prefetch
POLL = 15
def _get_yt_or_prefetch(url, prev_path=None):
    if not url or "youtu" not in url.lower():
        return url
    pref = yt_prefetch.get_result(url)
    if pref and Path(pref).exists():
        return pref
    return yt.download_yt(url, prev_path=prev_path)
def _track_prefetch(new_path, prev_path, current_path, subs, idx):
    if new_path and yt._is_in_yt_dir(str(new_path)):
        if current_path and current_path != str(new_path):
            prev_path = current_path
        current_path = str(new_path)
        try:
            nxt = subs[(idx+1) % len(subs)] if subs else None
            if nxt and nxt.get("is_yt") and nxt.get("arquivo"):
                yt_prefetch.prefetch(nxt["arquivo"], prev_path=prev_path)
        except:
            pass
    return prev_path, current_path
def _list_should_stop():
    if not state.is_on():
        log.err("modo automático desativado, encerrando.")
        import sys
        sys.exit(0)
    if state.get_list() is None:
        log.err("modo lista encerrado, voltando à agenda.")
        return True
    return False
def _run_list():
    while True:
        cfg = state.get_list()
        if cfg is None:
            return
        entries_list = entries.load_checked()
        if entries_list is not None:
            break
        log.err("erro no yml, aguardando correção...")
        if _list_should_stop():
            return
        time.sleep(POLL)
    if not entries_list:
        log.err("nenhum wallpaper no yml, encerrando.")
        import sys
        sys.exit(0)
    lista = entries.find_list(cfg["nome"])
    if lista is not None:
        subs = lista["sub_entries"]
    else:
        e = transitions.find_by_name(entries_list, cfg["nome"])
        if e is None or e.get("is_list"):
            log.err(f"'{cfg['nome']}' não encontrado no yml, encerrando.")
            import sys
            sys.exit(0)
        subs = [e]
    log.err(f"modo '{cfg['nome']}' ativado.")
    if cfg.get("slideshow"):
        _run_list_slideshow(cfg, lista)
        return
    if len(subs) == 1 or any(s["hora_start"] is not None for s in subs):
        _run_list_schedule(subs, cfg)
        return
    _run_list_cycle(subs, cfg)
def _run_list_cycle(subs, cfg):
    """Sub-itens só de tempo: um após o outro, cada um pelo seu tempo.
    Com `loop` int N, faz N passadas completas e volta à agenda do yml.
    Se `shuffled` (lista com shuffled:true), ordem é randomica diária com salt — mesma
    lógica determinística de diretório local e de playlist youtube (day_shuffled)."""
    salt = media.get_salt()
    day = date.today().isoformat()
    ciclos = 0
    prev_yt_path = None
    current_yt_path = None
    while True:
        if _list_should_stop():
            return
        cfg = state.get_list()
        if cfg is None:
            return
        hoje = [s for s in subs if parse.matches_day(s, date.today())] or subs
        if cfg.get("shuffled"):
            hoje = media.day_shuffled(hoje, media.get_salt(), date.today())
        idx = int(cfg.get("idx", 0)) % len(hoje)
        sub = hoje[idx]
        applied_path = _apply_named(sub, prev_path=prev_yt_path)
        if applied_path and yt._is_in_yt_dir(applied_path):
            if current_yt_path and current_yt_path != applied_path:
                prev_yt_path = current_yt_path
            current_yt_path = applied_path
            try:
                nxt_sub = hoje[(idx + 1) % len(hoje)]
                if nxt_sub.get("is_yt") and nxt_sub.get("arquivo"):
                    yt_prefetch.prefetch(nxt_sub["arquivo"], prev_path=prev_yt_path)
            except Exception:
                pass
        tempo_s = max(randomcfg.cfg_seconds(sub.get("tempo"), default=1800), 5)
        if sub.get("integro"):
            path_for_dur = None
            if sub.get("is_yt"):
                try:
                    path_for_dur = _get_yt_or_prefetch(sub["arquivo"], prev_path=prev_yt_path)
                except Exception:
                    path_for_dur = None
            else:
                path_for_dur = sub.get("arquivo") or sub.get("local")
            if path_for_dur and media.match_tipo(str(path_for_dur), "video"):
                dur = media.video_duration(str(path_for_dur)) or 5
                if sub.get("tempo") is not None:
                    tempo_s = int(max(tempo_s, max(dur, 5)))
                else:
                    tempo_s = int(max(dur, 5))
        idx += 1
        if idx >= len(hoje):
            loop = cfg.get("loop")
            if parse.is_loop_n(loop):
                ciclos += 1
                if ciclos >= loop:
                    state.clear_list()
                    log.err(f"lista concluída ({loop} vezes), voltando à agenda do yml.")
                    return
                idx = 0
            elif loop:
                idx = 0
            else:
                state.set_list({**cfg, "idx": idx})
                time.sleep(POLL)
                state.clear_list()
                log.err("lista concluída, voltando à agenda do yml.")
                return
        state.set_list({**cfg, "idx": idx})
        deadline = time.monotonic() + tempo_s
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if _list_should_stop():
                return
            time.sleep(min(left, float(POLL)))
def _run_list_schedule(subs, cfg):
    """Agenda da lista (mini-agenda) ou item único persistente."""
    last_applied = None
    day_started = datetime.now().date()
    prev_yt_path = None
    current_yt_path = None
    while True:
        if _list_should_stop():
            return
        cfg = state.get_list()
        if cfg is None:
            return
        now = datetime.now()
        if not cfg.get("persist") and not cfg.get("loop") and now.date() != day_started:
            state.clear_list()
            log.err("lista concluída, voltando à agenda do yml.")
            return
        active = schedule.resolve_active(subs, now)
        if active is not None:
            has_playlist = "list=" in str(active.get("arquivo", "")).lower()
            is_yt_list = bool(active.get("is_yt_list"))
            if active.get("is_yt") and has_playlist and not is_yt_list:
                try:
                    url = active["arquivo"]
                    all_ids = yt.get_playlist_ids(url)
                    if all_ids:
                        chosen_id = media.day_shuffled(all_ids, media.get_salt())[0] if active.get("shuffled") else all_ids[0]
                        playlist_id = yt._extract_playlist_id(url) or "playlist"
                        cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
                        chosen = str(cached[0]) if cached else _get_yt_or_prefetch(f"https://youtu.be/{chosen_id}", prev_path=prev_yt_path)
                        key = (str(chosen), active["nome"], chosen_id)
                        if key != last_applied:
                            try:
                                plugin, _ = apply.apply(str(chosen), loop=bool(active.get("repetir") or active.get("loop")), som=active.get("som"), integro=bool(active.get("integro")))
                                log.err(f"aplicando: {entries.format_entry(active)} [1/1] {chosen_id} ({plugin})")
                                last_applied = key
                                if yt._is_in_yt_dir(chosen):
                                    if current_yt_path and current_yt_path != chosen: prev_yt_path = current_yt_path
                                    current_yt_path = chosen
                            except Exception as e:
                                log.err(f"erro ao aplicar {chosen}: {e}")
                                last_applied = None
                except Exception as e:
                    log.err(f"erro youtube {active['arquivo']}: {e}")
            elif (active.get("is_yt") or is_yt_list) and has_playlist:
                try:
                    url = active["arquivo"]
                    all_ids = yt.get_playlist_ids(url)
                    if all_ids:
                        shuffled_ids = media.day_shuffled(all_ids, media.get_salt()) if active.get("shuffled") else all_ids
                        pos_key = f"yta_list:{active['nome']}:{url}"
                        pos = state.get_pos()
                        yta_pos = pos if pos and isinstance(pos, dict) and pos.get("dir") == pos_key else None
                        idx = int(yta_pos.get("idx", 0)) % len(shuffled_ids) if yta_pos else 0
                        loop_val = active.get("loop")
                        is_loop_true = loop_val is True
                        is_loop_n = parse.is_loop_n(loop_val)
                        if not is_loop_true and not is_loop_n and idx >= len(shuffled_ids):
                            state.set_pos({"idx": 0, "dir": pos_key, "day": date.today().isoformat(), "salt": media.get_salt()})
                        else:
                            chosen_id = shuffled_ids[idx % len(shuffled_ids)]
                            playlist_id = yt._extract_playlist_id(url) or "playlist"
                            cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
                            if not cached:
                                chosen = _get_yt_or_prefetch(f"https://youtu.be/{chosen_id}", prev_path=prev_yt_path)
                            else:
                                chosen = str(cached[0])
                            key = (str(chosen), active["nome"], idx)
                            if key != last_applied:
                                try:
                                    plugin, _ = apply.apply(str(chosen), loop=bool(active.get("repetir") or is_loop_true), som=active.get("som"), integro=bool(active.get("integro")))
                                    log.err(f"aplicando: {entries.format_entry(active)} [{idx+1}/{len(shuffled_ids)}] {chosen_id} ({plugin})")
                                    last_applied = key
                                    if yt._is_in_yt_dir(chosen):
                                        if current_yt_path and current_yt_path != chosen: prev_yt_path = current_yt_path
                                        current_yt_path = chosen
                                        try:
                                            nid = shuffled_ids[(idx+1) % len(shuffled_ids)]
                                            yt_prefetch.prefetch(f"https://youtu.be/{nid}", prev_path=prev_yt_path)
                                        except: pass
                                except Exception as e:
                                    log.err(f"erro ao aplicar {chosen}: {e}")
                                    last_applied = None
                            if active.get("integro") and media.match_tipo(str(chosen), "video"):
                                dur = media.video_duration(str(chosen)) or 0
                                step_s = int(max(dur, 5))
                            else:
                                step_s = 10
                            next_idx = idx + 1
                            if not is_loop_true and not is_loop_n and next_idx >= len(shuffled_ids):
                                state.set_pos({"idx": 0, "dir": pos_key, "day": date.today().isoformat(), "salt": media.get_salt()})
                            elif is_loop_true and next_idx >= len(shuffled_ids):
                                next_idx = 0
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date.today().isoformat(), "salt": media.get_salt()})
                            elif is_loop_n and next_idx >= len(shuffled_ids):
                                next_idx = 0
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date.today().isoformat(), "salt": media.get_salt()})
                            else:
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date.today().isoformat(), "salt": media.get_salt()})
                            nxt = transitions.next_transition(subs, now)
                            slot_end = nxt if nxt else datetime.now() + timedelta(seconds=step_s)
                            delay = min(step_s, max((slot_end - datetime.now()).total_seconds(), 1.0))
                            deadline = time.monotonic() + delay
                            while True:
                                left = deadline - time.monotonic()
                                if left <= 0:
                                    break
                                if _list_should_stop():
                                    return
                                time.sleep(min(left, float(POLL)))
                            continue
                except Exception as e:
                    log.err(f"erro youtube playlist {active['arquivo']}: {e}")
            key = (active["arquivo"], active["nome"], active["file_index"])
            if key != last_applied:
                try:
                    path = active["arquivo"]
                    if active.get("is_yt"):
                        path = _get_yt_or_prefetch(path, prev_path=prev_yt_path)
                    plugin, path = apply.apply(
                        path,
                        loop=bool(active.get("repetir") or active.get("loop")),
                        som=active.get("som"),
                        integro=bool(active.get("integro")),
                    )
                    log.err(f"aplicando: {entries.format_entry(active)} ({plugin})")
                    last_applied = key
                    if yt._is_in_yt_dir(path):
                        if current_yt_path and current_yt_path != path: prev_yt_path = current_yt_path
                        current_yt_path = path
                        try:
                            nxt_e = transitions.next_entry(subs, active, datetime.now())
                            if nxt_e and nxt_e.get("is_yt"): yt_prefetch.prefetch(nxt_e["arquivo"], prev_path=prev_yt_path)
                        except: pass
                except Exception as e:
                    log.err(f"erro ao aplicar {active['arquivo']}: {e}")
                    last_applied = None
        nxt = transitions.next_transition(subs, now)
        if nxt is None:
            if cfg.get("persist") or cfg.get("loop"):
                time.sleep(POLL)
                continue
            state.clear_list()
            log.err("lista concluída, voltando à agenda do yml.")
            return
        delay = max((nxt - datetime.now()).total_seconds(), 1.0)
        time.sleep(min(delay, float(POLL)))
def _apply_named(sub, prev_path=None):
    try:
        path = sub["arquivo"]
        if sub.get("is_yt"):
            path = _get_yt_or_prefetch(path, prev_path=prev_path)
        plugin, path = apply.apply(
            path,
            loop=bool(sub.get("repetir") or sub.get("loop")),
            som=sub.get("som"),
            integro=bool(sub.get("integro")),
        )
        log.err(f"aplicando: {entries.format_entry(sub)} ({plugin})")
        return path
    except Exception as e:
        log.err(f"erro ao aplicar {sub.get('arquivo')}: {e}")
        return None
def _run_list_slideshow(cfg, lista):
    """Lista como slideshow (com -t/-m/-q/-l/-rep/-i/-v/-int/-s).
    Com `loop` int N, faz N passadas e volta à agenda do yml."""
    salt = media.get_salt()
    dir_key = f"list:{cfg.get('nome')}"
    passadas = 0
    while True:
        if _list_should_stop():
            return
        cfg = state.get_list()
        if cfg is None:
            return
        if lista is None:
            log.err("lista não encontrada, encerrando.")
            state.clear_list()
            return
        files = entries.list_media_queue(lista, cfg.get("tipo"))
        if not files:
            log.err("nenhuma mídia na lista, aguardando...")
            time.sleep(POLL)
            continue
        loop = cfg.get("loop") or False
        rep = bool(cfg.get("rep"))
        integro = bool(cfg.get("integro"))
        som = bool(cfg.get("som"))
        tempo_s = max(randomcfg.cfg_seconds(cfg.get("tempo"), default=1800), 5)
        qtd = cfg.get("qtd")
        max_s = cfg.get("max")
        order = media.day_shuffled(files, salt) if cfg.get("shuffled") else files
        day = date.today().isoformat()
        pos = state.get_pos()
        if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
            idx = int(pos.get("idx", 0)) % len(order)
        else:
            idx = int(cfg.get("idx", 0)) % len(order)
            state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})
        chosen = order[idx % len(order)]
        try:
            plugin, path = apply.apply(chosen, loop=rep or loop is True, som=som, integro=integro)
            log.err(f"aplicando: {path} ({plugin}) [{idx + 1}/{len(order)}]")
        except Exception as e:
            log.err(f"erro ao aplicar {chosen}: {e}")
        if integro and media.match_tipo(chosen, "video"):
            dur = media.video_duration(chosen)
            if cfg.get("tempo") is not None:
                step_s = int(max(tempo_s, max(dur or 0, 5)))
            else:
                step_s = int(max(dur or tempo_s, 5))
        else:
            step_s = tempo_s
        idx += 1
        if loop is True:
            if idx >= len(order):
                idx = 0
        elif parse.is_loop_n(loop):
            if idx >= len(order):
                passadas += 1
                if passadas >= loop:
                    state.clear_list()
                    log.err(f"slideshow concluído ({loop} passadas), voltando à agenda do yml.")
                    return
                idx = 0
        else:
            if qtd is not None:
                qtd = int(qtd) - 1
                if qtd <= 0:
                    state.clear_list()
                    log.err("slideshow encerrado, voltando à agenda do yml.")
                    return
            if max_s is not None:
                max_s = int(max_s) - step_s
                if max_s <= 0:
                    state.clear_list()
                    log.err("slideshow encerrado, voltando à agenda do yml.")
                    return
            if idx >= len(order):
                if len(order) == 1:
                    idx = 0
                else:
                    state.clear_list()
                    log.err("slideshow encerrado, voltando à agenda do yml.")
                    return
            cfg["qtd"] = qtd
            cfg["max"] = max_s
            state.set_list(cfg)
        state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})
        deadline = time.monotonic() + step_s
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if _list_should_stop():
                return
            time.sleep(min(left, float(POLL)))

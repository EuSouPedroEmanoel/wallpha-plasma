import time
from datetime import datetime, timedelta
from pathlib import Path

from . import apply, entries, log, media, schedule, state, transitions, yt, yt_prefetch

POLL = 15


def _remember(active):
    """Registra a mídia lógica aplicada para que `wallpha -n` sobreviva ao daemon."""
    state.set_last(transitions.last_key(active))


def _override_active(entries_list, now):
    """Resolve override da agenda ou uma mídia manual enquanto durar o prazo."""
    override = state.get_override()
    if not override:
        return None, None
    try:
        until = datetime.fromisoformat(str(override["until"]))
    except (KeyError, TypeError, ValueError):
        state.clear_override()
        return None, None
    if now >= until:
        state.clear_override()
        return None, None
    # Arquivo escolhido diretamente por ``-c ... -t`` não existe no yml.
    # Crie uma entrada normalizada mínima para o loop do daemon reaplicar a
    # mídia até o prazo, sem interferir no cálculo da próxima transição.
    manual_path = override.get("path")
    if manual_path:
        return ({
            "nome": "manual", "local": str(manual_path), "arquivo": str(manual_path),
            "is_dir": False, "is_yt": False, "is_list": False, "is_yt_list": False,
            "file_index": 0, "hora_start": None, "hora_end": None, "tempo": None,
            "default": False, "repetir": False, "loop": False, "som": False,
            "integro": False, "shuffled": False,
        }, until)
    try:
        key = override["key"]
    except (KeyError, TypeError):
        state.clear_override()
        return None, None
    active = transitions.entry_from_last(entries_list, key, now)
    if active is None:
        state.clear_override()
        return None, None
    return active, until


def _get_yt_or_prefetch(url, prev_path=None):
    """Tenta pegar do prefetch, senão baixa com fallback best->worst. Limpa prev_path antes se N tocando."""
    if not url:
        return url
    # tenta prefetch
    pref = yt_prefetch.get_result(url)
    if pref and Path(pref).exists():
        return pref
    # fallback sync com prev_path (caller garante N tocando)
    try:
        return yt.download_yt(url, prev_path=prev_path)
    except Exception:
        # tenta sem prev_path se falhou
        return yt.download_yt(url)


def _prefetch_next_for_schedule(entries_list, active, prev_path):
    """Calcula próximo YT URL da agenda e dispara prefetch."""
    try:
        nxt = transitions.next_entry(entries_list, active, datetime.now()) if active else None
        if nxt and nxt.get("is_yt") and nxt.get("arquivo"):
            # só prefetch se N ainda toca (verifica arquivo de active existe)
            cur_path = active.get("arquivo") if active else None
            if cur_path and Path(cur_path).exists() or (active and active.get("is_yt") and yt._is_in_yt_dir(cur_path or "")):
                # na verdade verifica se current N ainda está tocando: arquivo de N existe ou é YT em yt_dir
                # simplifica: se active ainda é o resolvido, assume tocando
                yt_prefetch.prefetch(nxt["arquivo"], prev_path=prev_path)
        elif nxt and nxt.get("is_yt_list"):
            # para yta, prefetch próximo id da playlist
            url = nxt.get("arquivo")
            if url and "list=" in url.lower():
                try:
                    ids = yt.get_playlist_ids(url)
                    if ids:
                        # escolhe próximo id baseado em pos
                        pos_key = f"yta:{nxt['nome']}:{url}"
                        pos = state.get_pos()
                        yta_pos = pos if pos and isinstance(pos, dict) and pos.get("dir") == pos_key else None
                        idx = int(yta_pos.get("idx", 0)) % len(ids) if yta_pos else 0
                        # N+1 é idx, já que idx aponta para próximo a tocar
                        shuffled = media.day_shuffled(ids, media.get_salt()) if nxt.get("shuffled") else ids
                        next_id = shuffled[idx % len(shuffled)]
                        yt_prefetch.prefetch(f"https://youtu.be/{next_id}", prev_path=prev_path)
                except Exception:
                    pass
    except Exception:
        pass


def _run_schedule():
    while True:
        if not state.is_on():
            log.err("modo automático desativado, encerrando.")
            import sys
            sys.exit(0)
        entries_list = entries.load_checked()
        if entries_list is None:
            log.err("erro no yml, aguardando correção...")
            time.sleep(POLL)
            continue
        if not entries_list:
            log.err("nenhum wallpaper no yml, encerrando.")
            import sys
            sys.exit(0)
        break

    log.err(f"daemon iniciado com {len(entries_list)} wallpaper(s).")
    last_applied = None
    integro_key = None
    integro_advance = None
    prev_yt_path = None
    current_yt_path = None

    while True:
        if not state.is_on():
            log.err("modo automático desativado, encerrando.")
            import sys
            sys.exit(0)
        if state.get_random() is not None:
            log.err("modo aleatório ativado, encerrando.")
            import sys
            sys.exit(0)

        entries_list = entries.load_checked()
        if entries_list is None:
            log.err("erro no yml, aguardando correção...")
            time.sleep(POLL)
            continue
        if not entries_list:
            time.sleep(POLL)
            continue

        now = datetime.now()
        active = schedule.resolve_active(entries_list, now)
        override_active, override_until = _override_active(entries_list, now)
        if override_active is not None:
            active = override_active

        if active is not None and active.get("integro"):
            is_playlist_yt = bool(active.get("is_yt_list") and "list=" in str(active.get("arquivo") or "").lower())
            is_video_candidate = bool(
                (active.get("is_dir") or active.get("is_yt") or media.match_tipo(active.get("arquivo") or "", "video"))
                and not is_playlist_yt
            )
            if is_video_candidate:
                key = (active["local"], active["nome"], active.get("arquivo"))
                if key != integro_key:
                    integro_key = key
                    integro_advance = None
                if integro_advance is None or now >= integro_advance:
                    if integro_advance is not None:
                        nxt = transitions.next_entry(entries_list, active, now)
                        if nxt is not None:
                            active = nxt
                        key = (active["local"], active["nome"], active.get("arquivo"))
                        integro_key = key
                    try:
                        path_for_apply = active["arquivo"]
                        if active.get("is_yt"):
                            path_for_apply = _get_yt_or_prefetch(path_for_apply, prev_path=prev_yt_path)
                        plugin, path = apply.apply(
                            path_for_apply,
                            loop=bool(active.get("repetir") or active.get("loop")),
                            som=active.get("som"), integro=True
                        )
                        log.err(f"aplicando: {entries.format_entry(active)} ({plugin})")
                        last_applied = (active["arquivo"], active["nome"], active.get("file_index", 0))
                        _remember(active)
                        # atualiza N e N-1 para prefetch
                        if active.get("is_yt") and yt._is_in_yt_dir(path_for_apply):
                            if current_yt_path and current_yt_path != path_for_apply:
                                prev_yt_path = current_yt_path
                            current_yt_path = path_for_apply
                        else:
                            # para não-YT, mantém tracking mas não limpa
                            if current_yt_path:
                                prev_yt_path = current_yt_path
                            current_yt_path = None
                        _prefetch_next_for_schedule(entries_list, active, prev_yt_path)
                    except Exception as e:
                        log.err(f"erro ao aplicar {active.get('arquivo')}: {e}")
                        last_applied = None
                        dur = 5
                    else:
                        dur_path = str(path) if 'path' in locals() else active.get("arquivo")
                        dur = media.video_duration(dur_path) or 5.0
                        if active.get("tempo") is not None:
                            from .randomcfg import cfg_seconds
                            tempo_s = max(cfg_seconds(active.get("tempo"), default=1800), 5)
                            dur = max(dur, tempo_s)
                        if dur < 5:
                            dur = 5
                    integro_advance = now + timedelta(seconds=max(dur, 5))
                delay = max((integro_advance - datetime.now()).total_seconds(), 1.0)
                time.sleep(min(delay, float(POLL)))
                continue

        integro_key = None
        integro_advance = None

        if active is not None:
            yt_playlist_handled = False
            is_yt_list = bool(active.get("is_yt_list"))
            has_playlist = "list=" in str(active.get("arquivo", "")).lower()
            if active.get("is_yt") and has_playlist and not is_yt_list:
                try:
                    url = active["arquivo"]
                    yt_playlist_handled = True
                    all_ids = yt.get_playlist_ids(url)
                    if all_ids:
                        if active.get("shuffled"):
                            chosen_id = media.day_shuffled(all_ids, media.get_salt())[0]
                        else:
                            chosen_id = all_ids[0]
                        video_url = f"https://youtu.be/{chosen_id}"
                        try:
                            playlist_id = yt._extract_playlist_id(url) or "playlist"
                            cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
                            if cached:
                                chosen = str(cached[0])
                            else:
                                chosen = _get_yt_or_prefetch(video_url, prev_path=prev_yt_path)
                        except Exception:
                            chosen = _get_yt_or_prefetch(video_url, prev_path=prev_yt_path)
                        key = (str(chosen), active["nome"], chosen_id)
                        if key != last_applied:
                            try:
                                plugin, _ = apply.apply(str(chosen), loop=bool(active.get("repetir") or active.get("loop")), som=active.get("som"), integro=bool(active.get("integro")))
                                log.err(f"aplicando: {entries.format_entry(active)} [1/1] {chosen_id} ({plugin})")
                                last_applied = key
                                _remember(active)
                                # tracking YT para limpeza N-1 antes de N+1
                                if yt._is_in_yt_dir(chosen):
                                    if current_yt_path and current_yt_path != chosen:
                                        prev_yt_path = current_yt_path
                                    current_yt_path = chosen
                                # prefetch não se aplica aqui (single id)
                            except Exception as e:
                                log.err(f"erro ao aplicar {chosen}: {e}")
                                last_applied = None
                except Exception as e:
                    log.err(f"erro youtube {active['arquivo']}: {e}")
            elif active.get("is_yt") and has_playlist and is_yt_list:
                try:
                    url = active["arquivo"]
                    try:
                        all_ids = yt.get_playlist_ids(url)
                    except Exception as e:
                        log.err(f"falha ao listar playlist {url}: {e}")
                        all_ids = []
                    if all_ids:
                        yt_playlist_handled = True
                        if active.get("shuffled"):
                            shuffled_ids = media.day_shuffled(all_ids, media.get_salt())
                        else:
                            shuffled_ids = all_ids
                        pos_key = f"yta:{active['nome']}:{url}"
                        pos = state.get_pos()
                        yta_pos = pos if pos and isinstance(pos, dict) and pos.get("dir") == pos_key else None
                        idx = int(yta_pos.get("idx", 0)) % len(shuffled_ids) if yta_pos else 0
                        loop_val = active.get("loop")
                        is_loop_true = loop_val is True
                        is_loop_n = parse_is_loop_n(loop_val)
                        if not is_loop_true and not is_loop_n and idx >= len(shuffled_ids):
                            state.set_pos({"idx": 0, "dir": pos_key, "day": date_today_iso(), "salt": media.get_salt()})
                        else:
                            chosen_id = shuffled_ids[idx % len(shuffled_ids)]
                            video_url = f"https://youtu.be/{chosen_id}"
                            try:
                                playlist_id = yt._extract_playlist_id(url) or "playlist"
                                cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
                                if not cached:
                                    single_path = _get_yt_or_prefetch(video_url, prev_path=prev_yt_path)
                                    chosen = single_path
                                else:
                                    chosen = str(cached[0])
                            except Exception:
                                chosen = _get_yt_or_prefetch(video_url, prev_path=prev_yt_path)
                            key = (str(chosen), active["nome"], idx)
                            if key != last_applied:
                                try:
                                    plugin, _ = apply.apply(str(chosen), loop=bool(active.get("repetir") or is_loop_true), som=active.get("som"), integro=bool(active.get("integro")))
                                    log.err(f"aplicando: {entries.format_entry(active)} [{idx+1}/{len(shuffled_ids)}] {chosen_id} ({plugin})")
                                    last_applied = key
                                    _remember(active)
                                    if yt._is_in_yt_dir(chosen):
                                        if current_yt_path and current_yt_path != chosen:
                                            prev_yt_path = current_yt_path
                                        current_yt_path = chosen
                                    # prefetch próximo id da mesma playlist
                                    try:
                                        nxt_id = shuffled_ids[(idx + 1) % len(shuffled_ids)]
                                        yt_prefetch.prefetch(f"https://youtu.be/{nxt_id}", prev_path=prev_yt_path)
                                    except Exception:
                                        pass
                                except Exception as e:
                                    log.err(f"erro ao aplicar {chosen}: {e}")
                                    last_applied = None
                            if active.get("integro") and media.match_tipo(str(chosen), "video"):
                                dur = media.video_duration(str(chosen)) or 0
                                step_s = int(max(dur, 5))
                            else:
                                if active.get("tempo"):
                                    from .randomcfg import cfg_seconds
                                    total_tempo = cfg_seconds(active.get("tempo"), default=1800)
                                    step_s = max(total_tempo // len(shuffled_ids), 5) if shuffled_ids else 10
                                else:
                                    step_s = 10
                            next_idx = idx + 1
                            if not is_loop_true and not is_loop_n and next_idx >= len(shuffled_ids):
                                state.set_pos({"idx": 0, "dir": pos_key, "day": date_today_iso(), "salt": media.get_salt()})
                            elif is_loop_true and next_idx >= len(shuffled_ids):
                                next_idx = 0
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date_today_iso(), "salt": media.get_salt()})
                            elif is_loop_n and next_idx >= len(shuffled_ids):
                                next_idx = 0
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date_today_iso(), "salt": media.get_salt()})
                            else:
                                state.set_pos({"idx": next_idx, "dir": pos_key, "day": date_today_iso(), "salt": media.get_salt()})
                            nxt = transitions.next_transition(entries_list, datetime.now())
                            slot_end = nxt if nxt else datetime.now() + timedelta(seconds=step_s)
                            delay = min(step_s, max((slot_end - datetime.now()).total_seconds(), 1.0))
                            deadline = time.monotonic() + delay
                            while True:
                                left = deadline - time.monotonic()
                                if left <= 0:
                                    break
                                if not state.is_on():
                                    log.err("modo automático desativado, encerrando.")
                                    import sys
                                    sys.exit(0)
                                if state.get_random() is not None or state.get_list() is not None:
                                    import sys
                                    sys.exit(0)
                                time.sleep(min(left, float(POLL)))
                            continue
                    else:
                        log.err(f"playlist vazia: {url}")
                        yt_playlist_handled = True
                except Exception as e:
                    log.err(f"erro ao preparar youtube playlist {active['arquivo']}: {e}")
                    yt_playlist_handled = True
            if active.get("is_yt") and not yt_playlist_handled:
                try:
                    dl_path = _get_yt_or_prefetch(active["arquivo"], prev_path=prev_yt_path)
                    path = dl_path
                    key = (path, active["nome"], active.get("file_index", 0))
                    if key != last_applied:
                        try:
                            plugin, _ = apply.apply(
                                path,
                                loop=bool(active.get("repetir") or active.get("loop")),
                                som=active.get("som"),
                                integro=bool(active.get("integro")),
                            )
                            log.err(f"aplicando: {entries.format_entry(active)} ({plugin})")
                            last_applied = key
                            _remember(active)
                            if yt._is_in_yt_dir(path):
                                if current_yt_path and current_yt_path != path:
                                    prev_yt_path = current_yt_path
                                current_yt_path = path
                            _prefetch_next_for_schedule(entries_list, active, prev_yt_path)
                        except Exception as e:
                            log.err(f"erro ao aplicar {active['arquivo']}: {e}")
                            last_applied = None
                    yt_playlist_handled = True
                except Exception as e:
                    log.err(f"erro ao preparar youtube {active['arquivo']}: {e}")
            if not yt_playlist_handled:
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
                        _remember(active)
                        try:
                            p = path if 'path' in locals() else active.get("arquivo")
                            if p and yt._is_in_yt_dir(str(p)):
                                if current_yt_path and current_yt_path != str(p):
                                    prev_yt_path = current_yt_path
                                current_yt_path = str(p)
                            _prefetch_next_for_schedule(entries_list, active, prev_yt_path)
                        except Exception:
                            pass
                    except Exception as e:
                        log.err(f"erro ao aplicar {active['arquivo']}: {e}")
                        last_applied = None

        nxt = transitions.next_transition(entries_list, datetime.now())
        if override_until is not None and (nxt is None or override_until < nxt):
            nxt = override_until
        if nxt is None:
            time.sleep(POLL)
            continue

        delay = max((nxt - datetime.now()).total_seconds(), 1.0)
        delay = min(delay, float(POLL))
        time.sleep(delay)


def parse_is_loop_n(v):
    from .parse import is_loop_n
    return is_loop_n(v)


def date_today_iso():
    from datetime import date
    return date.today().isoformat()

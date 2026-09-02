import time
from datetime import date
from pathlib import Path

from . import apply, log, media, parse, randomcfg, state, yt, yt_prefetch

POLL = 15


def _get_yt_or_prefetch(url, prev_path=None):
    if not url or "youtu" not in url.lower():
        # para lista não-YT, tenta prefetch mesmo assim (no-op)
        try:
            return yt.download_yt(url, prev_path=prev_path) if "youtu" in url.lower() else url
        except Exception:
            return url
    pref = yt_prefetch.get_result(url)
    if pref and Path(pref).exists():
        return pref
    return yt.download_yt(url, prev_path=prev_path)


def _random_should_stop():
    if not state.is_on():
        log.err("modo automático desativado, encerrando.")
        import sys
        sys.exit(0)
    if state.get_random() is None:
        log.err("modo aleatório encerrado, voltando à agenda.")
        return True
    return False


def _run_random():
    salt = media.get_salt()
    dir_key = state.get_random().get("dir")
    log.err("modo aleatório iniciado.")
    passadas = 0
    prev_yt_path = None
    current_yt_path = None

    while True:
        if _random_should_stop():
            return True

        rnd = state.get_random()
        loop = rnd.get("loop") or False
        rep = bool(rnd.get("rep"))
        integro = bool(rnd.get("integro"))
        som = bool(rnd.get("som"))
        raw_tempo = rnd.get("tempo")
        if raw_tempo is None and integro:
            tempo_s = None
        else:
            tempo_s = max(randomcfg.cfg_seconds(raw_tempo, default=1800), 5)
        qtd = rnd.get("qtd")
        max_s = rnd.get("max")

        dir_path = Path(dir_key) if dir_key else None
        playlist_marker = dir_path / ".playlist_url" if dir_path else None
        is_yt_playlist = playlist_marker and playlist_marker.is_file()
        log.err(f"DEBUG _run_random dir_key={dir_key} is_yt_playlist={is_yt_playlist} marker={playlist_marker}")
        if is_yt_playlist:
            try:
                url = playlist_marker.read_text(encoding="utf-8").strip()
                all_ids = yt.get_playlist_ids(url)
                if not all_ids:
                    raise RuntimeError("playlist vazia")
                order_ids = media.day_shuffled(all_ids, salt)
                day = date.today().isoformat()
                pos = state.get_pos()
                if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
                    idx = int(pos.get("idx", 0)) % len(order_ids)
                else:
                    idx = 0
                    state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})
                chosen_id = order_ids[idx % len(order_ids)]
                playlist_id = yt._extract_playlist_id(url) or "playlist"
                next_url = f"https://youtu.be/{chosen_id}"
                cached = list((yt.yt_dir() / playlist_id).glob(f"{chosen_id}.*"))
                if cached:
                    chosen = str(cached[0])
                else:
                    pref = yt_prefetch.get_result(next_url)
                    if pref and Path(pref).exists():
                        chosen = pref
                    else:
                        chosen = yt.download_yt(next_url, prev_path=prev_yt_path)
                    if Path(chosen).is_dir():
                        files_in = [p for p in Path(chosen).iterdir() if p.is_file()]
                        chosen = str(files_in[0]) if files_in else chosen
                try:
                    plugin, path = apply.apply(chosen, loop=rep or loop is True, som=som, integro=integro)
                    log.err(f"aplicando: {path} ({plugin}) [{idx + 1}/{len(order_ids)}] {chosen_id} (youtube-list)")
                    # tracking e prefetch próximo (qualquer lista)
                    if yt._is_in_yt_dir(chosen):
                        if current_yt_path and current_yt_path != chosen:
                            prev_yt_path = current_yt_path
                        current_yt_path = chosen
                    try:
                        nxt_id = order_ids[(idx + 1) % len(order_ids)]
                        yt_prefetch.prefetch(f"https://youtu.be/{nxt_id}", prev_path=prev_yt_path)
                    except Exception:
                        pass
                except Exception as e:
                    log.err(f"erro ao aplicar {chosen}: {e}")
                if integro and media.match_tipo(chosen, "video"):
                    dur = media.video_duration(chosen)
                    if rnd.get("tempo") is None:
                        step_s = int(max(dur or 5, 5))
                    else:
                        step_s = int(max(tempo_s, max(dur or 0, 5)))
                else:
                    step_s = tempo_s if tempo_s is not None else 5
                idx += 1
                if loop is True:
                    if idx >= len(order_ids):
                        idx = 0
                elif parse.is_loop_n(loop):
                    if idx >= len(order_ids):
                        passadas += 1
                        if passadas >= loop:
                            return True
                        idx = 0
                else:
                    if qtd is not None:
                        qtd = int(qtd) - 1
                        if qtd <= 0:
                            return True
                    if max_s is not None:
                        max_s = int(max_s) - step_s
                        if max_s <= 0:
                            return True
                    if idx >= len(order_ids):
                        if len(order_ids) == 1:
                            idx = 0
                        else:
                            return True
                    rnd["qtd"] = qtd
                    rnd["max"] = max_s
                    state.set_random(rnd)
                state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})
                deadline = time.monotonic() + step_s
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        break
                    if _random_should_stop():
                        return True
                    time.sleep(min(left, float(POLL)))
                continue
            except Exception as e:
                log.err(f"erro playlist youtube-list {e}, aguardando...")
                time.sleep(POLL)
                continue

        _, files, err = randomcfg.build_random_queue(rnd)
        if err:
            log.err(f"{err}, aguardando...")
            time.sleep(POLL)
            continue
        if not files:
            log.err("nenhum arquivo de mídia encontrado, aguardando...")
            time.sleep(POLL)
            continue

        order = media.day_shuffled(files, salt)
        day = date.today().isoformat()
        pos = state.get_pos()
        if pos and pos.get("day") == day and pos.get("salt") == salt and pos.get("dir") == dir_key:
            idx = int(pos.get("idx", 0)) % len(order)
        else:
            idx = 0
            state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})

        chosen = order[idx % len(order)]
        # tenta prefetch se for YT (raro em random file, mas cobre)
        if "youtu" in str(chosen).lower() and yt._is_in_yt_dir(str(chosen)) is False:
            # chosen é URL, tenta prefetch
            pref = yt_prefetch.get_result(str(chosen))
            if pref and Path(pref).exists():
                chosen = pref
            else:
                try:
                    chosen = yt.download_yt(str(chosen), prev_path=prev_yt_path)
                except Exception:
                    pass
        try:
            plugin, path = apply.apply(chosen, loop=rep or loop is True, som=som, integro=integro)
            log.err(f"aplicando: {path} ({plugin}) [{idx + 1}/{len(order)}]")
            if yt._is_in_yt_dir(str(chosen)) or yt._is_in_yt_dir(str(path)):
                p = str(path) if yt._is_in_yt_dir(str(path)) else str(chosen)
                if current_yt_path and current_yt_path != p:
                    prev_yt_path = current_yt_path
                current_yt_path = p
                # prefetch próximo da mesma ordem se for YT
                try:
                    nxt = order[(idx + 1) % len(order)]
                    if "youtu" in str(nxt).lower():
                        yt_prefetch.prefetch(str(nxt), prev_path=prev_yt_path)
                    elif yt._is_in_yt_dir(str(nxt)):
                        yt_prefetch.prefetch(str(nxt), prev_path=prev_yt_path)
                except Exception:
                    pass
        except Exception as e:
            log.err(f"erro ao aplicar {chosen}: {e}")

        if integro and media.match_tipo(chosen, "video"):
            dur = media.video_duration(chosen)
            if rnd.get("tempo") is not None:
                step_s = int(max(tempo_s, max(dur or 0, 5)))
            else:
                step_s = int(max(dur or 5, 5))
        else:
            step_s = tempo_s if tempo_s is not None else 5
        idx += 1
        if loop is True:
            if idx >= len(order):
                idx = 0
        elif parse.is_loop_n(loop):
            if idx >= len(order):
                passadas += 1
                if passadas >= loop:
                    return True
                idx = 0
        else:
            if qtd is not None:
                qtd = int(qtd) - 1
                if qtd <= 0:
                    return True
            if max_s is not None:
                max_s = int(max_s) - step_s
                if max_s <= 0:
                    return True
            if idx >= len(order):
                if len(order) == 1:
                    idx = 0
                else:
                    return True
            rnd["qtd"] = qtd
            rnd["max"] = max_s
            state.set_random(rnd)
        state.set_pos({"idx": idx, "day": day, "salt": salt, "dir": dir_key})

        deadline = time.monotonic() + step_s
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if _random_should_stop():
                return True
            time.sleep(min(left, float(POLL)))

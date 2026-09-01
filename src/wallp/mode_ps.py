import os
from datetime import datetime, timedelta
from pathlib import Path

from . import entries, log, media, schedule, transitions

# limite para aviso de pesado (mesmo do yt buffer)
try:
    HEAVY_LIMIT = int(os.environ.get("WALLP_YT_CACHE_MB", "500")) * 1024 * 1024
except ValueError:
    HEAVY_LIMIT = 500 * 1024 * 1024

def _hum_size(n):
    if n is None:
        return "-"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if n < 1024:
        return f"{n} B"
    if n < 1024*1024:
        return f"{n/1024:.1f} KB"
    if n < 1024*1024*1024:
        return f"{n/1024/1024:.1f} MB"
    return f"{n/1024/1024/1024:.2f} GB"

def _hum_tempo(td):
    if td is None:
        return "-"
    try:
        # round para evitar 29.9s -> 29s por epsilon de 100ms
        s = int(round(td.total_seconds()))
    except AttributeError:
        try:
            s = int(round(float(td)))
        except Exception:
            return str(td)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s//60}m" + (f"{s%60}s" if s%60 else "")
    if s < 86400:
        h = s//3600; m = (s%3600)//60
        return f"{h}h" + (f"{m}m" if m else "")
    d = s//86400; h = (s%86400)//3600
    return f"{d}d" + (f"{h}h" if h else "")

def _entry_size_bytes(e):
    """Tamanho em bytes do arquivo ativo (ou soma se dir com muitos arquivos e não tem arquivo específico)."""
    try:
        if e.get("is_yt"):
            # yt: verifica cache em tmpfs se já baixado, senão desconhecido
            p = Path(str(e.get("arquivo") or e.get("local") or ""))
            if p.is_file():
                return p.stat().st_size
            # tenta yt_dir cache por id
            return None
        if e.get("is_dir"):
            arq = e.get("arquivo")
            if arq and Path(arq).is_file():
                return Path(arq).stat().st_size
            # total do diretório
            tot = 0
            for f in (e.get("files") or []):
                try:
                    tot += Path(f).stat().st_size
                except OSError:
                    pass
            return tot if tot else None
        else:
            p = Path(str(e.get("arquivo") or e.get("local") or ""))
            if p.is_file():
                return p.stat().st_size
            return None
    except OSError:
        return None

def _entry_dur(e):
    # duração do item (tempo ativo até próxima troca no schedule)
    # para dir/lista usa helpers; para integro pode ser video_duration, mas mostra tempo do yml
    if e.get("is_dir"):
        return entries._dir_tempo(e)
    if e.get("is_list"):
        # se tem sub_nome, mostra duração do sub, senão total
        return e.get("tempo") or entries._list_total(e)
    return e.get("tempo")

def _short_path(arq):
    """Só pasta pai + arquivo, ex: Wallpapers/celeste.mp4"""
    try:
        p = Path(str(arq)).expanduser()
        if not p.name:
            return str(arq)
        # se tem parent com nome (não root)
        if p.parent and p.parent.name and p.parent.name not in (".", "/"):
            return f"{p.parent.name}/{p.name}"
        return p.name
    except Exception:
        return str(arq)


def _entry_loop_str(e):
    v = e.get("loop")
    if v is True:
        return "true"
    if v is False or v is None:
        return "false"
    try:
        return str(int(v))
    except Exception:
        return str(v)

def _ps_mode(opts):
    n = opts.get("ps_count")
    # sem N explícito → só atual (1); compat fallback antigo 10 vira 1
    if n is None:
        n = 1
    try:
        n = int(n)
    except (ValueError, TypeError):
        n = 1
    n = max(1, min(n, 100))

    entries_list = entries.load_checked()
    if entries_list is None:
        import sys; sys.exit(1)
    if not entries_list:
        log.err("nenhum wallpaper no yml. Rode: wallp --init")
        import sys; sys.exit(1)

    now = datetime.now()
    cur = now
    seen = []
    # evita loop infinito se schedule cíclico sem transição (dir loop infinito)
    # usa next_transition para avançar; se não houver, usa duración do ativo
    for idx in range(n):
        active = schedule.resolve_active(entries_list, cur)
        if active is None:
            # sem ativo, tenta próximo dia 00:00
            nxt_day = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            active = schedule.resolve_active(entries_list, nxt_day)
            if active is None:
                break
            cur = nxt_day

        # calcula próximo instante de troca
        nxt = transitions.next_transition(entries_list, cur)
        # se ativo é dir/lista com duração interna, next_transition já cobra;
        # se for vídeo loop infinito, next_transition pode ser None (infinito) — mostra até fim do dia
        if nxt is None:
            # fallback: usa duração do ativo se finita, senão fim do dia
            dur = _entry_dur(active)
            if dur is not None:
                try:
                    nxt = cur + dur
                except Exception:
                    nxt = cur + timedelta(hours=1)
            else:
                nxt = cur.replace(hour=23, minute=59, second=59) + timedelta(seconds=1)

        # garante avanço mínimo
        if nxt <= cur:
            nxt = cur + timedelta(milliseconds=100)

        seen.append((cur, nxt, active))

        # avança para logo após nxt (epsilon pequeno para cair no próximo slot)
        cur = nxt + timedelta(milliseconds=100)
        # evita ficar preso no mesmo arquivo se for loop infinito real (vídeo loop:true sem tempo)
        if len(seen) >= 2 and seen[-1][2].get("arquivo") == seen[-2][2].get("arquivo") and seen[-1][2].get("nome") == seen[-2][2].get("nome"):
            if _entry_dur(active) is None:
                # vídeo com loop infinito: mesmo arquivo até -x, preenche resto
                while len(seen) < n:
                    nxt2 = cur + timedelta(hours=1)
                    seen.append((cur, nxt2, active))
                    cur = nxt2 + timedelta(milliseconds=100)
                break

        # evita cruzar muito futuro (365 dias já coberto por next_transition)
        if (cur - now).days > 370:
            break

    # render — sem N mostra só o atual
    if len(seen) == 1:
        print(f"Wallpaper atual — {now.strftime('%Y-%m-%d %H:%M:%S')} (wallp -ps):\n")
    else:
        print(f"Próximos {len(seen)} wallpapers a partir de {now.strftime('%Y-%m-%d %H:%M:%S')} (wallp -ps {n}):\n")
    for i, (start, end, e) in enumerate(seen, 1):
        size = _entry_size_bytes(e)
        size_s = _hum_size(size)
        # marca pesado
        heavy = size is not None and size > HEAVY_LIMIT
        heavy_mark = f" ⚠️ >{_hum_size(HEAVY_LIMIT)}" if heavy else ""
        nome = (e.get("nome") or "")[:40]
        # para lista, mostra sub_nome
        if e.get("is_list") and e.get("sub_nome"):
            nome = f"{e['nome']}/{e['sub_nome']}"[:40]
        dur = _entry_dur(e)
        real = end - start
        # se dur é None (default sem tempo ou vídeo loop infinito), mostra duração real até próxima troca
        if dur is None:
            dur = real
        dur_s = _hum_tempo(dur)
        loop_s = _entry_loop_str(e)
        integro_s = "true" if e.get("integro") else "false"
        # hora
        if e.get("hora_start") is not None:
            hs = e["hora_start"].strftime("%H:%M")
            he = e["hora_end"].strftime("%H:%M") if e.get("hora_end") else ""
            hora_s = f"{hs}-{he}" if he else f"{hs}+{dur_s}"
        else:
            hora_s = f"{start.strftime('%H:%M')}"
        # duração real até próxima troca (para default sem tempo, já é dur)
        real_s = _hum_tempo(real)
        # arquivo — só pasta pai + nome (curto)
        arq = e.get("arquivo") or e.get("local") or ""
        arq_disp = _short_path(arq)

        # tópicos (em vez de tabela)
        print(f"{i}. {nome}")
        print(f"   • arquivo: {arq_disp}")
        print(f"   • tamanho: {size_s}{heavy_mark}" + (f"  ⚠️ pesado (> {_hum_size(HEAVY_LIMIT)}) — considere comprimir" if heavy else ""))
        print(f"   • duração: {dur_s}")
        print(f"   • loop: {loop_s}")
        print(f"   • integro: {integro_s}")
        print(f"   • hora: {hora_s}")
        print(f"   • período: {start.strftime('%m-%d %H:%M')} → {end.strftime('%H:%M')} ({real_s})")
        if i != len(seen):
            print()

    print()
    # rodapé com dicas
    if any(_entry_size_bytes(e) and _entry_size_bytes(e) > HEAVY_LIMIT for _,_,e in seen):
        print(f"⚠️  Vídeos >{_hum_size(HEAVY_LIMIT)} podem estourar RAM/tmpfs 500MB e aumentar plasmashell (+50MB). Rode wallp --profile para varredura completa.")
    print(f"Dica: wallp -ps 20  |  wallp --profile  |  wallp -al")

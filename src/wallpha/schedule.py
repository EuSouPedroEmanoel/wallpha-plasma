from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import entries as ent
from .media import day_shuffled, get_salt
from .parse import _dia_rank, is_loop_n, matches_day

def _hora_entries(entries):
    return sorted((e for e in entries if e["hora_start"] is not None), key=lambda e: e["hora_start"])


def _slot_end(e, day, nxt_start):
    if e["hora_end"] is not None:
        return datetime.combine(day, e["hora_end"])
    start = datetime.combine(day, e["hora_start"])
    loop = e.get("loop")
    if loop is True:
        return nxt_start
    if is_loop_n(loop):
        if not e["is_dir"] and not e.get("is_list"):
            return nxt_start
        if e["is_dir"]:
            return start + ent._dir_tempo(e) * len(e["files"]) * loop
        return start + (e["tempo"] or ent._list_total(e)) * loop
    if e["is_dir"]:
        return start + ent._dir_tempo(e) * len(e["files"])
    if e.get("is_list"):
        return start + (e["tempo"] or ent._list_total(e))
    return start + e["tempo"]


def _hora_slots(entries, day):
    he = _hora_entries(entries)
    slots = []
    n = len(he)
    for i, e in enumerate(he):
        start = datetime.combine(day, e["hora_start"])
        nxt = he[i + 1]["hora_start"] if i + 1 < n else None
        nxt_start = datetime.combine(day, nxt) if nxt else datetime.combine(day + timedelta(days=1), time(0, 0))
        end = _slot_end(e, day, nxt_start)
        end = min(end, nxt_start)
        if end <= start:
            end = start + timedelta(seconds=1)
        slots.append((start, end, e))
    return slots


def _rotation(entries):
    """Itens sem hora e sem default, do mais específico pro mais genérico.
    O dia mais específico roda primeiro (em loop, nunca passa pro genérico);
    se a rotação dele termina, o genérico seguinte segue até o default."""
    rot = [e for e in entries if e["hora_start"] is None and not e["default"]]
    return sorted(rot, key=lambda e: -_dia_rank(e.get("dia")))


def _default(entries):
    """Default mais específico ativo (maior rank de dia); o global (sem dia) é o piso."""
    best = None
    best_rank = -1
    for e in entries:
        if not e["default"]:
            continue
        r = _dia_rank(e.get("dia"))
        if r > best_rank:
            best = e
            best_rank = r
    return best


def _cycle_order(entries):
    """Ordem da agenda no dia: rotação (específico -> genérico) e depois os
    defaults (mais específico primeiro). Usado no avanço manual (-n)."""
    rot = _rotation(entries)
    dflts = sorted((e for e in entries if e["default"]), key=lambda e: -_dia_rank(e.get("dia")))
    return rot + dflts


def _rot_duration(e):
    """Duração da rotação do item: None = infinita (trava até o fim do slot/dia).
    Vídeo com `loop` trava o playback (infinito); dir/lista com `loop: N`
    duram exatamente N ciclos."""
    loop = e.get("loop")
    if loop is True:
        return None
    if is_loop_n(loop):
        if e["is_dir"]:
            return ent._dir_tempo(e) * len(e["files"]) * loop
        if e.get("is_list"):
            return (e["tempo"] or ent._list_total(e)) * loop
        return None
    if loop:
        return None
    if e["is_dir"]:
        return ent._dir_tempo(e) * len(e["files"])
    if e.get("is_list"):
        return e["tempo"] or ent._list_total(e)
    return e["tempo"]


def _free_before(slots, day_start, now):
    total = (now - day_start).total_seconds()
    for start, end, _ in slots:
        ov = min(now, end) - max(day_start, start)
        if ov.total_seconds() > 0:
            total -= ov.total_seconds()
    return max(total, 0.0)


def _resolve_rot(rot, free):
    acc = 0.0
    for e in rot:
        d = _rot_duration(e)
        if d is None:
            return e, max(free - acc, 0.0)
        secs = d.total_seconds()
        if free < acc + secs:
            return e, max(free - acc, 0.0)
        acc += secs
    return None, None


def _with_file(e, within):
    if e["is_dir"]:
        t = ent._dir_tempo(e).total_seconds()
        idx = int(within // t) % len(e["files"])
        e = dict(e)
        e["file_index"] = idx
        e["arquivo"] = e["files"][idx]
    return e


def _sub_by_within(subs, e, within, day=None):
    """Sub-item ativo por rotação de tempo (within = segundos na lista).
    Com `day`, sub-itens com `dia` fora daquele dia são pulados.
    Se a lista tem `shuffled:true`, a ordem é randomica diaria com salt — mesma
    lógica determinística de diretório local e playlist youtube (day_shuffled)."""
    active = [s for s in subs if matches_day(s, day)] or subs
    if e.get("shuffled"):
        active = day_shuffled(active, get_salt(), day)
    total = ent._list_total(e, day).total_seconds()
    if e["loop"] and total > 0:
        within = within % total
    acc = 0.0
    for s in active:
        secs = ent._sub_dur(s, e).total_seconds()
        if within < acc + secs:
            return s, max(within - acc, 0.0)
        acc += secs
    return active[-1], max(within - acc, 0.0)


def _with_list(e, within, now):
    """Achata uma lista no sub-item ativo: hora (mini-agenda) ou rotação de tempo.
    Listas aninhadas achata recursivamente (sub_nome vira caminho pai/filho)."""
    subs = e["sub_entries"]
    if any(s["hora_start"] is not None for s in subs):
        sub = resolve_active(subs, now) or subs[0]
        idx = ent._sub_index(subs, sub)
        if sub.get("is_list"):
            out = ent._apply_sub(dict(e), sub)
            out["sub_index"] = idx
            out["sub_nome"] = f"{sub['nome']}/{sub['sub_nome']}" if sub.get("sub_nome") else sub["nome"]
            return out
        out = ent._apply_sub(dict(e), sub)
        out["sub_index"] = idx
        out["sub_nome"] = sub["nome"]
        return out
    sub, sub_within = _sub_by_within(subs, e, within, now.date())
    idx = subs.index(sub)
    if sub.get("is_list"):
        inner = _with_list(sub, sub_within, now)
        out = ent._apply_sub(dict(e), inner)
        out["sub_index"] = idx
        out["sub_nome"] = f"{sub['nome']}/{inner['sub_nome']}" if inner.get("sub_nome") else sub["nome"]
        return out
    if sub["is_dir"]:
        sub = _with_file(dict(sub), sub_within)
    out = ent._apply_sub(dict(e), sub)
    out["sub_index"] = idx
    out["sub_nome"] = sub["nome"]
    return out


def _default_result(d, free, now):
    if d.get("is_list"):
        return _with_list(d, free, now)
    if d["is_dir"]:
        t = ent._dir_tempo(d).total_seconds()
        idx = int(free // t) % len(d["files"])
        d = dict(d)
        d["file_index"] = idx
        d["arquivo"] = d["files"][idx]
    return d


def _with_file_or_list(e, within, now):
    if e.get("is_list"):
        return _with_list(e, within, now)
    return _with_file(e, within)


def resolve_active(entries, now):
    day = now.date()
    entries = [e for e in entries if matches_day(e, day)]
    day_start = datetime.combine(day, time(0, 0))
    slots = _hora_slots(entries, day)

    for start, end, e in slots:
        if start <= now < end:
            return _with_file_or_list(e, (now - start).total_seconds(), now)

    rot = _rotation(entries)
    dflt = _default(entries)
    free = _free_before(slots, day_start, now)

    if rot:
        e, within = _resolve_rot(rot, free)
        if e is not None:
            return _with_file_or_list(e, within, now)
        if dflt is not None:
            return _default_result(dflt, free, now)
        total = _finite_total(rot)
        if total is not None and total.total_seconds() > 0:
            free2 = free % total.total_seconds()
            e, within = _resolve_rot(rot, free2)
            if e is not None:
                return _with_file_or_list(e, within, now)
        return None

    if dflt is not None:
        return _default_result(dflt, free, now)
    return None


def _finite_total(rot):
    total = timedelta(0)
    for e in rot:
        d = _rot_duration(e)
        if d is None:
            return None
        total += d
    return total

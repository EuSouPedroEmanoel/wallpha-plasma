from datetime import date, datetime, time, timedelta

from . import entries as ent
from . import schedule as sch
from .parse import is_loop_n, matches_day


def _wall_for_free(slots, day_start, F2):
    wall = day_start + timedelta(seconds=F2)
    for _ in range(12):
        ov = timedelta(0)
        for start, end, _ in slots:
            lo = max(start, day_start)
            hi = min(end, wall)
            if hi > lo:
                ov += hi - lo
        new = day_start + timedelta(seconds=F2 + ov.total_seconds())
        if abs((new - wall).total_seconds()) < 1e-6:
            break
        wall = new
    return wall


def _next_list_offsets(e, within):
    """Offsets (s, relativos ao início da lista) das próximas trocas internas.
    Listas aninhadas contribuem com as trocas internas delas (relativas ao pai).
    Com `loop` int N, cobre os N ciclos e termina em N * total."""
    total = ent._list_total(e).total_seconds()
    loop = e.get("loop")
    offsets = []
    if is_loop_n(loop) and total > 0:
        first = int(within // total)
        for c in range(first, loop):
            shift = c * total
            acc = 0.0
            for s in e["sub_entries"]:
                t = ent._sub_dur(s, e).total_seconds()
                start = acc
                acc += t
                offsets.append(shift + acc)
                if s.get("is_list"):
                    w = max(within - shift - start, 0.0) if c == first else 0.0
                    for o in _next_list_offsets(s, w):
                        offsets.append(shift + start + o)
        offsets.append(loop * total)
        return sorted({o for o in offsets if o > within})
    base = 0.0
    if loop and total > 0:
        base = int(within // total) * total
    acc = base
    for s in e["sub_entries"]:
        t = ent._sub_dur(s, e).total_seconds()
        start = acc
        acc += t
        offsets.append(acc)
        if s.get("is_list"):
            for o in _next_list_offsets(s, max(within - start, 0.0)):
                offsets.append(start + o)
    return [o for o in offsets if o > within]


def next_transition(entries, now):
    day = now.date()
    day_start = datetime.combine(day, time(0, 0))
    cands = set()

    for delta in range(367):
        d = (now + timedelta(days=delta)).date()
        fe = [e for e in entries if matches_day(e, d)]
        if not fe:
            continue
        if delta > 0:
            if sch._rotation(fe) or sch._default(fe) is not None:
                cands.add(datetime.combine(d, time(0, 0)))
        for start, end, e in sch._hora_slots(fe, d):
            cands.add(start)
            cands.add(end)
            if e.get("is_list"):
                within = (now - start).total_seconds() if delta == 0 else 0.0
                for o in _next_list_offsets(e, max(within, 0.0)):
                    cands.add(start + timedelta(seconds=o))

        if delta > 0:
            continue

        slots_today = sch._hora_slots(fe, day)
        free = sch._free_before(slots_today, day_start, now)

        rot = sch._rotation(fe)
        if rot:
            acc = 0.0
            for e in rot:
                d = sch._rot_duration(e)
                if d is None:
                    if e.get("is_list"):
                        for o in _next_list_offsets(e, max(free - acc, 0.0)):
                            cands.add(_wall_for_free(slots_today, day_start, acc + o))
                    elif e["is_dir"]:
                        t = ent._dir_tempo(e).total_seconds()
                        k = int((free - acc) // t) + 1
                        cands.add(_wall_for_free(slots_today, day_start, acc + k * t))
                    break
                secs = d.total_seconds()
                cands.add(_wall_for_free(slots_today, day_start, acc))
                cands.add(_wall_for_free(slots_today, day_start, acc + secs))
                if e.get("is_list"):
                    for o in _next_list_offsets(e, max(free - acc, 0.0)):
                        cands.add(_wall_for_free(slots_today, day_start, acc + o))
                elif e["is_dir"]:
                    t = ent._dir_tempo(e).total_seconds()
                    n = e["loop"] if is_loop_n(e["loop"]) else 1
                    for k in range(1, len(e["files"]) * n + 1):
                        cands.add(_wall_for_free(slots_today, day_start, acc + k * t))
                acc += secs
            if sch._default(fe) is not None:
                cands.add(_wall_for_free(slots_today, day_start, acc))
        else:
            dflt = sch._default(fe)
            if dflt is not None:
                if dflt.get("is_list"):
                    for o in _next_list_offsets(dflt, max(free, 0.0)):
                        cands.add(_wall_for_free(slots_today, day_start, o))
                elif dflt["is_dir"]:
                    t = ent._dir_tempo(dflt).total_seconds()
                    k = int(free // t) + 1
                    cands.add(_wall_for_free(slots_today, day_start, k * t))

    future = sorted(b for b in cands if b > now)
    return future[0] if future else None


def next_entry(entries, active, now):
    if not entries:
        return None
    if active is None:
        return dict(entries[0])
    if active.get("is_list"):
        return _next_list_entry(active, now)
    if active["is_dir"]:
        e = dict(active)
        idx = (active["file_index"] + 1) % len(active["files"])
        e["file_index"] = idx
        e["arquivo"] = e["files"][idx]
        return e
    day = now.date()
    today = [e for e in entries if matches_day(e, day)]
    if not today:
        today = entries
    rot = sch._cycle_order(today) or today
    key = (active["local"], active["nome"])
    idx = next((i for i, e in enumerate(rot) if (e["local"], e["nome"]) == key), None)
    if idx is None:
        return dict(rot[0])
    return dict(rot[(idx + 1) % len(rot)])


def _next_list_entry(active, now=None):
    now = now or datetime.now()
    day = now.date()
    subs = active.get("sub_entries") or []
    if not subs:
        return dict(active)
    today = [s for s in subs if matches_day(s, day)]
    if not today:
        today = subs
    idx = int(active.get("sub_index", 0))
    sub = today[(idx + 1) % len(today)]
    if sub.get("is_list"):
        inner = _next_list_entry(sub, now)
        out = ent._apply_sub(dict(active), inner)
        out["sub_index"] = (idx + 1) % len(today)
        out["sub_nome"] = f"{sub['nome']}/{inner['sub_nome']}" if inner.get("sub_nome") else sub["nome"]
        return out
    out = ent._apply_sub(dict(active), sub)
    out["sub_index"] = (idx + 1) % len(today)
    out["sub_nome"] = sub["nome"]
    return out


def next_sub_by_nome(e, sub_nome):
    """Achata a lista `e` no sub-item `sub_nome` (ou no primeiro se None).
    Sub-lista aninhada achata no primeiro sub dela (sub_nome vira caminho)."""
    subs = e.get("sub_entries") or []
    if not subs:
        return dict(e)
    idx = next((i for i, s in enumerate(subs) if s["nome"] == sub_nome), 0)
    sub = subs[idx]
    if sub.get("is_list"):
        inner = next_sub_by_nome(sub, None)
        out = ent._apply_sub(dict(e), inner)
        out["sub_index"] = idx
        out["sub_nome"] = f"{sub['nome']}/{inner['sub_nome']}" if inner.get("sub_nome") else sub["nome"]
        return out
    out = ent._apply_sub(dict(e), sub)
    out["sub_index"] = idx
    out["sub_nome"] = sub["nome"]
    return out


def advance_in_list(e, sub_nome, now=None):
    """Próximo sub-item da lista `e` depois de `sub_nome` (ciclando)."""
    now = now or datetime.now()
    day = now.date()
    subs = e.get("sub_entries") or []
    if not subs:
        return None
    today = [s for s in subs if matches_day(s, day)]
    if not today:
        today = subs
    if sub_nome is None:
        return next_sub_by_nome(e, today[0]["nome"])
    idx = next((i for i, s in enumerate(today) if s["nome"] == sub_nome), -1)
    return next_sub_by_nome(e, today[(idx + 1) % len(today)]["nome"])


def find_by_name(entries, name):
    name = name.strip().lower()
    for e in entries:
        if e["nome"].lower() == name:
            return dict(e)
    return None


def next_after(entries, key, now=None):
    """Próximo wallpaper ativo hoje, depois do item (local, nome) de `key`.
    Segue a ordem de especificidade do dia (específico primeiro)."""
    if not entries:
        return None
    if isinstance(key, (list, tuple)) and len(key) == 2:
        now = now or datetime.now()
        day = now.date()
        today = [e for e in entries if matches_day(e, day)]
        if not today:
            today = entries
        rot = sch._cycle_order(today) or today
        local, nome = key
        for i, e in enumerate(rot):
            if e["local"] == local and e["nome"] == nome:
                return dict(rot[(i + 1) % len(rot)])
    return None


def advance_in_dir(entry, last_file):
    """Próximo arquivo do diretório `entry`, depois de `last_file` (ciclando)."""
    files = entry["files"] or []
    if not files:
        return None
    if last_file in files:
        idx = files.index(last_file)
    else:
        idx = -1
    return files[(idx + 1) % len(files)]

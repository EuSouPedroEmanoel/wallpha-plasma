import re
from datetime import date, datetime, time, timedelta

DEFAULT_TEMPO = "30m"

WEEKDAYS = {
    "seg": 0,
    "ter": 1,
    "qua": 2,
    "qui": 3,
    "sex": 4,
    "sab": 5,
    "dom": 6,
}

DIA_RANK = {"weekday": 1, "monthday": 2, "yearday": 3, "date": 4}


def _dia_rank(dia):
    """Especificidade do dia: 0 (sem dia) é o mais genérico, 4 (data) o mais específico."""
    if dia is None:
        return 0
    return DIA_RANK.get(dia["tipo"], 0)


def parse_tempo(value):
    """'30m', '2h', '1d', '1h30m10s', 45 -> timedelta. None se inválido."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return timedelta(minutes=int(value))
    s = str(value).strip().lower()
    if s.isdigit():
        return timedelta(minutes=int(s))
    m = re.fullmatch(r"(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", s)
    if not m or not any(m.groups()):
        return None
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=se)


def parse_time(value):
    """'9h', '9h30m', '9h30m15s', '30m', '15s', '08:00', '08:00:00' -> time."""
    s = str(value).strip().lower()
    if ":" in s:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
        raise ValueError(f"horário inválido: {value!r}")
    m = re.fullmatch(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", s)
    if not m or not any(m.groups()):
        raise ValueError(f"horário inválido: {value!r}")
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    if h > 23 or mi > 59 or se > 59:
        raise ValueError(f"horário inválido: {value!r}")
    return time(h, mi, se)


def parse_hora(value):
    """'9h-10h' -> (9:00, 10:00); '9h' -> (9:00, None); None -> (None, None)."""
    if value is None:
        return None, None
    if isinstance(value, time):
        return value, None
    s = str(value).strip()
    if "-" in s:
        a, b = s.split("-", 1)
        start = parse_time(a.strip())
        end = parse_time(b.strip())
        if end <= start:
            raise ValueError(f"range de hora inválido (fim <= início): {value!r}")
        return start, end
    return parse_time(s), None


def parse_loop(value):
    """Tag `loop`: False (sem loop), True (infinito) ou int N >= 1 (N ciclos).
    None/false/0 -> False; true -> True; N inteiro (int ou str) >= 1 -> int N."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        n = value
    elif isinstance(value, float) and value.is_integer():
        n = int(value)
    else:
        s = str(value).strip().lower()
        if s == "true":
            return True
        if s == "false" or s == "":
            return False
        if not s.isdigit():
            raise ValueError(f"loop aceita true/false ou número de vezes, veio: {value!r}")
        n = int(s)
    if n == 0:
        return False
    if n >= 1:
        return n
    raise ValueError(f"loop aceita true/false ou número de vezes, veio: {value!r}")


def is_loop_n(value):
    """True se `loop` é um número de ciclos (int, mas NÃO bool — bool é int em Python)."""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_dia(value):
    """Tag `dia`: weekday, monthday, yearday ou data específica.
    seg/ter/qua/qui/sex/sab/dom -> weekday
    1-31                     -> monthday (todo dia N do mês)
    'DD-MM'                  -> yearday (todo ano nesse dia)
    'DD-MM-AAAA'             -> data específica
    Retorna {'tipo', 'valor'} ou None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        if 1 <= n <= 31:
            return {"tipo": "monthday", "valor": n}
        raise ValueError(f"dia inválido: {value!r} (monthday vai de 1 a 31)")
    s = str(value).strip().lower()
    if not s:
        raise ValueError("dia vazio")
    if s in WEEKDAYS:
        return {"tipo": "weekday", "valor": WEEKDAYS[s]}
    if s.isdigit():
        n = int(s)
        if 1 <= n <= 31:
            return {"tipo": "monthday", "valor": n}
        raise ValueError(f"dia inválido: {value!r} (monthday vai de 1 a 31)")
    parts = s.split("-")
    if len(parts) == 3:
        d, m, a = parts
        if not (d.isdigit() and m.isdigit() and a.isdigit()):
            raise ValueError(f"dia inválido: {value!r} (use DD-MM-AAAA)")
        try:
            return {"tipo": "date", "valor": datetime.strptime(f"{d}-{m}-{a}", "%d-%m-%Y").date()}
        except ValueError:
            raise ValueError(f"dia inválido: {value!r} (use DD-MM-AAAA)")
    if len(parts) == 2:
        d, m = parts
        if not (d.isdigit() and m.isdigit()):
            raise ValueError(f"dia inválido: {value!r} (use DD-MM)")
        day, month = int(d), int(m)
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError(f"dia inválido: {value!r} (use DD-MM)")
        return {"tipo": "yearday", "valor": (day, month)}
    raise ValueError(f"dia inválido: {value!r} (use seg, N, DD-MM ou DD-MM-AAAA)")


def matches_day(entry, day):
    """True se o item está ativo em `day` (sem `dia` vale todos os dias)."""
    dia = entry.get("dia")
    if dia is None:
        return True
    if dia["tipo"] == "weekday":
        return day.weekday() == dia["valor"]
    if dia["tipo"] == "monthday":
        return day.day == dia["valor"]
    if dia["tipo"] == "yearday":
        return (day.day, day.month) == dia["valor"]
    if dia["tipo"] == "date":
        return day == dia["valor"]
    return True


def fmt_dia(dia):
    if dia is None:
        return ""
    if dia["tipo"] == "weekday":
        return next((k for k, v in WEEKDAYS.items() if v == dia["valor"]), "?")
    if dia["tipo"] == "monthday":
        return str(dia["valor"])
    if dia["tipo"] == "yearday":
        d, m = dia["valor"]
        return f"{d:02d}-{m:02d}"
    return dia["valor"].strftime("%d-%m-%Y")


def _fmt_secs(total):
    h, r = divmod(total, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h" + (f"{m}m" if m else "")
    if m:
        return f"{m}m" + (f"{s}s" if s else "")
    return f"{s}s"


def _fmt_tempo(td):
    return _fmt_secs(int(td.total_seconds()))


def _fim_txt(loop):
    """Final da mensagem de ativação conforme o modo de loop."""
    from .parse import is_loop_n
    if loop is True:
        return " — só para com: wallpha -x"
    if is_loop_n(loop):
        return f" — {loop} passadas e volta à agenda (-a)"
    return " — ao terminar volta à agenda (-a)"

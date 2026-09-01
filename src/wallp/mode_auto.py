import sys

from . import entries, log, state, transitions
from .service import _start_service


def _auto_mode(opts):
    entries_list = entries.load_checked()
    if entries_list is None:
        sys.exit(1)
    try:
        entries.check_global_default(entries_list)
    except ValueError as e:
        log.err(str(e))
        sys.exit(1)

    if not opts["target"]:
        state.clear_list()
        state.clear_random()
        state.set_on(True)
        _start_service()
        log.info("Modo automático ativado (agenda do yml).")
        return
    e = transitions.find_by_name(entries_list, opts["target"])
    lista = None
    if e is not None and e.get("is_list"):
        lista = e
    else:
        lista = entries.find_list(opts["target"])
    if lista is None and e is None:
        log.err(f"'{opts['target']}' não encontrado no yml")
        sys.exit(1)

    if lista is not None:
        cfg = {
            "nome": lista["nome"],
            "tempo": None, "max": None, "qtd": None,
            "loop": lista.get("loop"),
            "rep": False, "tipo": None, "integro": False, "som": None,
            "slideshow": False, "persist": False, "idx": 0,
            "shuffled": bool(lista.get("shuffled")),
        }
    else:
        cfg = {
            "nome": e["nome"],
            "tempo": None, "max": None, "qtd": None,
            "loop": e.get("loop"),
            "rep": bool(e.get("repetir")), "tipo": None,
            "integro": bool(e.get("integro")), "som": e.get("som"),
            "slideshow": False, "persist": True, "idx": 0,
            "shuffled": bool(e.get("shuffled")),
        }
    cur = state.get_list()
    # se já está no mesmo modo (mesmo nome e flags), não reinicia nem limpa pos para não cortar episódio
    if cur and cur.get("nome") == cfg["nome"] and cur.get("shuffled") == cfg["shuffled"] and cur.get("integro") == cfg["integro"] and cur.get("persist") == cfg["persist"]:
        # apenas garante que está on, sem restart
        state.set_on(True)
        log.info(f"Modo automático já está em '{opts['target']}'")
        return
    state.clear_pos()
    state.clear_random()
    state.set_list(cfg)
    state.set_on(True)
    _start_service()
    log.info(f"Modo automático ativado para '{opts['target']}' (até: wallp -x).")

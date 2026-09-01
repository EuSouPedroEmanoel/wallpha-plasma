import re
import sys

from . import cli, entries, log, state, yt
from .daemon import run as daemon_run
from .mode_auto import _auto_mode
from .mode_change import _change
from .mode_random import _random_mode
from .service import _show_log, _start_service, _stop_service


def main():
    opts = cli.parse()

    if opts["init"]:
        from .paths import DEFAULT_CONFIG
        created = entries.init_template()
        print(("wallp.yml criado em " if created else "wallp.yml já existe em ") + str(DEFAULT_CONFIG))
        return

    if opts["daemon"]:
        daemon_run()
        return

    if opts["list"]:
        _list_mode(opts)
        return

    if opts["random"]:
        _random_mode(opts)
    elif opts["auto"]:
        _auto_mode(opts)
    elif opts["stop"]:
        target = opts.get("target")
        if target is not None and target != "cache":
            log.err("só 'cache' é aceito com -x")
            sys.exit(1)
        if target == "cache":
            yt.clean_yt_buffer()
            log.info("buffer do youtube limpo.")
            return
        # stop normal: desativa e esvazia buffer
        state.set_on(False)
        state.clear_random()
        state.clear_list()
        _stop_service()
        yt.clean_yt_buffer()
        log.info("Modo automático/aleatório desativado (daemon parado). buffer do youtube limpo.")
    elif opts["change"]:
        _change(opts["target"], opts)
    elif opts["next"]:
        _change(None, opts)
    elif opts["log"]:
        _show_log(opts, follow=False)
        return
    else:
        cli.help()
        sys.exit(1)

    if opts["log"]:
        _show_log(opts, follow=True)


def _list_mode(opts):
    """Lista wallpapers do yml; filtra por regex em nome/local se target fornecido."""
    entries_list = entries.load_checked()
    if entries_list is None:
        sys.exit(1)
    if not entries_list and not entries.LISTAS:
        log.err("nenhum wallpaper configurado. Rode: wallp --init")
        sys.exit(1)

    pat = opts.get("target")
    rx = None
    if pat:
        try:
            rx = re.compile(pat, re.IGNORECASE)
        except re.error as e:
            log.err(f"regex inválido {pat!r}: {e}")
            sys.exit(1)

    def _entry_field_match(nome, local, arquivo=""):
        return bool(rx.search(nome or "") or rx.search(local or "") or rx.search(arquivo or ""))

    def _match(e):
        if rx is None:
            return True
        if _entry_field_match(e.get("nome"), e.get("local"), e.get("arquivo")):
            return True
        if e.get("is_list"):
            for s in e.get("sub_entries") or []:
                if _entry_field_match(s.get("nome"), s.get("local"), s.get("arquivo") or s.get("local")):
                    return True
                if s.get("is_list"):
                    for ss in s.get("sub_entries") or []:
                        if _entry_field_match(ss.get("nome"), ss.get("local"), ss.get("arquivo") or ss.get("local")):
                            return True
        if rx.search(entries.format_entry(e)):
            return True
        return False

    filt_entries = [e for e in entries_list if _match(e)]

    filt_listas = []
    seen_nomes = {e["nome"] for e in entries_list}
    for nome, lst in entries.LISTAS.items():
        if lst in filt_entries:
            continue
        if _match(lst):
            filt_listas.append(lst)

    if pat and not filt_entries and not filt_listas:
        print(f"nenhum item casa com regex {pat!r}")
        return

    if filt_entries:
        print(f"Itens da agenda ({len(filt_entries)}):")
        for e in filt_entries:
            print(f"  - {entries.format_entry(e)}  [wallp -c \"{e['nome']}\"]")
            if e.get("is_list"):
                parent_hit = rx is None or bool(rx.search(e.get("nome") or "") or rx.search(e.get("local") or ""))
                for s in e.get("sub_entries") or []:
                    if rx is not None and not parent_hit:
                        if not (rx.search(s.get("nome") or "") or rx.search(s.get("local") or "") or rx.search(s.get("arquivo") or "") or rx.search(entries.format_entry(s))):
                            if s.get("is_list"):
                                sub_hit = any(rx.search(ss.get("nome") or "") or rx.search(ss.get("local") or "") for ss in s.get("sub_entries") or [])
                                if not sub_hit:
                                    continue
                            else:
                                continue
                    print(f"      * {entries.format_entry(s)}")
                    if s.get("is_list"):
                        for ss in s.get("sub_entries") or []:
                            if rx is not None and not parent_hit:
                                if not (rx.search(ss.get("nome") or "") or rx.search(ss.get("local") or "")):
                                    continue
                            print(f"          - {entries.format_entry(ss)}")
        if filt_listas:
            print()

    if filt_listas:
        uniq = [l for l in filt_listas if l["nome"] not in {e["nome"] for e in filt_entries}]
        if uniq:
            print(f"Listas nomeadas ({len(uniq)}):")
            for lst in uniq:
                subs = lst.get("sub_entries") or []
                print(f"  - {lst['nome']} [{len(subs)} itens]  [wallp -c \"{lst['nome']}\"]")
                parent_hit = bool(rx.search(lst.get("nome") or "") or rx.search(lst.get("local") or ""))
                for s in subs:
                    if rx is not None and not parent_hit:
                        if not (rx.search(s.get("nome") or "") or rx.search(s.get("local") or "") or rx.search(entries.format_entry(s))):
                            continue
                    print(f"      * {entries.format_entry(s)}")

    if rx is None:
        total_nomes = len({e['nome'] for e in entries_list} | set(entries.LISTAS.keys()))
        print(f"\nTotal: {len(entries_list)} entradas na agenda + {len(entries.LISTAS)} listas nomeadas = {total_nomes} nomes únicos (use: wallp -c <nome>)")
        if filt_listas or filt_entries:
            print(f"Dica: filtre com regex: wallp -al \"poke|celeste\"  (case-insensitive, regex Python)")


# Compat: re-export antigos símbolos para testes que fazem `wallp._start_list` etc.
try:
    from .mode_change import _apply_named, _change_yml_next, _list_next, _list_slideshow_next, _start_list, _yt_path
    from .mode_random import _random_next
except ImportError:
    pass
# _start_service/_stop_service já importados de service, mas garante alias para monkeypatch
# (tests fazem `monkeypatch.setattr(wallp, "_start_service", ...)`)
__all__ = ["main"]

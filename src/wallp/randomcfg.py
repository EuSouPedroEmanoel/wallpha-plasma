from pathlib import Path

from .media import list_tree_files, match_tipo
from .parse import parse_tempo


def random_boundary(idx, elapsed, qtd, max_s, loop, total):
    """Decide o passo do slideshow aleatório.
    idx: quantos já mostrou; elapsed: segundos desde o início; qtd/max_s: limites;
    loop: se reinicia para sempre; total: tamanho da lista.
    Retorna 'ok' (continua), 'loop' (reinicia a lista) ou 'end' (encerra)."""
    if loop:
        return "loop" if idx >= total else "ok"
    if max_s is not None and elapsed >= max_s:
        return "end"
    if qtd is not None and idx >= qtd:
        return "end"
    if idx >= total:
        return "end"
    return "ok"


def default_scan_roots():
    """Raiz padrão do -r sem argumento: a pasta pessoal (~), recursiva (pega tudo)."""
    home = Path.home()
    return [home] if home.is_dir() else []


def cfg_seconds(value, default=None):
    """Tempo do config random (int = segundos, ou string '30m') -> segundos."""
    if value is None:
        return default
    from datetime import timedelta
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, (int, float)):
        return int(value)
    td = parse_tempo(value)
    return int(td.total_seconds()) if td else default


def build_random_queue(cfg):
    """Raízes e arquivos da fila do -r (recursivo). Retorna (roots, files, erro)."""
    single = cfg.get("file")
    if single:
        p = Path(single).expanduser()
        if not p.is_file():
            return None, None, "arquivo não existe"
        return [p.parent], [str(p)], None
    dir_arg = cfg.get("dir")
    if dir_arg:
        p = Path(dir_arg).expanduser()
        if not p.exists():
            return None, None, "diretório não existe"
        roots = [p if p.is_dir() else p.parent]
    else:
        roots = default_scan_roots()
        if not roots:
            return None, None, "nenhuma pasta de imagens/vídeos encontrada"
    files = []
    for root in roots:
        files += list_tree_files(str(root))
    files = [f for f in files if match_tipo(f, cfg.get("tipo"))]
    if not files:
        return None, None, "nenhum arquivo de mídia encontrado"
    return roots, files, None

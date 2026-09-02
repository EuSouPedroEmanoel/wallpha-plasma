import os
import re
import subprocess
from pathlib import Path

from .media import VIDEO_EXTS, WALLPHA_EXTS
from .media import day_shuffled, get_salt

YT_CACHE_MB = int(os.environ.get("WALLPHA_YT_CACHE_MB") or os.environ.get("WALLP_YT_CACHE_MB") or "500")

YT_FORMATS = [
    "bestvideo+bestaudio/best",
    "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "worstvideo+worstaudio/worst",
]


def _cache_bytes():
    try:
        return int(
            os.environ.get("WALLPHA_YT_CACHE_MB")
            or os.environ.get("WALLP_YT_CACHE_MB")
            or str(YT_CACHE_MB)
        ) * 1024 * 1024
    except ValueError:
        return YT_CACHE_MB * 1024 * 1024


def _yt_total_bytes():
    yt = yt_dir()
    if not yt.is_dir():
        return 0
    total = 0
    for p in yt.rglob("*"):
        if p.is_file() and p.suffix.lower() in WALLPHA_EXTS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _is_in_yt_dir(path):
    try:
        yp = yt_dir().resolve()
        pp = Path(path).resolve()
        return yp in pp.parents or pp.parent == yp or pp == yp
    except OSError:
        return False


def cleanup_prev(prev_path):
    """Remove N-1 do buffer se estiver em yt_dir. Retorna True se removeu."""
    if not prev_path:
        return False
    try:
        p = Path(prev_path)
        if not p.exists():
            return False
        if not _is_in_yt_dir(p):
            return False
        p.unlink()
        # limpa pastas vazias
        yt = yt_dir()
        for d in sorted([x for x in yt.rglob("*") if x.is_dir()], reverse=True):
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass
        return True
    except OSError:
        return False


def yt_dir():
    """Diretório do buffer do -y/youtube: tmpfs em RAM, limpo pelo sistema no logout.
    Limite de 500 MiB (YT_CACHE_MB) com limpeza LRU após cada download; `wallpha -x cache`
    limpa só o buffer sem tocar no daemon."""
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    d = Path(base) / "wallpha"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def clean_yt_buffer(keep=None):
    """Limpeza LRU por mtime do buffer do YouTube.
    Mantém `keep` (arquivo recém-baixado) e os mais recentes que caibam em YT_CACHE_MB;
    apaga o resto. Falha de download não limpa. Unlink de arquivo aberto é seguro no Linux.
    Se `keep` for diretório, mantém todos os arquivos dentro dele.
    Sem `keep`, esvazia o buffer inteiro (usado por `wallpha -x` e `wallpha -x cache`)."""
    try:
        yt = yt_dir()
        if not yt.is_dir():
            return
        # Sem keep -> esvazia tudo (para -x e -x cache)
        if keep is None:
            for p in yt.rglob("*"):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            for d in sorted([p for p in yt.rglob("*") if p.is_dir()], reverse=True):
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                except OSError:
                    pass
            return

        limit = _cache_bytes()
        files = [p for p in yt.rglob("*") if p.is_file() and p.suffix.lower() in WALLPHA_EXTS]
        try:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return

        keep_path = Path(keep).resolve() if keep is not None else None
        keep_files = set()
        if keep_path is not None:
            try:
                if keep_path.is_dir():
                    keep_files = {p.resolve() for p in keep_path.rglob("*") if p.is_file()}
                elif keep_path.is_file():
                    keep_files = {keep_path.resolve()}
                else:
                    keep_files = {keep_path.resolve()}
            except OSError:
                keep_files = set()

        if keep_path is not None and keep_path.is_file() and keep_path.resolve() not in {f.resolve() for f in files}:
            try:
                files.insert(0, keep_path)
            except OSError:
                pass

        kept = set()
        total = 0
        if keep_files:
            for kf in keep_files:
                try:
                    if kf.is_file():
                        sz = kf.stat().st_size
                    else:
                        continue
                    kept.add(kf)
                    total += sz
                except OSError:
                    pass
        for f in files:
            rf = f.resolve()
            if rf in kept:
                continue
            try:
                sz = f.stat().st_size
            except OSError:
                continue
            if total + sz <= limit:
                kept.add(rf)
                total += sz

        for f in files:
            rf = f.resolve()
            if rf in kept:
                continue
            try:
                f.unlink()
            except OSError:
                pass

        for d in sorted([p for p in yt.rglob("*") if p.is_dir()], reverse=True):
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    except Exception:
        pass


def _prune_yt_cache(limit_bytes=None):
    """Compat: antigo nome, delega para clean_yt_buffer."""
    clean_yt_buffer()


def _extract_playlist_id(url):
    m = re.search(r"[?&]list=([^&]+)", url)
    return m.group(1) if m else None


def get_playlist_ids(url):
    """Retorna lista de IDs da playlist sem baixar vídeos (usado para shuffle sem download)."""
    r = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s", "--yes-playlist", url],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "falha ao listar playlist").strip())
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def _get_shuffled_playlist_ids(url):
    """Obtém IDs da playlist via --flat-playlist e retorna embaralhados por dia (sem baixar vídeos)."""
    ids = get_playlist_ids(url)
    return day_shuffled(ids, get_salt())


def _download_single_with_fallback(url, tpl, prev_path=None):
    """Tenta baixar single video em ordem best->worst baseado em filesize, considerando soma sem prev_path.
    Se prev_path for fornecido, já deve ter sido limpo antes (caller garante N tocando)."""
    limit = _cache_bytes()
    # total sem prev (prev já deve ter sido limpo pelo caller, mas calcula de forma defensiva)
    total_before = _yt_total_bytes()
    if prev_path:
        try:
            pp = Path(prev_path)
            if pp.exists() and _is_in_yt_dir(pp):
                # se ainda não foi limpo, considera seu tamanho como livre
                try:
                    total_before -= pp.stat().st_size
                except OSError:
                    pass
        except OSError:
            pass
        if total_before < 0:
            total_before = 0

    last_err = None
    for fmt in YT_FORMATS:
        args = [
            "yt-dlp",
            "--no-playlist",
            "--extractor-args",
            "youtube:player_client=android",
            "-f",
            fmt,
            "--format-sort",
            "size",
            "-o",
            tpl,
            "--print",
            "after_move:filepath",
            url,
        ]
        r = subprocess.run(args, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            last_err = (r.stderr or r.stdout or "falha ao baixar o vídeo").strip()
            continue
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        if not lines:
            last_err = "não consegui localizar o vídeo baixado"
            continue
        path = lines[-1].strip()
        if not path or not Path(path).is_file():
            last_err = "não consegui localizar o vídeo baixado"
            continue
        try:
            new_size = Path(path).stat().st_size
        except OSError:
            new_size = 0
        # fallback best->worst: se prev_path fornecido (prefetch com N tocando), verifica soma sem N-1
        # senão, verifica apenas tamanho do arquivo
        should_keep = False
        if prev_path:
            if total_before + new_size <= limit:
                should_keep = True
        else:
            if new_size <= limit:
                should_keep = True
        if should_keep:
            clean_yt_buffer(keep=path)
            return path
        else:
            if fmt == YT_FORMATS[-1]:
                # último formato, mantém mesmo estourando (keep entra sempre)
                clean_yt_buffer(keep=path)
                return path
            # não cabe, tenta resolução menor
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
            last_err = f"arquivo {new_size} bytes excede limite {limit} (soma {total_before + new_size}), tentando menor"
            continue
    # se chegou aqui, nenhuma resolução coube; tenta retornar o menor mesmo estourando (keep entra sempre)
    # último formato é worst, então força download em worst se ainda não tentou?
    # Na prática, o loop já tentou worst; se falhou por tamanho, retorna erro
    raise RuntimeError(last_err or "falha ao baixar o vídeo em todas as resoluções")


def download_yt(url, batch_size=7, prev_path=None):
    """Baixa um vídeo do YouTube pro buffer em RAM e devolve o caminho local.
    Se a URL contiver playlist (list=), prepara fila embaralhada sem baixar tudo — baixa sob demanda com LRU.
    Limite de 500 MiB (YT_CACHE_MB) por soma (desconsiderando prev_path que será limpo) com fallback best->worst por filesize.
    `prev_path` é o N-1 a limpar antes de baixar N+1 (caller garante que N está tocando).
    `wallpha -x cache` limpa só o buffer; `wallpha -x` esvazia tudo."""
    # Limpa N-1 antes de baixar N+1 se fornecido (caller já verificou que N toca)
    if prev_path:
        cleanup_prev(prev_path)

    is_playlist = "list=" in url.lower()
    if is_playlist:
        playlist_id = _extract_playlist_id(url) or "playlist"
        folder = yt_dir() / playlist_id
        folder.mkdir(parents=True, exist_ok=True)
        marker = folder / ".playlist_url"
        try:
            marker.write_text(url, encoding="utf-8")
        except OSError:
            pass
        existing = len([p for p in folder.glob("*.mp4")] + [p for p in folder.glob("*.webm")] + [p for p in folder.glob("*.mkv")])
        if existing == 0:
            tpl = str(folder / "%(id)s.%(ext)s")
            # para batch, tenta best primeiro; se exceder, o LRU pós-download vai lidar, mas também tenta fallback
            # simplifica: tenta com fallback também, mas batch baixa 7 de uma vez; usa helper single para cada?
            # Mantém lógica simples: tenta batch com best, se falhar por tamanho tenta worst
            last_err = None
            for fmt in YT_FORMATS:
                args = [
                    "yt-dlp",
                    "--yes-playlist",
                    "--playlist-items",
                    f"1:{batch_size}",
                    "--extractor-args",
                    "youtube:player_client=android",
                    "-f",
                    fmt,
                    "--format-sort",
                    "size",
                    "-o",
                    tpl,
                    "--print",
                    "after_move:filepath",
                    url,
                ]
                r = subprocess.run(args, capture_output=True, text=True, timeout=600)
                if r.returncode == 0:
                    try:
                        files = sorted([p for p in folder.glob("*") if p.is_file()], key=lambda p: p.stat().st_mtime if p.is_file() else 0)
                        keep = str(files[-1]) if files else str(folder)
                    except OSError:
                        keep = str(folder)
                    try:
                        clean_yt_buffer(keep=keep)
                    except Exception:
                        pass
                    # verifica soma após batch
                    if _yt_total_bytes() <= _cache_bytes():
                        break
                    else:
                        # excedeu, tenta menor: apaga tudo exceto keep? Para simplificar, apaga batch e tenta menor
                        for p in folder.glob("*"):
                            if p.is_file() and p.name != Path(keep).name:
                                try:
                                    p.unlink()
                                except OSError:
                                    pass
                        last_err = "batch excede limite, tentando menor"
                        continue
                elif r.returncode != 0:
                    last_err = (r.stderr or r.stdout or "falha ao baixar o vídeo").strip()
                    continue
                break
            else:
                if last_err and not any(folder.iterdir()):
                    raise RuntimeError(last_err)
            if r.returncode != 0:
                if folder.is_dir() and any(folder.iterdir()):
                    return str(folder)
                raise RuntimeError((r.stderr or r.stdout or "falha ao baixar o vídeo").strip())
        return str(folder)
    # vídeo único (sem playlist)
    tpl = str(yt_dir() / "%(id)s.%(ext)s")
    return _download_single_with_fallback(url, tpl, prev_path=prev_path)

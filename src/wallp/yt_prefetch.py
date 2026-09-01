import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import yt

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wallp-prefetch")
_lock = threading.Lock()
_current_future = None
_current_url = None
_current_prev = None


def is_prefetching():
    with _lock:
        return _current_future is not None and not _current_future.done()


def prefetch(url, prev_path=None):
    """Inicia download de N+1 em background, limpando N-1 antes se N ainda toca.
    Só limpa prev_path se caller garantir que N está tocando (daemon verifica)."""
    global _current_future, _current_url, _current_prev
    if not url:
        return None
    with _lock:
        # se já está baixando o mesmo url, não reinicia
        if _current_url == url and _current_future and not _current_future.done():
            return _current_future
        # cancela anterior se diferente
        if _current_future and not _current_future.done():
            try:
                _current_future.cancel()
            except Exception:
                pass
        _current_url = url
        _current_prev = prev_path

        def _task():
            try:
                return yt.download_yt(url, prev_path=prev_path)
            except Exception as e:
                raise

        _current_future = _executor.submit(_task)
        return _current_future


def get_result(url=None, timeout=0):
    """Retorna path de url se prefetch terminou, ou None se ainda não/erro/url diferente."""
    global _current_future, _current_url
    with _lock:
        fut = _current_future
        cur = _current_url
    if fut is None:
        return None
    if url is not None and cur != url:
        return None
    if not fut.done():
        return None
    try:
        return fut.result(timeout=timeout)
    except Exception:
        return None


def wait_for(url, timeout=30):
    """Espera prefetch terminar e retorna path ou None."""
    global _current_future, _current_url
    with _lock:
        fut = _current_future
        cur = _current_url
    if fut is None or (url is not None and cur != url):
        return None
    try:
        return fut.result(timeout=timeout)
    except Exception:
        return None


def cancel():
    global _current_future, _current_url, _current_prev
    with _lock:
        if _current_future and not _current_future.done():
            try:
                _current_future.cancel()
            except Exception:
                pass
        _current_future = None
        _current_url = None
        _current_prev = None


def _is_current_playing(current_path):
    """Verifica se N ainda está tocando: arquivo existe e está em yt_dir (se for YT) ou existe em geral."""
    if not current_path:
        return False
    try:
        p = Path(current_path)
        return p.exists()
    except OSError:
        return False

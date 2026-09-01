import json
import os
import random
import re
import secrets
import subprocess
from datetime import date
from pathlib import Path

from .paths import SALT_FILE

WALLP_EXTS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpeg", ".mpg", ".ogg", ".ogv",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".avif",
}

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpeg", ".mpg", ".ogg", ".ogv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".avif"}


def video_duration(path, fallback=None):
    """Duração de um vídeo em segundos (via ffprobe). None/fallback se falhar."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return fallback


def match_tipo(path, tipo):
    """Filtro do -i/-v: 'imagem'/'video'/None (tudo)."""
    if tipo not in ("imagem", "video"):
        return True
    ext = Path(path).suffix.lower()
    if tipo == "video":
        return ext in VIDEO_EXTS
    return ext in IMAGE_EXTS


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def list_dir_files(path):
    p = Path(path)
    files = [str(f) for f in sorted(p.iterdir(), key=lambda f: _natural_key(f.name))
             if f.is_file() and f.suffix.lower() in WALLP_EXTS and not f.name.startswith(".")]
    return files


def list_tree_files(path):
    """Todos os arquivos de mídia de `path`, recursivo (inclui subpastas)."""
    root = Path(path)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if not d.startswith(".")]
        for name in sorted(filenames, key=_natural_key):
            if name.startswith("."):
                continue
            if Path(name).suffix.lower() in WALLP_EXTS:
                files.append(str(Path(dirpath) / name))
    return files


def get_salt():
    """Salt persistido em ~/.config/wallp/shuffle.json (gerado na 1ª vez)."""
    try:
        if SALT_FILE.exists():
            return json.loads(SALT_FILE.read_text(encoding="utf-8")).get("salt") or ""
        SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
        salt = secrets.token_hex(16)
        SALT_FILE.write_text(json.dumps({"salt": salt}), encoding="utf-8")
        return salt
    except OSError:
        return secrets.token_hex(16)


def day_shuffled(files, salt=None, day=None):
    """Embaralha com seed = salt + data: mesma ordem o dia todo, nova à meia-noite."""
    day = day or date.today()
    rnd = random.Random(f"{salt or ''}#{day.isoformat()}")
    out = list(files)
    rnd.shuffle(out)
    return out

import sys
from datetime import datetime

from .paths import LOG_FILE


def _append_log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} wallpha: {msg}\n")
    except OSError:
        pass


def err(msg):
    _append_log(msg)
    print(f"wallpha: {msg}", file=sys.stderr)


def info(msg):
    _append_log(msg)
    print(msg)

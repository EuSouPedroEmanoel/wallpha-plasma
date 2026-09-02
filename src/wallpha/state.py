import json
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "wallpha"
STATE_FILE = STATE_DIR / "auto"
RANDOM_FILE = STATE_DIR / "random"
LIST_FILE = STATE_DIR / "list"
LAST_FILE = STATE_DIR / "last"
POS_FILE = STATE_DIR / "pos"
CURRENT_FILE = STATE_DIR / "current"


def set_on(on):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text("on" if on else "off", encoding="utf-8")


def is_on():
    try:
        return STATE_FILE.read_text(encoding="utf-8").strip() == "on"
    except (FileNotFoundError, OSError):
        return False


def set_random(cfg):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RANDOM_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def get_random():
    try:
        return json.loads(RANDOM_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def clear_random():
    try:
        RANDOM_FILE.unlink()
    except FileNotFoundError:
        pass


def set_list(cfg):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LIST_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def get_list():
    try:
        return json.loads(LIST_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def clear_list():
    try:
        LIST_FILE.unlink()
    except FileNotFoundError:
        pass


def set_last(key):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_FILE.write_text(json.dumps(key, ensure_ascii=False), encoding="utf-8")


def get_last():
    try:
        return json.loads(LAST_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def set_pos(pos):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    POS_FILE.write_text(json.dumps(pos, ensure_ascii=False), encoding="utf-8")


def clear_pos():
    try:
        POS_FILE.unlink()
    except FileNotFoundError:
        pass


def get_pos():
    try:
        return json.loads(POS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def set_current(cur):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_FILE.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")


def get_current():
    try:
        return json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def clear_current():
    try:
        CURRENT_FILE.unlink()
    except FileNotFoundError:
        pass
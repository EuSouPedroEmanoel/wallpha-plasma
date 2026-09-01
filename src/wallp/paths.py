import os
import tempfile
from pathlib import Path

DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "wallp" / "wallp.yml"
SALT_FILE = DEFAULT_CONFIG.parent / "shuffle.json"
LOG_FILE = Path(os.environ.get("WALLP_LOG_FILE") or (Path(tempfile.gettempdir()) / "wallp.log"))

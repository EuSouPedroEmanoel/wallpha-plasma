import os
import tempfile
from pathlib import Path

# compat 2.0: fallback WALLP_* por 1 release (ver README)
DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "wallpha" / "wallpha.yml"
SALT_FILE = DEFAULT_CONFIG.parent / "shuffle.json"
LOG_FILE = Path(
    os.environ.get("WALLPHA_LOG_FILE")
    or os.environ.get("WALLP_LOG_FILE")
    or (Path(tempfile.gettempdir()) / "wallpha.log")
)

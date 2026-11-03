"""Application resources and writable user data are deliberately separate."""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
APP_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
EXE_ROOT = Path(sys.executable).resolve().parent if FROZEN else APP_ROOT

def user_root():
    override = os.environ.get('LUME_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if FROZEN:
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'LumeReader'
    return APP_ROOT

USER_ROOT = user_root()

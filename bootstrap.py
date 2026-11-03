"""Load project-local dependencies with the existing sperm interpreter."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
for folder in (ROOT / 'vendor', ROOT / '.runtime' / 'packages'):
    if folder.is_dir():
        sys.path.insert(0, str(folder))
os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')

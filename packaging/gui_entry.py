"""Frozen GUI entry point; the console worker is built separately."""
import os
import sys
from multiprocessing import freeze_support
import bootstrap

if __name__ == '__main__':
    freeze_support()
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        from lume.paths import USER_ROOT
        folder = USER_ROOT / 'data' / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        sys.stderr = open(folder / 'application.log', 'a', encoding='utf-8')
    from run import main
    raise SystemExit(main())

"""Console entry point for QProcess JSON events and command-line conversion."""
from multiprocessing import freeze_support
import bootstrap
from run import main

if __name__ == '__main__':
    freeze_support()
    raise SystemExit(main())

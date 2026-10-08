"""Run SHARC with the repository and legacy virtualenv dependencies on sys.path."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SHARC_SOURCE = REPO / "sharc"
VENV_SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SHARC_SOURCE))
sys.path.append(str(VENV_SITE_PACKAGES))

from sharc.main_cli import main


if __name__ == "__main__":
    main(sys.argv[1:])

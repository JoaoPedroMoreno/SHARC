"""New viewpoint of the approved FS model; existing renders remain unchanged."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_latincom_fs_assets as renderer

renderer.OUT = renderer.ROOT / "figuras/tcc_assets/fs_angular"
renderer.VIEWS = (("angular", -3.2, 1),)

if __name__ == "__main__":
    renderer.main()

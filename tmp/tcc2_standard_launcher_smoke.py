"""One-snapshot standard-CLI smoke test, independent of campaign outputs."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import yaml

root = Path(__file__).resolve().parents[1]
scripts = root / "sharc/campaigns/07_TCC2_DC_MSS_to_FS/Scripts"
spec = importlib.util.spec_from_file_location("tcc2_generate", scripts / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)
output = root / "tmp" / ("tcc2_standard_launcher_validation_" + datetime.now().strftime("%Y%m%dT%H%M%S%f"))
output.mkdir(exist_ok=False)
cfg = generate.build(525, 40, .5, 5, snapshots=1)
cfg["general"]["output_dir"] = str(output)
path = output / "smoke_input.yaml"
path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
subprocess.run([sys.executable, str(root / "sharc/main_cli.py"), "-p", str(path)],
               cwd=root, check=True)
subprocess.run([sys.executable, str(scripts / "audit_outputs.py"), str(output)],
               cwd=root, check=True)

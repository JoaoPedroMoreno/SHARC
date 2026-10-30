"""Use the existing viewer with just one orbital frame for a screenshot."""
import sys
import json
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sharc.satellite.ngso.backend import api
import yaml

# Zero whole periods plus the model's inclusive first step yields time t=0 only.
api.PROFILES["presentation"] = replace(
    api.PROFILES["presentation"], grid_size=28, n_periods=0
)


class CaptureHandler(api.SatelliteMapHandler):
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/system3_capture.html":
            content = (api.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
            content = content.replace("</head>", '<link rel="stylesheet" href="/system3_capture.css"></head>')
            content = content.replace("</body>", '<script src="/system3_capture.js"></script></body>')
            data, mime = content.encode("utf-8"), "text/html; charset=utf-8"
        elif route in ("/system3_capture.js", "/system3_capture.css"):
            data = (Path(__file__).parent / route[1:]).read_bytes()
            mime = "text/javascript" if route.endswith(".js") else "text/css"
        elif route == "/capture_parameters.json":
            params = yaml.safe_load(Path(api.DEFAULT_PARAM_FILE).read_text(encoding="utf-8"))
            orbit = params["imt"]["topology"]["mss_dc"]["orbits"][0]
            self._write_json({"orbit": orbit, "frequencyMHz": params["imt"]["frequency"],
                              "bandwidthMHz": params["imt"]["bandwidth"],
                              "source": str(api.DEFAULT_PARAM_FILE)})
            return
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


api.SatelliteMapHandler = CaptureHandler

if __name__ == "__main__":
    api.main()

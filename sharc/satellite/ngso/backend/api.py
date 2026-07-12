"""Small HTTP server for the NGSO satellite map frontend."""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _add_local_venv_site_packages() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    site_packages = repo_root / ".venv" / "Lib" / "site-packages"
    if site_packages.exists():
        sys.path.append(str(site_packages))


_add_local_venv_site_packages()

from sharc.satellite.ngso.backend.orbit_model import PROFILES, build_simulation


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
DEFAULT_PARAM_FILE: str | None = None


@lru_cache(maxsize=32)
def cached_simulation(profile: str, param_file: str | None) -> dict:
    return build_simulation(profile=profile, param_file=param_file)


class SatelliteMapHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def _write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._write_json({"status": "ok", "profiles": list(PROFILES)})
            return

        if parsed.path == "/api/simulation":
            query = parse_qs(parsed.query)
            profile = query.get("profile", ["fast"])[0]
            if profile not in PROFILES:
                self._write_json(
                    {
                        "error": f"Perfil invalido: {profile}",
                        "availableProfiles": list(PROFILES),
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                param_file = query.get("param_file", [DEFAULT_PARAM_FILE])[0]
                self._write_json(cached_simulation(profile, param_file))
            except Exception as exc:  # pragma: no cover - runtime path
                self._write_json(
                    {"error": str(exc), "profile": profile},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if parsed.path == "/":
            self.path = "/index.html"
        else:
            self.path = parsed.path
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the NGSO satellite map.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--param-file", default=None)
    args = parser.parse_args()

    global DEFAULT_PARAM_FILE
    DEFAULT_PARAM_FILE = args.param_file

    server = ThreadingHTTPServer((args.host, args.port), SatelliteMapHandler)
    print(f"Satellite map available at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

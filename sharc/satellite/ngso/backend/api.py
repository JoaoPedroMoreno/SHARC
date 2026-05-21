"""Small HTTP server for the NGSO satellite map frontend."""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sharc.satellite.ngso.backend.orbit_model import FOOTPRINT_MODES, PROFILES, build_simulation


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@lru_cache(maxsize=len(PROFILES) * len(FOOTPRINT_MODES))
def cached_simulation(profile: str, footprint_mode: str) -> dict:
    return build_simulation(profile=profile, footprint_mode=footprint_mode)


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
            self._write_json(
                {
                    "status": "ok",
                    "profiles": list(PROFILES),
                    "footprintModes": sorted(FOOTPRINT_MODES),
                }
            )
            return

        if parsed.path == "/api/simulation":
            query = parse_qs(parsed.query)
            profile = query.get("profile", ["fast"])[0]
            footprint_mode = query.get("footprintMode", ["beam_radius_fixed"])[0]
            if profile not in PROFILES:
                self._write_json(
                    {
                        "error": f"Perfil invalido: {profile}",
                        "availableProfiles": list(PROFILES),
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            if footprint_mode not in FOOTPRINT_MODES:
                self._write_json(
                    {
                        "error": f"Modo de footprint invalido: {footprint_mode}",
                        "availableFootprintModes": sorted(FOOTPRINT_MODES),
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                self._write_json(cached_simulation(profile, footprint_mode))
            except Exception as exc:  # pragma: no cover - runtime path
                self._write_json(
                    {"error": str(exc), "profile": profile, "footprintMode": footprint_mode},
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
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), SatelliteMapHandler)
    print(f"Satellite map available at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

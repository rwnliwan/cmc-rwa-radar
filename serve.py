"""RWA Radar — local dashboard server.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only. Milestone 27 Nov
(DESIGN-CMC-RWA.md §4.1, §6).

Serves the static dashboard (dashboard/index.html) plus the snapshot JSON
written by the CLI (out/cmc_snapshot.json) on 127.0.0.1:8000.

Read-only by design:
- The server NEVER reads the API key (.env.local) and NEVER makes any
  outbound network call. It only serves files that already exist on disk.
- Only two kinds of paths are served: the dashboard itself, and
  out/cmc_snapshot*.json files (the canonical snapshot + timestamped
  archives written by cmc_run.py). Everything else is 404 — no directory
  listing, no path traversal.
- The dashboard renders ONLY what the snapshot contains. It never
  invents data; missing history is shown as "not available", not faked.

Usage:  python3 serve.py [--port 8000]
Then open http://127.0.0.1:8000/ in a browser.
"""

import argparse
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
OUT_DIR = BASE_DIR / "out"
SNAPSHOT_NAME = "cmc_snapshot.json"
# Only canonical snapshot + timestamped archives are servable.
SNAPSHOT_RE = re.compile(r"^cmc_snapshot(_\d+_snap-[0-9a-f]+)?\.json$")

HOST = "127.0.0.1"  # localhost only — never bind 0.0.0.0
DEFAULT_PORT = 8000


class DashboardHandler(BaseHTTPRequestHandler):
    """Serve dashboard/index.html and out/cmc_snapshot*.json, nothing else."""

    server_version = "RWA-Radar/0.1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep logs short, one line each
        sys.stderr.write("serve: %s - %s\n"
                         % (self.address_string(), fmt % args))

    def _send_file(self, path, content_type):
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _send_json_error(self, status, message):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Strip any query string; reject encoded traversal outright.
        raw = self.path.split("?", 1)[0]
        if ".." in raw or "%" in raw:
            self._send_json_error(400, "bad path")
            return
        if raw in ("/", "/index.html"):
            self._send_file(DASHBOARD_DIR / "index.html", "text/html")
            return
        if raw == "/cmc_snapshot.json":
            self._send_file(OUT_DIR / SNAPSHOT_NAME, "application/json")
            return
        if raw.startswith("/out/"):
            name = raw[len("/out/"):]
            if SNAPSHOT_RE.match(name):
                self._send_file(OUT_DIR / name, "application/json")
                return
            self._send_json_error(404, "not found")
            return
        self._send_json_error(404, "not found")

    def do_POST(self):
        self._send_json_error(405, "read-only server")

    def do_PUT(self):
        self._send_json_error(405, "read-only server")

    def do_DELETE(self):
        self._send_json_error(405, "read-only server")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="serve.py",
        description="RWA Radar — serve the local dashboard "
                    "(read-only, localhost only).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="port to listen on (default 8000)")
    args = parser.parse_args(argv)

    if not (DASHBOARD_DIR / "index.html").is_file():
        print("error: dashboard/index.html not found", file=sys.stderr)
        return 2
    if not (OUT_DIR / SNAPSHOT_NAME).is_file():
        print("warning: %s not found — run `python3 cmc_run.py board` "
              "first so the dashboard has data to show"
              % (OUT_DIR / SNAPSHOT_NAME), file=sys.stderr)

    server = ThreadingHTTPServer((HOST, args.port), DashboardHandler)
    print("RWA Radar dashboard: http://%s:%d/" % (HOST, args.port))
    print("Serving dashboard/index.html + out/cmc_snapshot*.json "
          "(read-only, localhost only).")
    print("Stop with Ctrl-C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nserve.py stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

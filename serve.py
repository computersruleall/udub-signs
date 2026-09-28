"""Wayfinder local helper: serves the sign builder and exports signs to GitHub.

Run it (or double-click "Start Wayfinder.bat"), then use the builder at
http://127.0.0.1:8765. "Export to GitHub" sends the rendered PNG here; this
script commits it to the repo with your existing `gh` login (no token is
typed, stored or sent anywhere by the page) and answers with a raw image URL
plus a ready-to-paste ImageFrame command.

The image URL is pinned to the commit that added the file, so it always
serves exactly that image and never a stale cached copy.
"""
import base64
import hashlib
import json
import re
import subprocess
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = "computersruleall/udub-signs"
BRANCH = "main"
HOST, PORT = "127.0.0.1", 8765
ROOT = Path(__file__).resolve().parent
MAX_PNG = 8 * 1024 * 1024
SLUG = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>\n')


class GhError(RuntimeError):
    pass


def gh_api(method, path, body=None):
    cmd = ["gh", "api", "-X", method, path]
    if body is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(body) if body is not None else None,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise GhError((r.stderr or r.stdout).strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}


def put_file(path, data, message):
    """Create or update one file in the repo; returns the API response."""
    sha = None
    try:
        sha = gh_api("GET", f"repos/{REPO}/contents/{path}?ref={BRANCH}")["sha"]
    except GhError as e:
        if "Not Found" not in str(e) and "404" not in str(e):
            raise
    body = {"message": message, "content": base64.b64encode(data).decode(), "branch": BRANCH}
    if sha:
        body["sha"] = sha
    return gh_api("PUT", f"repos/{REPO}/contents/{path}", body)


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8"}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")

    def send_json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def trusted(self):
        # Only the builder itself may call the API: same host, plus a custom header that
        # a cross-site page cannot send without a CORS preflight (which is never answered).
        if self.headers.get("X-Wayfinder") != "1":
            return False
        origin = self.headers.get("Origin")
        return origin in (None, f"http://{HOST}:{PORT}", f"http://localhost:{PORT}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/wayfinder.html")
            self.end_headers()
            return
        if self.path.split("?")[0] == "/wayfinder.html":
            # the page is written as an artifact body; give it the document head a browser expects
            body = (HEAD + (ROOT / "wayfinder.html").read_text(encoding="utf-8")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/ping":
            if not self.trusted():
                return self.send_json(403, {"error": "forbidden"})
            return self.send_json(200, {"ok": True, "repo": REPO})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/export":
            return self.send_json(404, {"error": "not found"})
        if not self.trusted():
            return self.send_json(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_PNG * 2:
                return self.send_json(413, {"error": "The image is too large to export."})
            req = json.loads(self.rfile.read(length))
            slug = str(req.get("slug", ""))
            if not SLUG.match(slug):
                return self.send_json(400, {"error": "Sign name must be letters, numbers and spaces."})
            png = base64.b64decode(req["png"], validate=True)
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > MAX_PNG:
                return self.send_json(400, {"error": "That is not a PNG the builder made."})
            maps_w, maps_h = int(req["mapsW"]), int(req["mapsH"])

            digest = hashlib.sha256(png).hexdigest()[:8]
            img_path = f"signs/{slug}-{digest}.png"
            res = put_file(img_path, png, f"Add sign {slug} ({maps_w}x{maps_h} maps)")
            commit = res["commit"]["sha"]
            url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{img_path}"
            # the layout, so the sign can be reopened and edited later
            layout = json.dumps(req.get("sign", {}), indent=1, ensure_ascii=False).encode("utf-8")
            put_file(f"signs/{slug}.json", layout, f"Save layout for {slug}")

            command = f"/imageframe create {slug} {url} {maps_w} {maps_h} combined"
            print(f"  exported {img_path}\n  {command}")
            return self.send_json(200, {"url": url, "command": command, "path": img_path,
                                        "page": f"https://github.com/{REPO}/blob/{BRANCH}/{img_path}"})
        except GhError as e:
            return self.send_json(502, {"error": f"GitHub refused the upload: {e}"})
        except (KeyError, ValueError) as e:
            return self.send_json(400, {"error": f"Bad export request: {e}"})


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Wayfinder is already running - opening http://{HOST}:{PORT}")
        webbrowser.open(f"http://{HOST}:{PORT}/wayfinder.html")
        return
    url = f"http://{HOST}:{PORT}/wayfinder.html"
    print(f"Wayfinder running at {url}\nExports go to github.com/{REPO}\nClose this window to stop.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

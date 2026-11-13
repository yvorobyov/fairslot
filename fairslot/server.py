"""Local helper for the browser page: `python -m fairslot app`.

It serves fairslot.html on 127.0.0.1 only and fetches applications from the sources the
organizer configured. Tokens stay in one workspace file on this computer. The page itself
(fairslot.html) also works without this helper, using pasted or dropped files.
"""
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sources

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET_KEYS = ("token",)


def _html_path():
    for p in (os.path.join(HERE, "..", "fairslot.html"), os.path.join(HERE, "fairslot.html")):
        if os.path.exists(p):
            return os.path.abspath(p)
    raise SystemExit("fairslot.html not found next to the package")


def load_workspace(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def save_workspace(path, ws):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ws, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def public_view(ws):
    """Never send secrets back to the page."""
    ws = json.loads(json.dumps(ws))
    for blk in (ws.get("source") or {}, (ws.get("source") or {}).get("roster") or {}):
        for k in SECRET_KEYS:
            if blk.get(k):
                blk[k + "_set"] = True
                blk[k] = ""
    return ws


def merge_secrets(new, old):
    """A blank token from the page means 'keep the saved one'."""
    new = json.loads(json.dumps(new))
    src_new, src_old = new.get("source") or {}, (old or {}).get("source") or {}
    for k in SECRET_KEYS:
        if not src_new.get(k) and src_old.get(k) and src_new.get("type") == src_old.get("type"):
            src_new[k] = src_old[k]
    new["source"] = src_new
    return new


def fetch_for_page(ws_spec, saved, http=None):
    spec = merge_secrets({"source": ws_spec}, saved)["source"]
    spec.setdefault("utc_offset", (saved or {}).get("utc_offset", 0))
    res = sources.load(spec, http=http)
    res["csv"] = sources.to_csv_texts(res)
    res["counts"] = {"slots": len(res["slots"]), "applications": len(res["applications"]), "members": len(res["members"])}
    return res


def make_handler(ws_path, token, http=None):
    with open(_html_path(), encoding="utf-8") as f:
        html = f.read()
    page = html.replace("</head>", '<script>window.FS_APP=%s;</script>\n</head>' % json.dumps({"token": token}), 1)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _guard(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost"):
                self._send(403, json.dumps({"error": "forbidden host"}))
                return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            if self.path.split("?")[0] in ("/", "/index.html"):
                return self._send(200, page, "text/html; charset=utf-8")
            self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if not self._guard():
                return
            if self.headers.get("X-Fairslot-Token") != token:
                return self._send(403, json.dumps({"error": "bad token"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                saved = load_workspace(ws_path)
                if self.path == "/api/workspace/get":
                    return self._send(200, json.dumps(public_view(saved)))
                if self.path == "/api/workspace/save":
                    save_workspace(ws_path, merge_secrets(body, saved))
                    return self._send(200, json.dumps({"ok": True}))
                if self.path == "/api/fetch":
                    return self._send(200, json.dumps(fetch_for_page(body.get("source") or saved.get("source") or {}, saved, http), ensure_ascii=False))
                self._send(404, json.dumps({"error": "not found"}))
            except sources.SourceError as e:
                self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
            except Exception as e:  # keep the page usable, show a readable message
                self._send(200, json.dumps({"error": "Не получилось: %s" % e}, ensure_ascii=False))
    return H


def serve(port=8765, workspace="fairslot-workspace.json", open_browser=True, http=None):
    token = secrets.token_urlsafe(16)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(os.path.abspath(workspace), token, http))
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("fairslot is running at", url, "\nWorkspace file:", os.path.abspath(workspace), "\nPress Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return srv

"""Mock Jira REST v3 untuk menguji scripts/jira_push.py tanpa akun Jira asli.

Jalankan: python scripts/_mock_jira.py --port 8899
Lalu:     JIRA_BASE_URL=http://127.0.0.1:8899 python scripts/jira_push.py ...
"""

import argparse
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RECEIVED = []
COUNTER = {"n": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.path != "/rest/api/3/issue":
            self.send_error(404)
            return
        if not self.headers.get("Authorization", "").startswith("Basic "):
            self._json({"errorMessages": ["auth required"]}, 401)
            return
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n) or b"{}")
        COUNTER["n"] += 1
        project = payload.get("fields", {}).get("project", {}).get("key", "PROJ")
        key = f"{project}-{COUNTER['n']}"
        RECEIVED.append({"key": key, "received": time.time(), "payload": payload})
        self._json({"id": uuid.uuid4().hex, "key": key, "self": f"http://x/rest/api/3/issue/{key}"}, 201)

    def do_GET(self):  # noqa: N802
        if self.path == "/rest/api/3/myself":
            if not self.headers.get("Authorization", "").startswith("Basic "):
                self._json({"errorMessages": ["auth required"]}, 401)
                return
            self._json({"displayName": "Mock User", "emailAddress": "mock@example.com"})
            return
        if self.path == "/_received":
            self._json(RECEIVED)
            return
        self.send_error(404)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8899)
    a = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"[mock-jira] http://127.0.0.1:{a.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

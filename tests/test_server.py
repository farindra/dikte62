"""Server lokal: UI, API rapat, arsip, pengaturan, dan token akses."""

import http.client
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fixtures  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "server.py"
MEETINGS = ROOT / ".data" / "meetings"
MID = "ci_meeting"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_ready(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meetings", timeout=1).close()
            return True
        except urllib.error.HTTPError:
            return True  # 401 = server hidup (mode token)
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def start(port: int, *extra: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(SERVER), "--port", str(port), *extra],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    if proc.stdout:
        proc.stdout.close()


def get(port: int, path: str, cookie: str = "") -> tuple[int, bytes, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if cookie:
        req.add_header("Cookie", cookie)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read(), dict(r.headers)


def post(port: int, path: str, payload: dict) -> tuple[int, bytes]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read()


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = MEETINGS / MID
        base.mkdir(parents=True, exist_ok=True)
        (base / "meta.json").write_text(json.dumps(fixtures.meta(MID)))
        (base / "facts.json").write_text(json.dumps(fixtures.FACTS))
        (base / "artifacts.json").write_text(json.dumps(fixtures.ARTIFACTS))
        (base / "transcript.json").write_text(json.dumps(fixtures.transcript()))
        (base / "speakers.json").write_text(json.dumps({"S1": "Indra"}))

        cls.port = free_port()
        cls.proc = start(cls.port)
        if not wait_ready(cls.port):
            out = cls.proc.stdout.read() if cls.proc.stdout else ""
            stop(cls.proc)
            raise RuntimeError(f"server tidak siap:\n{out}")

    @classmethod
    def tearDownClass(cls):
        stop(cls.proc)
        shutil.rmtree(MEETINGS / MID, ignore_errors=True)

    def test_index_served(self):
        status, body, headers = get(self.port, "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Dikte62", body)
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_static_assets(self):
        for path in ["/app.js", "/style.css"]:
            with self.subTest(path=path):
                status, body, _ = get(self.port, path)
                self.assertEqual(status, 200)
                self.assertGreater(len(body), 100)

    def test_meetings_list(self):
        _, body, _ = get(self.port, "/api/meetings")
        data = json.loads(body)
        row = next((m for m in data if m["id"] == MID), None)
        self.assertIsNotNone(row, data)
        self.assertEqual(row["counts"]["decisions"], 1)
        self.assertFalse(row["archived"])
        self.assertIn("created_at", row)

    def test_meeting_detail(self):
        _, body, _ = get(self.port, f"/api/meeting/{MID}")
        data = json.loads(body)
        self.assertEqual(len(data["transcript"]["segments_data"]), 3)
        self.assertEqual(data["speaker_names"]["S1"], "Indra")
        self.assertFalse(data["has_audio"])
        self.assertIn("brd", data["artifacts"])

    def test_settings_never_leak_secret(self):
        _, body, _ = get(self.port, "/api/settings")
        data = json.loads(body)
        gem = data["gemini_api_key"]
        self.assertIn("configured", gem)
        self.assertIn("tail", gem)
        self.assertLessEqual(len(gem["tail"]), 4)

    def test_archive_roundtrip(self):
        post(self.port, "/api/archive", {"id": MID, "archived": True})
        _, body, _ = get(self.port, "/api/meetings")
        row = next(m for m in json.loads(body) if m["id"] == MID)
        self.assertTrue(row["archived"])
        post(self.port, "/api/archive", {"id": MID, "archived": False})

    def test_unknown_meeting_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            get(self.port, "/api/meeting/tidak-ada")
        self.assertEqual(ctx.exception.code, 404)

    def test_delete_removes_meeting(self):
        # rapat sementara agar rapat utama tidak terhapus
        base = MEETINGS / "ci_temp"
        base.mkdir(parents=True, exist_ok=True)
        (base / "meta.json").write_text(json.dumps(fixtures.meta("ci_temp")))
        status, _ = post(self.port, "/api/delete", {"id": "ci_temp"})
        self.assertEqual(status, 200)
        self.assertFalse(base.exists())


class TokenTest(unittest.TestCase):
    TOKEN = "rahasia-ci"

    def test_token_flow(self):
        base = MEETINGS / MID
        base.mkdir(parents=True, exist_ok=True)
        (base / "meta.json").write_text(json.dumps(fixtures.meta(MID)))
        port = free_port()
        proc = start(port, "--token", self.TOKEN)
        try:
            self.assertTrue(wait_ready(port))

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                get(port, "/api/meetings")
            self.assertEqual(ctx.exception.code, 401)

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", f"/?token={self.TOKEN}")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 302)
            cookie = resp.getheader("Set-Cookie") or ""
            conn.close()
            self.assertIn("dikte_token=", cookie)

            status, body, _ = get(port, "/api/meetings", cookie="dikte_token=" + self.TOKEN)
            self.assertEqual(status, 200)
            self.assertIn(b"ci_meeting", body)

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                get(port, "/api/meetings", cookie="dikte_token=salah")
            self.assertEqual(ctx.exception.code, 401)
        finally:
            stop(proc)
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
